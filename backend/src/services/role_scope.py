"""Shared current role, TeamCoach, Player-link, and TeamPlayer resolution."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User


@dataclass(frozen=True, slots=True)
class CurrentRoleTeamScope:
    """Relationship projection shared by dashboard and RAG read boundaries."""

    role: UserRole
    teams: tuple[Team, ...]
    linked_player_id: UUID | None


async def resolve_current_role_team_scope(
    session: AsyncSession,
    user: User,
    *,
    include_head_coach_teams: bool,
) -> CurrentRoleTeamScope:
    """Resolve the repository's one authoritative role-to-Team relationship model."""

    role = UserRole(user.role)
    if role is UserRole.HEAD_COACH:
        teams: tuple[Team, ...] = ()
        if include_head_coach_teams:
            teams = tuple(
                (await session.scalars(select(Team).order_by(Team.name, Team.id))).all()
            )
        return CurrentRoleTeamScope(
            role=role,
            teams=teams,
            linked_player_id=None,
        )
    if role is UserRole.ASSISTANT_COACH:
        teams = tuple(
            (
                await session.scalars(
                    select(Team)
                    .join(TeamCoach, TeamCoach.team_id == Team.id)
                    .where(TeamCoach.user_id == user.id)
                    .order_by(Team.name, Team.id)
                )
            ).all()
        )
        return CurrentRoleTeamScope(
            role=role,
            teams=teams,
            linked_player_id=None,
        )

    player = await session.scalar(
        select(Player).where(
            Player.user_id == user.id,
            Player.is_active.is_(True),
        )
    )
    if player is None:
        return CurrentRoleTeamScope(role=role, teams=(), linked_player_id=None)
    teams = tuple(
        (
            await session.scalars(
                select(Team)
                .join(TeamPlayer, TeamPlayer.team_id == Team.id)
                .where(TeamPlayer.player_id == player.id)
                .order_by(Team.name, Team.id)
            )
        ).all()
    )
    return CurrentRoleTeamScope(
        role=role,
        teams=teams,
        linked_player_id=player.id,
    )
