"""Unit tests for the initial Head Coach seed script."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.seed_head_coach import seed_head_coach
from src.enums import UserRole
from src.services.password_service import PasswordService


@pytest.mark.asyncio
async def test_seed_head_coach_creates_argon2id_account() -> None:
    """A missing seed account is inserted with a server-generated password hash."""

    session = MagicMock()
    session.scalar = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    user, created = await seed_head_coach(
        session,
        email="HeadCoach@VKCA.test",
        password="SuperSecur3!P@ss",
        first_name="Head",
        last_name="Coach",
    )

    assert created is True
    assert user.email == "headcoach@vkca.test"
    assert user.role == UserRole.HEAD_COACH
    assert user.hashed_password.startswith("$argon2id$")
    assert PasswordService.verify_password(
        "SuperSecur3!P@ss", user.hashed_password
    )
    session.add.assert_called_once_with(user)
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_seed_head_coach_is_idempotent() -> None:
    """An existing account is returned without changing its credentials."""

    existing_user = MagicMock()
    session = MagicMock()
    session.scalar = AsyncMock(return_value=existing_user)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    user, created = await seed_head_coach(
        session,
        email="headcoach@vkca.test",
        password="SuperSecur3!P@ss",
    )

    assert user is existing_user
    assert created is False
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()
