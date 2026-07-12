"""HTTP routes for read-only player career statistics."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import MatchFormat
from src.schemas.stats import BattingStatsResponse, BowlingStatsResponse
from src.services.stats_service import StatsService

router = APIRouter(prefix="/players", tags=["stats"])


@router.get("/{player_id}/stats/batting", response_model=list[BattingStatsResponse])
async def get_batting_stats(
    player_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    match_format: Annotated[MatchFormat | None, Query(alias="format")] = None,
) -> list[BattingStatsResponse]:
    """Return a player's batting totals, optionally for one format."""

    rows = await StatsService(session).get_batting_stats(player_id, match_format)
    return [BattingStatsResponse.model_validate(row) for row in rows]


@router.get("/{player_id}/stats/bowling", response_model=list[BowlingStatsResponse])
async def get_bowling_stats(
    player_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    match_format: Annotated[MatchFormat | None, Query(alias="format")] = None,
) -> list[BowlingStatsResponse]:
    """Return a player's bowling totals, optionally for one format."""

    rows = await StatsService(session).get_bowling_stats(player_id, match_format)
    return [BowlingStatsResponse.model_validate(row) for row in rows]
