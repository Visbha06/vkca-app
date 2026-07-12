"""Cricket match database model."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from src.enums import MatchFormat
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class Match(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A recorded cricket match and its outcome."""

    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "format IN ('T20', 'one-day', 'test', 'other')",
            name="ck_matches_format",
        ),
    )

    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    format: Mapped[MatchFormat] = mapped_column(String(20), nullable=False)
    opponent_name: Mapped[str] = mapped_column(String(200), nullable=False)
    venue: Mapped[str] = mapped_column(String(200), nullable=False)
    result: Mapped[str] = mapped_column(String(200), nullable=False)
