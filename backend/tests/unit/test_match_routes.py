"""Unit tests for match API routes."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import MatchFormat
from src.main import app
from src.schemas.match import MatchResponse


def make_match_response(match_id: UUID | None = None) -> MatchResponse:
    """Build a complete match response for route mocks."""

    now = datetime.now(UTC)
    return MatchResponse(
        id=match_id or uuid4(),
        match_date=date(2026, 7, 1),
        format=MatchFormat.T20,
        opponent_name="Challengers CC",
        venue="Main Ground",
        result="Won by 7 wickets",
        created_at=now,
        updated_at=now,
        version_number=1,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_match = AsyncMock()
    service.list_matches = AsyncMock()
    mocker.patch("src.routes.matches.MatchService", return_value=service)
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
async def test_create_match_returns_created_match(client, service_mock) -> None:
    match = make_match_response()
    service_mock.create_match.return_value = match

    result = await client.post(
        "/api/v1/matches",
        json={
            "match_date": "2026-07-01",
            "format": "T20",
            "opponent_name": "Challengers CC",
            "venue": "Main Ground",
            "result": "Won by 7 wickets",
        },
    )

    assert result.status_code == 201
    assert result.json() == match.model_dump(mode="json")
    service_mock.create_match.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_matches_returns_all_matches(client, service_mock) -> None:
    match = make_match_response()
    service_mock.list_matches.return_value = [match]

    result = await client.get("/api/v1/matches")

    assert result.status_code == 200
    assert result.json() == [match.model_dump(mode="json")]
    service_mock.list_matches.assert_awaited_once_with()
