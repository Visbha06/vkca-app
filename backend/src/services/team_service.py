"""Application service for team queries and roster membership operations."""

from uuid import UUID

from sqlalchemy import func, select
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
)


class TeamNotFoundError(Exception):
    """Raised when a requested team does not exist."""

    def __init__(self) -> None:
        super().__init__("Team not found.")


class PlayerNotFoundError(Exception):
    """Raised when a requested player does not exist."""

    def __init__(self) -> None:
        super().__init__("Player not found.")


class TeamMembershipAlreadyExistsError(Exception):
    """Raised when a player is already on the requested team."""

    def __init__(self) -> None:
        super().__init__("Player is already a member of this team.")


class TeamService:
    """Query team summaries and retrieve ordered team rosters."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_team(self, payload: TeamCreate) -> Team:
        """Keep the legacy endpoint compatible until atomic creation lands."""

        team = Team(**payload.model_dump(exclude={"player_ids"}))
        self.session.add(team)
        await self.session.commit()
        await self.session.refresh(team)
        return team

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
