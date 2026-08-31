"""Rebuildable structured-over projections."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.innings import Innings
    from src.models.scoring.participant import MatchParticipant


class InningsOver(UUIDMixin, TimestampMixin, Base):
    """Current projection for one numbered over in an Innings."""

    __tablename__ = "innings_overs"
    __table_args__ = (
        UniqueConstraint(
            "innings_id",
            "over_number",
            name="uq_innings_overs_innings_number",
        ),
        CheckConstraint(
            "over_number >= 0 AND legal_ball_count >= 0 "
            "AND total_runs BETWEEN 0 AND 2147483647 "
            "AND runs_conceded BETWEEN 0 AND 2147483647 "
            "AND wickets >= 0 AND projection_revision >= 0",
            name="ck_innings_overs_projection_values",
        ),
        Index("ix_innings_overs_projection", "innings_id", "projection_revision"),
    )

    innings_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "innings.id",
            ondelete="CASCADE",
            name="fk_innings_overs_innings_id_innings",
        ),
        nullable=False,
    )
    over_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bowler_participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_overs_bowler_id_match_participants",
        ),
        nullable=False,
    )
    legal_ball_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    total_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    runs_conceded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    wickets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    projection_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    innings: Mapped[Innings] = relationship(back_populates="overs")
    bowler: Mapped[MatchParticipant] = relationship()
