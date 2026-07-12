"""Aggregate player bowling statistics database model."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.enums import MatchFormat
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class PlayerBowlingStats(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A player's lifetime bowling totals for one match format."""

    __tablename__ = "player_bowling_stats"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "format", name="uq_player_bowling_stats_player_format"
        ),
        CheckConstraint(
            "format IN ('T20', 'one-day', 'test', 'other')",
            name="ck_player_bowling_stats_format",
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
    overs_bowled: Mapped[Decimal] = mapped_column(
        Numeric(7, 1),
        nullable=False,
        default=Decimal("0.0"),
        server_default=text("0.0"),
    )
    runs_conceded: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    wickets: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    best_bowled: Mapped[str | None] = mapped_column(String(20), nullable=True)
    maidens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    four_wicket_hauls: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    five_wicket_hauls: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    wides: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
    catches: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text("0")
    )
