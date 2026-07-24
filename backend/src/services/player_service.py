"""Application service for player profile operations."""

from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.models.data_sync_log import DataSyncLog
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.schemas.player import (
    PaginatedPlayerResponse,
    PlayerCreate,
    PlayerResponse,
    PlayerUpdate,
    TeamSummary,
)
from src.services.occ import StaleVersionError, check_and_increment_version


class PlayerAlreadyExistsError(Exception):
    """Raised when a player's identity matches an existing profile."""


class PlayerNotFoundError(Exception):
    """Raised when a requested player does not exist."""


class PlayerService:
    """Create, query, and update player profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _with_team_summaries(
        self,
        players: list[Player],
    ) -> list[PlayerResponse]:
        """Serialize players and populate team summaries in one batch query."""

        teams_by_player: dict[UUID, list[TeamSummary]] = {
            player.id: [] for player in players
        }
        if players:
            membership_statement = (
                select(TeamPlayer.player_id, Team.id, Team.name)
                .join(Team, Team.id == TeamPlayer.team_id)
                .where(TeamPlayer.player_id.in_(teams_by_player))
                .order_by(Team.name, Team.id)
            )
            membership_rows = (await self.session.execute(membership_statement)).all()
            for player_id, listed_team_id, team_name in membership_rows:
                teams_by_player[player_id].append(
                    TeamSummary(id=listed_team_id, name=team_name)
                )

        return [
            PlayerResponse.model_validate(player).model_copy(
                update={"teams": teams_by_player[player.id]}
            )
            for player in players
        ]

    async def create_player(self, payload: PlayerCreate) -> Player:
        """Create a unique player profile."""

        duplicate_statement = select(Player.id).where(
            Player.first_name == payload.first_name,
            Player.last_name == payload.last_name,
            Player.date_of_birth == payload.date_of_birth,
        )
        if await self.session.scalar(duplicate_statement) is not None:
            raise PlayerAlreadyExistsError

        player = Player(**payload.model_dump())
        self.session.add(player)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(player)
        return player

    async def list_players(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        team_id: UUID | None = None,
        unassigned: bool = False,
        search: str | None = None,
    ) -> PaginatedPlayerResponse:
        """Return one filtered page of active players in stable name order."""

        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if team_id is not None and unassigned:
            raise ValueError("team_id and unassigned are mutually exclusive")

        filters: list[ColumnElement[bool]] = [Player.is_active.is_(True)]
        normalized_search = search.strip() if search is not None else ""
        if normalized_search:
            escaped_search = (
                normalized_search.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            search_pattern = f"%{escaped_search}%"
            filters.append(
                or_(
                    Player.first_name.ilike(search_pattern, escape="\\"),
                    Player.last_name.ilike(search_pattern, escape="\\"),
                    func.concat(
                        Player.first_name,
                        " ",
                        Player.last_name,
                    ).ilike(search_pattern, escape="\\"),
                )
            )

        membership_exists = exists(
            select(TeamPlayer.player_id).where(TeamPlayer.player_id == Player.id)
        )
        if team_id is not None:
            filters.append(
                exists(
                    select(TeamPlayer.player_id).where(
                        TeamPlayer.player_id == Player.id,
                        TeamPlayer.team_id == team_id,
                    )
                )
            )
        elif unassigned:
            filters.append(~membership_exists)

        total_players = int(
            await self.session.scalar(select(func.count(Player.id)).where(*filters))
            or 0
        )
        statement = (
            select(Player)
            .where(*filters)
            .order_by(Player.last_name, Player.first_name, Player.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        players = list((await self.session.scalars(statement)).all())

        player_responses = await self._with_team_summaries(players)
        total_pages = (total_players + page_size - 1) // page_size
        return PaginatedPlayerResponse(
            players=player_responses,
            page=page,
            page_size=page_size,
            total_players=total_players,
            total_pages=total_pages,
            has_previous=page > 1,
            has_next=page < total_pages,
        )

    async def get_player_by_id(self, player_id: UUID) -> PlayerResponse:
        """Return a player regardless of active status."""

        player = await self.session.get(Player, player_id)
        if player is None:
            raise PlayerNotFoundError
        return (await self._with_team_summaries([player]))[0]

    async def update_player(
        self,
        player_id: UUID,
        payload: PlayerUpdate,
    ) -> PlayerResponse:
        """Apply a partial player update using optimistic concurrency control."""

        player = await self.session.get(Player, player_id)
        if player is None:
            raise PlayerNotFoundError

        changes = payload.model_dump(exclude_unset=True)
        incoming_version = changes.pop("version_number")
        try:
            await check_and_increment_version(
                self.session,
                Player,
                player_id,
                incoming_version,
            )
        except StaleVersionError as exc:
            self.session.add(
                DataSyncLog(
                    source="player-update",
                    status="conflict",
                    target_table=Player.__tablename__,
                    error_message=str(exc),
                )
            )
            await self.session.commit()
            raise

        await self.session.refresh(player)
        for field, value in changes.items():
            setattr(player, field, value)

        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(player)
        return (await self._with_team_summaries([player]))[0]
