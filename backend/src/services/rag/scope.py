"""Request-time RAG authorization scope derived from current relationships."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.models.player import Player
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.services.role_scope import resolve_current_role_team_scope


@dataclass(frozen=True, slots=True)
class RagAccessScope:
    """Current relational visibility; never accepted from a client or persisted."""

    user_id: UUID
    role: UserRole
    is_active: bool
    linked_player_id: UUID | None
    team_ids: tuple[UUID, ...]
    age_groups: tuple[str, ...]
    active_player_ids: tuple[UUID, ...]
    is_unlinked_player: bool
    can_read_all_registered_sources: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "team_ids", tuple(sorted(set(self.team_ids), key=str)))
        object.__setattr__(
            self,
            "age_groups",
            tuple(sorted({item.strip() for item in self.age_groups if item.strip()})),
        )
        object.__setattr__(
            self,
            "active_player_ids",
            tuple(sorted(set(self.active_player_ids), key=str)),
        )

    @property
    def denies_all(self) -> bool:
        """Return whether no candidate query should be issued for this scope."""

        return not self.is_active or self.is_unlinked_player


class RagAccessScopeResolver:
    """Resolve role scope using the dashboard's authoritative relationship model."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, user: User) -> RagAccessScope:
        """Resolve current User, TeamCoach, TeamPlayer, and active Player state."""

        role = UserRole(user.role)
        if not user.is_active:
            return self._empty(user, role, unlinked=role is UserRole.PLAYER)
        base_scope = await resolve_current_role_team_scope(
            self.session,
            user,
            include_head_coach_teams=False,
        )
        if base_scope.role is UserRole.HEAD_COACH:
            return RagAccessScope(
                user_id=user.id,
                role=role,
                is_active=True,
                linked_player_id=None,
                team_ids=(),
                age_groups=(),
                active_player_ids=(),
                is_unlinked_player=False,
                can_read_all_registered_sources=True,
            )
        if base_scope.role is UserRole.ASSISTANT_COACH:
            teams = base_scope.teams
            team_ids = tuple(team.id for team in teams)
            active_player_ids: tuple[UUID, ...] = ()
            if team_ids:
                active_player_ids = tuple(
                    (
                        await self.session.scalars(
                            select(Player.id)
                            .join(TeamPlayer, TeamPlayer.player_id == Player.id)
                            .where(
                                TeamPlayer.team_id.in_(team_ids),
                                Player.is_active.is_(True),
                            )
                            .distinct()
                            .order_by(Player.id)
                        )
                    ).all()
                )
            return RagAccessScope(
                user_id=user.id,
                role=role,
                is_active=True,
                linked_player_id=None,
                team_ids=team_ids,
                age_groups=tuple(team.age_group for team in teams),
                active_player_ids=active_player_ids,
                is_unlinked_player=False,
                can_read_all_registered_sources=False,
            )

        if base_scope.linked_player_id is None:
            return self._empty(user, role, unlinked=True)
        teams = base_scope.teams
        return RagAccessScope(
            user_id=user.id,
            role=role,
            is_active=True,
            linked_player_id=base_scope.linked_player_id,
            team_ids=tuple(team.id for team in teams),
            age_groups=tuple(team.age_group for team in teams),
            active_player_ids=(base_scope.linked_player_id,),
            is_unlinked_player=False,
            can_read_all_registered_sources=False,
        )

    @staticmethod
    def _empty(user: User, role: UserRole, *, unlinked: bool) -> RagAccessScope:
        return RagAccessScope(
            user_id=user.id,
            role=role,
            is_active=False if not user.is_active else True,
            linked_player_id=None,
            team_ids=(),
            age_groups=(),
            active_player_ids=(),
            is_unlinked_player=unlinked,
            can_read_all_registered_sources=False,
        )
