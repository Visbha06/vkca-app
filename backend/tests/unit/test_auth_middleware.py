"""Unit tests for linked Player profile enforcement on bearer requests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.enums import UserRole
from src.middleware.auth import _authenticate_access_token
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.token_service import TokenService


def make_bearer_records() -> tuple[User, AuthSession]:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        first_name="Linked",
        last_name="Player",
        email="linked.player@example.com",
        hashed_password="$argon2id$unit-test-only",
        role=UserRole.PLAYER,
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )
    auth_session = AuthSession(
        id=uuid4(),
        user_id=user.id,
        token_family_id=uuid4(),
        current_token_hash="hash",
        rotated_token_hashes=[],
        last_used_at=now,
        expires_at=now + timedelta(days=7),
        revoked_at=None,
        revocation_reason=None,
        created_at=now,
        version_number=1,
    )
    return user, auth_session


@pytest.mark.asyncio
async def test_bearer_rejects_linked_inactive_player_profile(mocker) -> None:
    user, auth_session = make_bearer_records()
    session = AsyncMock()
    session.scalar.side_effect = [auth_session, user, False]
    mocker.patch.object(
        TokenService,
        "decode_and_verify_access_token",
        return_value={"sub": str(user.id), "sid": str(auth_session.id)},
    )

    with pytest.raises(HTTPException) as raised:
        await _authenticate_access_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            session,
        )

    assert raised.value.status_code == 401
    assert raised.value.detail == "Not authenticated"


@pytest.mark.asyncio
async def test_bearer_allows_unlinked_or_active_linked_player_profile(
    mocker,
) -> None:
    user, auth_session = make_bearer_records()
    session = AsyncMock()
    session.scalar.side_effect = [auth_session, user, None]
    mocker.patch.object(
        TokenService,
        "decode_and_verify_access_token",
        return_value={"sub": str(user.id), "sid": str(auth_session.id)},
    )

    authenticated = await _authenticate_access_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
        session,
    )

    assert authenticated == (user, auth_session)


@pytest.mark.asyncio
async def test_independently_disabled_user_stays_rejected_without_profile_lookup(
    mocker,
) -> None:
    user, auth_session = make_bearer_records()
    user.is_active = False
    session = AsyncMock()
    session.scalar.side_effect = [auth_session, user]
    mocker.patch.object(
        TokenService,
        "decode_and_verify_access_token",
        return_value={"sub": str(user.id), "sid": str(auth_session.id)},
    )

    with pytest.raises(HTTPException):
        await _authenticate_access_token(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            session,
        )

    assert session.scalar.await_count == 2
