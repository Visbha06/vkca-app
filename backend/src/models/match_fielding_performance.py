"""Per-match fielding performance database model."""

from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class MatchFieldingPerformance(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A player's fielding figures for one match."""

    __tablename__ = "match_fielding_performances"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "match_id",
            name="uq_match_fielding_performances_player_match",
        ),
        Index("ix_match_fielding_performances_match_id", "match_id"),
    )

    player_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("players.id"),
        nullable=False,
    )
    match_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("matches.id"),
        nullable=False,
    )
    catches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    stumpings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    run_outs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    dropped_catches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
