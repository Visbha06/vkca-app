"""Authenticated 25-step acceptance journey for internal and external T20s."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text

from src.database import AsyncSessionFactory
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.background_work_item import BackgroundWorkItem
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.scoring.delivery import Delivery
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.models.scoring.participant import MatchParticipant
from src.models.team_coach import TeamCoach
from src.models.user import User
from tests.integration.test_match_scoring_api import _phase7_configuration


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as value:
        yield value


@pytest_asyncio.fixture(loop_scope="session")
async def quickstart_match_ids(authenticated_client):
    ids: list[UUID] = []
    try:
        yield ids
    finally:
        async with AsyncSessionFactory() as session:
            await session.execute(delete(Innings).where(Innings.match_id.in_(ids)))
            await session.execute(delete(Match).where(Match.id.in_(ids)))
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.parametrize("external", [False, True], ids=["internal", "external"])
async def test_014_authenticated_25_step_quickstart(
    client: httpx.AsyncClient,
    quickstart_match_ids: list[UUID],
    external: bool,
) -> None:
    """Run the documented scoring, correction, privacy, and OCC journey twice."""

    # 1. The isolated integration database must already be at migration 016.
    async with AsyncSessionFactory() as session:
        assert (
            await session.scalar(text("SELECT version_num FROM alembic_version"))
            == "016"
        )

    # 2-5. Seed both academy teams; configure one internal or one external Match.
    config, participants = await _phase7_configuration(
        client, "T20", external, quickstart_match_ids
    )
    match_id = UUID(config["match_id"])
    side_by_code = {side["side_code"]: side for side in config["sides"]}
    assert config["policy"]["policy_code"] == "T20"
    assert config["policy"]["capability_profile"] == "T20"
    assert config["policy"]["innings_sequence"] == ["home", "away"]
    assert len(config["participants"]) == 22
    if external:
        assert side_by_code["away"]["side_kind"] == "external"
        assert side_by_code["away"]["team_id"] is None
        assert all(
            item["participant_kind"] == "external" and item["player_id"] is None
            for item in config["participants"]
            if item["side_id"] == side_by_code["away"]["id"]
        )
        assert all(
            "user_id" not in item and "token" not in item
            for item in config["participants"]
            if item["side_id"] == side_by_code["away"]["id"]
        )
        async with AsyncSessionFactory() as session:
            opposition = list(
                (
                    await session.scalars(
                        select(MatchParticipant).where(
                            MatchParticipant.match_id == match_id,
                            MatchParticipant.side_id
                            == UUID(side_by_code["away"]["id"]),
                        )
                    )
                ).all()
            )
            assert len(opposition) == 11
            assert all(item.player_id is None for item in opposition)
            assert all(item.participant_kind == "external" for item in opposition)
    else:
        assert all(
            item["participant_kind"] == "internal" and item["player_id"] is not None
            for item in config["participants"]
        )

    # 6. Assert the immutable T20 capability contract returned by configuration.
    policy = config["policy"]
    assert policy["legal_ball_limit"] == 120
    assert policy["over_length_legal_balls"] == 6
    assert policy["bowler_quota_legal_balls"] == 24
    assert policy["wicket_limit"] == 10
    assert policy["target_mode"] == "prior_innings_plus_one"
    assert policy["consecutive_overs_prohibited"] is True

    # 7. Start innings one. A same-version concurrent pair also covers step 24's
    # OCC contract while this innings is still writable.
    started = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": config["match_version_number"],
            "innings_number": 1,
            "opening_striker_participant_id": participants["home"][0],
            "opening_non_striker_participant_id": participants["home"][1],
            "opening_bowler_participant_id": participants["away"][0],
        },
    )
    assert started.status_code == 200, started.text
    state = started.json()
    innings_id = UUID(state["id"])
    innings_path = f"/api/v1/matches/{match_id}/innings/{innings_id}"
    first_attempt = {
        "innings_version_number": state["version_number"],
        "attempted_sequence": 1,
        "striker_participant_id": participants["home"][0],
        "non_striker_participant_id": participants["home"][1],
        "bowler_participant_id": participants["away"][0],
        "runs_off_bat": 0,
        "extras": {},
    }
    concurrent = await asyncio.gather(
        client.post(innings_path + "/deliveries", json=first_attempt),
        client.post(innings_path + "/deliveries", json=first_attempt),
    )
    assert sorted(response.status_code for response in concurrent) == [200, 409]
    state_response = await client.get(innings_path)
    assert state_response.status_code == 200, state_response.text
    state = state_response.json()
    sequence = 2

    async def append(**facts):
        nonlocal state, sequence
        payload = {
            "innings_version_number": state["version_number"],
            "attempted_sequence": sequence,
            "striker_participant_id": state["striker_participant_id"],
            "non_striker_participant_id": state["non_striker_participant_id"],
            "bowler_participant_id": state["current_bowler_participant_id"],
            "runs_off_bat": 0,
            "extras": {},
        }
        payload.update(facts)
        response = await client.post(innings_path + "/deliveries", json=payload)
        assert response.status_code == 200, response.text
        sequence += 1
        current = await client.get(innings_path)
        assert current.status_code == 200, current.text
        state = current.json()
        return response.json()

    # 8-12. Record ordinary, boundary, five-run, multiple-wide, and no-ball facts.
    await append(runs_off_bat=1)
    boundary = await append(runs_off_bat=4)
    assert boundary["active_revision"]["total_runs"] == 4
    five = await append(runs_off_bat=5)
    assert five["active_revision"]["total_runs"] == 5
    wide = await append(extras={"wide_runs": 3})
    assert wide["active_revision"]["is_legal"] is False
    no_ball = await append(
        runs_off_bat=4,
        extras={"no_ball_penalty_runs": 1},
    )
    assert no_ball["active_revision"]["is_legal"] is False

    # 13. Persist one ordered catcher, reject a conflicting duplicate shape atomically.
    dismissed = state["striker_participant_id"]
    caught = await append(
        wicket={
            "dismissal_type": "caught",
            "dismissed_participant_id": dismissed,
            "fielders": [
                {"participant_id": participants["away"][1], "role": "catcher"}
            ],
        }
    )
    assert (
        caught["active_revision"]["wicket"]["primary_fielder_participant_id"]
        == (participants["away"][1])
    )
    assert caught["active_revision"]["wicket"]["fielders"][0]["ordinal"] == 1
    async with AsyncSessionFactory() as session:
        attempts_before_conflict = await session.scalar(
            select(func.count(Delivery.id)).where(Delivery.innings_id == innings_id)
        )
    duplicate_shape = await client.post(
        innings_path + "/deliveries",
        json={
            "innings_version_number": state["version_number"],
            "attempted_sequence": sequence,
            "striker_participant_id": participants["home"][2],
            "non_striker_participant_id": state["non_striker_participant_id"],
            "bowler_participant_id": state["current_bowler_participant_id"],
            "runs_off_bat": 0,
            "extras": {},
            "wicket": {
                "dismissal_type": "bowled",
                "dismissed_participant_id": participants["home"][2],
                "fielders": [],
            },
            "wickets": [{"dismissal_type": "bowled"}],
        },
    )
    assert duplicate_shape.status_code == 422
    async with AsyncSessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(Delivery.id)).where(Delivery.innings_id == innings_id)
            )
            == attempts_before_conflict
        )

    next_batter = await client.post(
        innings_path + "/next-batter",
        json={
            "innings_version_number": state["version_number"],
            "batter_participant_id": participants["home"][2],
            "replacing_participant_id": dismissed,
            "reason": "Wicket",
        },
    )
    assert next_batter.status_code == 200, next_batter.text
    state = next_batter.json()
    used_batters = set(participants["home"][:3])
    retired_hurt_id: str | None = None

    # 14. Exercise both retired-hurt branches: replacement internally and
    # approved return externally.
    retired_hurt_id = state["striker_participant_id"]
    retired = await client.post(
        innings_path + "/retired-hurt",
        json={
            "innings_version_number": state["version_number"],
            "participant_id": retired_hurt_id,
            "reason": "Assessment after a delivery",
        },
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["wickets_lost"] == 1
    assert retired.json()["blocking_state"]["kind"] == "awaiting_next_batter"
    if external:
        returned = await client.post(
            innings_path + "/retired-hurt-return",
            json={
                "innings_version_number": retired.json()["version_number"],
                "participant_id": retired_hurt_id,
                "reason": "Cleared to return",
            },
        )
        assert returned.status_code == 200, returned.text
        state = returned.json()
        assert (
            state["striker_participant_id"] == retired_hurt_id
            or state["non_striker_participant_id"] == retired_hurt_id
        )
        assert state["blocking_state"]["kind"] == "none"
        retired_hurt_id = None
    else:
        replacement_batter = participants["home"][3]
        selected = await client.post(
            innings_path + "/next-batter",
            json={
                "innings_version_number": retired.json()["version_number"],
                "batter_participant_id": replacement_batter,
                "replacing_participant_id": retired_hurt_id,
                "reason": "Retired-hurt replacement",
            },
        )
        assert selected.status_code == 200, selected.text
        state = selected.json()
        used_batters.add(replacement_batter)
        assert state["blocking_state"]["kind"] == "none"

    # 15-16. Finish an over, read the deterministic bowler suggestion, and select it.
    while state["legal_balls"] < 6:
        await append()
    assert state["over_progress"]["overs_completed"] == 1
    bowler_options = await client.get(innings_path + "/next-bowler")
    assert bowler_options.status_code == 200, bowler_options.text
    suggestion = bowler_options.json()["suggested_bowler_participant_id"]
    assert suggestion is not None
    assert suggestion != participants["away"][0]
    chosen_bowler = await client.post(
        innings_path + "/next-bowler",
        json={
            "innings_version_number": state["version_number"],
            "bowler_participant_id": suggestion,
        },
    )
    assert chosen_bowler.status_code == 200, chosen_bowler.text
    state = chosen_bowler.json()

    # 17. Add bye, leg-bye, and penalty deliveries to exercise the complete extras fold.
    await append(extras={"bye_runs": 2})
    await append(extras={"leg_bye_runs": 1})
    await append(extras={"penalty_runs": 1})

    # 18. Complete innings one through its T20 all-out path. Bowler choices rotate
    # at every completed over; unused batting-order entries are introduced once.
    while state["wickets_lost"] < 10:
        if state["current_bowler_participant_id"] is None:
            options = await client.get(innings_path + "/next-bowler")
            assert options.status_code == 200, options.text
            next_bowler_id = options.json()["suggested_bowler_participant_id"]
            assert next_bowler_id is not None
            chosen = await client.post(
                innings_path + "/next-bowler",
                json={
                    "innings_version_number": state["version_number"],
                    "bowler_participant_id": next_bowler_id,
                },
            )
            assert chosen.status_code == 200, chosen.text
            state = chosen.json()

        dismissed = state["striker_participant_id"]
        wicket_response = await append(
            wicket={
                "dismissal_type": "bowled",
                "dismissed_participant_id": dismissed,
                "fielders": [],
            }
        )
        if state["lifecycle_state"] == "completed":
            break
        available = [
            participant_id
            for participant_id in participants["home"]
            if participant_id not in used_batters
        ]
        if available:
            incoming = available[0]
            selected = await client.post(
                innings_path + "/next-batter",
                json={
                    "innings_version_number": state["version_number"],
                    "batter_participant_id": incoming,
                    "replacing_participant_id": dismissed,
                    "reason": "Wicket",
                },
            )
            assert selected.status_code == 200, selected.text
            state = selected.json()
            used_batters.add(incoming)
        elif retired_hurt_id is not None:
            returned = await client.post(
                innings_path + "/retired-hurt-return",
                json={
                    "innings_version_number": state["version_number"],
                    "participant_id": retired_hurt_id,
                    "reason": "Return to complete the innings",
                },
            )
            assert returned.status_code == 200, returned.text
            state = returned.json()
            retired_hurt_id = None
        else:
            pytest.fail("the fixed batting order ran out before ten wickets")
        assert wicket_response["active_revision"]["wicket"] is not None

    assert state["lifecycle_state"] == "completed"
    assert state["completion_reason"] == "all_out"
    assert state["wickets_lost"] == 10

    # 19-21. Start innings two at first-innings total + 1 and win automatically.
    target = state["total_runs"] + 1
    started_second = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": state["match_version_number"],
            "innings_number": 2,
            "opening_striker_participant_id": participants["away"][0],
            "opening_non_striker_participant_id": participants["away"][1],
            "opening_bowler_participant_id": participants["home"][0],
        },
    )
    assert started_second.status_code == 200, started_second.text
    second_state = started_second.json()
    assert second_state["target_runs"] == target
    second_path = f"/api/v1/matches/{match_id}/innings/{second_state['id']}"
    chase_response = await client.post(
        second_path + "/deliveries",
        json={
            "innings_version_number": second_state["version_number"],
            "attempted_sequence": 1,
            "striker_participant_id": participants["away"][0],
            "non_striker_participant_id": participants["away"][1],
            "bowler_participant_id": participants["home"][0],
            "runs_off_bat": target,
            "extras": {},
        },
    )
    assert chase_response.status_code == 200, chase_response.text
    assert chase_response.json()["innings_total_runs"] == target
    assert chase_response.json()["blocking_state"]["kind"] == "match_completed"

    # 22. The bounded scorecard agrees with delivery history, policy, and result.
    scorecard_response = await client.get(f"/api/v1/matches/{match_id}/scorecard")
    assert scorecard_response.status_code == 200, scorecard_response.text
    scorecard = scorecard_response.json()
    assert scorecard["lifecycle_state"] == "completed"
    assert scorecard["result_code"] == "win_by_wickets"
    assert [inning["total_runs"] for inning in scorecard["innings"]] == [
        target - 1,
        target,
    ]
    first_score = scorecard["innings"][0]
    assert first_score["wickets_lost"] == 10
    assert first_score["extras"]["wides"] == 3
    assert first_score["extras"]["no_balls"] == 1
    assert first_score["extras"]["byes"] == 2
    assert first_score["extras"]["leg_byes"] == 1
    assert first_score["extras"]["penalty_runs"] == 1
    first_history = await client.get(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/deliveries?limit=100"
    )
    assert first_history.status_code == 200, first_history.text
    history_items = first_history.json()["deliveries"]
    caught_history = next(
        item
        for item in history_items
        if item["active_revision"]["wicket"] is not None
        and item["active_revision"]["wicket"]["dismissal_type"] == "caught"
    )
    assert (
        caught_history["active_revision"]["wicket"]["primary_fielder_participant_id"]
        == (participants["away"][1])
    )
    assert scorecard["blocking_state"]["kind"] == "match_completed"

    # 23. Correct the winning delivery after completion and retain terminal state.
    latest_innings = await client.get(second_path)
    correction_body = {
        "match_version_number": scorecard["match_version_number"],
        "innings_version_number": latest_innings.json()["version_number"],
        "expected_revision_number": 1,
        "reason": "Correct the winning delivery while preserving the result",
        "replacement": {
            "striker_participant_id": participants["away"][0],
            "non_striker_participant_id": participants["away"][1],
            "bowler_participant_id": participants["home"][0],
            "runs_off_bat": target + 1,
            "extras": {},
        },
    }
    correction = await client.post(
        second_path + f"/deliveries/{chase_response.json()['id']}/correction",
        json=correction_body,
    )
    assert correction.status_code == 200, correction.text
    assert correction.json()["match_lifecycle_state"] == "completed"
    assert correction.json()["result_code"] == "win_by_wickets"
    assert correction.json()["active_revision"]["revision_number"] == 2
    async with AsyncSessionFactory() as session:
        revisions = list(
            (
                await session.scalars(
                    select(DeliveryRevision)
                    .where(
                        DeliveryRevision.delivery_id
                        == UUID(chase_response.json()["id"])
                    )
                    .order_by(DeliveryRevision.revision_number)
                )
            ).all()
        )
        assert [item.revision_state for item in revisions] == ["superseded", "active"]

    # 24. Concurrency was exercised at the initial open version: one writer won,
    # and the stale competing command returned 409 without a second active slot.
    async with AsyncSessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(Delivery.id)).where(
                    Delivery.innings_id == innings_id,
                    Delivery.attempted_sequence == 1,
                )
            )
            == 1
        )
        assert await session.scalar(
            select(func.count(DeliveryRevision.id))
            .join(Delivery)
            .where(
                Delivery.innings_id == innings_id,
                DeliveryRevision.revision_state == "active",
            )
        ) == await session.scalar(
            select(func.count(Delivery.id)).where(Delivery.innings_id == innings_id)
        )

    # 25. Read-only quality visibility, bounded outbox work, allowlisted audits,
    # and role-denied findings complete the authenticated acceptance boundary.
    findings_before = await client.get(
        "/api/v1/data-quality", params={"domain": "scoring", "page_size": 100}
    )
    assert findings_before.status_code == 200, findings_before.text
    async with AsyncSessionFactory() as session:
        audits_before_roles = int(
            await session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(
                    BusinessAuditEvent.target_entity_id == match_id
                )
            )
            or 0
        )
        works = list(
            (
                await session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.source_type == "match",
                        BackgroundWorkItem.source_key == str(match_id),
                    )
                )
            ).all()
        )
        assert len(works) == 1
        assert works[0].payload["scoring_refresh"]["reason"] == "correction"
        assert "replacement" not in works[0].payload
        assert "deliveries" not in works[0].payload

        home_team_id = UUID(side_by_code["home"]["team_id"])
        assistant = User(
            first_name="Quickstart",
            last_name="Assistant",
            email=f"quickstart-assistant-{uuid4().hex}@example.test",
            hashed_password="unused-test-hash",
            role=UserRole.ASSISTANT_COACH,
            is_active=True,
        )
        player_user = User(
            first_name="Quickstart",
            last_name="Player",
            email=f"quickstart-player-{uuid4().hex}@example.test",
            hashed_password="unused-test-hash",
            role=UserRole.PLAYER,
            is_active=True,
        )
        session.add_all([assistant, player_user])
        await session.flush()
        assistant_session = AuthSession(
            user_id=assistant.id,
            token_family_id=uuid4(),
            current_token_hash=uuid4().hex + uuid4().hex,
            rotated_token_hashes=[],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        player_session = AuthSession(
            user_id=player_user.id,
            token_family_id=uuid4(),
            current_token_hash=uuid4().hex + uuid4().hex,
            rotated_token_hashes=[],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add_all(
            [
                assistant_session,
                player_session,
                TeamCoach(team_id=home_team_id, user_id=assistant.id),
            ]
        )
        await session.commit()

    async def as_actor(actor: User, auth_session: AuthSession):
        async def override_current_user():
            return actor, auth_session

        app.dependency_overrides[get_current_user] = override_current_user
        return await client.get(
            "/api/v1/data-quality", params={"domain": "scoring", "page_size": 100}
        )

    assistant_result = await as_actor(assistant, assistant_session)
    player_result = await as_actor(player_user, player_session)
    assert assistant_result.status_code == 403
    assert player_result.status_code == 403
    app.dependency_overrides.pop(get_current_user, None)

    async with AsyncSessionFactory() as session:
        assert (
            int(
                await session.scalar(
                    select(func.count(BusinessAuditEvent.id)).where(
                        BusinessAuditEvent.target_entity_id == match_id
                    )
                )
                or 0
            )
            == audits_before_roles
        )
        assert (
            await session.scalar(
                select(func.count(BackgroundWorkItem.id)).where(
                    BackgroundWorkItem.source_type == "match",
                    BackgroundWorkItem.source_key == str(match_id),
                )
            )
            == 1
        )
        if external:
            external_ids = [UUID(value) for value in participants["away"]]
            assert (
                await session.scalar(
                    select(func.count(MatchParticipant.id)).where(
                        MatchParticipant.match_id == match_id,
                        MatchParticipant.player_id.is_not(None),
                        MatchParticipant.id.in_(external_ids),
                    )
                )
                == 0
            )
        successful_actions = list(
            (
                await session.scalars(
                    select(BusinessAuditEvent.action_type).where(
                        BusinessAuditEvent.target_entity_id == match_id
                    )
                )
            ).all()
        )
        assert successful_actions.count("scoring.initialized") == 1
        assert successful_actions.count("scoring.innings_started") == 2
        assert successful_actions.count("scoring.innings_completed") == 2
        assert successful_actions.count("scoring.match_completed") == 1
        assert successful_actions.count("scoring.delivery_corrected") == 1
        assert len(successful_actions) == 7
