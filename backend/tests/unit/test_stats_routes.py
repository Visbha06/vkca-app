"""Unit tests for player career statistics routes."""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import MatchFormat
from src.main import app
from src.schemas.stats import BattingStatsResponse, BowlingStatsResponse


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.get_batting_stats = AsyncMock()
    service.get_bowling_stats = AsyncMock()
    mocker.patch("src.routes.stats.StatsService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_batting_stats_passes_optional_format(client, service_mock) -> None:
    player_id = uuid4()
    stats = BattingStatsResponse(
        format=MatchFormat.T20,
        matches=1,
        innings=1,
        not_outs=1,
        runs=82,
        balls_faced=55,
        high_score=82,
        hundreds=0,
        fifties=1,
        ducks=0,
        fours=9,
        sixes=3,
    )
    service_mock.get_batting_stats.return_value = [stats]

    result = await client.get(f"/api/v1/players/{player_id}/stats/batting?format=T20")

    assert result.status_code == 200
    assert result.json() == [stats.model_dump(mode="json")]
    service_mock.get_batting_stats.assert_awaited_once_with(player_id, MatchFormat.T20)


@pytest.mark.asyncio
async def test_get_bowling_stats_returns_all_formats(client, service_mock) -> None:
    player_id = uuid4()
    stats = BowlingStatsResponse(
        format=MatchFormat.ONE_DAY,
        matches=1,
        innings=1,
        overs_bowled=Decimal("4.0"),
        runs_conceded=22,
        wickets=3,
        best_bowled="3/22",
        maidens=1,
        four_wicket_hauls=0,
        five_wicket_hauls=0,
        wides=1,
        catches=2,
    )
    service_mock.get_bowling_stats.return_value = [stats]

    result = await client.get(f"/api/v1/players/{player_id}/stats/bowling")

    assert result.status_code == 200
    assert result.json() == [stats.model_dump(mode="json")]
    service_mock.get_bowling_stats.assert_awaited_once_with(player_id, None)


@pytest.mark.asyncio
async def test_get_stats_returns_empty_array_when_no_data(client, service_mock) -> None:
    service_mock.get_batting_stats.return_value = []

    result = await client.get(f"/api/v1/players/{uuid4()}/stats/batting")

    assert result.status_code == 200
    assert result.json() == []
