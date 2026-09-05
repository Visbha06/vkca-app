"""Current-database scoring authorization and Team-scope adapter."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import MatchSideKind, ParticipationState, UserRole
from src.models.match import Match
from src.models.player import Player
from src.models.scoring.innings import Innings
from src.models.scoring.participant import MatchParticipant
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.services.role_scope import (
    CurrentRoleTeamScope,
    resolve_current_role_team_scope,
)
from src.services.scoring.errors import (
    ScoringAuthenticationError,
    ScoringAuthorizationError,
    ScoringValidationError,
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

    async def load_eligible_internal_players(
        self,
        player_team_assignments: dict[UUID, UUID],
    ) -> dict[UUID, Player]:
        """Resolve active Players whose current roster owns each requested ID."""

        if not player_team_assignments:
            return {}
        rows = (
            await self.session.execute(
                select(Player, TeamPlayer.team_id)
                .join(TeamPlayer, TeamPlayer.player_id == Player.id)
                .where(
                    Player.id.in_(player_team_assignments),
                    Player.is_active.is_(True),
                    TeamPlayer.team_id.in_(set(player_team_assignments.values())),
                )
            )
        ).all()
        eligible: dict[UUID, Player] = {}
        for player, team_id in rows:
            if player_team_assignments.get(player.id) == team_id:
                eligible[player.id] = player
        if set(eligible) != set(player_team_assignments):
            raise ScoringValidationError(
                "Every internal participant must be an active member of its "
                "configured academy Team."
            )
        return eligible


def require_configuration_scope(
    context: ScoringCommandContext,
    academy_team_ids: set[UUID],
) -> None:
    """Public policy seam for current role and Team configuration authority."""

    context.require_mutation_scope(academy_team_ids)


def academy_team_ids_for_match(match: Match) -> set[UUID]:
    """Return the configured academy sides that anchor scoring scope."""

    return {
        side.team_id
        for side in match.scoring_sides
        if side.side_kind == MatchSideKind.ACADEMY and side.team_id is not None
    }


def require_scoring_mutation_scope(
    context: ScoringCommandContext,
    match: Match,
) -> None:
    """Authorize a scoring mutation from current Match-side ownership."""

    context.require_mutation_scope(academy_team_ids_for_match(match))


def require_scoring_read_scope(
    context: ScoringCommandContext,
    match: Match,
) -> None:
    """Authorize a protected scoring read from current Match-side ownership."""

    context.require_read_scope(academy_team_ids_for_match(match))


def validate_innings_selections(
    innings: Innings,
    participants: list[MatchParticipant],
    *,
    striker_participant_id: UUID,
    non_striker_participant_id: UUID,
    bowler_participant_id: UUID,
    require_current: bool,
) -> None:
    """Validate fixed-side membership and optionally the current active selection."""

    participant_by_id = {participant.id: participant for participant in participants}
    striker = participant_by_id.get(striker_participant_id)
    non_striker = participant_by_id.get(non_striker_participant_id)
    bowler = participant_by_id.get(bowler_participant_id)
    if striker is None or non_striker is None or bowler is None:
        raise ScoringValidationError(
            "Every selection must be a fixed Match participant."
        )
    if striker.id == non_striker.id:
        raise ScoringValidationError("Striker and non-striker must be distinct.")
    if (
        striker.side_id != innings.batting_side_id
        or non_striker.side_id != innings.batting_side_id
    ):
        raise ScoringValidationError("Active batters must belong to the batting side.")
    if bowler.side_id != innings.fielding_side_id:
        raise ScoringValidationError(
            "The current bowler must belong to the fielding side."
        )
    entry_by_id = {entry.participant_id: entry for entry in innings.batting_entries}
    for batter_id in (striker.id, non_striker.id):
        entry = entry_by_id.get(batter_id)
        if entry is None or (
            require_current
            and ParticipationState(entry.participation_state)
            is not ParticipationState.ACTIVE
        ):
            raise ScoringValidationError(
                "Both batters must be eligible in this Innings."
            )
    if require_current and (
        innings.striker_participant_id != striker.id
        or innings.non_striker_participant_id != non_striker.id
        or innings.current_bowler_participant_id != bowler.id
    ):
        raise ScoringValidationError(
            "Delivery selections do not match the authoritative Innings state."
        )


async def load_scoring_command_context(
    session: AsyncSession,
    authenticated_user: User | UUID,
) -> ScoringCommandContext:
    """Public functional seam used by scoring commands and route dependencies."""

    return await ScoringAuthorizationAdapter(session).load_context(authenticated_user)
