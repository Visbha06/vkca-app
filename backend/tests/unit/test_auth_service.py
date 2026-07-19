"""Unit tests for security-event session revocation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from src.enums import UserRole
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService, InvalidSessionError
from src.services.token_service import TokenService


def make_user(user_id: UUID | None = None) -> User:
    """Build a persisted-looking user for isolated service tests."""

    now = datetime.now(UTC)
    return User(
        id=user_id or uuid4(),
        first_name="Session",
        last_name="Owner",
        email="session.owner@example.com",
        hashed_password="$argon2id$unit-test-only",
        role=UserRole.PLAYER,
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


def make_auth_session(
    user: User,
    *,
    current_token_hash: str | None = None,
    revoked: bool = False,
) -> AuthSession:
    """Build one independently revocable session owned by ``user``."""

    now = datetime.now(UTC)
    return AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_family_id=uuid4(),
        current_token_hash=current_token_hash or uuid4().hex * 2,
        rotated_token_hashes=[],
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=now if revoked else None,
        revocation_reason="logout" if revoked else None,
        version_number=1,
    )


@pytest.fixture
def db_session() -> AsyncMock:
    """Provide a database session mock with a synchronous ``add`` method."""

    session = AsyncMock()
    session.add = Mock()
    scalar_result = Mock()
    scalar_result.all.return_value = []
    session.scalars.return_value = scalar_result
    return session


@pytest.mark.asyncio
async def test_logout_revokes_only_current_session(
    db_session: AsyncMock,
    mocker,
) -> None:
    user = make_user()
    current_session = make_auth_session(user)
    other_session = make_auth_session(user)
    audit_log = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    await AuthService(db_session).logout(
        user,
        current_session,
        "127.0.0.1",
        "pytest",
    )

    assert current_session.revoked_at is not None
    assert current_session.revocation_reason == "logout"
    assert current_session.version_number == 2
    assert other_session.revoked_at is None
    audit_log.assert_awaited_once_with(
        db_session,
        "logout",
        user_id=user.id,
        session_id=current_session.id,
        result="success",
        ip_address="127.0.0.1",
        user_agent="pytest",
        target_resource="/api/v1/auth/logout",
    )
    db_session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_multiple_sessions_independent(
    db_session: AsyncMock,
    mocker,
) -> None:
    user = make_user()
    sessions = [make_auth_session(user) for _ in range(3)]
    mocker.patch.object(AuditService, "log_event", new_callable=AsyncMock)

    await AuthService(db_session).logout(
        user,
        sessions[1],
        None,
        None,
    )

    assert sessions[0].revoked_at is None
    assert sessions[1].revoked_at is not None
    assert sessions[2].revoked_at is None
    db_session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_change_revokes_all_sessions(
    db_session: AsyncMock,
    mocker,
) -> None:
    user = make_user()
    sessions = [make_auth_session(user), make_auth_session(user)]
    db_session.scalars.return_value.all.return_value = sessions
    audit_log = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    revoked = await AuthService(db_session).revoke_user_sessions(
        user.id,
        reason="password_change",
        target_resource=f"/api/v1/users/{user.id}/change-password",
    )

    assert revoked == sessions
    assert all(auth_session.revoked_at is not None for auth_session in sessions)
    assert {item.revocation_reason for item in sessions} == {"password_change"}
    assert {item.version_number for item in sessions} == {2}
    assert audit_log.await_count == 2


@pytest.mark.asyncio
async def test_user_disable_revokes_all_sessions(
    db_session: AsyncMock,
    mocker,
) -> None:
    user = make_user()
    sessions = [make_auth_session(user), make_auth_session(user)]
    db_session.scalars.return_value.all.return_value = sessions
    audit_log = mocker.patch.object(
        AuditService,
        "log_event",
        new_callable=AsyncMock,
    )

    revoked = await AuthService(db_session).revoke_user_sessions(
        user.id,
        reason="user_disabled",
        target_resource=f"/api/v1/users/{user.id}/disable",
    )

    assert revoked == sessions
    assert all(auth_session.revoked_at is not None for auth_session in sessions)
    assert {item.revocation_reason for item in sessions} == {"user_disabled"}
    assert audit_log.await_count == 2


@pytest.mark.asyncio
async def test_refresh_rejected_for_revoked_session(
    db_session: AsyncMock,
) -> None:
    user = make_user()
    refresh_token = "revoked-refresh-token"
    token_hash = TokenService.hash_token(refresh_token)
    revoked_session = make_auth_session(
        user,
        current_token_hash=token_hash,
        revoked=True,
    )
    db_session.scalar.return_value = revoked_session
    token_service = Mock(spec=TokenService)
    token_service.hash_token.return_value = token_hash

    with pytest.raises(InvalidSessionError):
        await AuthService(
            db_session,
            token_service=token_service,
        ).refresh(refresh_token, "127.0.0.1", "pytest")

    token_service.generate_refresh_token.assert_not_called()
    db_session.execute.assert_not_awaited()
    db_session.commit.assert_not_awaited()
