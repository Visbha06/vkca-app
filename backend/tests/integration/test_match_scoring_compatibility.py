"""Phase 8 scorecard, compatibility, authorization, and quality integration."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete

from src.database import AsyncSessionFactory
from src.enums import (
    BattingStyle,
    BowlingStyle,
    MatchFormat,
    MatchParticipantType,
    PlayerType,
    UserRole,
)
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.scoring.innings import Innings
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture(loop_scope="session")
async def compatibility_match_ids(authenticated_client):
    match_ids: list[UUID] = []
    yield match_ids
    async with AsyncSessionFactory() as session:
        for model in (
            MatchBattingPerformance,
            MatchBowlingPerformance,
            MatchFieldingPerformance,
        ):
            await session.execute(delete(model).where(model.match_id.in_(match_ids)))
        await session.execute(delete(Innings).where(Innings.match_id.in_(match_ids)))
        await session.execute(delete(Match).where(Match.id.in_(match_ids)))
        await session.commit()


def _player(name: str, *, user_id: UUID | None = None) -> Player:
    return Player(
        first_name=name,
        last_name=uuid4().hex[:8],
        date_of_birth=date(2008, 1, 1),
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        is_active=True,
        user_id=user_id,
    )


def _user(role: UserRole, name: str) -> User:
    return User(
        first_name=name,
        last_name="Compatibility",
        email=f"{name.lower()}-{uuid4().hex}@example.test",
        hashed_password="unused-test-hash",
        role=role,
        is_active=True,
    )


async def _configured_scoring_case(
    client: httpx.AsyncClient,
    match_ids: list[UUID],
    *,
    external: bool,
) -> dict[str, object]:
    unique = uuid4().hex[:8]
    async with AsyncSessionFactory() as session:
        home = Team(name=f"Compat Home {unique}", age_group="U15")
        away = Team(name=f"Compat Away {unique}", age_group="U15")
        home_players = [_player("HomeOne"), _player("HomeTwo")]
        away_players = [_player("AwayOne"), _player("AwayTwo"), _player("AwayThree")]
        session.add_all([home, away, *home_players, *away_players])
        await session.flush()
        session.add_all(
            [
                TeamPlayer(team_id=team.id, player_id=player.id, roster_order=index)
                for team, players in ((home, home_players), (away, away_players))
                for index, player in enumerate(players, 1)
            ]
        )
        match = Match(
            match_date=date(2026, 9, 10),
            format=MatchFormat.T20,
            participant_type=(
                MatchParticipantType.EXTERNAL
                if external
                else MatchParticipantType.INTERNAL
            ),
            home_team_id=home.id,
            away_team_id=None if external else away.id,
            external_opponent_name="Visitors XI" if external else None,
            venue="Compatibility Ground",
            result="Scheduled",
            version_number=1,
        )
        session.add(match)
        await session.commit()
        match_ids.append(match.id)

    participants: list[dict[str, object]] = [
        {
            "side_code": "home",
            "participant_kind": "internal",
            "player_id": str(player.id),
            "batting_order_position": index,
        }
        for index, player in enumerate(home_players, 1)
    ]
    if external:
        participants.extend(
            {
                "side_code": "away",
                "participant_kind": "external",
                "display_name": name,
                "batting_order_position": index,
            }
            for index, name in enumerate(
                ("Visiting Bowler", "Visiting Fielder", "Visiting Batter"), 1
            )
        )
    else:
        participants.extend(
            {
                "side_code": "away",
                "participant_kind": "internal",
                "player_id": str(player.id),
                "batting_order_position": index,
            }
            for index, player in enumerate(away_players, 1)
        )
    configured = await client.put(
        f"/api/v1/matches/{match.id}/configuration",
        json={
            "match_version_number": 1,
            "format": "T20",
            "policy": {
                "policy_code": "T20",
                "capability_profile": "T20",
                "innings_sequence": ["home", "away"],
            },
            "sides": [
                {
                    "side_code": "home",
                    "side_kind": "academy",
                    "team_id": str(home.id),
                },
                (
                    {
                        "side_code": "away",
                        "side_kind": "external",
                        "display_name": "Visitors XI",
                    }
                    if external
                    else {
                        "side_code": "away",
                        "side_kind": "academy",
                        "team_id": str(away.id),
                    }
                ),
            ],
            "participants": participants,
        },
    )
    assert configured.status_code == 200, configured.text
    configuration = configured.json()
    side_ids = {item["side_code"]: item["id"] for item in configuration["sides"]}
    batters = [
        item["id"]
        for item in configuration["participants"]
        if item["side_id"] == side_ids["home"]
    ]
    bowlers = [
        item["id"]
        for item in configuration["participants"]
        if item["side_id"] == side_ids["away"]
    ]
    started = await client.post(
        f"/api/v1/matches/{match.id}/innings",
        json={
            "match_version_number": configuration["match_version_number"],
            "innings_number": 1,
            "opening_striker_participant_id": batters[0],
            "opening_non_striker_participant_id": batters[1],
            "opening_bowler_participant_id": bowlers[0],
        },
    )
    assert started.status_code == 200, started.text
    state = started.json()
    base = f"/api/v1/matches/{match.id}/innings/{state['id']}"
    facts = {
        "striker_participant_id": batters[0],
        "non_striker_participant_id": batters[1],
        "bowler_participant_id": bowlers[0],
        "runs_off_bat": 4,
        "extras": {},
    }
    first = await client.post(
        base + "/deliveries",
        json={
            "innings_version_number": state["version_number"],
            "attempted_sequence": 1,
            **facts,
        },
    )
    assert first.status_code == 200, first.text
    first_delivery = first.json()
    second = await client.post(
        base + "/deliveries",
        json={
            "innings_version_number": first_delivery["innings_version_number"],
            "attempted_sequence": 2,
            **{**facts, "runs_off_bat": 0, "extras": {"wide_runs": 2}},
        },
    )
    assert second.status_code == 200, second.text
    return {
        "match_id": match.id,
        "home_team_id": home.id,
        "home_player_id": home_players[0].id,
        "innings_id": UUID(state["id"]),
        "base": base,
        "facts": facts,
        "first_delivery": first_delivery,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("external", [False, True])
async def test_internal_and_external_scorecards_and_performance_authority(
    client,
    compatibility_match_ids,
    external,
):
    case = await _configured_scoring_case(
        client, compatibility_match_ids, external=external
    )
    match_id = case["match_id"]

    scorecard = await client.get(f"/api/v1/matches/{match_id}/scorecard")
    assert scorecard.status_code == 200, scorecard.text
    body = scorecard.json()
    assert body["scoring_authority"] == "delivery_history"
    assert body["innings"][0]["total_runs"] == 6
    assert body["innings"][0]["legal_balls"] == 1
    assert body["innings"][0]["extras"]["wides"] == 2
    assert body["participant_performances"]
    if external:
        opposition = [
            item
            for item in body["participants"]
            if item["participant_kind"] == "external"
        ]
        assert opposition
        assert all(item["player_id"] is None for item in opposition)

    performances = await client.get(f"/api/v1/matches/{match_id}/performances")
    assert performances.status_code == 200, performances.text
    assert performances.json()["derived"]
    assert performances.json()["legacy_batting"] == []

    rejected = await client.post(
        f"/api/v1/matches/{match_id}/performances",
        json={
            "performances": [
                {
                    "player_id": str(case["home_player_id"]),
                    "batting": {"runs_scored": 99},
                    "bowling": {"overs_bowled": 1.0},
                    "fielding": {"catches": 1},
                }
            ]
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["code"] == "scoring_authority_conflict"


@pytest.mark.asyncio
async def test_current_team_reads_player_read_only_and_head_only_quality(
    client,
    compatibility_match_ids,
):
    case = await _configured_scoring_case(
        client, compatibility_match_ids, external=True
    )
    assistant = _user(UserRole.ASSISTANT_COACH, "Assistant")
    unrelated = _user(UserRole.ASSISTANT_COACH, "Unrelated")
    player_actor = _user(UserRole.PLAYER, "Player")
    actor_sessions: dict[UUID, AuthSession] = {}
    async with AsyncSessionFactory() as session:
        session.add_all([assistant, unrelated, player_actor])
        await session.flush()
        for actor in (assistant, unrelated, player_actor):
            auth_session = AuthSession(
                user_id=actor.id,
                token_family_id=uuid4(),
                current_token_hash=uuid4().hex + uuid4().hex,
                rotated_token_hashes=[],
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            actor_sessions[actor.id] = auth_session
            session.add(auth_session)
        linked_player = await session.get(Player, case["home_player_id"])
        assert linked_player is not None
        linked_player.user_id = player_actor.id
        session.add(TeamCoach(team_id=case["home_team_id"], user_id=assistant.id))
        await session.commit()

    async def request_as(actor: User, method: str, path: str, **kwargs):
        async def override_current_user():
            return actor, actor_sessions[actor.id]

        app.dependency_overrides[get_current_user] = override_current_user
        return await client.request(method, path, **kwargs)

    match_id = case["match_id"]
    assert (
        await request_as(assistant, "GET", f"/api/v1/matches/{match_id}/scorecard")
    ).status_code == 200
    assert (
        await request_as(unrelated, "GET", f"/api/v1/matches/{match_id}/scorecard")
    ).status_code == 404
    assert (
        await request_as(player_actor, "GET", f"/api/v1/matches/{match_id}/scorecard")
    ).status_code == 200
    forbidden_delivery = await request_as(
        player_actor,
        "POST",
        str(case["base"]) + "/deliveries",
        json={
            "innings_version_number": 3,
            "attempted_sequence": 3,
            **case["facts"],
        },
    )
    assert forbidden_delivery.status_code == 403
    assert (
        await request_as(
            assistant,
            "GET",
            "/api/v1/data-quality",
            params={"domain": "scoring"},
        )
    ).status_code == 403

    async with AsyncSessionFactory() as session:
        innings = await session.get(Innings, case["innings_id"])
        assert innings is not None
        innings.total_runs += 1
        await session.commit()

    app.dependency_overrides.pop(get_current_user, None)
    head_findings = await client.get(
        "/api/v1/data-quality", params={"domain": "scoring", "page_size": 100}
    )
    assert head_findings.status_code == 200, head_findings.text
    assert "scoring.projection_mismatch" in {
        item["rule_id"] for item in head_findings.json()["findings"]
    }

    first = case["first_delivery"]
    current = (await client.get(f"/api/v1/matches/{match_id}/scorecard")).json()
    corrected = await request_as(
        assistant,
        "POST",
        str(case["base"]) + f"/deliveries/{first['id']}/correction",
        json={
            "innings_version_number": current["innings"][0]["version_number"],
            "match_version_number": current["match_version_number"],
            "expected_revision_number": 1,
            "reason": "Correct observed boundary",
            "replacement": {**case["facts"], "runs_off_bat": 3},
        },
    )
    assert corrected.status_code == 200, corrected.text
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_legacy_aggregate_match_remains_readable_and_writable(
    client,
    compatibility_match_ids,
):
    async with AsyncSessionFactory() as session:
        team = Team(name=f"Legacy {uuid4().hex[:8]}", age_group="U13")
        away = Team(name=f"Legacy Away {uuid4().hex[:8]}", age_group="U13")
        player = _player("LegacyPlayer")
        session.add_all([team, away, player])
        await session.flush()
        match = Match(
            match_date=date(2026, 9, 10),
            format=MatchFormat.T20,
            participant_type=MatchParticipantType.INTERNAL,
            home_team_id=team.id,
            away_team_id=away.id,
            venue="Legacy Ground",
            result="Home won",
            version_number=1,
        )
        session.add(match)
        await session.commit()
        compatibility_match_ids.append(match.id)

    written = await client.post(
        f"/api/v1/matches/{match.id}/performances",
        json={
            "performances": [
                {
                    "player_id": str(player.id),
                    "batting": {"runs_scored": 42, "balls_faced": 30},
                    "bowling": {
                        "overs_bowled": 2.0,
                        "runs_conceded": 12,
                        "wickets_taken": 1,
                    },
                    "fielding": {"catches": 1},
                }
            ]
        },
    )
    assert written.status_code == 201, written.text

    read = await client.get(f"/api/v1/matches/{match.id}/performances")
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["scoring_authority"] == "legacy_aggregate"
    assert body["derived"] == []
    assert body["legacy_batting"][0]["runs_scored"] == 42
    assert body["legacy_bowling"][0]["wickets_taken"] == 1
    assert body["legacy_fielding"][0]["catches"] == 1
