"""Match-scoped, innings-aware participant performance projections."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import PerformanceProvenance, ScoringDismissalType
from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.match import Match
    from src.models.scoring.innings import Innings
    from src.models.scoring.participant import MatchParticipant


class MatchParticipantPerformance(UUIDMixin, TimestampMixin, Base):
    """Canonical participant figures derived from delivery history."""

    __tablename__ = "match_participant_performances"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "innings_id",
            "participant_id",
            name="uq_match_participant_performances_innings_participant",
        ),
        CheckConstraint(
            "dismissal_type IS NULL OR dismissal_type IN "
            "('bowled', 'caught', 'caught_and_bowled', 'lbw', 'run_out', "
            "'stumped', 'hit_wicket', 'retired_out')",
            name="ck_match_participant_performances_dismissal",
        ),
        CheckConstraint(
            "provenance = 'delivery_derived'",
            name="ck_match_participant_performances_provenance",
        ),
        CheckConstraint(
            "batting_runs BETWEEN 0 AND 2147483647 "
            "AND runs_conceded BETWEEN 0 AND 2147483647 "
            "AND extras_conceded BETWEEN 0 AND 2147483647",
            name="ck_match_participant_performances_run_bounds",
        ),
        CheckConstraint(
            "balls_faced >= 0 AND fours >= 0 AND sixes >= 0 "
            "AND bowling_legal_balls >= 0 AND bowling_wickets >= 0 "
            "AND wides >= 0 AND no_balls >= 0 AND catches >= 0 "
            "AND stumpings >= 0 AND run_out_involvements >= 0 "
            "AND projection_revision >= 0",
            name="ck_match_participant_performances_counts",
        ),
        Index(
            "ix_match_participant_performances_match_projection",
            "match_id",
            "projection_revision",
        ),
        Index(
            "ix_match_participant_performances_participant",
            "participant_id",
        ),
    )

    match_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "matches.id",
            ondelete="CASCADE",
            name="fk_match_participant_performances_match_id_matches",
        ),
        nullable=False,
    )
    innings_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "innings.id",
            ondelete="CASCADE",
            name="fk_match_participant_performances_innings_id_innings",
        ),
        nullable=False,
    )
    participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_match_participant_performances_participant",
        ),
        nullable=False,
    )
    batting_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    balls_faced: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    fours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    sixes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    dismissal_type: Mapped[ScoringDismissalType | None] = mapped_column(
        String(32),
        nullable=True,
    )
    bowling_legal_balls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    runs_conceded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bowling_wickets: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    wides: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    no_balls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    extras_conceded: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    catches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    stumpings: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    run_out_involvements: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    projection_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    provenance: Mapped[PerformanceProvenance] = mapped_column(
        String(24),
        nullable=False,
        default=PerformanceProvenance.DELIVERY_DERIVED,
        server_default=text("'delivery_derived'"),
    )

    match: Mapped[Match] = relationship(back_populates="scoring_performances")
    innings: Mapped[Innings] = relationship(
        back_populates="match_participant_performances"
    )
    participant: Mapped[MatchParticipant] = relationship()
