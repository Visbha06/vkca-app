"""Unit tests for player API routes."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import BattingStyle, BowlingStyle, PlayerType, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.player import Player
from src.schemas.player import PaginatedPlayerResponse, PlayerResponse, TeamSummary
from src.services.occ import StaleVersionError
from src.services.player_service import PlayerService


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
        teams=[TeamSummary(id=uuid4(), name="Senior XI")],
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

    async def override_get_current_user():
        return Mock(role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
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
async def test_list_players_returns_default_paginated_profiles(
    client, service_mock
) -> None:
    player = make_player_response()
    response = PaginatedPlayerResponse(
        players=[player],
        page=1,
        page_size=20,
        total_players=1,
        total_pages=1,
        has_previous=False,
        has_next=False,
    )
    service_mock.list_players.return_value = response

    result = await client.get("/api/v1/players")

    assert result.status_code == 200
    assert result.json() == response.model_dump(mode="json")
    service_mock.list_players.assert_awaited_once_with(
        page=1,
        page_size=20,
        team_id=None,
        unassigned=False,
        search=None,
    )


@pytest.mark.asyncio
async def test_list_players_forwards_pagination_and_team_filter(
    client, service_mock
) -> None:
    team_id = uuid4()
    response = PaginatedPlayerResponse(
        players=[],
        page=2,
        page_size=5,
        total_players=6,
        total_pages=2,
        has_previous=True,
        has_next=False,
    )
    service_mock.list_players.return_value = response

    result = await client.get(f"/api/v1/players?page=2&page_size=5&team_id={team_id}")

    assert result.status_code == 200
    assert result.json() == response.model_dump(mode="json")
    service_mock.list_players.assert_awaited_once_with(
        page=2,
        page_size=5,
        team_id=team_id,
        unassigned=False,
        search=None,
    )


@pytest.mark.asyncio
async def test_list_players_forwards_unassigned_filter(client, service_mock) -> None:
    response = PaginatedPlayerResponse(
        players=[],
        page=1,
        page_size=20,
        total_players=0,
        total_pages=0,
        has_previous=False,
        has_next=False,
    )
    service_mock.list_players.return_value = response

    result = await client.get("/api/v1/players?unassigned=true")

    assert result.status_code == 200
    service_mock.list_players.assert_awaited_once_with(
        page=1,
        page_size=20,
        team_id=None,
        unassigned=True,
        search=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("search", ["sach", "  Sachin Tend  ", "", "   "])
async def test_list_players_forwards_optional_search(
    client, service_mock, search: str
) -> None:
    response = PaginatedPlayerResponse(
        players=[],
        page=1,
        page_size=20,
        total_players=0,
        total_pages=0,
        has_previous=False,
        has_next=False,
    )
    service_mock.list_players.return_value = response

    result = await client.get("/api/v1/players", params={"search": search})

    assert result.status_code == 200
    service_mock.list_players.assert_awaited_once_with(
        page=1,
        page_size=20,
        team_id=None,
        unassigned=False,
        search=search,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("search", ["Sachin", "Tendulkar", "Sachin Tendulkar"])
async def test_player_search_matches_first_last_and_full_name(search: str) -> None:
    """Build a search query covering each documented name representation."""

    session = Mock()
    session.scalar = AsyncMock(return_value=0)
    scalar_result = Mock()
    scalar_result.all.return_value = []
    session.scalars = AsyncMock(return_value=scalar_result)

    await PlayerService(session).list_players(search=search)

    statement = session.scalars.await_args.args[0]
    sql = str(statement).lower()
    assert "lower(players.first_name)" in sql
    assert "lower(players.last_name)" in sql
    assert "lower(concat(players.first_name" in sql
    assert f"%{search.lower()}%" in {
        str(value).lower() for value in statement.compile().params.values()
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101"])
async def test_list_players_rejects_invalid_pagination(
    client, service_mock, query: str
) -> None:
    result = await client.get(f"/api/v1/players?{query}")

    assert result.status_code == 422
    service_mock.list_players.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_players_rejects_conflicting_team_filters(
    client, service_mock
) -> None:
    result = await client.get(f"/api/v1/players?team_id={uuid4()}&unassigned=true")

    assert result.status_code == 422
    assert result.json() == {"detail": "team_id and unassigned are mutually exclusive"}
    service_mock.list_players.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_player_returns_profile_with_teams(client, service_mock) -> None:
    player = make_player_response()
    service_mock.get_player_by_id.return_value = player

    result = await client.get(f"/api/v1/players/{player.id}")

    assert result.status_code == 200
    assert result.json() == player.model_dump(mode="json")
    service_mock.get_player_by_id.assert_awaited_once_with(player.id)


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
