"""Application service for team and roster membership operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.schemas.team import TeamCreate


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
    """Create teams, list teams, and manage team rosters."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_team(self, payload: TeamCreate) -> Team:
        """Persist a cricket team."""

        team = Team(**payload.model_dump())
        self.session.add(team)
        await self.session.commit()
        await self.session.refresh(team)
        return team

    async def list_teams(self) -> list[Team]:
        """Return all teams in stable name order."""

        statement = select(Team).order_by(Team.name, Team.age_group, Team.id)
        return list((await self.session.scalars(statement)).all())

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
