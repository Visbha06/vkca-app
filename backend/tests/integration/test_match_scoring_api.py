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
    MatchParticipantType,
    PlayerType,
    ScoringAuthority,
)
from src.main import app
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.player import Player
from src.models.scoring.participant import MatchParticipant
from src.models.scoring.scoring_policy import ScoringPolicy
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
