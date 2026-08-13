"""Automated API timing assertions for the measurable success criteria."""

from datetime import date
from time import monotonic
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.enums import (
    BattingStyle,
    BowlingStyle,
    MatchFormat,
    MatchParticipantType,
    PlayerType,
)
from src.main import app
from src.models.data_sync_log import DataSyncLog
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.models.team import Team


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a real PostgreSQL session for timing assertions."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Route API dependencies through the integration-test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_players(count: int) -> list[Player]:
    """Build unique players for a full cricket squad."""

    run_id = uuid4()
    return [
        Player(
            first_name=f"Timing-{index}",
            last_name=f"Player-{run_id}",
            date_of_birth=date(2000, 1, index + 1),
            batting_style=BattingStyle.RIGHT,
            bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
            player_type=PlayerType.ALL_ROUNDER,
        )
        for index in range(count)
    ]


async def delete_performance_data(
    session: AsyncSession,
    player_ids: list[UUID],
    match_id: UUID,
    team_id: UUID,
) -> None:
    """Remove rows produced by one timed batch in foreign-key order."""

    for model in (
        MatchFieldingPerformance,
        MatchBowlingPerformance,
        MatchBattingPerformance,
        PlayerBowlingStats,
        PlayerBattingStats,
    ):
        await session.execute(delete(model).where(model.player_id.in_(player_ids)))
    await session.execute(delete(Match).where(Match.id == match_id))
    await session.execute(delete(Player).where(Player.id.in_(player_ids)))
    await session.execute(delete(Team).where(Team.id == team_id))


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_eleven_player_batch_completes_within_three_seconds(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """SC-002: write 33 performance rows and aggregates in under three seconds."""

    players = make_players(11)
    team = Team(id=uuid4(), name=f"Timing Team {uuid4()}", age_group="U15")
    match = Match(
        match_date=date(2026, 7, 12),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=team.id,
        external_opponent_name=f"Timing Opponent {uuid4()}",
        venue="Timing Ground",
        result="Won",
    )
    db_session.add_all([*players, team, match])
    await db_session.flush()
    player_ids = [player.id for player in players]
    team_id = team.id
    match_id = match.id
    await db_session.commit()

    payload = {
        "performances": [
            {
                "player_id": str(player_id),
                "batting": {
                    "runs_scored": 20 + index,
                    "balls_faced": 15 + index,
                    "dismissal": "caught",
                    "fours": 2,
                    "sixes": 1,
                },
                "bowling": {
                    "overs_bowled": "4.0",
                    "maidens": 0,
                    "runs_conceded": 24 + index,
                    "wickets_taken": 1,
                    "wides": 1,
                },
                "fielding": {"catches": 1},
            }
            for index, player_id in enumerate(player_ids)
        ]
    }

    try:
        started_at = monotonic()
        response = await client.post(
            f"/api/v1/matches/{match_id}/performances",
            json=payload,
        )
        elapsed = monotonic() - started_at

        assert response.status_code == 201, response.text
        assert response.json()["performances_created"] == 11
        assert response.json()["batting_records"] == 11
        assert response.json()["bowling_records"] == 11
        assert response.json()["fielding_records"] == 11
        assert elapsed < 3, f"11-player batch took {elapsed:.3f}s"
    finally:
        await db_session.rollback()
        await delete_performance_data(db_session, player_ids, match_id, team_id)
        await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_occ_conflict_response_completes_within_one_second(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """SC-003: return and audit a stale player update in under one second."""

    player = make_players(1)[0]
    db_session.add(player)
    await db_session.flush()
    player_id = player.id
    await db_session.commit()

    try:
        current_update = await client.put(
            f"/api/v1/players/{player_id}",
            json={"bio": "Current update", "version_number": 1},
        )
        assert current_update.status_code == 200

        started_at = monotonic()
        stale_update = await client.put(
            f"/api/v1/players/{player_id}",
            json={"bio": "Stale update", "version_number": 1},
        )
        elapsed = monotonic() - started_at

        assert stale_update.status_code == 409
        assert elapsed < 1, f"OCC conflict response took {elapsed:.3f}s"
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(DataSyncLog).where(
                DataSyncLog.target_table == "players",
                DataSyncLog.error_message.contains(str(player_id)),
            )
        )
        await db_session.execute(delete(Player).where(Player.id == player_id))
        await db_session.commit()
