"""Per-match batting performance database model."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.enums import DismissalType
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class MatchBattingPerformance(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A player's batting figures for one match."""

    __tablename__ = "match_batting_performances"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "match_id",
            name="uq_match_batting_performances_player_match",
        ),
        CheckConstraint(
            "dismissal IN ('not out', 'caught', 'bowled', 'lbw', "
            "'run out', 'stumped', 'other')",
            name="ck_match_batting_performances_dismissal",
        ),
        Index("ix_match_batting_performances_match_id", "match_id"),
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
    runs_scored: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    balls_faced: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    dismissal: Mapped[DismissalType] = mapped_column(
        String(20),
        nullable=False,
        default=DismissalType.NOT_OUT,
        server_default=text("'not out'"),
    )
    fours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    sixes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
