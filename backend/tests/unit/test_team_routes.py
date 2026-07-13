"""Unit tests for team and roster membership API routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.schemas.team import TeamPlayerResponse, TeamResponse
from src.services.team_service import TeamMembershipAlreadyExistsError


def make_team_response(team_id: UUID | None = None) -> TeamResponse:
    """Build a complete team response for route mocks."""

    now = datetime.now(UTC)
    return TeamResponse(
        id=team_id or uuid4(),
        name="U14 Lions",
        age_group="U14",
        created_at=now,
        updated_at=now,
        version_number=1,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_team = AsyncMock()
    service.list_teams = AsyncMock()
    service.add_player_to_team = AsyncMock()
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
async def test_create_team_returns_created_team(client, service_mock) -> None:
    team = make_team_response()
    service_mock.create_team.return_value = team

    result = await client.post(
        "/api/v1/teams",
        json={"name": "U14 Lions", "age_group": "U14"},
    )

    assert result.status_code == 201
    assert result.json() == team.model_dump(mode="json")
    service_mock.create_team.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_teams_returns_all_teams(client, service_mock) -> None:
    team = make_team_response()
    service_mock.list_teams.return_value = [team]

    result = await client.get("/api/v1/teams")

    assert result.status_code == 200
    assert result.json() == [team.model_dump(mode="json")]
    service_mock.list_teams.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_add_player_to_team_returns_created_membership(
    client, service_mock
) -> None:
    team_id = uuid4()
    player_id = uuid4()
    membership = TeamPlayerResponse(
        team_id=team_id,
        player_id=player_id,
        joined_at=datetime.now(UTC),
    )
    service_mock.add_player_to_team.return_value = membership

    result = await client.post(f"/api/v1/teams/{team_id}/players/{player_id}")

    assert result.status_code == 201
    assert result.json() == membership.model_dump(mode="json")
    service_mock.add_player_to_team.assert_awaited_once_with(team_id, player_id)


@pytest.mark.asyncio
async def test_add_player_to_team_returns_conflict_for_duplicate_membership(
    client, service_mock
) -> None:
    team_id = uuid4()
    player_id = uuid4()
    service_mock.add_player_to_team.side_effect = TeamMembershipAlreadyExistsError()

    result = await client.post(f"/api/v1/teams/{team_id}/players/{player_id}")

    assert result.status_code == 409
    assert result.json() == {"detail": "Player is already a member of this team."}
    service_mock.add_player_to_team.assert_awaited_once_with(team_id, player_id)
