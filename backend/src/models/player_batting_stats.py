"""Aggregate player batting statistics database model."""

from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.enums import MatchFormat
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class PlayerBattingStats(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A player's lifetime batting totals for one match format."""

    __tablename__ = "player_batting_stats"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "format", name="uq_player_batting_stats_player_format"
        ),
        CheckConstraint(
            "format IN ('T20', 'one-day', 'test', 'other')",
            name="ck_player_batting_stats_format",
        ),
    )

    player_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("players.id"),
        nullable=False,
    )
    format: Mapped[MatchFormat] = mapped_column(String(20), nullable=False)
    matches: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    innings: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    not_outs: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    runs: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    balls_faced: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    high_score: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    hundreds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    fifties: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    ducks: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    fours: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    sixes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
