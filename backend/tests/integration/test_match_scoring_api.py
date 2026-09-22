"""Authenticated Phase 3 Match-scoring configuration integration coverage."""

from datetime import date
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, insert, select

from src.database import AsyncSessionFactory
from src.enums import (
    BattingStyle,
    BowlingStyle,
    MatchFormat,
    MatchLifecycleState,
    MatchParticipantType,
    MatchResultCode,
    PlayerType,
    ScoringAuthority,
)
from src.main import app
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.player import Player
from src.models.scoring.delivery import Delivery
from src.models.scoring.delivery_fielder import DeliveryFielder
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.models.scoring.over import InningsOver
from src.models.scoring.participant import MatchParticipant
from src.models.scoring.participant_summary import InningsParticipantSummary
from src.models.scoring.scoring_policy import ScoringPolicy
from src.models.scoring.transition_event import InningsTransitionEvent
from src.models.scoring.wicket_event import WicketEvent
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.models.user import User


@pytest_asyncio.fixture(loop_scope="session")
async def phase5_matches(authenticated_client):
    match_ids: list[UUID] = []
    try:
        yield match_ids
    finally:
        async with AsyncSessionFactory() as session:
            for match_id in match_ids:
                await session.execute(
                    delete(Innings).where(Innings.match_id == match_id)
                )
                await session.execute(delete(Match).where(Match.id == match_id))
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.parametrize(
    ("profile", "limit", "quota", "external"),
    [
        ("T20", None, 24, False),
        ("one-day", 30, 6, True),
        ("one-day", 240, 48, False),
        ("test", None, None, True),
    ],
)
async def test_phase5_overs_suggestions_overrides_and_quotas(
    client, profile, limit, quota, external, phase5_matches, data_quality_query_counter
):
    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        home = Team(name=f"Bowler-Home-{unique}", age_group="U15")
        away = Team(name=f"Bowler-Away-{unique}", age_group="U15")
        home_players = [await _player(f"Home-{i}", unique) for i in range(2)]
        away_players = [
            await _player(name, unique) for name in ["Asha", "Bela", "Cora"]
        ]
        session.add_all([home, away, *home_players, *away_players])
        await session.flush()
        session.add_all(
            [
                TeamPlayer(team_id=team.id, player_id=player.id, roster_order=i)
                for team, players in [(home, home_players), (away, away_players)]
                for i, player in enumerate(players, start=1)
            ]
        )
        match = _match(
            home_team_id=home.id,
            away_team_id=None if external else away.id,
            opponent="Visitors" if external else None,
            format=MatchFormat(profile),
        )
        session.add(match)
        await session.commit()
        match_id = match.id
        phase5_matches.append(match_id)
        policy = {
            "policy_code": profile,
            "capability_profile": profile,
            "innings_sequence": ["home", "away"] * (2 if profile == "test" else 1),
        }
        if limit:
            policy["legal_ball_limit"] = limit
        config = await client.put(
            f"/api/v1/matches/{match_id}/configuration",
            json={
                "match_version_number": 1,
                "format": profile,
                "policy": policy,
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
                    }
                    if external
                    else {
                        "side_code": "away",
                        "side_kind": "academy",
                        "team_id": str(away.id),
                    },
                ],
                "participants": [
                    *[
                        _participant("home", p.id, i)
                        for i, p in enumerate(home_players, 1)
                    ],
                    *[
                        {
                            "side_code": "away",
                            "participant_kind": "external",
                            "display_name": name,
                            "batting_order_position": i,
                        }
                        for i, name in enumerate(["Asha", "Bela", "Cora"], 1)
                    ],
                ]
                if external
                else [
                    *[
                        _participant("home", p.id, i)
                        for i, p in enumerate(home_players, 1)
                    ],
                    *[
                        _participant("away", p.id, i)
                        for i, p in enumerate(away_players, 1)
                    ],
                ],
            },
        )
    assert config.status_code == 200, config.text
    side_ids = {s["side_code"]: s["id"] for s in config.json()["sides"]}
    batters = [
        p["id"]
        for p in config.json()["participants"]
        if p["side_id"] == side_ids["home"]
    ]
    bowlers = [
        p["id"]
        for p in config.json()["participants"]
        if p["side_id"] == side_ids["away"]
    ]
    started = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": config.json()["match_version_number"],
            "innings_number": 1,
            "opening_striker_participant_id": batters[0],
            "opening_non_striker_participant_id": batters[1],
            "opening_bowler_participant_id": bowlers[0],
        },
    )
    assert started.status_code == 200, started.text
    state = started.json()
    base = f"/api/v1/matches/{match_id}/innings/{state['id']}"
    sequence = 0

    async def score(extras=None):
        nonlocal sequence, state
        sequence += 1
        response = await client.post(
            base + "/deliveries",
            json={
                "innings_version_number": state["version_number"],
                "attempted_sequence": sequence,
                "striker_participant_id": state["striker_participant_id"],
                "non_striker_participant_id": state["non_striker_participant_id"],
                "bowler_participant_id": state["current_bowler_participant_id"],
                "runs_off_bat": 0,
                "extras": extras or {},
            },
        )
        assert response.status_code == 200, response.text
        state = (await client.get(base)).json()
        return response.json()

    for over in range(2):
        for ball in range(6):
            illegal = await score(
                {"wide_runs": 1} if ball % 2 else {"no_ball_penalty_runs": 1}
            )
            assert illegal["innings_legal_balls"] == over * 6 + ball
            legal = await score()
            assert legal["active_revision"]["over_number"] == over
            assert legal["active_revision"]["ball_in_over"] == ball + 1
        assert state["current_bowler_participant_id"] is None
        assert state["blocking_state"]["kind"] == "awaiting_next_bowler"
        assert state["over_progress"]["overs_completed"] == over + 1
        with data_quality_query_counter.count() as queries:
            options = (await client.get(base + "/next-bowler")).json()
        assert not any(
            "from deliveries" in sql.lower() or "from delivery_revisions" in sql.lower()
            for sql in queries.statements
        )
        assert options["policy"]["bowler_quota_legal_balls"] == quota
        previous = bowlers[0 if over == 0 else 2]
        previous_option = next(
            p for p in options["candidates"] if p["participant_id"] == previous
        )
        assert not previous_option["is_eligible"]
        assert previous_option["legal_balls_bowled"] == 6
        denied = await client.post(
            base + "/next-bowler",
            json={
                "innings_version_number": state["version_number"],
                "bowler_participant_id": previous,
                "override_reason": "Cannot bypass eligibility",
            },
        )
        assert denied.status_code == 409
        if over == 0:
            assert options["suggested_bowler_participant_id"] == bowlers[1]
            body = {
                "innings_version_number": state["version_number"],
                "bowler_participant_id": bowlers[2],
                "override_reason": "Change of tactics",
            }
            chosen = await client.post(base + "/next-bowler", json=body)
            assert chosen.status_code == 200, chosen.text
            state = chosen.json()
            assert state["current_bowler_participant_id"] == bowlers[2]
            assert (
                await client.post(base + "/next-bowler", json=body)
            ).status_code == 409
            assert (await client.get(base)).json()[
                "current_bowler_participant_id"
            ] == bowlers[2]
        else:
            assert (
                options["suggested_bowler_participant_id"]
                == bowlers[1 if quota == 6 else 0]
            )
            assert options["completed_bowler_participant_ids"] == [
                bowlers[0],
                bowlers[2],
            ]
            if quota == 6:
                exhausted = next(
                    p
                    for p in options["candidates"]
                    if p["participant_id"] == bowlers[0]
                )
                assert exhausted["reason_code"] == "quota_exhausted"
                assert (
                    await client.post(
                        base + "/next-bowler",
                        json={
                            "innings_version_number": state["version_number"],
                            "bowler_participant_id": bowlers[0],
                            "override_reason": "No bypass",
                        },
                    )
                ).status_code == 409
    async with AsyncSessionFactory() as session:
        events = (
            await session.scalars(
                select(InningsTransitionEvent).where(
                    InningsTransitionEvent.innings_id == UUID(state["id"]),
                    InningsTransitionEvent.event_kind == "next_bowler",
                )
            )
        ).all()
        assert len(events) == 1
        assert events[0].anchored_attempted_sequence == 12
        assert events[0].anchored_revision_id is not None
        assert events[0].reason == "Change of tactics"
        assert (
            await session.scalar(
                select(func.count())
                .select_from(BusinessAuditEvent)
                .where(BusinessAuditEvent.target_entity_id == match_id)
            )
            == 2
        )


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as test_client:
        yield test_client


async def _player(first_name: str, last_name: str) -> Player:
    return Player(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date(2005, 1, 1),
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        is_active=True,
    )


def _match(
    *,
    home_team_id: UUID,
    away_team_id: UUID | None,
    opponent: str | None = None,
    version_number: int = 1,
    format: MatchFormat = MatchFormat.T20,
) -> Match:
    return Match(
        match_date=date(2026, 8, 31),
        format=format,
        participant_type=(
            MatchParticipantType.INTERNAL
            if away_team_id is not None
            else MatchParticipantType.EXTERNAL
        ),
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        external_opponent_name=opponent,
        venue="Integration Ground",
        result="Scheduled",
        version_number=version_number,
    )


def _t20_policy(sequence: list[str] | None = None) -> dict[str, object]:
    return {
        "policy_code": "T20",
        "capability_profile": "T20",
        "innings_sequence": sequence or ["home", "away"],
    }


def _participant(
    side_code: str,
    player_id: UUID,
    position: int = 1,
) -> dict[str, object]:
    return {
        "side_code": side_code,
        "participant_kind": "internal",
        "player_id": str(player_id),
        "batting_order_position": position,
    }


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_internal_and_external_configuration_survive_roster_mutation(
    client: httpx.AsyncClient,
) -> None:
    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        home = Team(name=f"Home-{unique}", age_group="U15")
        away = Team(name=f"Away-{unique}", age_group="U13")
        home_player = await _player("Home", unique)
        away_player = await _player("Away", unique)
        session.add_all([home, away, home_player, away_player])
        await session.flush()
        session.add_all(
            [
                TeamPlayer(team_id=home.id, player_id=home_player.id, roster_order=1),
                TeamPlayer(team_id=away.id, player_id=away_player.id, roster_order=1),
            ]
        )
        internal_match = _match(home_team_id=home.id, away_team_id=away.id)
        external_match = _match(
            home_team_id=home.id,
            away_team_id=None,
            opponent=f"Visitors-{unique}",
            format=MatchFormat.ONE_DAY,
        )
        session.add_all([internal_match, external_match])
        await session.commit()
        ids = (
            home.id,
            away.id,
            home_player.id,
            away_player.id,
            internal_match.id,
            external_match.id,
        )
    home_id, away_id, home_player_id, away_player_id, internal_id, external_id = ids

    internal = await client.put(
        f"/api/v1/matches/{internal_id}/configuration",
        json={
            "match_version_number": 1,
            "format": "T20",
            "policy": _t20_policy(),
            "sides": [
                {"side_code": "home", "side_kind": "academy", "team_id": str(home_id)},
                {"side_code": "away", "side_kind": "academy", "team_id": str(away_id)},
            ],
            "participants": [
                _participant("home", home_player_id),
                _participant("away", away_player_id),
            ],
        },
    )
    external = await client.put(
        f"/api/v1/matches/{external_id}/configuration",
        json={
            "match_version_number": 1,
            "format": "one-day",
            "policy": {
                "policy_code": "one-day",
                "capability_profile": "one-day",
                "innings_sequence": ["home", "away"],
                "legal_ball_limit": 240,
            },
            "sides": [
                {"side_code": "home", "side_kind": "academy", "team_id": str(home_id)},
                {
                    "side_code": "away",
                    "side_kind": "external",
                    "display_name": f"Visitors-{unique}",
                },
            ],
            "participants": [
                _participant("home", home_player_id),
                {
                    "side_code": "away",
                    "participant_kind": "external",
                    "display_name": "External Batter One",
                    "batting_order_position": 1,
                },
            ],
        },
    )

    assert internal.status_code == 200, internal.text
    assert external.status_code == 200, external.text
    assert external.json()["policy"]["bowler_quota_legal_balls"] == 48
    assert external.json()["policy"]["innings_sequence"] == ["home", "away"]
    external_participant = next(
        item
        for item in external.json()["participants"]
        if item["participant_kind"] == "external"
    )
    assert external_participant["player_id"] is None

    async with AsyncSessionFactory() as session:
        await session.execute(
            delete(TeamPlayer).where(TeamPlayer.player_id == home_player_id)
        )
        await session.commit()

    read_internal = await client.get(f"/api/v1/matches/{internal_id}")
    read_external = await client.get(f"/api/v1/matches/{external_id}")
    assert read_internal.status_code == 200, read_internal.text
    assert read_external.status_code == 200, read_external.text
    assert [
        item["display_name_snapshot"]
        for item in read_internal.json()["scoring_participants"]
    ] == [f"Away {unique}", f"Home {unique}"]
    assert read_external.json()["innings_sequence"] == ["home", "away"]
    assert read_external.json()["scoring_authority"] == "delivery_history"

    async with AsyncSessionFactory() as session:
        external_identity = await session.scalar(
            select(MatchParticipant).where(
                MatchParticipant.match_id == external_id,
                MatchParticipant.player_id.is_(None),
            )
        )
        account_count = int(
            await session.scalar(
                select(func.count(User.id)).where(
                    User.first_name == "External Batter One"
                )
            )
            or 0
        )
        audit_count = int(
            await session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(
                    BusinessAuditEvent.target_entity_id.in_([internal_id, external_id]),
                    BusinessAuditEvent.action_type == "scoring.initialized",
                )
            )
            or 0
        )
        external_audit = await session.scalar(
            select(BusinessAuditEvent).where(
                BusinessAuditEvent.target_entity_id == external_id,
                BusinessAuditEvent.action_type == "scoring.initialized",
            )
        )
    assert external_identity is not None
    assert account_count == 0
    assert audit_count == 2
    assert external_audit is not None
    assert external_audit.target_entity_type == "match"
    assert external_audit.event_metadata == {
        "capability_profile": "one-day",
        "capability_version": 1,
        "innings_sequence": ["home", "away"],
        "participant_count": 2,
    }


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_version_and_invalid_roster_fail_atomically(
    client: httpx.AsyncClient,
) -> None:
    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        home = Team(name=f"Atomic-Home-{unique}", age_group="U15")
        away = Team(name=f"Atomic-Away-{unique}", age_group="U13")
        player = await _player("Atomic", unique)
        session.add_all([home, away, player])
        await session.flush()
        session.add(TeamPlayer(team_id=home.id, player_id=player.id, roster_order=1))
        stale_match = _match(
            home_team_id=home.id,
            away_team_id=None,
            opponent=f"Stale-{unique}",
            version_number=2,
        )
        invalid_match = _match(
            home_team_id=home.id,
            away_team_id=None,
            opponent=f"Invalid-{unique}",
        )
        session.add_all([stale_match, invalid_match])
        await session.commit()
        ids = home.id, away.id, player.id, stale_match.id, invalid_match.id
    home_id, _away_id, player_id, stale_id, invalid_id = ids

    def payload(match_version: int, opponent: str) -> dict[str, object]:
        return {
            "match_version_number": match_version,
            "format": "T20",
            "policy": _t20_policy(),
            "sides": [
                {"side_code": "home", "side_kind": "academy", "team_id": str(home_id)},
                {
                    "side_code": "away",
                    "side_kind": "external",
                    "display_name": opponent,
                },
            ],
            "participants": [
                _participant("home", player_id),
                {
                    "side_code": "away",
                    "participant_kind": "external",
                    "display_name": "Opponent",
                    "batting_order_position": 1,
                },
            ],
        }

    stale = await client.put(
        f"/api/v1/matches/{stale_id}/configuration",
        json=payload(1, f"Stale-{unique}"),
    )
    invalid_payload = payload(1, f"Invalid-{unique}")
    invalid_payload["participants"][0]["side_code"] = "away"  # type: ignore[index]
    invalid = await client.put(
        f"/api/v1/matches/{invalid_id}/configuration",
        json=invalid_payload,
    )

    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "scoring_version_conflict"
    assert invalid.status_code == 422, invalid.text
    async with AsyncSessionFactory() as session:
        for match_id in (stale_id, invalid_id):
            match = await session.get(Match, match_id)
            assert match is not None
            assert match.scoring_authority == ScoringAuthority.LEGACY_AGGREGATE
            assert match.configured_at is None
            assert (
                await session.scalar(
                    select(ScoringPolicy).where(ScoringPolicy.match_id == match_id)
                )
                is None
            )


def test_scoring_configuration_route_is_mounted() -> None:
    operation = app.openapi()["paths"]["/api/v1/matches/{match_id}/configuration"]
    assert "put" in operation


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_phase4_authoritative_delivery_and_transition_flow(
    client: httpx.AsyncClient,
) -> None:
    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        home = Team(name=f"Scoring-Home-{unique}", age_group="U15")
        away = Team(name=f"Scoring-Away-{unique}", age_group="U15")
        home_players = [await _player(f"Home-{index}", unique) for index in range(1, 5)]
        away_players = [await _player(f"Away-{index}", unique) for index in range(1, 3)]
        session.add_all([home, away, *home_players, *away_players])
        await session.flush()
        session.add_all(
            [
                TeamPlayer(team_id=home.id, player_id=player.id, roster_order=index)
                for index, player in enumerate(home_players, start=1)
            ]
            + [
                TeamPlayer(team_id=away.id, player_id=player.id, roster_order=index)
                for index, player in enumerate(away_players, start=1)
            ]
        )
        match = _match(home_team_id=home.id, away_team_id=away.id)
        session.add(match)
        await session.commit()
        match_id, home_id, away_id = match.id, home.id, away.id
        home_player_ids = [player.id for player in home_players]
        away_player_ids = [player.id for player in away_players]

    configuration = await client.put(
        f"/api/v1/matches/{match_id}/configuration",
        json={
            "match_version_number": 1,
            "format": "T20",
            "policy": _t20_policy(),
            "sides": [
                {
                    "side_code": "home",
                    "side_kind": "academy",
                    "team_id": str(home_id),
                },
                {
                    "side_code": "away",
                    "side_kind": "academy",
                    "team_id": str(away_id),
                },
            ],
            "participants": [
                *[
                    _participant("home", player_id, position)
                    for position, player_id in enumerate(home_player_ids, start=1)
                ],
                *[
                    _participant("away", player_id, position)
                    for position, player_id in enumerate(away_player_ids, start=1)
                ],
            ],
        },
    )
    assert configuration.status_code == 200, configuration.text
    side_ids = {side["side_code"]: side["id"] for side in configuration.json()["sides"]}
    home_participants = sorted(
        (
            item
            for item in configuration.json()["participants"]
            if item["side_id"] == side_ids["home"]
        ),
        key=lambda item: item["batting_order_position"],
    )
    away_participants = sorted(
        (
            item
            for item in configuration.json()["participants"]
            if item["side_id"] == side_ids["away"]
        ),
        key=lambda item: item["batting_order_position"],
    )
    striker, non_striker, _suggested_batter, next_batter = [
        item["id"] for item in home_participants
    ]
    bowler, catcher = [item["id"] for item in away_participants]

    started = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        headers={"X-Request-ID": f"phase4-{unique}"},
        json={
            "match_version_number": configuration.json()["match_version_number"],
            "innings_number": 1,
            "opening_striker_participant_id": striker,
            "opening_non_striker_participant_id": non_striker,
            "opening_bowler_participant_id": bowler,
        },
    )
    assert started.status_code == 200, started.text
    innings_id = started.json()["id"]
    version = started.json()["version_number"]
    failed_duplicate_start = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": configuration.json()["match_version_number"],
            "innings_number": 1,
            "opening_striker_participant_id": striker,
            "opening_non_striker_participant_id": non_striker,
            "opening_bowler_participant_id": bowler,
        },
    )
    assert failed_duplicate_start.status_code == 409

    retired_before_first_ball = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/retired-hurt",
        json={
            "innings_version_number": version,
            "participant_id": striker,
            "reason": "pre-delivery assessment",
        },
    )
    assert retired_before_first_ball.status_code == 200, retired_before_first_ball.text
    returned_before_first_ball = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/retired-hurt-return",
        json={
            "innings_version_number": retired_before_first_ball.json()[
                "version_number"
            ],
            "participant_id": striker,
            "reason": "cleared before first delivery",
        },
    )
    assert returned_before_first_ball.status_code == 200, (
        returned_before_first_ball.text
    )
    version = returned_before_first_ball.json()["version_number"]
    invalid_attempts = [
        {
            "runs_off_bat": 2_147_483_647,
            "extras": {"no_ball_penalty_runs": 1},
        },
        {
            "runs_off_bat": 0,
            "extras": {},
            "wicket": {
                "dismissal_type": "caught",
                "dismissed_participant_id": striker,
                "fielders": [],
            },
        },
        {
            "runs_off_bat": 0,
            "extras": {},
            "wicket": {
                "dismissal_type": "timed_out",
                "dismissed_participant_id": striker,
                "fielders": [],
            },
        },
    ]
    for invalid_facts in invalid_attempts:
        rejected = await client.post(
            f"/api/v1/matches/{match_id}/innings/{innings_id}/deliveries",
            json={
                "innings_version_number": version,
                "attempted_sequence": 1,
                "striker_participant_id": striker,
                "non_striker_participant_id": non_striker,
                "bowler_participant_id": bowler,
                **invalid_facts,
            },
        )
        assert rejected.status_code == 422

    attempts: list[dict[str, object]] = [
        {"runs_off_bat": 1, "extras": {}},
        {"runs_off_bat": 0, "extras": {"wide_runs": 3}},
        {"runs_off_bat": 4, "extras": {"no_ball_penalty_runs": 1}},
        {"runs_off_bat": 0, "extras": {"bye_runs": 2}},
        {
            "runs_off_bat": 0,
            "extras": {},
            "wicket": {
                "dismissal_type": "caught",
                "dismissed_participant_id": non_striker,
                "fielders": [{"participant_id": catcher, "role": "catcher"}],
            },
        },
    ]
    current_striker, current_non_striker = striker, non_striker
    latest: httpx.Response | None = None
    for sequence, facts in enumerate(attempts, start=1):
        if sequence == 2:
            current_striker, current_non_striker = non_striker, striker
        latest = await client.post(
            f"/api/v1/matches/{match_id}/innings/{innings_id}/deliveries",
            json={
                "innings_version_number": version,
                "attempted_sequence": sequence,
                "striker_participant_id": current_striker,
                "non_striker_participant_id": current_non_striker,
                "bowler_participant_id": bowler,
                **facts,
            },
        )
        assert latest.status_code == 200, latest.text
        version = latest.json()["innings_version_number"]

    assert latest is not None
    assert latest.json()["innings_total_runs"] == 11
    assert latest.json()["innings_legal_balls"] == 3
    assert latest.json()["innings_wickets_lost"] == 1
    assert latest.json()["blocking_state"]["kind"] == "awaiting_next_batter"
    wicket = latest.json()["active_revision"]["wicket"]
    assert wicket["fielders"] == [
        {"participant_id": catcher, "ordinal": 1, "role": "catcher"}
    ]
    assert wicket["primary_fielder_participant_id"] == catcher

    blocked = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/deliveries",
        json={
            "innings_version_number": version,
            "attempted_sequence": 6,
            "striker_participant_id": next_batter,
            "non_striker_participant_id": striker,
            "bowler_participant_id": bowler,
            "runs_off_bat": 1,
            "extras": {},
        },
    )
    assert blocked.status_code == 422
    selected = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/next-batter",
        json={
            "innings_version_number": version,
            "batter_participant_id": next_batter,
            "replacing_participant_id": non_striker,
            "reason": "dismissal",
        },
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["blocking_state"]["kind"] == "none"

    retired = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/retired-hurt",
        json={
            "innings_version_number": selected.json()["version_number"],
            "participant_id": next_batter,
            "reason": "injury",
        },
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["wickets_lost"] == 1
    assert retired.json()["blocking_state"]["kind"] == "awaiting_next_batter"
    returned = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/retired-hurt-return",
        json={
            "innings_version_number": retired.json()["version_number"],
            "participant_id": next_batter,
            "reason": "cleared",
        },
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["blocking_state"]["kind"] == "none"

    history = await client.get(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/deliveries?limit=5"
    )
    assert history.status_code == 200, history.text
    assert [item["attempted_sequence"] for item in history.json()["deliveries"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    async with AsyncSessionFactory() as session:
        innings = await session.get(Innings, UUID(innings_id))
        delivery_count = int(
            await session.scalar(
                select(func.count(Delivery.id)).where(
                    Delivery.innings_id == UUID(innings_id)
                )
            )
            or 0
        )
        wicket_event = await session.scalar(
            select(WicketEvent)
            .join(
                DeliveryFielder,
                DeliveryFielder.delivery_revision_id
                == WicketEvent.delivery_revision_id,
            )
            .where(DeliveryFielder.participant_id == UUID(catcher))
        )
        audit_count = int(
            await session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(
                    BusinessAuditEvent.target_entity_id == match_id,
                    BusinessAuditEvent.action_type == "scoring.innings_started",
                )
            )
            or 0
        )
        start_audit = await session.scalar(
            select(BusinessAuditEvent).where(
                BusinessAuditEvent.target_entity_id == match_id,
                BusinessAuditEvent.action_type == "scoring.innings_started",
            )
        )
        scoring_audit_count = int(
            await session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(
                    BusinessAuditEvent.target_entity_id == match_id,
                    BusinessAuditEvent.action_category == "scoring",
                )
            )
            or 0
        )
        match = await session.get(Match, match_id)
        assert match is not None
        match.lifecycle_state = MatchLifecycleState.ABANDONED
        match.result_code = MatchResultCode.NO_RESULT
        await session.commit()
    assert innings is not None
    assert (innings.total_runs, innings.legal_balls, innings.wickets_lost) == (11, 3, 1)
    assert delivery_count == 5
    assert wicket_event is not None
    assert audit_count == 1
    assert scoring_audit_count == 2
    assert start_audit is not None
    assert start_audit.actor_display_name == "Integration Head Coach"
    assert start_audit.actor_role == "head coach"
    assert start_audit.request_id == f"phase4-{unique}"
    assert start_audit.event_metadata == {
        "innings_id": innings_id,
        "innings_number": 1,
        "batting_side_id": side_ids["home"],
        "fielding_side_id": side_ids["away"],
    }

    abandoned = await client.get(f"/api/v1/matches/{match_id}/innings/{innings_id}")
    assert abandoned.status_code == 200, abandoned.text
    assert abandoned.json()["lifecycle_state"] == "in_progress"
    assert abandoned.json()["blocking_state"] == {
        "kind": "match_abandoned",
        "is_blocked": True,
        "reason_code": "match_abandoned",
    }
    after_abandonment = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings_id}/deliveries",
        json={
            "innings_version_number": returned.json()["version_number"],
            "attempted_sequence": 6,
            "striker_participant_id": next_batter,
            "non_striker_participant_id": striker,
            "bowler_participant_id": bowler,
            "runs_off_bat": 0,
            "extras": {},
        },
    )
    assert after_abandonment.status_code == 409

    async with AsyncSessionFactory() as session:
        await session.execute(delete(Innings).where(Innings.match_id == match_id))
        await session.execute(delete(Match).where(Match.id == match_id))
        await session.commit()


async def _phase7_configuration(
    client, profile, external, match_ids, boundary="after_completed_innings"
):
    from tests.unit.test_scoring_projections import _completion_policy

    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        teams = [
            Team(name=f"Completion-{side}-{unique}", age_group="U15")
            for side in ("home", "away")
        ]
        players = [
            [await _player(f"{side}-{i}", unique) for i in range(11)]
            for side in ("home", "away")
        ]
        session.add_all([*teams, *players[0], *players[1]])
        await session.flush()
        session.add_all(
            [
                TeamPlayer(team_id=team.id, player_id=p.id, roster_order=i)
                for team, roster in zip(teams, players, strict=True)
                for i, p in enumerate(roster, 1)
            ]
        )
        match = _match(
            home_team_id=teams[0].id,
            away_team_id=None if external else teams[1].id,
            opponent="Visitors" if external else None,
            format=MatchFormat(profile),
        )
        session.add(match)
        await session.commit()
        match_ids.append(match.id)
        policy = {
            "policy_code": profile,
            "capability_profile": profile,
            "innings_sequence": ["home", "away"] * (2 if profile == "test" else 1),
        }
        if profile == "other":
            columns = _completion_policy(profile, boundary).policy_columns()
            policy.update(
                {
                    key: value
                    for key, value in columns.items()
                    if key not in {"policy_version"}
                }
            )
        response = await client.put(
            f"/api/v1/matches/{match.id}/configuration",
            json={
                "match_version_number": 1,
                "format": profile,
                "policy": policy,
                "sides": [
                    {
                        "side_code": "home",
                        "side_kind": "academy",
                        "team_id": str(teams[0].id),
                    },
                    {
                        "side_code": "away",
                        "side_kind": "external",
                        "display_name": "Visitors",
                    }
                    if external
                    else {
                        "side_code": "away",
                        "side_kind": "academy",
                        "team_id": str(teams[1].id),
                    },
                ],
                "participants": [
                    *[
                        _participant("home", p.id, i)
                        for i, p in enumerate(players[0], 1)
                    ],
                    *[
                        {
                            "side_code": "away",
                            "participant_kind": "external",
                            "display_name": f"Visitor {i}",
                            "batting_order_position": i,
                        }
                        if external
                        else _participant("away", p.id, i)
                        for i, p in enumerate(players[1], 1)
                    ],
                ],
            },
        )
    assert response.status_code == 200, response.text
    config = response.json()
    sides = {s["side_code"]: s["id"] for s in config["sides"]}
    participants = {
        code: [p["id"] for p in config["participants"] if p["side_id"] == id]
        for code, id in sides.items()
    }
    return config, participants


async def _phase7_start(client, config, participants, number, version):
    side = config["policy"]["innings_sequence"][number - 1]
    fielding = "away" if side == "home" else "home"
    response = await client.post(
        f"/api/v1/matches/{config['match_id']}/innings",
        json={
            "match_version_number": version,
            "innings_number": number,
            "opening_striker_participant_id": participants[side][0],
            "opening_non_striker_participant_id": participants[side][1],
            "opening_bowler_participant_id": participants[fielding][0],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _phase7_score(client, match_id, state, sequence, runs=0, wicket=False):
    base = f"/api/v1/matches/{match_id}/innings/{state['id']}"
    response = await client.post(
        base + "/deliveries",
        json={
            "innings_version_number": state["version_number"],
            "attempted_sequence": sequence,
            "striker_participant_id": state["striker_participant_id"],
            "non_striker_participant_id": state["non_striker_participant_id"],
            "bowler_participant_id": state["current_bowler_participant_id"],
            "runs_off_bat": runs,
            "wicket": {
                "dismissal_type": "bowled",
                "dismissed_participant_id": state["striker_participant_id"],
                "fielders": [],
            }
            if wicket
            else None,
        },
    )
    assert response.status_code == 200, response.text
    read = await client.get(base)
    assert read.status_code == 200, read.text
    return read.json(), response.json()


async def _phase7_all_out(client, match_id, state, batters, bowlers, runs):
    state, _ = await _phase7_score(client, match_id, state, 1, runs=runs)
    base = f"/api/v1/matches/{match_id}/innings/{state['id']}"
    for wicket in range(10):
        dismissed = state["striker_participant_id"]
        state, _ = await _phase7_score(client, match_id, state, wicket + 2, wicket=True)
        if wicket == 9:
            break
        response = await client.post(
            base + "/next-batter",
            json={
                "innings_version_number": state["version_number"],
                "batter_participant_id": batters[wicket + 2],
                "replacing_participant_id": dismissed,
                "reason": "dismissal",
            },
        )
        assert response.status_code == 200, response.text
        state = response.json()
        if state["current_bowler_participant_id"] is None:
            response = await client.post(
                base + "/next-bowler",
                json={
                    "innings_version_number": state["version_number"],
                    "bowler_participant_id": bowlers[1],
                    "override_reason": "Tactical change",
                },
            )
            assert response.status_code == 200, response.text
            state = response.json()
    assert state["lifecycle_state"] == "completed"
    assert state["completion_reason"] == "all_out"
    assert state["wickets_lost"] == 10
    return state


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("outcome", ["chase", "tie", "runs"])
async def test_phase7_fixed_over_completion_chase_and_tie(
    client, external, outcome, phase5_matches
):
    from src.models.background_work_item import BackgroundWorkItem

    config, participants = await _phase7_configuration(
        client, "T20", external, phase5_matches
    )
    match_id = config["match_id"]
    first = await _phase7_start(
        client, config, participants, 1, config["match_version_number"]
    )
    first = await _phase7_all_out(
        client, match_id, first, participants["home"], participants["away"], 4
    )
    second = await _phase7_start(
        client, config, participants, 2, first["match_version_number"]
    )
    assert second["target_runs"] == 5
    if outcome == "chase":
        second, _ = await _phase7_score(client, match_id, second, 1, runs=6)
        assert second["completion_reason"] == "target_reached"
    else:
        second = await _phase7_all_out(
            client,
            match_id,
            second,
            participants["away"],
            participants["home"],
            4 if outcome == "tie" else 2,
        )
    assert second["blocking_state"]["kind"] == "match_completed"
    async with AsyncSessionFactory() as session:
        match = await session.get(Match, UUID(match_id))
        assert match.lifecycle_state == "completed"
        assert (
            match.result_code
            == {"chase": "win_by_wickets", "tie": "tie", "runs": "win_by_runs"}[outcome]
        )
        if outcome == "chase":
            assert match.result_details["wickets_remaining"] == 10
        audits = list(
            (
                await session.scalars(
                    select(BusinessAuditEvent).where(
                        BusinessAuditEvent.target_entity_id == UUID(match_id)
                    )
                )
            ).all()
        )
        assert sum(a.action_type == "scoring.innings_completed" for a in audits) == 2
        assert sum(a.action_type == "scoring.match_completed" for a in audits) == 1
        jobs = list(
            (
                await session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.source_key == match_id
                    )
                )
            ).all()
        )
        assert len(jobs) == 1
    rejected = await client.post(
        f"/api/v1/matches/{match_id}/completion",
        json={
            "match_version_number": second["match_version_number"],
            "completion_kind": "abandonment",
            "reason": "Rain",
        },
    )
    assert rejected.status_code == 409


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.parametrize("external", [False, True])
@pytest.mark.parametrize("kind", ["draw", "declared", "manual"])
async def test_phase7_test_declaration_and_explicit_match_boundary(
    client, external, kind, phase5_matches
):
    config, participants = await _phase7_configuration(
        client, "test", external, phase5_matches
    )
    match_id = config["match_id"]
    state = await _phase7_start(
        client, config, participants, 1, config["match_version_number"]
    )
    base = f"/api/v1/matches/{match_id}"
    invalid = await client.post(
        base + "/completion",
        json={
            "match_version_number": state["match_version_number"],
            "completion_kind": kind,
            "reason": "Close of play",
        },
    )
    assert invalid.status_code == 409
    invalid = await client.post(
        base + f"/innings/{state['id']}/completion",
        json={
            "innings_version_number": state["version_number"],
            "completion_kind": "abandonment",
            "reason": "Rain",
        },
    )
    assert invalid.status_code == 422
    completed = await client.post(
        base + f"/innings/{state['id']}/completion",
        json={
            "innings_version_number": state["version_number"],
            "completion_kind": "declaration",
            "reason": "Captain declares",
        },
    )
    assert completed.status_code == 200, completed.text
    state = completed.json()
    stale = await client.post(
        base + "/completion",
        json={
            "match_version_number": state["match_version_number"] - 1,
            "completion_kind": kind,
            "reason": "Close of play",
        },
    )
    assert stale.status_code == 409
    completed = await client.post(
        base + "/completion",
        json={
            "match_version_number": state["match_version_number"],
            "completion_kind": kind,
            "reason": "Close of play",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["result_code"] == kind
    assert completed.json()["blocking_state"]["kind"] == "match_completed"


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.parametrize(
    "boundary", ["after_completed_innings", "any_nonterminal_state"]
)
async def test_phase7_other_manual_boundary(client, boundary, phase5_matches):
    config, participants = await _phase7_configuration(
        client, "other", True, phase5_matches, boundary
    )
    match_id = config["match_id"]
    state = await _phase7_start(
        client, config, participants, 1, config["match_version_number"]
    )
    base = f"/api/v1/matches/{match_id}"
    if boundary == "after_completed_innings":
        rejected = await client.post(
            base + "/completion",
            json={
                "match_version_number": state["match_version_number"],
                "completion_kind": "manual",
                "reason": "Agreed end",
            },
        )
        assert rejected.status_code == 409
        completed = await client.post(
            base + f"/innings/{state['id']}/completion",
            json={
                "innings_version_number": state["version_number"],
                "completion_kind": "manual",
                "reason": "Close innings",
            },
        )
        assert completed.status_code == 200, completed.text
        state = completed.json()
    completed = await client.post(
        base + "/completion",
        json={
            "match_version_number": state["match_version_number"],
            "completion_kind": "manual",
            "reason": "Agreed end",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["result_code"] == "manual"


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.parametrize("started", [False, True])
async def test_phase7_abandonment_preserves_underlying_innings(
    client, started, phase5_matches
):
    config, participants = await _phase7_configuration(
        client, "T20", True, phase5_matches
    )
    match_id, version = config["match_id"], config["match_version_number"]
    if started:
        state = await _phase7_start(client, config, participants, 1, version)
        version = state["match_version_number"]
    response = await client.post(
        f"/api/v1/matches/{match_id}/completion",
        json={
            "match_version_number": version,
            "completion_kind": "abandonment",
            "reason": "Rain",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["lifecycle_state"] == "abandoned"
    assert body["result_code"] == "no_result"
    assert body["blocking_state"]["kind"] == "match_abandoned"
    if started:
        assert body["innings"][0]["lifecycle_state"] == "in_progress"
        assert body["innings"][0]["completion_reason"] is None
        assert body["innings"][0]["blocking_state"]["kind"] == "match_abandoned"
    else:
        assert body["innings"] == []


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_phase7_test_ordered_four_innings_aggregate_result(
    client, phase5_matches
):
    config, participants = await _phase7_configuration(
        client, "test", False, phase5_matches
    )
    match_id = config["match_id"]
    version = config["match_version_number"]
    for number, runs in enumerate([2, 4, 6, 8], 1):
        state = await _phase7_start(client, config, participants, number, version)
        assert state["target_runs"] is None
        assert state["legal_balls"] == state["total_runs"] == 0
        state, _ = await _phase7_score(client, match_id, state, 1, runs=runs)
        denied = await client.post(
            f"/api/v1/matches/{match_id}/completion",
            json={
                "match_version_number": state["match_version_number"],
                "completion_kind": "draw",
                "reason": "Close of play",
            },
        )
        assert denied.status_code == 409
        response = await client.post(
            f"/api/v1/matches/{match_id}/innings/{state['id']}/completion",
            json={
                "innings_version_number": state["version_number"],
                "completion_kind": "declaration",
                "reason": "Captain declares",
            },
        )
        assert response.status_code == 200, response.text
        version = response.json()["match_version_number"]
    assert response.json()["blocking_state"]["kind"] == "match_completed"
    async with AsyncSessionFactory() as session:
        match = await session.get(Match, UUID(match_id))
        assert match.result_code == "win_by_runs"
        assert match.result_details == {
            "winning_side_code": "away",
            "runs_margin": 4,
            "side_totals": {"home": 8, "away": 12},
        }
    rejected = await client.post(
        f"/api/v1/matches/{match_id}/completion",
        json={
            "match_version_number": version,
            "completion_kind": "draw",
            "reason": "Close of play",
        },
    )
    assert rejected.status_code == 409


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_sc002_projected_scorecard_meets_warm_read_budget(
    client, phase5_matches, data_quality_query_counter
):
    """Measure one cold read and 30 warm projection-only scorecard reads."""

    from time import perf_counter

    from src.enums import InningsTransitionType
    from src.models.scoring.transition_event import InningsTransitionEvent

    config, participants = await _phase7_configuration(
        client, "test", True, phase5_matches
    )
    started = await _phase7_start(
        client, config, participants, 1, config["match_version_number"]
    )
    match_id = UUID(config["match_id"])
    innings_id = UUID(started["id"])
    batting_ids = [UUID(value) for value in participants["home"]]
    fielding_ids = [UUID(value) for value in participants["away"]]
    endpoint = f"/api/v1/matches/{match_id}/scorecard"

    async with AsyncSessionFactory() as session:
        actor_id = await session.scalar(
            select(InningsTransitionEvent.created_by_user_id)
            .where(InningsTransitionEvent.innings_id == innings_id)
            .limit(1)
        )
        assert actor_id is not None

        delivery_rows: list[dict[str, object]] = []
        revision_rows: list[dict[str, object]] = []
        transitions: list[InningsTransitionEvent] = []
        legal_seen = 0
        for sequence in range(1, 1001):
            delivery_id, revision_id = uuid4(), uuid4()
            is_legal = sequence > 100
            if is_legal:
                legal_seen += 1
            over_index = max(0, (legal_seen - 1) // 6)
            bowler_id = fielding_ids[over_index % 2]
            wide_runs = 1 if not is_legal else 0
            delivery_rows.append(
                {
                    "id": delivery_id,
                    "innings_id": innings_id,
                    "attempted_sequence": sequence,
                }
            )
            revision_rows.append(
                {
                    "id": revision_id,
                    "delivery_id": delivery_id,
                    "revision_number": 1,
                    "revision_state": "active",
                    "striker_participant_id": batting_ids[0],
                    "non_striker_participant_id": batting_ids[1],
                    "bowler_participant_id": bowler_id,
                    "runs_off_bat": 0,
                    "wide_runs": wide_runs,
                    "no_ball_penalty_runs": 0,
                    "bye_runs": 0,
                    "leg_bye_runs": 0,
                    "penalty_runs": 0,
                    "total_runs": wide_runs,
                    "is_legal": is_legal,
                    "completed_runs": 0,
                    "balls_faced": is_legal,
                    "bowler_conceded_runs": wide_runs,
                    "over_number": over_index,
                    "ball_in_over": ((legal_seen - 1) % 6 + 1) if is_legal else 1,
                    "recorded_by_user_id": actor_id,
                }
            )
            if is_legal and legal_seen % 6 == 0 and legal_seen < 900:
                next_over = legal_seen // 6
                transitions.append(
                    InningsTransitionEvent(
                        innings_id=innings_id,
                        event_kind=InningsTransitionType.NEXT_BOWLER,
                        participant_id=fielding_ids[next_over % 2],
                        anchored_attempted_sequence=sequence,
                        anchored_revision_id=revision_id,
                        over_number=next_over,
                        reason="Performance fixture over rotation",
                        created_by_user_id=actor_id,
                    )
                )

        assert legal_seen == 900
        await session.execute(insert(Delivery), delivery_rows)
        await session.execute(insert(DeliveryRevision), revision_rows)
        session.add_all(transitions)

        session.add_all(
            [
                InningsOver(
                    innings_id=innings_id,
                    over_number=over_number,
                    bowler_participant_id=fielding_ids[over_number % 2],
                    legal_ball_count=6,
                    total_runs=100 if over_number == 0 else 0,
                    runs_conceded=100 if over_number == 0 else 0,
                    wickets=0,
                    is_complete=True,
                    projection_revision=1000,
                )
                for over_number in range(150)
            ]
        )
        summaries = {
            item.participant_id: item
            for item in (
                await session.scalars(
                    select(InningsParticipantSummary).where(
                        InningsParticipantSummary.innings_id == innings_id
                    )
                )
            ).all()
        }
        batting_summary = summaries[batting_ids[0]]
        batting_summary.participation_state = "active"
        batting_summary.batting_runs = 0
        batting_summary.balls_faced = 900
        batting_summary.projection_revision = 1000
        summaries[batting_ids[1]].participation_state = "active"
        summaries[batting_ids[1]].projection_revision = 1000
        summaries[fielding_ids[0]].bowling_legal_balls = 450
        summaries[fielding_ids[0]].bowling_overs_completed = 75
        summaries[fielding_ids[0]].runs_conceded = 100
        summaries[fielding_ids[0]].wides = 100
        summaries[fielding_ids[0]].projection_revision = 1000
        summaries[fielding_ids[1]].bowling_legal_balls = 450
        summaries[fielding_ids[1]].bowling_overs_completed = 75
        summaries[fielding_ids[1]].projection_revision = 1000
        innings = await session.get(Innings, innings_id)
        assert innings is not None
        innings.legal_balls = 900
        innings.total_runs = 100
        innings.wickets_lost = 0
        innings.projection_revision = 1000
        innings.striker_participant_id = batting_ids[0]
        innings.non_striker_participant_id = batting_ids[1]
        innings.current_bowler_participant_id = None
        snapshot = dict(innings.state_snapshot)
        snapshot.pop("blocking_state", None)
        snapshot["extras"] = {
            "wides": 100,
            "no_balls": 0,
            "byes": 0,
            "leg_byes": 0,
            "penalty_runs": 0,
        }
        innings.state_snapshot = snapshot
        await session.commit()

        assert (
            await session.scalar(
                select(func.count(DeliveryRevision.id))
                .join(Delivery)
                .where(
                    Delivery.innings_id == innings_id,
                    DeliveryRevision.revision_state == "active",
                )
            )
            == 1000
        )
        assert (
            await session.scalar(
                select(func.count(DeliveryRevision.id)).where(
                    DeliveryRevision.delivery_id.in_(
                        select(Delivery.id).where(Delivery.innings_id == innings_id)
                    ),
                    DeliveryRevision.is_legal.is_(True),
                )
            )
            == 900
        )
        assert (
            await session.scalar(
                select(func.count(DeliveryRevision.id)).where(
                    DeliveryRevision.delivery_id.in_(
                        select(Delivery.id).where(Delivery.innings_id == innings_id)
                    ),
                    DeliveryRevision.is_legal.is_(False),
                )
            )
            == 100
        )

    cold_start = perf_counter()
    cold = await client.get(endpoint)
    cold_elapsed = perf_counter() - cold_start
    assert cold.status_code == 200, cold.text
    assert cold_elapsed >= 0
    assert cold.json()["innings"][0]["projection_revision"] == 1000
    assert cold.json()["innings"][0]["total_runs"] == 100
    assert cold.json()["innings"][0]["legal_balls"] == 900

    for _ in range(5):
        warmup = await client.get(endpoint)
        assert warmup.status_code == 200, warmup.text

    with data_quality_query_counter.count() as counter:
        warm_durations = []
        for _ in range(30):
            warm_start = perf_counter()
            response = await client.get(endpoint)
            warm_durations.append(perf_counter() - warm_start)
            assert response.status_code == 200, response.text

    assert sum(duration <= 1.0 for duration in warm_durations) >= 29
    normalized_sql = [statement.lower() for statement in counter.statements]
    assert not any(
        " from deliveries" in statement or " from delivery_revisions" in statement
        for statement in normalized_sql
    )
    assert counter.total <= 30 * 20
