"""Unit coverage for current-database RAG access-scope resolution."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.enums import (
    BattingStyle,
    BowlingStyle,
    PlayerType,
    UserRole,
)
from src.models.player import Player
from src.models.team import Team
from src.models.user import User
from src.services.rag.scope import RagAccessScopeResolver


class ScalarItems:
    def __init__(self, items) -> None:
        self.items = tuple(items)

    def all(self):
        return self.items


def _user(role: UserRole, *, active: bool = True) -> User:
    return User(
        id=uuid4(),
        first_name="Scope",
        last_name="User",
        email=f"scope-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=role,
        is_active=active,
    )


def _player(*, user_id=None, active: bool = True) -> Player:
    return Player(
        id=uuid4(),
        user_id=user_id,
        first_name="Linked",
        last_name="Player",
        date_of_birth=date(2012, 1, 1),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=active,
    )


@pytest.mark.asyncio
async def test_head_coach_has_current_academy_scope_and_inactive_user_is_denied():
    session = AsyncMock()
    active = await RagAccessScopeResolver(session).resolve(_user(UserRole.HEAD_COACH))
    inactive = await RagAccessScopeResolver(session).resolve(
        _user(UserRole.HEAD_COACH, active=False)
    )

    assert active.can_read_all_registered_sources
    assert active.is_active
    assert not active.is_unlinked_player
    assert not inactive.is_active
    assert not inactive.can_read_all_registered_sources
    assert inactive.team_ids == ()


@pytest.mark.asyncio
async def test_assistant_scope_has_assignments_ages_and_every_active_player():
    assistant = _user(UserRole.ASSISTANT_COACH)
    u13 = Team(id=uuid4(), name="U13 Blue", age_group="U13")
    u15 = Team(id=uuid4(), name="U15 Gold", age_group="U15")
    active_player_ids = (uuid4(), uuid4(), uuid4())
    session = AsyncMock()
    session.scalars.side_effect = [
        ScalarItems((u13, u15)),
        ScalarItems(active_player_ids),
    ]

    scope = await RagAccessScopeResolver(session).resolve(assistant)

    assert scope.role is UserRole.ASSISTANT_COACH
    assert scope.team_ids == tuple(sorted((u13.id, u15.id), key=str))
    assert scope.age_groups == ("U13", "U15")
    assert scope.active_player_ids == tuple(sorted(active_player_ids, key=str))
    assert not scope.can_read_all_registered_sources


@pytest.mark.asyncio
async def test_linked_player_uses_memberships_and_unlinked_denies_scope():
    user = _user(UserRole.PLAYER)
    player = _player(user_id=user.id)
    team = Team(id=uuid4(), name="U13 Blue", age_group="U13")
    linked_session = AsyncMock()
    linked_session.scalar.return_value = player
    linked_session.scalars.return_value = ScalarItems((team,))

    linked = await RagAccessScopeResolver(linked_session).resolve(user)

    unlinked_session = AsyncMock()
    unlinked_session.scalar.return_value = None
    unlinked = await RagAccessScopeResolver(unlinked_session).resolve(user)

    assert linked.linked_player_id == player.id
    assert linked.active_player_ids == (player.id,)
    assert linked.team_ids == (team.id,)
    assert linked.age_groups == ("U13",)
    assert not linked.is_unlinked_player
    assert unlinked.is_unlinked_player
    assert unlinked.active_player_ids == ()
    assert unlinked.team_ids == ()
