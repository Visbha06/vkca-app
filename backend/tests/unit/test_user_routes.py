"""Unit tests for user account API routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.schemas.user import UserResponse
from src.services.user_service import UserAlreadyExistsError


def make_user_response(user_id: UUID | None = None) -> UserResponse:
    """Build a complete user response for route mocks."""

    now = datetime.now(UTC)
    return UserResponse(
        id=user_id or uuid4(),
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        role=UserRole.HEAD_COACH,
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_user = AsyncMock()
    service.list_users = AsyncMock()
    mocker.patch("src.routes.users.UserService", return_value=service)
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
async def test_create_user_returns_account_without_password(
    client, service_mock
) -> None:
    user = make_user_response()
    service_mock.create_user.return_value = user

    result = await client.post(
        "/api/v1/users",
        json={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "hashed_password": "$2b$12$prehashed",
            "role": "head coach",
        },
    )

    assert result.status_code == 201
    assert result.json()["id"] == str(user.id)
    assert "hashed_password" not in result.json()
    service_mock.create_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_users_returns_accounts_without_password(
    client, service_mock
) -> None:
    user = make_user_response()
    service_mock.list_users.return_value = [user]

    result = await client.get("/api/v1/users")

    assert result.status_code == 200
    assert result.json() == [user.model_dump(mode="json")]
    assert "hashed_password" not in result.json()[0]
    service_mock.list_users.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_create_user_returns_conflict_for_duplicate_email(
    client, service_mock
) -> None:
    service_mock.create_user.side_effect = UserAlreadyExistsError(
        "john.doe@example.com"
    )

    result = await client.post(
        "/api/v1/users",
        json={
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "hashed_password": "$2b$12$prehashed",
            "role": "staff",
        },
    )

    assert result.status_code == 409
    assert result.json() == {
        "detail": "A user with email 'john.doe@example.com' already exists."
    }
    service_mock.create_user.assert_awaited_once()
