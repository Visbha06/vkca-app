"""Unit coverage for authentication audit events and data integrity."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.enums import UserRole
from src.middleware.auth import require_role
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.user import User
from src.routes.auth import get_audit_log
from src.routes.users import change_user_password, change_user_role, disable_user
from src.schemas.user import UserPasswordChange, UserRoleUpdate
from src.services.audit_service import AuditService
from src.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidSessionError,
    RateLimitExceededError,
)
from src.services.password_service import PasswordService
from src.services.rate_limiter import InMemoryRateLimiter
from src.services.token_service import TokenService


def make_user(*, role: UserRole = UserRole.HEAD_COACH) -> User:
    """Build a persisted-looking user for audit unit tests."""

    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        first_name="Audit",
        last_name="Tester",
        email=f"audit-{uuid4().hex}@example.com",
        hashed_password="$argon2id$unit-test-only",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


def make_auth_session(
    user: User,
    *,
    refresh_token: str = "current-refresh-token",
    rotated_refresh_tokens: tuple[str, ...] = (),
) -> AuthSession:
    """Build an active authentication session for audit unit tests."""

    now = datetime.now(UTC)
    return AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_family_id=uuid4(),
        current_token_hash=TokenService.hash_token(refresh_token),
        rotated_token_hashes=[
            TokenService.hash_token(token) for token in rotated_refresh_tokens
        ],
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
        revocation_reason=None,
        ip_address="127.0.0.1",
        user_agent="pytest",
        version_number=1,
    )


def make_session() -> AsyncMock:
    """Return an async database session with synchronous ORM staging."""

    session = AsyncMock(spec=AsyncSession)
    session.add = Mock()
    scalar_result = Mock()
    scalar_result.all.return_value = []
    session.scalars.return_value = scalar_result
    return session


def make_token_service() -> Mock:
    """Return deterministic token behavior for login and refresh tests."""

    token_service = Mock(spec=TokenService)
    token_service.generate_refresh_token.side_effect = [
        "new-refresh-token",
        "new-csrf-token",
    ]
    token_service.hash_token.side_effect = TokenService.hash_token
    token_service.create_access_token.return_value = "signed-access-token"
    return token_service


def make_request(path: str, *, method: str = "POST") -> Request:
    """Create request metadata used by authorization-denial auditing."""

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"user-agent", b"audit-test-agent")],
            "client": ("203.0.113.10", 54321),
            "server": ("testserver", 80),
        }
    )


@pytest.mark.asyncio
async def test_log_event_creates_record() -> None:
    session = make_session()
    user_id = uuid4()
    auth_session_id = uuid4()

    await AuditService.log_event(
        session,
        "login",
        user_id=user_id,
        session_id=auth_session_id,
        result="success",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/login",
    )

    record = session.add.call_args.args[0]
    assert isinstance(record, AuthAuditLog)
    assert record.event_type == "login"
    assert record.user_id == user_id
    assert record.session_id == auth_session_id
    assert record.result == "success"
    session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_log_event_no_sensitive_fields() -> None:
    session = make_session()

    await AuditService.log_event(
        session,
        "failed_login",
        result="failure",
        reason="invalid_credentials",
    )

    record = session.add.call_args.args[0]
    _assert_columns_absent(
        record,
        {
            "password",
            "hashed_password",
            "access_token",
            "refresh_token",
            "token_hash",
            "jwt_secret",
        },
    )


@pytest.mark.asyncio
async def test_login_success_logged(mocker) -> None:
    session = make_session()
    user = make_user()
    session.scalar.return_value = user
    mocker.patch.object(PasswordService, "verify_password", return_value=True)
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    _, auth_session, *_ = await AuthService(
        session,
        token_service=make_token_service(),
        rate_limiter=InMemoryRateLimiter(),
    ).login(user.email, "SecureP@ssword1", "127.0.0.1", "pytest")

    log_event.assert_awaited_once_with(
        session,
        "login",
        user_id=user.id,
        session_id=auth_session.id,
        result="success",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/login",
    )


@pytest.mark.asyncio
async def test_login_failure_logged(mocker) -> None:
    session = make_session()
    session.scalar.return_value = None
    mocker.patch.object(PasswordService, "verify_password", return_value=False)
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    with pytest.raises(InvalidCredentialsError):
        await AuthService(
            session,
            rate_limiter=InMemoryRateLimiter(),
        ).login(
            "missing@example.com",
            "WrongP@ssword1",
            "127.0.0.1",
            "pytest",
        )

    log_event.assert_awaited_once_with(
        session,
        "failed_login",
        user_id=None,
        result="failure",
        reason="unknown_email",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/login",
    )


@pytest.mark.asyncio
async def test_logout_logged(mocker) -> None:
    session = make_session()
    user = make_user()
    auth_session = make_auth_session(user)
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    await AuthService(session).logout(
        user,
        auth_session,
        "127.0.0.1",
        "pytest",
    )

    log_event.assert_awaited_once_with(
        session,
        "logout",
        user_id=user.id,
        session_id=auth_session.id,
        result="success",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/logout",
    )


@pytest.mark.asyncio
async def test_token_refresh_logged(mocker) -> None:
    session = make_session()
    user = make_user()
    auth_session = make_auth_session(user)
    session.scalar.side_effect = [auth_session, user]
    update_result = Mock()
    update_result.scalar_one_or_none.return_value = 2
    session.execute.return_value = update_result
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    await AuthService(
        session,
        token_service=make_token_service(),
    ).refresh("current-refresh-token", "127.0.0.1", "pytest")

    log_event.assert_awaited_once_with(
        session,
        "token_refresh",
        user_id=user.id,
        session_id=auth_session.id,
        result="success",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/refresh",
    )


@pytest.mark.asyncio
async def test_token_reuse_logged(mocker) -> None:
    session = make_session()
    user = make_user()
    auth_session = make_auth_session(
        user,
        rotated_refresh_tokens=("rotated-refresh-token",),
    )
    session.scalar.return_value = auth_session
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    with pytest.raises(InvalidSessionError):
        await AuthService(session).refresh(
            "rotated-refresh-token",
            "127.0.0.1",
            "pytest",
        )

    log_event.assert_awaited_once_with(
        session,
        "token_reuse",
        user_id=user.id,
        session_id=auth_session.id,
        result="failure",
        reason="rotated_token_reuse",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/refresh",
    )


@pytest.mark.asyncio
async def test_role_change_logged(mocker) -> None:
    session = make_session()
    user = make_user(role=UserRole.ASSISTANT_COACH)
    session.scalar.return_value = user
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    await change_user_role(
        user.id,
        UserRoleUpdate(role=UserRole.PLAYER),
        session,
        None,
    )

    assert any(call.args[1] == "role_change" for call in log_event.await_args_list)


@pytest.mark.asyncio
async def test_user_disable_logged(mocker) -> None:
    session = make_session()
    user = make_user()
    session.scalar.return_value = user
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    await disable_user(user.id, session, None)

    assert any(call.args[1] == "user_disablement" for call in log_event.await_args_list)


@pytest.mark.asyncio
async def test_password_change_logged(mocker) -> None:
    session = make_session()
    user = make_user()
    auth_session = make_auth_session(user)
    session.scalar.return_value = user
    mocker.patch.object(
        PasswordService,
        "hash_password",
        return_value="$argon2id$v=19$new-hash",
    )
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    await change_user_password(
        user.id,
        UserPasswordChange(new_password="ChangedP@ssword2"),
        session,
        (user, auth_session),
    )

    assert any(call.args[1] == "password_change" for call in log_event.await_args_list)


@pytest.mark.asyncio
async def test_rate_limit_logged(mocker) -> None:
    session = make_session()
    limiter = InMemoryRateLimiter()
    key = "rate.limit@example.com:127.0.0.1"
    for _ in range(5):
        limiter.record_failure(key)
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    with pytest.raises(RateLimitExceededError):
        await AuthService(session, rate_limiter=limiter).login(
            "rate.limit@example.com",
            "WrongP@ssword1",
            "127.0.0.1",
            "pytest",
        )

    log_event.assert_awaited_once_with(
        session,
        "rate_limit",
        result="failure",
        reason="rate_limited",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/login",
    )


@pytest.mark.asyncio
async def test_authorization_denial_logged(mocker) -> None:
    session = make_session()
    user = make_user(role=UserRole.PLAYER)
    auth_session = make_auth_session(user)
    log_event = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_role(UserRole.HEAD_COACH)(
            (user, auth_session),
            make_request("/api/v1/users"),
            session,
        )

    assert exc_info.value.status_code == 403
    log_event.assert_awaited_once_with(
        session,
        "authorization_denial",
        user_id=user.id,
        session_id=auth_session.id,
        result="failure",
        reason="insufficient_role",
        ip_address="203.0.113.10",
        user_agent="audit-test-agent",
        target_resource="/api/v1/users",
    )
    session.commit.assert_awaited_once_with()


def test_no_passwords_in_audit() -> None:
    _assert_columns_absent(AuthAuditLog(), {"password", "hashed_password"})


def test_no_token_hashes_in_audit() -> None:
    _assert_columns_absent(
        AuthAuditLog(),
        {"token_hash", "current_token_hash", "rotated_token_hashes"},
    )


def test_no_access_tokens_in_audit() -> None:
    _assert_columns_absent(AuthAuditLog(), {"access_token", "jwt"})


def test_no_refresh_tokens_in_audit() -> None:
    _assert_columns_absent(AuthAuditLog(), {"refresh_token"})


def test_no_signing_secrets_in_audit() -> None:
    _assert_columns_absent(
        AuthAuditLog(),
        {"jwt_secret", "signing_secret", "secret"},
    )


@pytest.mark.asyncio
async def test_all_required_fields_present_when_available() -> None:
    session = make_session()
    user_id = uuid4()
    auth_session_id = uuid4()

    await AuditService.log_event(
        session,
        "authorization_denial",
        user_id=user_id,
        session_id=auth_session_id,
        result="failure",
        reason="insufficient_role",
        ip_address="203.0.113.10",
        user_agent="audit-test-agent",
        target_resource="/api/v1/users",
    )

    record = session.add.call_args.args[0]
    assert record.event_type == "authorization_denial"
    assert record.user_id == user_id
    assert record.session_id == auth_session_id
    assert record.result == "failure"
    assert record.reason == "insufficient_role"
    assert record.ip_address == "203.0.113.10"
    assert record.user_agent == "audit-test-agent"
    assert record.target_resource == "/api/v1/users"
    assert AuthAuditLog.event_timestamp.property.columns[0].server_default is not None


@pytest.mark.asyncio
async def test_audit_log_filters_and_paginates() -> None:
    session = make_session()
    user_id = uuid4()
    start_time = datetime(2026, 7, 1, tzinfo=UTC)
    end_time = datetime(2026, 7, 31, tzinfo=UTC)

    result = await get_audit_log(
        session,
        None,
        event_type="login",
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        limit=25,
        offset=50,
    )

    assert result == []
    statement = session.scalars.await_args.args[0]
    statement_text = str(statement)
    parameters = statement.compile().params
    assert "auth_audit_log.event_type" in statement_text
    assert "auth_audit_log.user_id" in statement_text
    assert "auth_audit_log.event_timestamp >=" in statement_text
    assert "auth_audit_log.event_timestamp <=" in statement_text
    assert "ORDER BY auth_audit_log.event_timestamp DESC" in statement_text
    assert "login" in parameters.values()
    assert user_id in parameters.values()
    assert start_time in parameters.values()
    assert end_time in parameters.values()
    assert 25 in parameters.values()
    assert 50 in parameters.values()


def _assert_columns_absent(
    record: AuthAuditLog,
    sensitive_fields: set[str],
) -> None:
    """Assert the audit persistence model has no credential-bearing columns."""

    field_names = set(record.__table__.columns.keys())
    assert field_names.isdisjoint(sensitive_fields)
