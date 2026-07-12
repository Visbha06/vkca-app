"""Application service for player profile operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_sync_log import DataSyncLog
from src.models.player import Player
from src.schemas.player import PlayerCreate, PlayerUpdate
from src.services.occ import StaleVersionError, check_and_increment_version


class PlayerAlreadyExistsError(Exception):
    """Raised when a player's identity matches an existing profile."""


class PlayerNotFoundError(Exception):
    """Raised when a requested player does not exist."""


class PlayerService:
    """Create, query, and update player profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def list_players(self) -> list[Player]:
        """Return active player profiles in stable name order."""

        statement = (
            select(Player)
            .where(Player.is_active.is_(True))
            .order_by(Player.last_name, Player.first_name, Player.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_player_by_id(self, player_id: UUID) -> Player:
        """Return a player regardless of active status."""

        player = await self.session.get(Player, player_id)
        if player is None:
            raise PlayerNotFoundError
        return player

    async def update_player(
        self,
        player_id: UUID,
        payload: PlayerUpdate,
    ) -> Player:
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
        return player
