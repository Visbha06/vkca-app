"""Team roster membership database model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, VersionMixin


class TeamPlayer(TimestampMixin, VersionMixin, Base):
    """A player's membership in a cricket team."""

    __tablename__ = "team_players"
    __table_args__ = (Index("ix_team_players_team_order", "team_id", "roster_order"),)

    team_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("teams.id"),
        primary_key=True,
    )
    player_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("players.id"),
        primary_key=True,
    )
    roster_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
