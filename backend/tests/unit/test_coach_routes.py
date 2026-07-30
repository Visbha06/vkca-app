"""Unit tests for coach-directory authorization and responses."""

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
from src.schemas.coach import CoachResponse, PaginatedCoachResponse
from src.services.coach_service import CoachNotFoundError


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
    service.get_coach = AsyncMock()
    service.list_coaches = AsyncMock()
    mocker.patch("src.routes.coaches.CoachService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    session = Mock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()

    async def override_get_db():
        yield session

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
