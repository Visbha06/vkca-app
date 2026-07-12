"""Unit tests for the atomic performance submission route."""

from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.main import app
from src.schemas.performance import BatchPerformanceResponse
from src.services.performance_service import MatchNotFoundError


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.submit_batch_performance = AsyncMock()
    mocker.patch("src.routes.performances.PerformanceService", return_value=service)
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
async def test_submit_batch_performance_returns_created_counts(
    client, service_mock
) -> None:
    match_id = uuid4()
    player_id = uuid4()
    response = BatchPerformanceResponse(
        match_id=match_id,
        performances_created=1,
        batting_records=1,
        bowling_records=0,
        fielding_records=1,
        players_stats_updated=1,
    )
    service_mock.submit_batch_performance.return_value = response

    result = await client.post(
        f"/api/v1/matches/{match_id}/performances",
        json={
            "performances": [
                {
                    "player_id": str(player_id),
                    "batting": {"runs_scored": 82},
                    "fielding": {"catches": 2},
                }
            ]
        },
    )

    assert result.status_code == 201
    assert result.json() == response.model_dump(mode="json")
    submitted = service_mock.submit_batch_performance.await_args.args
    assert submitted[0] == match_id
    assert submitted[1][0].player_id == player_id


@pytest.mark.asyncio
async def test_submit_batch_performance_returns_not_found_for_unknown_match(
    client, service_mock
) -> None:
    match_id = uuid4()
    service_mock.submit_batch_performance.side_effect = MatchNotFoundError()

    result = await client.post(
        f"/api/v1/matches/{match_id}/performances",
        json={"performances": [{"player_id": str(uuid4()), "batting": {}}]},
    )

    assert result.status_code == 404
    assert result.json() == {"detail": "Match not found."}


@pytest.mark.asyncio
async def test_submit_batch_performance_rejects_empty_batch(
    client, service_mock
) -> None:
    result = await client.post(
        f"/api/v1/matches/{uuid4()}/performances",
        json={"performances": []},
    )

    assert result.status_code == 422
    service_mock.submit_batch_performance.assert_not_awaited()
