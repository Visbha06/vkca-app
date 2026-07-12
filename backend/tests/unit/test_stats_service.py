"""Unit tests for read-only aggregate statistics queries."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import MatchFormat
from src.models.player_batting_stats import PlayerBattingStats
from src.services.stats_service import StatsService


@pytest.mark.asyncio
async def test_get_batting_stats_returns_scalar_rows() -> None:
    player_id = uuid4()
    row = PlayerBattingStats(player_id=player_id, format=MatchFormat.T20)
    scalar_result = Mock()
    scalar_result.all.return_value = [row]
    session = AsyncMock()
    session.scalars.return_value = scalar_result

    result = await StatsService(session).get_batting_stats(player_id, MatchFormat.T20)

    assert result == [row]
    session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_bowling_stats_returns_empty_list_when_no_rows() -> None:
    scalar_result = Mock()
    scalar_result.all.return_value = []
    session = AsyncMock()
    session.scalars.return_value = scalar_result

    result = await StatsService(session).get_bowling_stats(uuid4())

    assert result == []
    session.scalars.assert_awaited_once()
