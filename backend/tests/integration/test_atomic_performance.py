"""PostgreSQL integration tests for atomic performance submission."""

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, MatchFormat, PlayerType
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.schemas.performance import BatchPerformanceRequest
from src.services.performance_service import PerformanceService, PlayerNotFoundError


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a real session and remove only rows created by this test."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_batch_submission_is_atomic_and_recalculates_stats(
    db_session: AsyncSession,
) -> None:
    player = Player(
        first_name="Atomic",
        last_name=f"Player-{uuid4()}",
        date_of_birth=date(2001, 1, 1),
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
    )
    match = Match(
        match_date=date(2026, 7, 1),
        format=MatchFormat.T20,
        opponent_name=f"Integration-{uuid4()}",
        venue="Test Ground",
        result="Won",
    )
    rollback_match = Match(
        match_date=date(2026, 7, 2),
        format=MatchFormat.T20,
        opponent_name=f"Rollback-{uuid4()}",
        venue="Test Ground",
        result="Won",
    )
    db_session.add_all([player, match, rollback_match])
    await db_session.flush()
    player_id = player.id
    match_id = match.id
    rollback_match_id = rollback_match.id
    await db_session.commit()

    try:
        payload = BatchPerformanceRequest.model_validate(
            {
                "performances": [
                    {
                        "player_id": player_id,
                        "batting": {
                            "runs_scored": 82,
                            "balls_faced": 55,
                            "dismissal": "not out",
                            "fours": 9,
                            "sixes": 3,
                        },
                        "bowling": {
                            "overs_bowled": "4.0",
                            "maidens": 1,
                            "runs_conceded": 22,
                            "wickets_taken": 3,
                            "wides": 1,
                        },
                        "fielding": {"catches": 2},
                    }
                ]
            }
        )

        response = await PerformanceService(db_session).submit_batch_performance(
            match_id,
            payload.performances,
        )

        assert response.batting_records == 1
        assert response.bowling_records == 1
        assert response.fielding_records == 1
        assert response.players_stats_updated == 1
        assert await db_session.scalar(
            select(MatchBattingPerformance).where(
                MatchBattingPerformance.match_id == match_id
            )
        )
        assert await db_session.scalar(
            select(MatchBowlingPerformance).where(
                MatchBowlingPerformance.match_id == match_id
            )
        )
        assert await db_session.scalar(
            select(MatchFieldingPerformance).where(
                MatchFieldingPerformance.match_id == match_id
            )
        )

        batting_stats = await db_session.scalar(
            select(PlayerBattingStats).where(
                PlayerBattingStats.player_id == player_id,
                PlayerBattingStats.format == MatchFormat.T20,
            )
        )
        bowling_stats = await db_session.scalar(
            select(PlayerBowlingStats).where(
                PlayerBowlingStats.player_id == player_id,
                PlayerBowlingStats.format == MatchFormat.T20,
            )
        )
        assert batting_stats is not None
        assert batting_stats.matches == 1
        assert batting_stats.innings == 1
        assert batting_stats.not_outs == 1
        assert batting_stats.runs == 82
        assert batting_stats.high_score == 82
        assert batting_stats.fifties == 1
        assert bowling_stats is not None
        assert bowling_stats.matches == 1
        assert bowling_stats.innings == 1
        assert bowling_stats.wickets == 3
        assert bowling_stats.best_bowled == "3/22"
        assert bowling_stats.catches == 2
        await db_session.rollback()

        invalid_payload = BatchPerformanceRequest.model_validate(
            {
                "performances": [
                    {"player_id": player_id, "batting": {"runs_scored": 10}},
                    {"player_id": uuid4(), "fielding": {"catches": 1}},
                ]
            }
        )
        with pytest.raises(PlayerNotFoundError):
            await PerformanceService(db_session).submit_batch_performance(
                rollback_match_id,
                invalid_payload.performances,
            )

        assert (
            await db_session.scalar(
                select(MatchBattingPerformance).where(
                    MatchBattingPerformance.match_id == rollback_match_id
                )
            )
            is None
        )
        assert (
            await db_session.scalar(
                select(MatchFieldingPerformance).where(
                    MatchFieldingPerformance.match_id == rollback_match_id
                )
            )
            is None
        )
    finally:
        await db_session.rollback()
        for model in (
            MatchFieldingPerformance,
            MatchBowlingPerformance,
            MatchBattingPerformance,
            PlayerBowlingStats,
            PlayerBattingStats,
        ):
            await db_session.execute(delete(model).where(model.player_id == player_id))
        await db_session.execute(
            delete(Match).where(Match.id.in_([match_id, rollback_match_id]))
        )
        await db_session.execute(delete(Player).where(Player.id == player_id))
        await db_session.commit()
