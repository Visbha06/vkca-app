"""Unit tests for authenticated user administration routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.user import User
from src.schemas.user import UserCreate
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService, InvalidCredentialsError
from src.services.password_service import PasswordService
from src.services.user_service import UserAlreadyExistsError, UserService


def make_user(
    user_id: UUID | None = None,
    *,
    role: UserRole = UserRole.HEAD_COACH,
    is_active: bool = True,
) -> User:
    """Build a persisted-looking user for route and service tests."""

    now = datetime.now(UTC)
    return User(
        id=user_id or uuid4(),
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


def make_auth_session(user: User) -> AuthSession:
    """Build an active authentication session owned by ``user``."""

    now = datetime.now(UTC)
    return AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_family_id=uuid4(),
        current_token_hash="a" * 64,
        rotated_token_hashes=[],
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
        revocation_reason=None,
        version_number=1,
    )


def user_payload(**overrides: str) -> dict[str, str]:
    """Return a valid user-creation request body."""

    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "Jane.Doe@Example.com",
        "password": "SecureP@ssword1",
        "role": "staff",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def db_session() -> AsyncMock:
    """Provide the database dependency as an isolated async mock."""

    session = AsyncMock()
    session.add = Mock()
    scalar_result = Mock()
    scalar_result.all.return_value = []
    session.scalars.return_value = scalar_result

    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    return session


@pytest.fixture
def head_coach() -> User:
    """Authenticate route requests as a head coach by default."""

    user = make_user()

    async def override_get_current_user():
        return user, make_auth_session(user)

    app.dependency_overrides[get_current_user] = override_get_current_user
    return user


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_user = AsyncMock()
    service.list_users = AsyncMock()
    mocker.patch("src.routes.users.UserService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client(db_session: AsyncMock, head_coach: User):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_user_with_password_hashes_correctly(mocker) -> None:
    session = AsyncMock()
    session.add = Mock()
    session.scalar.return_value = None
    password_hash = "$argon2id$v=19$server-generated"
    hash_password = mocker.patch.object(
        PasswordService,
        "hash_password",
        return_value=password_hash,
    )
    payload = UserCreate.model_validate(user_payload())

    created = await UserService(session).create_user(payload)

    hash_password.assert_called_once_with("SecureP@ssword1")
    assert created.hashed_password == password_hash
    assert created.email == "jane.doe@example.com"
    assert not hasattr(created, "password")
    session.add.assert_called_once_with(created)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_reject_client_hash_input(
    client: httpx.AsyncClient,
    service_mock,
) -> None:
    response = await client.post(
        "/api/v1/users",
        json={**user_payload(), "hashed_password": "$argon2id$client-hash"},
    )

    assert response.status_code == 422
    service_mock.create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_policy_enforced_on_create(
    client: httpx.AsyncClient,
    service_mock,
) -> None:
    response = await client.post(
        "/api/v1/users",
        json=user_payload(password="alllowercase1!"),
    )

    assert response.status_code == 422
    service_mock.create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_head_coach_denied(
    client: httpx.AsyncClient,
    service_mock,
) -> None:
    assistant = make_user(role=UserRole.ASSISTANT_COACH)

    async def override_get_current_user():
        return assistant, make_auth_session(assistant)

    app.dependency_overrides[get_current_user] = override_get_current_user
    response = await client.post("/api/v1/users", json=user_payload())

    assert response.status_code == 403
    service_mock.create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_email_returns_409(
    client: httpx.AsyncClient,
    service_mock,
) -> None:
    service_mock.create_user.side_effect = UserAlreadyExistsError(
        "jane.doe@example.com"
    )

    response = await client.post("/api/v1/users", json=user_payload())

    assert response.status_code == 409
    assert response.json() == {
        "detail": "A user with email 'jane.doe@example.com' already exists."
    }


@pytest.mark.asyncio
async def test_list_users_returns_accounts_without_password(
    client: httpx.AsyncClient,
    service_mock,
) -> None:
    user = make_user()
    service_mock.list_users.return_value = [user]

    response = await client.get("/api/v1/users")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(user.id)
    assert "hashed_password" not in response.json()[0]


@pytest.mark.asyncio
async def test_head_coach_can_change_role(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    target = make_user(role=UserRole.ASSISTANT_COACH)
    db_session.scalar.return_value = target

    response = await client.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "staff"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "staff"
    assert target.role is UserRole.STAFF
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_role_change_audited(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
    mocker,
) -> None:
    target = make_user(role=UserRole.ASSISTANT_COACH)
    db_session.scalar.return_value = target
    log_event = mocker.patch.object(AuditService, "log_event", new_callable=AsyncMock)

    response = await client.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "staff"},
    )

    assert response.status_code == 200
    log_event.assert_awaited_once()
    assert log_event.await_args.args[1] == "role_change"
    assert log_event.await_args.kwargs["user_id"] == target.id


@pytest.mark.asyncio
async def test_assistant_coach_cannot_change_role(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    assistant = make_user(role=UserRole.ASSISTANT_COACH)
    target = make_user(role=UserRole.STAFF)

    async def override_get_current_user():
        return assistant, make_auth_session(assistant)

    app.dependency_overrides[get_current_user] = override_get_current_user
    response = await client.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "head coach"},
    )

    assert response.status_code == 403
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_invalid_role_rejected(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    response = await client.patch(
        f"/api/v1/users/{uuid4()}/role",
        json={"role": "owner"},
    )

    assert response.status_code == 422
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_disable_user_sets_is_active_false(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    target = make_user()
    db_session.scalar.return_value = target
    db_session.scalars.return_value.all.return_value = []

    response = await client.post(f"/api/v1/users/{target.id}/disable")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert target.is_active is False
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
    mocker,
) -> None:
    target = make_user()
    db_session.scalar.return_value = target
    db_session.scalars.return_value.all.return_value = []
    mocker.patch.object(AuditService, "log_event", new_callable=AsyncMock)

    response = await client.post(f"/api/v1/users/{target.id}/disable")
    assert response.status_code == 200

    db_session.reset_mock()
    db_session.scalar.return_value = target
    mocker.patch.object(PasswordService, "verify_password", return_value=True)
    with pytest.raises(InvalidCredentialsError):
        await AuthService(db_session).login(
            target.email,
            "SecureP@ssword1",
            "127.0.0.1",
            "pytest",
        )


@pytest.mark.asyncio
async def test_disabled_user_sessions_revoked(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    target = make_user()
    sessions = [make_auth_session(target), make_auth_session(target)]
    db_session.scalar.return_value = target
    db_session.scalars.return_value.all.return_value = sessions

    response = await client.post(f"/api/v1/users/{target.id}/disable")

    assert response.status_code == 200
    assert all(item.revoked_at is not None for item in sessions)
    assert {item.revocation_reason for item in sessions} == {"user_disabled"}


@pytest.mark.asyncio
async def test_non_head_coach_cannot_disable(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    staff = make_user(role=UserRole.STAFF)

    async def override_get_current_user():
        return staff, make_auth_session(staff)

    app.dependency_overrides[get_current_user] = override_get_current_user
    response = await client.post(f"/api/v1/users/{uuid4()}/disable")

    assert response.status_code == 403
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_head_coach_can_revoke_user_sessions(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    target = make_user()
    sessions = [make_auth_session(target), make_auth_session(target)]
    db_session.scalar.return_value = target
    db_session.scalars.return_value.all.return_value = sessions

    response = await client.post(
        f"/api/v1/users/{target.id}/revoke-sessions",
    )

    assert response.status_code == 204
    assert all(item.revoked_at is not None for item in sessions)
    assert {item.revocation_reason for item in sessions} == {"admin_revocation"}
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_non_head_coach_cannot_revoke_user_sessions(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    assistant = make_user(role=UserRole.ASSISTANT_COACH)

    async def override_get_current_user():
        return assistant, make_auth_session(assistant)

    app.dependency_overrides[get_current_user] = override_get_current_user
    response = await client.post(
        f"/api/v1/users/{uuid4()}/revoke-sessions",
    )

    assert response.status_code == 403
    db_session.scalars.assert_not_awaited()
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_user_can_change_own_password(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
    head_coach: User,
    mocker,
) -> None:
    db_session.scalar.return_value = head_coach
    db_session.scalars.return_value.all.return_value = []
    hash_password = mocker.patch.object(
        PasswordService,
        "hash_password",
        return_value="$argon2id$v=19$new-server-hash",
    )

    response = await client.post(
        f"/api/v1/users/{head_coach.id}/change-password",
        json={"new_password": "EvenM0reSecure!"},
    )

    assert response.status_code == 204
    hash_password.assert_called_once_with("EvenM0reSecure!")
    assert head_coach.hashed_password == "$argon2id$v=19$new-server-hash"


@pytest.mark.asyncio
async def test_non_head_coach_cannot_change_another_users_password(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
) -> None:
    staff = make_user(role=UserRole.STAFF)
    target = make_user()

    async def override_get_current_user():
        return staff, make_auth_session(staff)

    app.dependency_overrides[get_current_user] = override_get_current_user
    db_session.scalar.return_value = target
    response = await client.post(
        f"/api/v1/users/{target.id}/change-password",
        json={"new_password": "EvenM0reSecure!"},
    )

    assert response.status_code == 403
    db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_change_revokes_sessions_and_is_audited(
    client: httpx.AsyncClient,
    db_session: AsyncMock,
    head_coach: User,
    mocker,
) -> None:
    sessions = [make_auth_session(head_coach), make_auth_session(head_coach)]
    db_session.scalar.return_value = head_coach
    db_session.scalars.return_value.all.return_value = sessions
    log_event = mocker.patch.object(AuditService, "log_event", new_callable=AsyncMock)
    mocker.patch.object(
        PasswordService,
        "hash_password",
        return_value="$argon2id$v=19$new-server-hash",
    )

    response = await client.post(
        f"/api/v1/users/{head_coach.id}/change-password",
        json={"new_password": "EvenM0reSecure!"},
    )

    assert response.status_code == 204
    assert all(item.revoked_at is not None for item in sessions)
    assert {item.revocation_reason for item in sessions} == {"password_change"}
    assert any(call.args[1] == "password_change" for call in log_event.await_args_list)
