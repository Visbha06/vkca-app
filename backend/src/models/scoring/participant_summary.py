"""Rebuildable per-Innings participant summaries."""

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

from src.enums import ParticipationState, ScoringDismissalType
from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.innings import Innings
    from src.models.scoring.participant import MatchParticipant


class InningsParticipantSummary(UUIDMixin, TimestampMixin, Base):
    """Batting, bowling, and fielding figures for one Innings participant."""

    __tablename__ = "innings_participant_summaries"
    __table_args__ = (
        UniqueConstraint(
            "innings_id",
            "participant_id",
            name="uq_innings_participant_summaries_participant",
        ),
        CheckConstraint(
            "participation_state IN ('not_batted', 'active', 'dismissed', "
            "'retired_hurt', 'retired_out', 'completed')",
            name="ck_innings_participant_summaries_state",
        ),
        CheckConstraint(
            "dismissal_type IS NULL OR dismissal_type IN "
            "('bowled', 'caught', 'caught_and_bowled', 'lbw', 'run_out', "
            "'stumped', 'hit_wicket', 'retired_out')",
            name="ck_innings_participant_summaries_dismissal",
        ),
        CheckConstraint(
            "batting_runs BETWEEN 0 AND 2147483647 "
            "AND runs_conceded BETWEEN 0 AND 2147483647",
            name="ck_innings_participant_summaries_run_bounds",
        ),
        CheckConstraint(
            "balls_faced >= 0 AND fours >= 0 AND sixes >= 0 "
            "AND bowling_legal_balls >= 0 AND bowling_overs_completed >= 0 "
            "AND bowling_balls_in_partial_over >= 0 AND bowling_wickets >= 0 "
            "AND wides >= 0 AND no_balls >= 0 AND fielding_dismissals >= 0 "
            "AND projection_revision >= 0",
            name="ck_innings_participant_summaries_counts",
        ),
        Index(
            "ix_innings_participant_summaries_projection",
            "innings_id",
            "projection_revision",
        ),
    )

    innings_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "innings.id",
            ondelete="CASCADE",
            name="fk_innings_participant_summaries_innings_id_innings",
        ),
        nullable=False,
    )
    participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_participant_summaries_participant",
        ),
        nullable=False,
    )
    participation_state: Mapped[ParticipationState] = mapped_column(
        String(20),
        nullable=False,
        default=ParticipationState.NOT_BATTED,
        server_default=text("'not_batted'"),
    )
    dismissal_type: Mapped[ScoringDismissalType | None] = mapped_column(
        String(32),
        nullable=True,
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
    bowling_legal_balls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bowling_overs_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bowling_balls_in_partial_over: Mapped[int] = mapped_column(
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
    fielding_dismissals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    projection_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    innings: Mapped[Innings] = relationship(back_populates="participant_summaries")
    participant: Mapped[MatchParticipant] = relationship()
