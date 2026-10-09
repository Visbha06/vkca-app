"""Database-backed correction provenance, atomicity, and OCC boundaries."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from src.database import AsyncSessionFactory
from src.main import app
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.models.team import Team
from src.models.team_player import TeamPlayer
from tests.integration.test_match_scoring_api import (
    _match,
    _participant,
    _player,
    _t20_policy,
)


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as value:
        yield value


@pytest_asyncio.fixture(loop_scope="session")
async def scoring_case(client, authenticated_client):
    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        home = Team(name=f"Correction-{unique}", age_group="U15")
        players = [await _player(f"Batter{i}", unique) for i in range(3)]
        session.add_all([home, *players])
        await session.flush()
        session.add_all(
            [
                TeamPlayer(team_id=home.id, player_id=p.id, roster_order=i)
                for i, p in enumerate(players, 1)
            ]
        )
        match = _match(home_team_id=home.id, away_team_id=None, opponent="Visitors")
        session.add(match)
        await session.commit()
        match_id = match.id
    try:
        configured = await client.put(
            f"/api/v1/matches/{match_id}/configuration",
            json={
                "match_version_number": 1,
                "format": "T20",
                "policy": _t20_policy(),
                "sides": [
                    {
                        "side_code": "home",
                        "side_kind": "academy",
                        "team_id": str(home.id),
                    },
                    {
                        "side_code": "away",
                        "side_kind": "external",
                        "display_name": "Visitors",
                    },
                ],
                "participants": [
                    *[_participant("home", p.id, i) for i, p in enumerate(players, 1)],
                    *[
                        {
                            "side_code": "away",
                            "participant_kind": "external",
                            "display_name": f"Fielder{i}",
                            "batting_order_position": i,
                        }
                        for i in range(1, 4)
                    ],
                ],
            },
        )
        assert configured.status_code == 200, configured.text
        config = configured.json()
        home_id = next(s["id"] for s in config["sides"] if s["side_code"] == "home")
        batters = [p["id"] for p in config["participants"] if p["side_id"] == home_id]
        bowlers = [p["id"] for p in config["participants"] if p["side_id"] != home_id]
        started = await client.post(
            f"/api/v1/matches/{match_id}/innings",
            json={
                "match_version_number": config["match_version_number"],
                "innings_number": 1,
                "opening_striker_participant_id": batters[0],
                "opening_non_striker_participant_id": batters[1],
                "opening_bowler_participant_id": bowlers[0],
            },
        )
        assert started.status_code == 200, started.text
        state = started.json()
        base = f"/api/v1/matches/{match_id}/innings/{state['id']}"
        facts = {
            "striker_participant_id": batters[0],
            "non_striker_participant_id": batters[1],
            "bowler_participant_id": bowlers[0],
            "runs_off_bat": 0,
        }
        yield {
            "match_id": match_id,
            "state": state,
            "base": base,
            "facts": facts,
            "batters": batters,
            "bowlers": bowlers,
        }
    finally:
        async with AsyncSessionFactory() as session:
            await session.execute(delete(Innings).where(Innings.match_id == match_id))
            await session.execute(delete(Match).where(Match.id == match_id))
            await session.commit()


async def _append(client, case, **overrides):
    state = (await client.get(case["base"])).json()
    response = await client.post(
        case["base"] + "/deliveries",
        json={
            "innings_version_number": state["version_number"],
            "attempted_sequence": state["legal_balls"] + 1,
            **case["facts"],
            **overrides,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _correction_body(case, delivery, **replacement):
    async with AsyncSessionFactory() as session:
        match = await session.get(Match, case["match_id"])
        innings = await session.get(Innings, UUID(case["state"]["id"]))
        return {
            "match_version_number": match.version_number,
            "innings_version_number": innings.version_number,
            "expected_revision_number": delivery["active_revision"]["revision_number"],
            "reason": "Correct observed delivery",
            "replacement": {**case["facts"], **replacement},
        }


@pytest.mark.asyncio
async def test_revision_chain_active_history_and_stale_correction(client, scoring_case):
    case = scoring_case
    delivery = await _append(client, case)
    path = case["base"] + f"/deliveries/{delivery['id']}/correction"
    first_body = await _correction_body(case, delivery, runs_off_bat=4)
    corrected = await client.post(path, json=first_body)
    assert corrected.status_code == 200, corrected.text
    second = corrected.json()
    assert second["innings_total_runs"] == 4
    assert (
        second["active_revision"]["supersedes_revision_id"]
        == delivery["active_revision"]["id"]
    )
    assert (await client.post(path, json=first_body)).status_code == 409
    final = await client.post(
        path, json=await _correction_body(case, second, runs_off_bat=6)
    )
    assert final.status_code == 200, final.text
    history = (await client.get(case["base"] + "/deliveries")).json()["deliveries"]
    assert len(history) == 1
    assert history[0]["active_revision"]["revision_number"] == 3
    assert history[0]["active_revision"]["runs_off_bat"] == 6
    async with AsyncSessionFactory() as session:
        revisions = list(
            (
                await session.scalars(
                    select(DeliveryRevision)
                    .where(DeliveryRevision.delivery_id == UUID(delivery["id"]))
                    .order_by(DeliveryRevision.revision_number)
                )
            ).all()
        )
        assert [r.runs_off_bat for r in revisions] == [0, 4, 6]
        assert [r.revision_state for r in revisions] == [
            "superseded",
            "superseded",
            "active",
        ]
        assert revisions[2].supersedes_revision_id == revisions[1].id
        audits = list(
            (
                await session.scalars(
                    select(BusinessAuditEvent).where(
                        BusinessAuditEvent.target_entity_id == case["match_id"],
                        BusinessAuditEvent.action_type == "scoring.delivery_corrected",
                    )
                )
            ).all()
        )
        assert len(audits) == 2
        assert all("replacement" not in event.event_metadata for event in audits)
        from src.models.background_work_item import BackgroundWorkItem

        work = list(
            (
                await session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.source_type == "match",
                        BackgroundWorkItem.source_key == str(case["match_id"]),
                    )
                )
            ).all()
        )
        assert len(work) == 1
        assert work[0].payload["scoring_refresh"]["reason"] == "correction"
        assert work[0].payload["scoring_refresh"]["projection_revision"] == 4


@pytest.mark.asyncio
async def test_reconciliation_blocks_selection_and_clears_by_correction(
    client, scoring_case
):
    case = scoring_case
    wicket = {
        "dismissal_type": "caught",
        "dismissed_participant_id": case["batters"][0],
        "fielders": [{"participant_id": case["bowlers"][1], "role": "catcher"}],
    }
    delivery = await _append(client, case, wicket=wicket)
    selected = await client.post(
        case["base"] + "/next-batter",
        json={
            "innings_version_number": delivery["innings_version_number"],
            "batter_participant_id": case["batters"][2],
            "replacing_participant_id": case["batters"][0],
            "reason": "Dismissal",
        },
    )
    assert selected.status_code == 200, selected.text
    path = case["base"] + f"/deliveries/{delivery['id']}/correction"
    corrected = await client.post(path, json=await _correction_body(case, delivery))
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["blocking_state"]["kind"] == "reconciliation_required"
    read = (await client.get(case["base"])).json()
    assert read["lifecycle_state"] == "reconciliation_required"
    blocked = await client.post(
        case["base"] + "/deliveries",
        json={
            **case["facts"],
            "innings_version_number": read["version_number"],
            "attempted_sequence": 2,
        },
    )
    assert blocked.status_code == 409
    restored = await client.post(
        path, json=await _correction_body(case, corrected.json(), wicket=wicket)
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["blocking_state"]["kind"] == "none"
    assert (await client.get(case["base"])).json()["reconciliation_reason"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage", ["record_delivery_corrected", "stage_scoring_refresh"]
)
async def test_correction_audit_or_refresh_failure_rolls_back_everything(
    client, scoring_case, mocker, stage
):
    case = scoring_case
    delivery = await _append(client, case)
    body = await _correction_body(case, delivery, runs_off_bat=4)
    mocker.patch(
        "src.services.scoring.service." + stage,
        new=mocker.AsyncMock(side_effect=RuntimeError("Injected failure")),
    )
    with pytest.raises(RuntimeError, match="Injected failure"):
        await client.post(
            case["base"] + f"/deliveries/{delivery['id']}/correction", json=body
        )
    read = (await client.get(case["base"])).json()
    assert read["total_runs"] == 0
    assert read["version_number"] == body["innings_version_number"]
    async with AsyncSessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DeliveryRevision)
                .where(DeliveryRevision.delivery_id == UUID(delivery["id"]))
            )
            == 1
        )
        match = await session.get(Match, case["match_id"])
        assert match.version_number == body["match_version_number"]


@pytest_asyncio.fixture(loop_scope="session")
async def concurrent_case(client, request):
    """Use a disposable schema so independent connections see committed fixtures."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.schema import CreateSchema, DropSchema

    from src.database import engine, get_db
    from src.middleware.auth import get_current_user
    from src.models import Base
    from src.models.scoring.match_side import MatchSide
    from src.models.scoring.participant import MatchParticipant
    from src.services.scoring.policy import resolve_format_capability
    from tests.fixtures.match_scoring import build_scoring_user

    schema = "phase6_" + uuid4().hex
    scoped_engine = engine.execution_options(schema_translate_map={None: schema})
    factory = async_sessionmaker(scoped_engine, expire_on_commit=False)
    saved = app.dependency_overrides.copy()
    async with engine.begin() as connection:
        await connection.execute(CreateSchema(schema))
    try:
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        actor = build_scoring_user()
        async with factory() as session:
            home = Team(name="Concurrent scoring", age_group="U15")
            players = [await _player(f"Batter{i}", schema) for i in range(3)]
            session.add_all([actor, home, *players])
            await session.flush()
            match = _match(home_team_id=home.id, away_team_id=None, opponent="Visitors")
            profile = getattr(request, "param", "T20")
            match.format = profile
            policy = {
                "policy_code": profile,
                "capability_profile": profile,
                "innings_sequence": ["home", "away"],
            }
            if profile == "one-day":
                policy["legal_ball_limit"] = 30
            match.scoring_authority = "delivery_history"
            match.configured_at = datetime.now(UTC)
            match.lifecycle_state = "scheduled"
            session.add(match)
            await session.flush()
            sides = [
                MatchSide(
                    match_id=match.id,
                    side_code="home",
                    side_kind="academy",
                    team_id=home.id,
                    display_name_snapshot="Academy",
                ),
                MatchSide(
                    match_id=match.id,
                    side_code="away",
                    side_kind="external",
                    display_name_snapshot="Visitors",
                ),
            ]
            session.add_all(sides)
            await session.flush()
            participants = [
                MatchParticipant(
                    match_id=match.id,
                    side_id=sides[0].id,
                    participant_kind="internal",
                    player_id=p.id,
                    display_name_snapshot=f"Batter{i}",
                    batting_order_position=i,
                )
                for i, p in enumerate(players, 1)
            ]
            participants += [
                MatchParticipant(
                    match_id=match.id,
                    side_id=sides[1].id,
                    participant_kind="external",
                    display_name_snapshot=f"Fielder{i}",
                    batting_order_position=i,
                )
                for i in range(1, 6)
            ]
            session.add_all(
                [
                    *participants,
                    resolve_format_capability(policy).to_model(match.id),
                ]
            )
            await session.commit()

        async def db():
            async with factory() as session:
                yield session

        async def user():
            return actor, None

        app.dependency_overrides[get_db] = db
        app.dependency_overrides[get_current_user] = user
        started = await client.post(
            f"/api/v1/matches/{match.id}/innings",
            json={
                "match_version_number": 1,
                "innings_number": 1,
                "opening_striker_participant_id": str(participants[0].id),
                "opening_non_striker_participant_id": str(participants[1].id),
                "opening_bowler_participant_id": str(participants[3].id),
            },
        )
        assert started.status_code == 200, started.text
        state = started.json()
        yield {
            "factory": factory,
            "match_id": match.id,
            "state": state,
            "base": f"/api/v1/matches/{match.id}/innings/{state['id']}",
            "facts": {
                "striker_participant_id": state["striker_participant_id"],
                "non_striker_participant_id": state["non_striker_participant_id"],
                "bowler_participant_id": state["current_bowler_participant_id"],
                "runs_off_bat": 0,
            },
        }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))


@pytest.mark.asyncio
async def test_concurrent_attempts_have_one_winner_and_one_active_slot(
    client, concurrent_case
):
    import asyncio

    from src.models.scoring.delivery import Delivery

    case = concurrent_case
    body = {**case["facts"], "innings_version_number": 1, "attempted_sequence": 1}
    first, second = await asyncio.gather(
        client.post(case["base"] + "/deliveries", json=body),
        client.post(case["base"] + "/deliveries", json=body),
    )
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    async with case["factory"]() as session:
        assert await session.scalar(select(func.count()).select_from(Delivery)) == 1
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DeliveryRevision)
                .where(DeliveryRevision.revision_state == "active")
            )
            == 1
        )
        assert (await session.get(Match, case["match_id"])).version_number == 3


@pytest.mark.asyncio
async def test_completed_reprocessing_is_invisible_and_competing_writer_is_stale(
    client, concurrent_case, mocker
):
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession

    case = concurrent_case
    delivery = await _append(client, case)
    async with case["factory"]() as session:
        match = await session.get(Match, case["match_id"])
        match.lifecycle_state = "completed"
        match.result_code = "win_by_runs"
        await session.commit()
        version = match.version_number
    entered, release = asyncio.Event(), asyncio.Event()
    original_flush = AsyncSession.flush
    seen = []

    async def pause_reprocessing(session, *args, **kwargs):
        await original_flush(session, *args, **kwargs)
        match = next(
            (
                value
                for value in session.identity_map.values()
                if isinstance(value, Match) and value.id == case["match_id"]
            ),
            None,
        )
        if match is not None and match.lifecycle_state == "correction_reprocessing":
            seen.append(
                await session.scalar(
                    select(Match.lifecycle_state).where(Match.id == match.id)
                )
            )
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=10)

    mocker.patch.object(AsyncSession, "flush", new=pause_reprocessing)
    body = {
        "match_version_number": version,
        "innings_version_number": delivery["innings_version_number"],
        "expected_revision_number": 1,
        "reason": "Correct result",
        "replacement": {**case["facts"], "runs_off_bat": 4},
    }
    path = case["base"] + f"/deliveries/{delivery['id']}/correction"
    task = asyncio.create_task(client.post(path, json=body))
    competing = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=10)
        read = await client.get(case["base"])
        assert read.json()["blocking_state"]["kind"] == "match_completed"
        async with case["factory"]() as session:
            assert (
                await session.get(Match, case["match_id"])
            ).lifecycle_state == "completed"
        competing = asyncio.create_task(client.post(path, json=body))
        release.set()
        corrected = await asyncio.wait_for(task, timeout=10)
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["match_lifecycle_state"] == "in_progress"
        assert corrected.json()["result_code"] == "pending"
        assert "correction_reprocessing" in seen
        assert (await asyncio.wait_for(competing, timeout=10)).status_code == 409
    finally:
        release.set()
        await asyncio.gather(
            task, *([competing] if competing else []), return_exceptions=True
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("concurrent_case", ["one-day"], indirect=True)
async def test_completed_match_correction_preserves_terminal_or_reopens_chase(
    client, concurrent_case
):
    """Seed completion markers pending Phase 7, with real canonical delivery history."""
    from src.models.scoring.transition_event import InningsTransitionEvent

    case = concurrent_case
    state = case["state"]
    for sequence in range(1, 31):
        response = await client.post(
            case["base"] + "/deliveries",
            json={
                "innings_version_number": state["version_number"],
                "attempted_sequence": sequence,
                "striker_participant_id": state["striker_participant_id"],
                "non_striker_participant_id": state["non_striker_participant_id"],
                "bowler_participant_id": state["current_bowler_participant_id"],
                "runs_off_bat": 0,
            },
        )
        assert response.status_code == 200, response.text
        state = (await client.get(case["base"])).json()
        if sequence % 6 == 0 and sequence < 30:
            options = (await client.get(case["base"] + "/next-bowler")).json()
            selected = await client.post(
                case["base"] + "/next-bowler",
                json={
                    "innings_version_number": state["version_number"],
                    "bowler_participant_id": options["suggested_bowler_participant_id"],
                },
            )
            assert selected.status_code == 200, selected.text
            state = selected.json()
    async with case["factory"]() as session:
        innings = await session.get(Innings, UUID(state["id"]))
        innings.lifecycle_state = "completed"
        innings.completion_reason = "legal_ball_limit"
        innings.completed_at = datetime.now(UTC)
        session.add(
            InningsTransitionEvent(
                innings_id=innings.id,
                event_kind="innings_completed",
                anchored_attempted_sequence=30,
                anchored_revision_id=UUID(response.json()["active_revision"]["id"]),
                created_by_user_id=UUID(
                    response.json()["active_revision"]["recorded_by_user_id"]
                ),
                created_at=datetime.now(UTC),
            )
        )
        match = await session.get(Match, case["match_id"])
        await session.commit()
        version = match.version_number
    from src.models.scoring.participant import MatchParticipant

    async with case["factory"]() as session:
        fielders = list(
            (
                await session.scalars(
                    select(MatchParticipant)
                    .where(MatchParticipant.side_id == UUID(state["fielding_side_id"]))
                    .order_by(MatchParticipant.batting_order_position)
                )
            ).all()
        )
    started = await client.post(
        f"/api/v1/matches/{case['match_id']}/innings",
        json={
            "match_version_number": version,
            "innings_number": 2,
            "opening_striker_participant_id": str(fielders[0].id),
            "opening_non_striker_participant_id": str(fielders[1].id),
            "opening_bowler_participant_id": case["facts"]["striker_participant_id"],
        },
    )
    assert started.status_code == 200, started.text
    chase = started.json()
    base = f"/api/v1/matches/{case['match_id']}/innings/{chase['id']}"
    facts = {
        "striker_participant_id": chase["striker_participant_id"],
        "non_striker_participant_id": chase["non_striker_participant_id"],
        "bowler_participant_id": chase["current_bowler_participant_id"],
        "runs_off_bat": 4,
        "extras": {"no_ball_penalty_runs": 1},
    }
    scored = await client.post(
        base + "/deliveries",
        json={**facts, "innings_version_number": 1, "attempted_sequence": 1},
    )
    assert scored.status_code == 200, scored.text
    async with case["factory"]() as session:
        innings = await session.get(Innings, UUID(chase["id"]))
        innings.lifecycle_state = "completed"
        innings.completion_reason = "target_reached"
        innings.completed_at = datetime.now(UTC)
        session.add(
            InningsTransitionEvent(
                innings_id=innings.id,
                event_kind="innings_completed",
                anchored_attempted_sequence=1,
                anchored_revision_id=UUID(scored.json()["active_revision"]["id"]),
                created_by_user_id=UUID(
                    scored.json()["active_revision"]["recorded_by_user_id"]
                ),
                created_at=datetime.now(UTC),
            )
        )
        match = await session.get(Match, case["match_id"])
        match.lifecycle_state = "completed"
        match.result_code = "win_by_wickets"
        await session.commit()
        version = match.version_number
    body = {
        "match_version_number": version,
        "innings_version_number": scored.json()["innings_version_number"],
        "expected_revision_number": 1,
        "reason": "Correct boundary",
        "replacement": {**facts, "runs_off_bat": 6},
    }
    path = base + f"/deliveries/{scored.json()['id']}/correction"
    terminal = await client.post(path, json=body)
    assert terminal.status_code == 200, terminal.text
    terminal = terminal.json()
    assert terminal["match_lifecycle_state"] == "completed"
    assert terminal["result_code"] == "win_by_wickets"
    assert terminal["innings_lifecycle_state"] == "completed"
    assert terminal["blocking_state"]["kind"] == "match_completed"
    assert (await client.get(base)).json()["target_runs"] == 1
    ordinary = await client.post(
        base + "/deliveries",
        json={
            **facts,
            "innings_version_number": terminal["innings_version_number"],
            "attempted_sequence": 2,
        },
    )
    assert ordinary.status_code == 409
    body.update(
        match_version_number=terminal["match_version_number"],
        innings_version_number=terminal["innings_version_number"],
        expected_revision_number=2,
        replacement={**facts, "runs_off_bat": 0, "extras": {}},
    )
    reopened = await client.post(path, json=body)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["match_lifecycle_state"] == "in_progress"
    assert reopened.json()["innings_lifecycle_state"] == "in_progress"
    assert reopened.json()["result_code"] == "pending"
    assert (await client.get(base)).json()["completed_at"] is None


@pytest.mark.asyncio
async def test_correction_replaces_ordered_fielders_without_mutating_old_rows(
    client, scoring_case
):
    from src.models.scoring.delivery_fielder import DeliveryFielder
    from src.models.scoring.wicket_event import WicketEvent

    case = scoring_case
    wicket = {
        "dismissal_type": "caught",
        "dismissed_participant_id": case["batters"][0],
        "fielders": [{"participant_id": case["bowlers"][1], "role": "catcher"}],
    }
    original = await _append(client, case, wicket=wicket)
    replacement = {
        "dismissal_type": "run_out",
        "dismissed_participant_id": case["batters"][0],
        "dismissed_end": "striker_end",
        "fielders": [
            {"participant_id": case["bowlers"][2], "role": "thrower"},
            {"participant_id": case["bowlers"][0], "role": "keeper"},
        ],
    }
    corrected = await client.post(
        case["base"] + f"/deliveries/{original['id']}/correction",
        json=await _correction_body(case, original, wicket=replacement),
    )
    assert corrected.status_code == 200, corrected.text
    current = corrected.json()["active_revision"]
    assert current["wicket"]["primary_fielder_participant_id"] == case["bowlers"][2]
    assert [f["participant_id"] for f in current["wicket"]["fielders"]] == [
        case["bowlers"][2],
        case["bowlers"][0],
    ]
    async with AsyncSessionFactory() as session:
        old_id = UUID(original["active_revision"]["id"])
        old_fielders = list(
            (
                await session.scalars(
                    select(DeliveryFielder).where(
                        DeliveryFielder.delivery_revision_id == old_id
                    )
                )
            ).all()
        )
        assert [str(f.participant_id) for f in old_fielders] == [case["bowlers"][1]]
        assert (
            await session.scalar(
                select(WicketEvent).where(WicketEvent.delivery_revision_id == old_id)
            )
        ).dismissal_type == "caught"
    summaries = (await client.get(case["base"])).json()["participant_summaries"]
    stats = {p["participant_id"]: p for p in summaries}
    assert stats[case["bowlers"][1]]["fielding_dismissals"] == 0
    assert stats[case["bowlers"][2]]["fielding_dismissals"] == 1
    assert stats[case["bowlers"][0]]["bowling_wickets"] == 0


@pytest.mark.asyncio
async def test_history_recalculates_downstream_ball_position_and_stale_retirement(
    client, scoring_case
):
    case = scoring_case
    original = await _append(client, case)
    later = await _append(client, case)
    stale_version = later["innings_version_number"]
    response = await client.post(
        case["base"] + f"/deliveries/{original['id']}/correction",
        json=await _correction_body(case, original, extras={"wide_runs": 1}),
    )
    assert response.status_code == 200, response.text
    history = (await client.get(case["base"] + "/deliveries")).json()["deliveries"]
    assert [item["active_revision"]["ball_in_over"] for item in history] == [1, 1]
    assert history[1]["active_revision"]["revision_number"] == 1
    async with AsyncSessionFactory() as session:
        stored = await session.get(
            DeliveryRevision, UUID(later["active_revision"]["id"])
        )
        assert stored.ball_in_over == 2
    stale = await client.post(
        case["base"] + "/retired-hurt",
        json={
            "innings_version_number": stale_version,
            "participant_id": case["batters"][0],
            "reason": "Injury",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "scoring_version_conflict"
