"""Application service for atomic team and roster operations."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.schemas.team import (
    PaginatedTeamResponse,
    TeamCreate,
    TeamResponse,
    TeamRosterPlayerResponse,
    TeamRosterResponse,
    TeamUpdate,
)
from src.services.occ import check_and_increment_version


class TeamNotFoundError(Exception):
    """Raised when a requested team does not exist."""

    def __init__(self) -> None:
        super().__init__("Team not found.")


class PlayerNotFoundError(Exception):
    """Raised when a requested player does not exist."""

    def __init__(self) -> None:
        super().__init__("Player not found.")


class TeamValidationError(Exception):
    """Raised when a complete roster fails domain validation."""


class TeamNameConflictError(Exception):
    """Raised when a normalized name already exists in an age group."""

    def __init__(self) -> None:
        super().__init__(
            "A team with this name already exists in the selected age group."
        )


class TeamMembershipAlreadyExistsError(Exception):
    """Raised when a player is already on the requested team."""

    def __init__(self) -> None:
        super().__init__("Player is already a member of this team.")


class TeamService:
    """Query and mutate teams while preserving complete roster consistency."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _validate_roster_players(self, player_ids: list[UUID]) -> None:
        """Require 7–15 distinct, existing, active players."""

        if not 7 <= len(player_ids) <= 15:
            raise TeamValidationError("A team roster must contain 7 to 15 players.")
        if len(set(player_ids)) != len(player_ids):
            raise TeamValidationError("A team roster cannot contain duplicate players.")

        statement = select(Player.id, Player.is_active).where(Player.id.in_(player_ids))
        rows = (await self.session.execute(statement)).all()
        players_by_id = {player_id: is_active for player_id, is_active in rows}
        missing_ids = [
            player_id for player_id in player_ids if player_id not in players_by_id
        ]
        if missing_ids:
            raise PlayerNotFoundError
        if any(not players_by_id[player_id] for player_id in player_ids):
            raise TeamValidationError(
                "Only active players can be selected for a team roster."
            )

    async def _ensure_unique_name(
        self,
        name: str,
        age_group: str,
        *,
        exclude_team_id: UUID | None = None,
    ) -> None:
        """Reject normalized name collisions within one age group."""

        statement = select(Team.id).where(
            func.lower(func.trim(Team.name)) == func.lower(func.trim(name)),
            Team.age_group == age_group,
        )
        if exclude_team_id is not None:
            statement = statement.where(Team.id != exclude_team_id)
        if await self.session.scalar(statement.limit(1)) is not None:
            raise TeamNameConflictError

    @staticmethod
    def _team_response(team: Team, player_count: int) -> TeamResponse:
        return TeamResponse.model_validate(team).model_copy(
            update={"player_count": player_count}
        )

    async def create_team(self, payload: TeamCreate) -> TeamResponse:
        """Create team details and the complete ordered roster atomically."""

        try:
            await self._validate_roster_players(payload.player_ids)
            await self._ensure_unique_name(payload.name, payload.age_group)

            team = Team(
                name=payload.name.strip(),
                age_group=payload.age_group,
            )
            self.session.add(team)
            await self.session.flush()
            self.session.add_all(
                [
                    TeamPlayer(
                        team_id=team.id,
                        player_id=player_id,
                        roster_order=index,
                    )
                    for index, player_id in enumerate(payload.player_ids, start=1)
                ]
            )
            await self.session.flush()
            await self.session.refresh(team)
            response = self._team_response(team, len(payload.player_ids))
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def update_team(
        self,
        team_id: UUID,
        payload: TeamUpdate,
    ) -> TeamResponse:
        """Replace team details and its ordered roster in one OCC transaction."""

        try:
            team = await self.session.get(Team, team_id)
            if team is None:
                raise TeamNotFoundError

            next_version = await check_and_increment_version(
                self.session,
                Team,
                team_id,
                payload.version_number,
            )
            await self._validate_roster_players(payload.player_ids)
            await self._ensure_unique_name(
                payload.name,
                payload.age_group,
                exclude_team_id=team_id,
            )

            team.name = payload.name.strip()
            team.age_group = payload.age_group
            team.version_number = next_version
            await self.session.execute(
                delete(TeamPlayer).where(TeamPlayer.team_id == team_id)
            )
            self.session.add_all(
                [
                    TeamPlayer(
                        team_id=team_id,
                        player_id=player_id,
                        roster_order=index,
                    )
                    for index, player_id in enumerate(payload.player_ids, start=1)
                ]
            )
            await self.session.flush()
            await self.session.refresh(team)
            response = self._team_response(team, len(payload.player_ids))
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def list_teams(
        self,
        *,
        page: int = 1,
        page_size: int = 12,
    ) -> PaginatedTeamResponse:
        """Return teams and roster counts in stable paginated order."""

        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        total_teams = int(await self.session.scalar(select(func.count(Team.id))) or 0)
        statement = (
            select(Team, func.count(TeamPlayer.player_id).label("player_count"))
            .outerjoin(TeamPlayer, TeamPlayer.team_id == Team.id)
            .group_by(Team.id)
            .order_by(Team.name, Team.age_group, Team.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(statement)).all()
        teams = [
            TeamResponse.model_validate(team).model_copy(
                update={"player_count": int(player_count)}
            )
            for team, player_count in rows
        ]
        return PaginatedTeamResponse(
            teams=teams,
            page=page,
            page_size=page_size,
            total_teams=total_teams,
            total_pages=(total_teams + page_size - 1) // page_size,
        )

    async def get_team_roster(self, team_id: UUID) -> TeamRosterResponse:
        """Return all roster members, ordered by their persisted position."""

        if await self.session.get(Team, team_id) is None:
            raise TeamNotFoundError

        statement = (
            select(
                TeamPlayer.player_id,
                Player.first_name,
                Player.last_name,
                Player.is_active,
                TeamPlayer.roster_order,
            )
            .join(Player, Player.id == TeamPlayer.player_id)
            .where(TeamPlayer.team_id == team_id)
            .order_by(TeamPlayer.roster_order.asc(), TeamPlayer.player_id.asc())
        )
        players = [
            TeamRosterPlayerResponse(
                player_id=player_id,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                roster_order=roster_order,
            )
            for player_id, first_name, last_name, is_active, roster_order in (
                await self.session.execute(statement)
            ).all()
        ]
        return TeamRosterResponse(team_id=team_id, players=players)

    async def add_player_to_team(
        self,
        team_id: UUID,
        player_id: UUID,
    ) -> TeamPlayer:
        """Add an existing player to an existing team once."""

        if await self.session.get(Team, team_id) is None:
            raise TeamNotFoundError
        if await self.session.get(Player, player_id) is None:
            raise PlayerNotFoundError

        membership_key = {"team_id": team_id, "player_id": player_id}
        if await self.session.get(TeamPlayer, membership_key) is not None:
            raise TeamMembershipAlreadyExistsError

        membership = TeamPlayer(**membership_key)
        self.session.add(membership)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise TeamMembershipAlreadyExistsError from exc
        await self.session.refresh(membership)
        return membership
