"""Read-only access to aggregate player statistics."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import MatchFormat
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats


class StatsService:
    """Query batting and bowling totals, optionally by match format."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_batting_stats(
        self,
        player_id: UUID,
        match_format: MatchFormat | None = None,
    ) -> list[PlayerBattingStats]:
        """Return batting aggregate rows in stable format order."""

        statement = select(PlayerBattingStats).where(
            PlayerBattingStats.player_id == player_id
        )
        if match_format is not None:
            statement = statement.where(PlayerBattingStats.format == match_format)
        statement = statement.order_by(PlayerBattingStats.format)
        return list((await self.session.scalars(statement)).all())

    async def get_bowling_stats(
        self,
        player_id: UUID,
        match_format: MatchFormat | None = None,
    ) -> list[PlayerBowlingStats]:
        """Return bowling aggregate rows in stable format order."""

        statement = select(PlayerBowlingStats).where(
            PlayerBowlingStats.player_id == player_id
        )
        if match_format is not None:
            statement = statement.where(PlayerBowlingStats.format == match_format)
        statement = statement.order_by(PlayerBowlingStats.format)
        return list((await self.session.scalars(statement)).all())
