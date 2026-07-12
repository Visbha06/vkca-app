"""Unit tests for player API routes."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.main import app
from src.models.player import Player
from src.schemas.player import PlayerResponse
from src.services.occ import StaleVersionError


def make_player_response(player_id: UUID | None = None) -> PlayerResponse:
    """Build a complete player response for route mocks."""

    now = datetime.now(UTC)
    return PlayerResponse(
        id=player_id or uuid4(),
        first_name="Sachin",
        last_name="Tendulkar",
        date_of_birth=date(1973, 4, 24),
        bio="Right-handed batter",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_LEG_BREAK,
        player_type=PlayerType.BATTER,
        player_metadata={},
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_player = AsyncMock()
    service.list_players = AsyncMock()
    service.get_player_by_id = AsyncMock()
    service.update_player = AsyncMock()
    mocker.patch("src.routes.players.PlayerService", return_value=service)
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
async def test_create_player_returns_created_profile(client, service_mock) -> None:
    response = make_player_response()
    service_mock.create_player.return_value = response

    result = await client.post(
        "/api/v1/players",
        json={
            "first_name": "Sachin",
            "last_name": "Tendulkar",
            "date_of_birth": "1973-04-24",
            "batting_style": "right",
            "bowling_style": "right-arm leg-break",
            "player_type": "batter",
        },
    )

    assert result.status_code == 201
    assert result.json()["id"] == str(response.id)
    service_mock.create_player.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_players_returns_active_profiles(client, service_mock) -> None:
    player = make_player_response()
    service_mock.list_players.return_value = [player]

    result = await client.get("/api/v1/players")

    assert result.status_code == 200
    assert result.json() == [player.model_dump(mode="json")]
    service_mock.list_players.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_update_player_returns_conflict_for_stale_version(
    client, service_mock
) -> None:
    player_id = uuid4()
    service_mock.update_player.side_effect = StaleVersionError(Player, player_id, 1)

    result = await client.put(
        f"/api/v1/players/{player_id}",
        json={"bio": "Stale update", "version_number": 1},
    )

    assert result.status_code == 409
    assert "Stale version 1" in result.json()["detail"]
    service_mock.update_player.assert_awaited_once()
