"""Unit tests for login, current-user, and logout API routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user, get_logout_user
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.auth_service import InvalidCredentialsError
from src.services.token_service import TokenService

TEST_JWT_SECRET = "pytest-only-jwt-secret-never-use-in-production"


def make_user(*, is_active: bool = True) -> User:
    """Build a persisted-looking user for route dependency overrides."""

    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        hashed_password="$argon2id$unit-test-only",
        role=UserRole.HEAD_COACH,
        is_active=is_active,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


def make_auth_session(user: User, *, revoked: bool = False) -> AuthSession:
    """Build a persisted-looking authentication session."""

    now = datetime.now(UTC)
    return AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_family_id=uuid4(),
        current_token_hash="a" * 64,
        rotated_token_hashes=[],
        last_used_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=now if revoked else None,
        revocation_reason="logout" if revoked else None,
        ip_address="127.0.0.1",
        user_agent="pytest",
        created_at=now,
        version_number=1,
    )


@pytest.fixture
def db_session() -> AsyncMock:
    session = AsyncMock()
    session.add = Mock()

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return session


@pytest.fixture
def auth_service_mock(mocker):
    service = mocker.Mock()
    service.login = AsyncMock()
    mocker.patch("src.routes.auth.AuthService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client(db_session: AsyncMock):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def invalid_credentials_response() -> InvalidCredentialsError:
    """Return the one service error exposed by every login failure mode."""

    return InvalidCredentialsError()


@pytest.mark.asyncio
async def test_login_success_returns_tokens_and_cookies(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)
    auth_service_mock.login.return_value = (
        user,
        auth_session,
        "signed-access-token",
        "opaque-refresh-token",
        "csrf-value",
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecureP@ssword1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "signed-access-token",
        "token_type": "bearer",
    }
    refresh_cookie = response.headers.get_list("set-cookie")[0]
    csrf_cookie = response.headers.get_list("set-cookie")[1]
    assert "refresh_token=opaque-refresh-token" in refresh_cookie
    assert "HttpOnly" in refresh_cookie
    assert "SameSite=lax" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie
    assert "csrf_token=csrf-value" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in csrf_cookie


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401_generic(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.login.side_effect = invalid_credentials_response()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "known@example.com", "password": "WrongPassword1!"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


@pytest.mark.asyncio
async def test_login_nonexistent_email_returns_401_generic(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.login.side_effect = invalid_credentials_response()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "WrongPassword1!"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


@pytest.mark.asyncio
async def test_login_disabled_user_returns_401_generic(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.login.side_effect = invalid_credentials_response()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "CorrectP@ssword1"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


@pytest.mark.asyncio
async def test_responses_byte_identical_across_failure_modes(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    responses = []
    for email, password in (
        ("known@example.com", "WrongPassword1!"),
        ("missing@example.com", "WrongPassword1!"),
        ("disabled@example.com", "CorrectP@ssword1"),
    ):
        auth_service_mock.login.side_effect = invalid_credentials_response()
        responses.append(
            await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
        )

    assert {response.status_code for response in responses} == {401}
    assert len({response.content for response in responses}) == 1


@pytest.mark.asyncio
async def test_me_returns_profile_with_session(client: httpx.AsyncClient) -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    async def override_get_current_user():
        return user, auth_session

    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer signed-access-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role.value,
        "is_active": True,
        "created_at": user.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": user.updated_at.isoformat().replace("+00:00", "Z"),
        "session": {
            "session_id": str(auth_session.id),
            "created_at": auth_session.created_at.isoformat().replace("+00:00", "Z"),
            "last_used_at": auth_session.last_used_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "expires_at": auth_session.expires_at.isoformat().replace("+00:00", "Z"),
        },
    }


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_me_with_expired_token_returns_401(client: httpx.AsyncClient) -> None:
    token = TokenService(
        jwt_secret=TEST_JWT_SECRET,
        jwt_algorithm="HS256",
        access_token_expire_minutes=-1,
    ).create_access_token(uuid4(), uuid4(), UserRole.STAFF)

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_me_with_malformed_token_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_me_with_wrong_signature_returns_401(client: httpx.AsyncClient) -> None:
    token = TokenService(
        jwt_secret="different-test-secret",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
    ).create_access_token(uuid4(), uuid4(), UserRole.STAFF)

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_logout_revokes_session(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    async def override_get_logout_user():
        return user, auth_session

    app.dependency_overrides[get_logout_user] = override_get_logout_user

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert auth_session.revoked_at is not None
    assert auth_session.revocation_reason == "logout"
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_logout_clears_cookies(client: httpx.AsyncClient) -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    async def override_get_logout_user():
        return user, auth_session

    app.dependency_overrides[get_logout_user] = override_get_logout_user
    client.cookies.set("refresh_token", "opaque-refresh-token", path="/api/v1/auth")
    client.cookies.set("csrf_token", "csrf-value", path="/api/v1/auth")

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    cookie_headers = response.headers.get_list("set-cookie")
    assert any(
        "refresh_token=" in value and "Max-Age=0" in value for value in cookie_headers
    )
    assert any(
        "csrf_token=" in value and "Max-Age=0" in value for value in cookie_headers
    )


@pytest.mark.asyncio
async def test_access_token_rejected_after_logout(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)
    token = TokenService(
        jwt_secret=TEST_JWT_SECRET,
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
    ).create_access_token(user.id, auth_session.id, user.role)

    async def override_get_logout_user():
        return user, auth_session

    app.dependency_overrides[get_logout_user] = override_get_logout_user
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204

    app.dependency_overrides.pop(get_logout_user)
    db_session.scalar.side_effect = [auth_session, user]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
