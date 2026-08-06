"""Unit tests for coach-directory authorization and responses."""

from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.user import User
from src.schemas.coach import CoachResponse, PaginatedCoachResponse
from src.services.coach_service import (
    CoachAlreadyExistsError,
    CoachInactiveError,
    CoachNotFoundError,
    CoachTeamValidationError,
)
from src.services.occ import StaleVersionError
from src.services.user_service import UserNotFoundError


def make_coach(coach_id: UUID | None = None) -> CoachResponse:
    now = datetime.now(UTC)
    return CoachResponse(
        id=coach_id or uuid4(),
        first_name="Vikram",
        last_name="Kumar",
        email="coach@vkca.test",
        role=UserRole.HEAD_COACH,
        is_active=True,
        version_number=1,
        created_at=now,
        updated_at=now,
        teams=[],
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_coach = AsyncMock()
    service.get_coach = AsyncMock()
    service.list_coaches = AsyncMock()
    service.update_team_assignments = AsyncMock()
    mocker.patch("src.routes.coaches.CoachService", return_value=service)
    return service


@pytest.fixture
def db_session():
    session = Mock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return Mock(id=uuid4(), role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_coaches_returns_filtered_paginated_directory(
    client, service_mock
) -> None:
    response = PaginatedCoachResponse(
        coaches=[make_coach()],
        page=2,
        page_size=5,
        total_coaches=6,
        total_pages=2,
        has_previous=True,
        has_next=False,
    )
    service_mock.list_coaches.return_value = response

    result = await client.get("/api/v1/coaches?status=all&page=2&page_size=5")

    assert result.status_code == 200
    assert result.json() == response.model_dump(mode="json")
    service_mock.list_coaches.assert_awaited_once_with(
        status="all", page=2, page_size=5
    )


@pytest.mark.asyncio
async def test_list_coaches_rejects_player_and_invalid_requests(
    client, service_mock
) -> None:
    app.dependency_overrides.pop(get_current_user)
    unauthenticated = await client.get("/api/v1/coaches")
    assert unauthenticated.status_code == 401

    async def player_user():
        return Mock(id=uuid4(), role=UserRole.PLAYER), Mock()

    app.dependency_overrides[get_current_user] = player_user
    forbidden = await client.get("/api/v1/coaches")
    assert forbidden.status_code == 403
    service_mock.list_coaches.assert_not_awaited()

    async def head_coach_user():
        return Mock(id=uuid4(), role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_current_user] = head_coach_user
    invalid = await client.get("/api/v1/coaches?status=bad&page=0")
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_get_coach_allows_any_active_coach_role(client, service_mock) -> None:
    coach = make_coach()
    service_mock.get_coach.return_value = coach

    result = await client.get(f"/api/v1/coaches/{coach.id}")

    assert result.status_code == 200
    assert result.json() == coach.model_dump(mode="json")
    service_mock.get_coach.assert_awaited_once_with(coach.id)


@pytest.mark.asyncio
async def test_get_coach_blocks_assistant_coach_from_inactive_details(
    client, service_mock
) -> None:
    coach = make_coach().model_copy(update={"is_active": False})
    service_mock.get_coach.return_value = coach

    async def assistant_coach_user():
        return Mock(id=uuid4(), role=UserRole.ASSISTANT_COACH), Mock()

    app.dependency_overrides[get_current_user] = assistant_coach_user
    result = await client.get(f"/api/v1/coaches/{coach.id}")

    assert result.status_code == 403


@pytest.mark.asyncio
async def test_get_coach_returns_not_found_for_missing_or_non_coach_user(
    client, service_mock
) -> None:
    coach_id = uuid4()
    service_mock.get_coach.side_effect = CoachNotFoundError()

    result = await client.get(f"/api/v1/coaches/{coach_id}")

    assert result.status_code == 404
    assert result.json() == {"detail": "Coach not found"}


@pytest.mark.asyncio
async def test_create_coach_returns_one_time_password(
    client,
    service_mock,
) -> None:
    coach = make_coach().model_copy(update={"role": UserRole.ASSISTANT_COACH})
    service_mock.create_coach.return_value = (coach, "Aa1!temporary-token")

    result = await client.post(
        "/api/v1/coaches",
        json={
            "first_name": "Asha",
            "last_name": "Patel",
            "email": "asha@vkca.test",
            "team_ids": [],
        },
    )

    assert result.status_code == 201
    assert result.json()["temporary_password"] == "Aa1!temporary-token"
    assert result.json()["role"] == UserRole.ASSISTANT_COACH
    service_mock.create_coach.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_coach_rejects_duplicate_and_missing_fields(
    client,
    service_mock,
) -> None:
    service_mock.create_coach.side_effect = CoachAlreadyExistsError("asha@vkca.test")
    duplicate = await client.post(
        "/api/v1/coaches",
        json={
            "first_name": "Asha",
            "last_name": "Patel",
            "email": "asha@vkca.test",
        },
    )
    missing = await client.post(
        "/api/v1/coaches",
        json={"last_name": "Patel", "email": "asha@vkca.test"},
    )

    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]
    assert missing.status_code == 400
    assert "first_name" in missing.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    [UserRole.ASSISTANT_COACH, UserRole.PLAYER],
)
async def test_create_coach_requires_head_coach(
    client,
    service_mock,
    role: UserRole,
) -> None:
    async def unauthorized_user():
        return Mock(id=uuid4(), role=role), Mock()

    app.dependency_overrides[get_current_user] = unauthorized_user
    result = await client.post(
        "/api/v1/coaches",
        json={
            "first_name": "Asha",
            "last_name": "Patel",
            "email": "asha@vkca.test",
        },
    )

    assert result.status_code == 403
    service_mock.create_coach.assert_not_awaited()


@pytest.mark.asyncio
async def test_disable_user_is_atomic_and_blocks_self_deactivation(
    client,
    db_session,
    mocker,
) -> None:
    target = Mock(
        id=uuid4(),
        first_name="Asha",
        last_name="Patel",
        email="asha@vkca.test",
        role=UserRole.ASSISTANT_COACH,
        is_active=False,
        version_number=5,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user_service = mocker.Mock()
    user_service.disable_user = AsyncMock(
        return_value=target,
    )
    mocker.patch("src.routes.users.UserService", return_value=user_service)

    result = await client.post(
        f"/api/v1/users/{target.id}/disable",
        json={"version_number": 4},
    )

    assert result.status_code == 200
    assert result.json()["is_active"] is False
    user_service.disable_user.assert_awaited_once_with(
        target.id,
        4,
        actor=ANY,
    )

    async def target_as_actor():
        return Mock(id=target.id, role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_current_user] = target_as_actor
    user_service.disable_user.reset_mock()
    self_result = await client.post(
        f"/api/v1/users/{target.id}/disable",
        json={"version_number": 5},
    )
    assert self_result.status_code == 403
    user_service.disable_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_reactivate_user_does_not_restore_sessions(
    client,
    mocker,
) -> None:
    user = Mock(
        id=uuid4(),
        first_name="Asha",
        last_name="Patel",
        email="asha@vkca.test",
        role=UserRole.ASSISTANT_COACH,
        is_active=True,
        version_number=5,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    user_service = mocker.Mock()
    user_service.reactivate_user = AsyncMock(return_value=user)
    mocker.patch("src.routes.users.UserService", return_value=user_service)
    auth_service = mocker.patch("src.routes.users.AuthService")

    result = await client.post(
        f"/api/v1/users/{user.id}/reactivate",
        json={"version_number": 4},
    )

    assert result.status_code == 200
    assert result.json()["is_active"] is True
    user_service.reactivate_user.assert_awaited_once_with(user.id, 4, actor=ANY)
    auth_service.assert_not_called()


@pytest.mark.asyncio
async def test_reactivate_user_handles_permissions_and_missing_user(
    client,
    mocker,
) -> None:
    user_id = uuid4()
    user_service = mocker.Mock()
    user_service.reactivate_user = AsyncMock(side_effect=UserNotFoundError())
    mocker.patch("src.routes.users.UserService", return_value=user_service)

    missing = await client.post(
        f"/api/v1/users/{user_id}/reactivate",
        json={"version_number": 1},
    )
    assert missing.status_code == 404

    async def assistant_coach_user():
        return Mock(id=uuid4(), role=UserRole.ASSISTANT_COACH), Mock()

    app.dependency_overrides[get_current_user] = assistant_coach_user
    forbidden = await client.post(
        f"/api/v1/users/{user_id}/reactivate",
        json={"version_number": 1},
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_update_coach_teams_returns_atomic_replacement(
    client,
    service_mock,
) -> None:
    coach = make_coach().model_copy(update={"version_number": 4})
    team_ids = [uuid4(), uuid4()]
    service_mock.update_team_assignments.return_value = coach

    result = await client.put(
        f"/api/v1/coaches/{coach.id}/teams",
        json={
            "team_ids": [str(team_id) for team_id in team_ids],
            "version_number": 3,
        },
    )

    assert result.status_code == 200
    assert result.json() == coach.model_dump(mode="json")
    payload = service_mock.update_team_assignments.await_args.args[1]
    assert payload.team_ids == team_ids
    assert payload.version_number == 3


@pytest.mark.asyncio
async def test_update_coach_teams_rejects_duplicate_team_ids(
    client,
    service_mock,
) -> None:
    coach_id = uuid4()
    team_id = uuid4()

    result = await client.put(
        f"/api/v1/coaches/{coach_id}/teams",
        json={
            "team_ids": [str(team_id), str(team_id)],
            "version_number": 1,
        },
    )

    assert result.status_code == 400
    assert "duplicates" in result.json()["detail"]
    service_mock.update_team_assignments.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (CoachInactiveError(), 403),
        (CoachTeamValidationError(), 400),
    ],
)
async def test_update_coach_teams_maps_domain_errors(
    client,
    service_mock,
    exception: Exception,
    expected_status: int,
) -> None:
    coach_id = uuid4()
    service_mock.update_team_assignments.side_effect = exception

    result = await client.put(
        f"/api/v1/coaches/{coach_id}/teams",
        json={"team_ids": [str(uuid4())], "version_number": 1},
    )

    assert result.status_code == expected_status


@pytest.mark.asyncio
async def test_update_coach_teams_returns_conflict_for_stale_version(
    client,
    service_mock,
) -> None:
    coach_id = uuid4()
    service_mock.update_team_assignments.side_effect = StaleVersionError(
        User,
        coach_id,
        1,
    )

    result = await client.put(
        f"/api/v1/coaches/{coach_id}/teams",
        json={"team_ids": [], "version_number": 1},
    )

    assert result.status_code == 409
    assert "Stale version" in result.json()["detail"]


@pytest.mark.asyncio
async def test_update_coach_teams_requires_head_coach(
    client,
    service_mock,
) -> None:
    async def assistant_coach_user():
        return Mock(id=uuid4(), role=UserRole.ASSISTANT_COACH), Mock()

    app.dependency_overrides[get_current_user] = assistant_coach_user
    result = await client.put(
        f"/api/v1/coaches/{uuid4()}/teams",
        json={"team_ids": [], "version_number": 1},
    )

    assert result.status_code == 403
    service_mock.update_team_assignments.assert_not_awaited()
