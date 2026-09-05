"""Authenticated Phase 3 Match-scoring configuration integration coverage."""

from datetime import date
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

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
from src.models.scoring.innings import Innings
from src.models.scoring.participant import MatchParticipant
from src.models.scoring.scoring_policy import ScoringPolicy
from src.models.scoring.wicket_event import WicketEvent
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.models.user import User


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
