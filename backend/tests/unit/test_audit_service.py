"""Unit tests for credential-free authentication audit records."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth_audit_log import AuthAuditLog
from src.services.audit_service import AuditService


@pytest.mark.asyncio
async def test_log_event_creates_record() -> None:
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()
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
    session = Mock(spec=AsyncSession)
    session.flush = AsyncMock()

    await AuditService.log_event(
        session,
        "failed_login",
        result="failure",
        reason="invalid_credentials",
    )

    record = session.add.call_args.args[0]
    field_names = set(record.__table__.columns.keys())
    sensitive_fields = {
        "password",
        "hashed_password",
        "access_token",
        "refresh_token",
        "token_hash",
        "jwt_secret",
    }
    assert field_names.isdisjoint(sensitive_fields)
