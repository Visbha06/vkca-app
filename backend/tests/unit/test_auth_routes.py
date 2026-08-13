"""Unit tests for login, current-user, and logout API routes."""

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException, Request

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user, get_logout_user, require_role
from src.models.auth_session import AuthSession
from src.models.user import User
from src.schemas.player import PaginatedPlayerResponse
from src.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidSessionError,
)
from src.services.token_service import TokenService

TEST_JWT_SECRET = "pytest-only-jwt-secret-never-use-in-production"
CURRENT_REFRESH_TOKEN = "current-refresh-token"
ROTATED_REFRESH_TOKEN = "rotated-refresh-token"
CSRF_TOKEN = "csrf-value"


def make_user(
    *,
    is_active: bool = True,
    role: UserRole = UserRole.HEAD_COACH,
) -> User:
    """Build a persisted-looking user for route dependency overrides."""

    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        hashed_password="$argon2id$unit-test-only",
        role=role,
        is_active=is_active,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


def make_auth_session(
    user: User,
    *,
    refresh_token: str = CURRENT_REFRESH_TOKEN,
    rotated_refresh_tokens: tuple[str, ...] = (),
    last_used_at: datetime | None = None,
    expires_at: datetime | None = None,
    revoked: bool = False,
) -> AuthSession:
    """Build a persisted-looking authentication session."""

    now = datetime.now(UTC)
    return AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_family_id=uuid4(),
        current_token_hash=TokenService.hash_token(refresh_token),
        rotated_token_hashes=[
            TokenService.hash_token(token) for token in rotated_refresh_tokens
        ],
        last_used_at=last_used_at or now,
        expires_at=expires_at or now + timedelta(days=30),
        revoked_at=now if revoked else None,
        revocation_reason="logout" if revoked else None,
        ip_address="127.0.0.1",
        user_agent="pytest",
        created_at=now,
        version_number=1,
    )


def set_auth_cookies(
    client: httpx.AsyncClient,
    *,
    refresh_token: str = CURRENT_REFRESH_TOKEN,
    csrf_token: str = CSRF_TOKEN,
) -> None:
    """Set the double-submit cookies sent by cookie-authenticated endpoints."""

    client.cookies.set("refresh_token", refresh_token, path="/api/v1/auth")
    client.cookies.set("csrf_token", csrf_token, path="/")


def csrf_headers(csrf_token: str = CSRF_TOKEN) -> dict[str, str]:
    """Return a matching CSRF request header."""

    return {"X-CSRF-Token": csrf_token}


def role_dependency_context() -> tuple[Request, AsyncMock]:
    """Return request and database collaborators for direct RBAC checks."""

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/test-resource",
            "raw_path": b"/api/v1/test-resource",
            "query_string": b"",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )
    session = AsyncMock()
    session.add = Mock()
    return request, session


def make_token_service(
    *,
    refresh_tokens: tuple[str, ...],
    access_tokens: tuple[str, ...],
) -> Mock:
    """Build a deterministic TokenService mock for rotation state tests."""

    service = Mock(spec=TokenService)
    service.hash_token.side_effect = TokenService.hash_token
    service.generate_refresh_token.side_effect = list(refresh_tokens)
    service.create_access_token.side_effect = list(access_tokens)
    return service


def occ_result(version_number: int) -> Mock:
    """Return a SQLAlchemy-looking result for a successful OCC update."""

    result = Mock()
    result.scalar_one_or_none.return_value = version_number
    return result


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
    service.refresh = AsyncMock()
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
    assert SimpleCookie(csrf_cookie)["csrf_token"]["path"] == "/"


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
async def test_login_linked_inactive_player_returns_the_same_generic_401(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.login.side_effect = invalid_credentials_response()

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "inactive.player@example.com",
            "password": "CorrectP@ssword1",
        },
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
async def test_patch_me_updates_profile(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    async def override_get_current_user():
        return user, auth_session

    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer signed-access-token"},
        json={"first_name": "Jane", "last_name": "Smith"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "first_name": "Jane",
        "last_name": "Smith",
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
    assert user.first_name == "Jane"
    assert user.last_name == "Smith"
    assert user.version_number == 2
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_patch_me_without_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/auth/me",
        json={"first_name": "Jane", "last_name": "Smith"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"first_name": "", "last_name": "Smith"},
        {"first_name": "Jane", "last_name": ""},
        {"last_name": "Smith"},
        {"first_name": "Jane"},
    ],
)
async def test_patch_me_rejects_invalid_profile(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
    payload: dict[str, str],
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    async def override_get_current_user():
        return user, auth_session

    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer signed-access-token"},
        json=payload,
    )

    assert response.status_code == 422
    db_session.commit.assert_not_awaited()


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
    ).create_access_token(uuid4(), uuid4(), UserRole.PLAYER)

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
    ).create_access_token(uuid4(), uuid4(), UserRole.PLAYER)

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
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/logout",
        headers=csrf_headers(),
    )

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
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/logout",
        headers=csrf_headers(),
    )

    assert response.status_code == 204
    cookie_headers = response.headers.get_list("set-cookie")
    refresh_cookie = next(
        value for value in cookie_headers if value.startswith("refresh_token=")
    )
    csrf_cookie = next(
        value for value in cookie_headers if value.startswith("csrf_token=")
    )
    assert "Max-Age=0" in refresh_cookie
    assert SimpleCookie(refresh_cookie)["refresh_token"]["path"] == "/api/v1/auth"
    assert "HttpOnly" in refresh_cookie
    assert "Max-Age=0" in csrf_cookie
    assert SimpleCookie(csrf_cookie)["csrf_token"]["path"] == "/"
    assert "HttpOnly" not in csrf_cookie


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
    set_auth_cookies(client)
    logout = await client.post(
        "/api/v1/auth/logout",
        headers=csrf_headers(),
    )
    assert logout.status_code == 204

    app.dependency_overrides.pop(get_logout_user)
    db_session.scalar.side_effect = [auth_session, user, None]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.refresh.return_value = (
        "new-access-token",
        "new-refresh-token",
        "new-csrf-token",
    )
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "new-access-token",
        "token_type": "bearer",
    }
    auth_service_mock.refresh.assert_awaited_once()
    assert auth_service_mock.refresh.await_args.args[0] == CURRENT_REFRESH_TOKEN


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.refresh.return_value = (
        "new-access-token",
        "new-refresh-token",
        "new-csrf-token",
    )
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    cookie_headers = response.headers.get_list("set-cookie")
    refresh_cookie = next(
        value for value in cookie_headers if value.startswith("refresh_token=")
    )
    assert "refresh_token=new-refresh-token" in refresh_cookie
    assert CURRENT_REFRESH_TOKEN not in refresh_cookie
    assert "HttpOnly" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie


@pytest.mark.asyncio
async def test_refresh_rotates_csrf_token(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    auth_service_mock.refresh.return_value = (
        "new-access-token",
        "new-refresh-token",
        "new-csrf-token",
    )
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    cookie_headers = response.headers.get_list("set-cookie")
    csrf_cookie = next(
        value for value in cookie_headers if value.startswith("csrf_token=")
    )
    assert "csrf_token=new-csrf-token" in csrf_cookie
    assert CSRF_TOKEN not in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert SimpleCookie(csrf_cookie)["csrf_token"]["path"] == "/"


@pytest.mark.asyncio
async def test_refresh_updates_last_used_at(
    db_session: AsyncMock,
    mocker,
) -> None:
    user = make_user()
    previous_last_used_at = datetime.now(UTC) - timedelta(hours=1)
    auth_session = make_auth_session(
        user,
        last_used_at=previous_last_used_at,
    )
    db_session.scalar.side_effect = [auth_session, user]
    db_session.execute.return_value = occ_result(2)
    token_service = make_token_service(
        refresh_tokens=("new-refresh-token", "new-csrf-token"),
        access_tokens=("new-access-token",),
    )
    audit_log = AsyncMock()
    mocker.patch(
        "src.services.auth_service.AuditService.log_event",
        new=audit_log,
    )

    await AuthService(db_session, token_service=token_service).refresh(
        CURRENT_REFRESH_TOKEN,
        "127.0.0.1",
        "pytest",
    )

    assert auth_session.last_used_at > previous_last_used_at
    assert auth_session.version_number == 2
    rotation_statement = db_session.execute.await_args.args[0]
    rotation_sql = str(rotation_statement)
    assert "auth_sessions.revoked_at IS NULL" in rotation_sql
    assert "auth_sessions.expires_at >" in rotation_sql
    assert "auth_sessions.last_used_at >" in rotation_sql
    audit_log.assert_awaited_once_with(
        db_session,
        "token_refresh",
        user_id=user.id,
        session_id=auth_session.id,
        result="success",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/refresh",
    )
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_refresh_rejects_expired_session_inactivity(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(
        user,
        last_used_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.scalar.return_value = auth_session
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session"}
    db_session.execute.assert_not_awaited()
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_rejects_expired_session_absolute(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(
        user,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db_session.scalar.return_value = auth_session
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session"}
    db_session.execute.assert_not_awaited()
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_rejects_revoked_session(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user, revoked=True)
    db_session.scalar.return_value = auth_session
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session"}
    db_session.execute.assert_not_awaited()
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_rejects_disabled_user(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user(is_active=False)
    auth_session = make_auth_session(user)
    db_session.scalar.side_effect = [auth_session, user]
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session"}
    db_session.execute.assert_not_awaited()
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reuse_rotated_token_revokes_family(db_session: AsyncMock) -> None:
    user = make_user()
    auth_session = make_auth_session(
        user,
        rotated_refresh_tokens=(ROTATED_REFRESH_TOKEN,),
    )
    db_session.scalar.return_value = auth_session

    with pytest.raises(InvalidSessionError):
        await AuthService(db_session).refresh(
            ROTATED_REFRESH_TOKEN,
            "127.0.0.1",
            "pytest",
        )

    statement = db_session.execute.await_args.args[0]
    statement_text = str(statement)
    statement_parameters = statement.compile().params
    assert "auth_sessions.token_family_id" in statement_text
    assert auth_session.token_family_id in statement_parameters.values()
    assert auth_session.revoked_at is not None
    assert auth_session.revocation_reason == "token_reuse"
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_reuse_returns_401(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(
        user,
        rotated_refresh_tokens=(ROTATED_REFRESH_TOKEN,),
    )
    db_session.scalar.return_value = auth_session
    set_auth_cookies(client, refresh_token=ROTATED_REFRESH_TOKEN)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session"}
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_reuse_logs_audit_event(
    db_session: AsyncMock,
    mocker,
) -> None:
    user = make_user()
    auth_session = make_auth_session(
        user,
        rotated_refresh_tokens=(ROTATED_REFRESH_TOKEN,),
    )
    db_session.scalar.return_value = auth_session
    audit_log = AsyncMock()
    mocker.patch(
        "src.services.auth_service.AuditService.log_event",
        new=audit_log,
    )

    with pytest.raises(InvalidSessionError):
        await AuthService(db_session).refresh(
            ROTATED_REFRESH_TOKEN,
            "203.0.113.10",
            "reuse-test-agent",
        )

    audit_log.assert_awaited_once_with(
        db_session,
        "token_reuse",
        user_id=user.id,
        session_id=auth_session.id,
        result="failure",
        reason="rotated_token_reuse",
        ip_address="203.0.113.10",
        user_agent="reuse-test-agent",
        target_resource="/api/v1/auth/refresh",
    )
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_valid_token_still_works_after_rotation(
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)
    db_session.scalar.side_effect = [auth_session, user, auth_session, user]
    db_session.execute.side_effect = [occ_result(2), occ_result(3)]
    token_service = make_token_service(
        refresh_tokens=(
            "first-new-refresh-token",
            "first-new-csrf-token",
            "second-new-refresh-token",
            "second-new-csrf-token",
        ),
        access_tokens=("first-access-token", "second-access-token"),
    )
    service = AuthService(db_session, token_service=token_service)

    first_result = await service.refresh(
        CURRENT_REFRESH_TOKEN,
        "127.0.0.1",
        "pytest",
    )
    second_result = await service.refresh(
        "first-new-refresh-token",
        "127.0.0.1",
        "pytest",
    )

    assert first_result == (
        "first-access-token",
        "first-new-refresh-token",
        "first-new-csrf-token",
    )
    assert second_result == (
        "second-access-token",
        "second-new-refresh-token",
        "second-new-csrf-token",
    )
    assert auth_session.current_token_hash == TokenService.hash_token(
        "second-new-refresh-token"
    )
    assert auth_session.rotated_token_hashes == [
        TokenService.hash_token(CURRENT_REFRESH_TOKEN),
        TokenService.hash_token("first-new-refresh-token"),
    ]
    assert auth_session.version_number == 3
    assert db_session.commit.await_count == 2


@pytest.mark.asyncio
async def test_refresh_without_csrf_header_returns_403(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    set_auth_cookies(client)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token missing or invalid"}
    auth_service_mock.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_with_mismatched_csrf_returns_403(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    set_auth_cookies(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        headers=csrf_headers("different-csrf-value"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token missing or invalid"}
    auth_service_mock.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_without_csrf_header_returns_403(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    async def override_get_logout_user():
        return user, auth_session

    app.dependency_overrides[get_logout_user] = override_get_logout_user
    set_auth_cookies(client)

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token missing or invalid"}
    assert auth_session.revoked_at is None
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_csrf_token_set_on_login(
    client: httpx.AsyncClient,
    auth_service_mock,
) -> None:
    user = make_user()
    auth_session = make_auth_session(user)
    auth_service_mock.login.return_value = (
        user,
        auth_session,
        "signed-access-token",
        CURRENT_REFRESH_TOKEN,
        CSRF_TOKEN,
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecureP@ssword1"},
    )

    assert response.status_code == 200
    csrf_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("csrf_token=")
    )
    assert f"csrf_token={CSRF_TOKEN}" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in csrf_cookie
    assert SimpleCookie(csrf_cookie)["csrf_token"]["path"] == "/"


@pytest.mark.asyncio
async def test_head_coach_access_to_admin_operations() -> None:
    user = make_user(role=UserRole.HEAD_COACH)
    auth_session = make_auth_session(user)

    result = await require_role(UserRole.HEAD_COACH)(
        (user, auth_session),
        *role_dependency_context(),
    )

    assert result is None


@pytest.mark.asyncio
async def test_assistant_coach_denied_admin_operations() -> None:
    user = make_user(role=UserRole.ASSISTANT_COACH)
    auth_session = make_auth_session(user)

    with pytest.raises(HTTPException) as exc_info:
        await require_role(UserRole.HEAD_COACH)(
            (user, auth_session),
            *role_dependency_context(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_player_read_only_enforcement() -> None:
    user = make_user(role=UserRole.PLAYER)
    auth_session = make_auth_session(user)

    read_result = await require_role(
        UserRole.HEAD_COACH,
        UserRole.ASSISTANT_COACH,
        UserRole.PLAYER,
    )((user, auth_session), *role_dependency_context())
    with pytest.raises(HTTPException) as exc_info:
        await require_role(
            UserRole.HEAD_COACH,
            UserRole.ASSISTANT_COACH,
        )((user, auth_session), *role_dependency_context())

    assert read_result is None
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_default_deny_no_rule() -> None:
    user = make_user()
    auth_session = make_auth_session(user)

    with pytest.raises(HTTPException) as exc_info:
        await require_role()((user, auth_session), *role_dependency_context())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Not authorized"


@pytest.mark.asyncio
async def test_role_from_jwt_not_trusted(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    user = make_user(role=UserRole.PLAYER)
    auth_session = make_auth_session(user)
    token = TokenService().create_access_token(
        user.id,
        auth_session.id,
        UserRole.HEAD_COACH,
    )
    db_session.scalar.side_effect = [auth_session, user, None]

    response = await client.post(
        "/api/v1/players",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}


@pytest.mark.asyncio
async def test_role_change_takes_effect_next_request() -> None:
    user = make_user(role=UserRole.PLAYER)
    auth_session = make_auth_session(user)
    cricket_data_access = require_role(
        UserRole.HEAD_COACH,
        UserRole.ASSISTANT_COACH,
    )

    with pytest.raises(HTTPException) as exc_info:
        await cricket_data_access(
            (user, auth_session),
            *role_dependency_context(),
        )
    user.role = UserRole.ASSISTANT_COACH
    result = await cricket_data_access(
        (user, auth_session),
        *role_dependency_context(),
    )

    assert exc_info.value.status_code == 403
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(UserRole))
async def test_players_get_all_roles(
    client: httpx.AsyncClient,
    mocker,
    role: UserRole,
) -> None:
    user = make_user(role=role)
    auth_session = make_auth_session(user)

    async def override_get_current_user():
        return user, auth_session

    service = mocker.Mock()
    empty_page = PaginatedPlayerResponse(
        players=[],
        page=1,
        page_size=20,
        total_players=0,
        total_pages=0,
        has_previous=False,
        has_next=False,
    )
    service.list_players = AsyncMock(return_value=empty_page)
    mocker.patch("src.routes.players.PlayerService", return_value=service)
    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.get("/api/v1/players")

    assert response.status_code == 200
    assert response.json() == empty_page.model_dump(mode="json")


@pytest.mark.asyncio
async def test_players_post_player_denied(client: httpx.AsyncClient) -> None:
    await _assert_player_write_denied(client, "/api/v1/players", json={})


@pytest.mark.asyncio
async def test_teams_post_player_denied(client: httpx.AsyncClient) -> None:
    await _assert_player_write_denied(client, "/api/v1/teams", json={})


@pytest.mark.asyncio
async def test_matches_post_player_denied(client: httpx.AsyncClient) -> None:
    await _assert_player_write_denied(client, "/api/v1/matches", json={})


@pytest.mark.asyncio
async def test_performances_post_player_denied(client: httpx.AsyncClient) -> None:
    await _assert_player_write_denied(
        client,
        f"/api/v1/matches/{uuid4()}/performances",
        json={"performances": []},
    )


async def _assert_player_write_denied(
    client: httpx.AsyncClient,
    path: str,
    **request_kwargs,
) -> None:
    user = make_user(role=UserRole.PLAYER)
    auth_session = make_auth_session(user)

    async def override_get_current_user():
        return user, auth_session

    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.post(path, **request_kwargs)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(UserRole))
async def test_stats_get_all_roles(
    client: httpx.AsyncClient,
    mocker,
    role: UserRole,
) -> None:
    user = make_user(role=role)
    auth_session = make_auth_session(user)

    async def override_get_current_user():
        return user, auth_session

    service = mocker.Mock()
    service.get_batting_stats = AsyncMock(return_value=[])
    mocker.patch("src.routes.stats.StatsService", return_value=service)
    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.get(f"/api/v1/players/{uuid4()}/stats/batting")

    assert response.status_code == 200
    assert response.json() == []
