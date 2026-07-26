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
from src.models.team import Team
from src.schemas.team import (
    PaginatedTeamResponse,
    TeamCreate,
    TeamResponse,
    TeamRosterPlayerResponse,
    TeamRosterResponse,
    TeamUpdate,
)
from src.services.occ import StaleVersionError
from src.services.team_service import (
    TeamNameConflictError,
    TeamNotFoundError,
    TeamValidationError,
)


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
    service.update_team = AsyncMock()
    service.list_teams = AsyncMock()
    service.get_team_roster = AsyncMock()
    mocker.patch("src.routes.teams.TeamService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    session = Mock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()

    async def override_get_db():
        yield session

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


def mutation_payload(*, version_number: int | None = None):
    payload = {
        "name": "Falcons",
        "age_group": "U13",
        "player_ids": [str(uuid4()) for _ in range(7)],
    }
    if version_number is not None:
        payload["version_number"] = version_number
    return payload


@pytest.mark.asyncio
async def test_create_team_returns_created_atomic_team(client, service_mock) -> None:
    response = make_team_response()
    service_mock.create_team.return_value = response
    payload = mutation_payload()

    result = await client.post("/api/v1/teams", json=payload)

    assert result.status_code == 201
    assert result.json() == response.model_dump(mode="json")
    service_mock.create_team.assert_awaited_once()
    submitted = service_mock.create_team.await_args.args[0]
    assert isinstance(submitted, TeamCreate)
    assert submitted.player_ids == [UUID(value) for value in payload["player_ids"]]


@pytest.mark.asyncio
async def test_create_team_rejects_invalid_and_conflicting_requests(
    client, service_mock
) -> None:
    invalid = mutation_payload()
    invalid["player_ids"] = invalid["player_ids"][:6]
    result = await client.post("/api/v1/teams", json=invalid)
    assert result.status_code == 422

    service_mock.create_team.side_effect = TeamValidationError(
        "A roster cannot contain duplicate players."
    )
    duplicate = await client.post("/api/v1/teams", json=mutation_payload())
    assert duplicate.status_code == 400

    service_mock.create_team.side_effect = TeamNameConflictError()
    conflict = await client.post("/api/v1/teams", json=mutation_payload())
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_create_team_rejects_unauthorized_users(
    client, service_mock
) -> None:
    async def override_get_current_user():
        return (
            Mock(id=uuid4(), role=UserRole.PLAYER),
            Mock(id=uuid4()),
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    result = await client.post("/api/v1/teams", json=mutation_payload())

    assert result.status_code == 403
    service_mock.create_team.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_team_returns_the_updated_atomic_team(
    client, service_mock
) -> None:
    team_id = uuid4()
    response = make_team_response(team_id).model_copy(
        update={"name": "Eagles", "version_number": 2}
    )
    service_mock.update_team.return_value = response
    payload = mutation_payload(version_number=1)
    payload["name"] = "Eagles"

    result = await client.put(f"/api/v1/teams/{team_id}", json=payload)

    assert result.status_code == 200
    assert result.json()["version_number"] == 2
    submitted_team_id, submitted = service_mock.update_team.await_args.args
    assert submitted_team_id == team_id
    assert isinstance(submitted, TeamUpdate)
    assert submitted.version_number == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (TeamValidationError("Roster is invalid."), 400),
        (TeamNotFoundError(), 404),
        (TeamNameConflictError(), 409),
    ],
)
async def test_update_team_maps_domain_errors(
    client, service_mock, error, expected_status
) -> None:
    service_mock.update_team.side_effect = error

    result = await client.put(
        f"/api/v1/teams/{uuid4()}",
        json=mutation_payload(version_number=1),
    )

    assert result.status_code == expected_status


@pytest.mark.asyncio
async def test_update_team_returns_conflict_for_stale_versions(
    client, service_mock
) -> None:
    team_id = uuid4()
    service_mock.update_team.side_effect = StaleVersionError(Team, team_id, 1)

    result = await client.put(
        f"/api/v1/teams/{team_id}",
        json=mutation_payload(version_number=1),
    )

    assert result.status_code == 409


@pytest.mark.asyncio
async def test_update_team_rejects_unauthorized_users(
    client, service_mock
) -> None:
    async def override_get_current_user():
        return (
            Mock(id=uuid4(), role=UserRole.PLAYER),
            Mock(id=uuid4()),
        )

    app.dependency_overrides[get_current_user] = override_get_current_user
    result = await client.put(
        f"/api/v1/teams/{uuid4()}",
        json=mutation_payload(version_number=1),
    )

    assert result.status_code == 403
    service_mock.update_team.assert_not_awaited()
