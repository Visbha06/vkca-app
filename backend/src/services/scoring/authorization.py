"""Current-database scoring authorization and Team-scope adapter."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.models.user import User
from src.services.role_scope import (
    CurrentRoleTeamScope,
    resolve_current_role_team_scope,
)
from src.services.scoring.errors import (
    ScoringAuthenticationError,
    ScoringAuthorizationError,
    ScoringVisibilityError,
)


@dataclass(frozen=True, slots=True)
class ScoringCommandContext:
    """Authenticated actor and freshly resolved authorization relationships."""

    user: User
    role_scope: CurrentRoleTeamScope

    @property
    def role(self) -> UserRole:
        return self.role_scope.role

    @property
    def scoped_team_ids(self) -> frozenset[UUID]:
        return frozenset(team.id for team in self.role_scope.teams)

    @property
    def linked_player_id(self) -> UUID | None:
        return self.role_scope.linked_player_id

    @property
    def may_mutate(self) -> bool:
        return self.role in {UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH}

    def can_access_any_team(self, academy_team_ids: set[UUID]) -> bool:
        """Return whether current role relationships cover the Match anchor."""

        if self.role is UserRole.HEAD_COACH:
            return True
        return bool(self.scoped_team_ids.intersection(academy_team_ids))

    def require_read_scope(self, academy_team_ids: set[UUID]) -> None:
        """Conceal Match resources outside the current role/Team scope."""

        if not self.can_access_any_team(academy_team_ids):
            raise ScoringVisibilityError("Scoring resource not found.")

    def require_mutation_scope(self, academy_team_ids: set[UUID]) -> None:
        """Require a coach role and a current assignment to the academy side."""

        if not self.may_mutate:
            raise ScoringAuthorizationError(
                "The current role has read-only Match access."
            )
        if not self.can_access_any_team(academy_team_ids):
            raise ScoringAuthorizationError(
                "The current coach assignment does not cover this Match."
            )


class ScoringAuthorizationAdapter:
    """Reload actors and delegate relationship resolution to ``role_scope``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def load_context(
        self, authenticated_user: User | UUID
    ) -> ScoringCommandContext:
        """Reload an active User and resolve all current scope relationships."""

        user_id = (
            authenticated_user
            if isinstance(authenticated_user, UUID)
            else authenticated_user.id
        )
        user = await self.session.scalar(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )
        if user is None:
            raise ScoringAuthenticationError(
                "Authentication is required for Match scoring."
            )
        try:
            scope = await resolve_current_role_team_scope(
                self.session,
                user,
                include_head_coach_teams=True,
            )
        except ValueError as exc:
            raise ScoringAuthorizationError(
                "The current account role is not eligible for Match scoring."
            ) from exc
        return ScoringCommandContext(user=user, role_scope=scope)


async def load_scoring_command_context(
    session: AsyncSession,
    authenticated_user: User | UUID,
) -> ScoringCommandContext:
    """Public functional seam used by scoring commands and route dependencies."""

    return await ScoringAuthorizationAdapter(session).load_context(authenticated_user)
