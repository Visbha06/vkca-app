"""Unit tests for team list and roster API routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import AgeGroup, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.schemas.team import (
    PaginatedTeamResponse,
    TeamResponse,
    TeamRosterPlayerResponse,
    TeamRosterResponse,
)
from src.services.team_service import TeamNotFoundError


def make_team_response(team_id: UUID | None = None) -> TeamResponse:
    now = datetime.now(UTC)
    return TeamResponse(
        id=team_id or uuid4(),
        name="U13 Lions",
        age_group=AgeGroup.U13,
        player_count=8,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_team = AsyncMock()
    service.list_teams = AsyncMock()
    service.get_team_roster = AsyncMock()
    mocker.patch("src.routes.teams.TeamService", return_value=service)
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
async def test_list_teams_returns_a_paginated_response(client, service_mock) -> None:
    team = make_team_response()
    response = PaginatedTeamResponse(
        teams=[team], page=2, page_size=12, total_teams=13, total_pages=2
    )
    service_mock.list_teams.return_value = response

    result = await client.get("/api/v1/teams?page=2&page_size=12")

    assert result.status_code == 200
    assert result.json() == response.model_dump(mode="json")
    service_mock.list_teams.assert_awaited_once_with(page=2, page_size=12)


@pytest.mark.asyncio
async def test_list_teams_rejects_unauthenticated_and_invalid_requests(client) -> None:
    app.dependency_overrides.pop(get_current_user)
    unauthenticated = await client.get("/api/v1/teams")
    assert unauthenticated.status_code == 401

    async def override_get_current_user():
        return Mock(role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_current_user] = override_get_current_user
    invalid = await client.get("/api/v1/teams?page=0")
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_get_team_roster_returns_ordered_players(client, service_mock) -> None:
    team_id = uuid4()
    roster = TeamRosterResponse(
        team_id=team_id,
        players=[
            TeamRosterPlayerResponse(
                player_id=uuid4(),
                first_name="Asha",
                last_name="Singh",
                is_active=True,
                roster_order=1,
            )
        ],
    )
    service_mock.get_team_roster.return_value = roster

    result = await client.get(f"/api/v1/teams/{team_id}/players")

    assert result.status_code == 200
    assert result.json() == roster.model_dump(mode="json")
    service_mock.get_team_roster.assert_awaited_once_with(team_id)


@pytest.mark.asyncio
async def test_get_team_roster_returns_not_found(client, service_mock) -> None:
    team_id = uuid4()
    service_mock.get_team_roster.side_effect = TeamNotFoundError()

    result = await client.get(f"/api/v1/teams/{team_id}/players")

    assert result.status_code == 404
    assert result.json() == {"detail": "Team not found."}
