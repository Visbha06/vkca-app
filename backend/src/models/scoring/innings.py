"""Ordered Innings aggregate and persisted current-state projection."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import (
    InningsCompletionMode,
    InningsLifecycleState,
    InningsReconciliationReason,
)
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.match import Match
    from src.models.scoring.batting_entry import BattingOrderEntry
    from src.models.scoring.delivery import Delivery
    from src.models.scoring.match_participant_performance import (
        MatchParticipantPerformance,
    )
    from src.models.scoring.match_side import MatchSide
    from src.models.scoring.over import InningsOver
    from src.models.scoring.participant import MatchParticipant
    from src.models.scoring.participant_summary import InningsParticipantSummary
    from src.models.scoring.transition_event import InningsTransitionEvent


class Innings(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """One capability-ordered batting phase and its reconcilable projection."""

    __tablename__ = "innings"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "innings_number",
            name="uq_innings_match_number",
        ),
        CheckConstraint(
            "innings_number >= 1",
            name="ck_innings_number_positive",
        ),
        CheckConstraint(
            "batting_side_id <> fielding_side_id",
            name="ck_innings_distinct_sides",
        ),
        CheckConstraint(
            "lifecycle_state IN "
            "('pending', 'in_progress', 'completed', 'reconciliation_required')",
            name="ck_innings_lifecycle_state",
        ),
        CheckConstraint(
            "(lifecycle_state = 'reconciliation_required' "
            "AND reconciliation_reason IS NOT NULL) OR "
            "(lifecycle_state <> 'reconciliation_required' "
            "AND reconciliation_reason IS NULL)",
            name="ck_innings_reconciliation_reason",
        ),
        CheckConstraint(
            "reconciliation_reason IS NULL OR "
            "reconciliation_reason = 'incompatible_replay'",
            name="ck_innings_reconciliation_reason_value",
        ),
        CheckConstraint(
            "striker_participant_id IS NULL OR non_striker_participant_id IS NULL "
            "OR striker_participant_id <> non_striker_participant_id",
            name="ck_innings_distinct_active_batters",
        ),
        CheckConstraint(
            "legal_balls >= 0 AND total_runs BETWEEN 0 AND 2147483647 "
            "AND wickets_lost >= 0 AND projection_revision >= 0 "
            "AND version_number >= 1",
            name="ck_innings_projection_values",
        ),
        CheckConstraint(
            "target_runs IS NULL OR target_runs BETWEEN 1 AND 2147483647",
            name="ck_innings_target_runs",
        ),
        CheckConstraint(
            "completion_reason IS NULL OR completion_reason IN "
            "('all_out', 'legal_ball_limit', 'target_reached', "
            "'declaration', 'manual')",
            name="ck_innings_completion_reason",
        ),
        CheckConstraint(
            "jsonb_typeof(state_snapshot) = 'object'",
            name="ck_innings_state_snapshot_object",
        ),
        CheckConstraint(
            "octet_length(state_snapshot::text) <= 16384",
            name="ck_innings_state_snapshot_bounded",
        ),
        Index("ix_innings_match_lifecycle", "match_id", "lifecycle_state"),
    )

    match_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "matches.id",
            ondelete="CASCADE",
            name="fk_innings_match_id_matches",
        ),
        nullable=False,
    )
    innings_number: Mapped[int] = mapped_column(Integer, nullable=False)
    batting_side_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_sides.id",
            name="fk_innings_batting_side_id_match_sides",
        ),
        nullable=False,
    )
    fielding_side_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_sides.id",
            name="fk_innings_fielding_side_id_match_sides",
        ),
        nullable=False,
    )
    lifecycle_state: Mapped[InningsLifecycleState] = mapped_column(
        String(32),
        nullable=False,
        default=InningsLifecycleState.PENDING,
        server_default=text("'pending'"),
    )
    reconciliation_reason: Mapped[InningsReconciliationReason | None] = mapped_column(
        String(64),
        nullable=True,
    )
    striker_participant_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_striker_id_match_participants",
        ),
        nullable=True,
    )
    non_striker_participant_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_non_striker_id_match_participants",
        ),
        nullable=True,
    )
    current_bowler_participant_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_current_bowler_id_match_participants",
        ),
        nullable=True,
    )
    legal_balls: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    total_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    wickets_lost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    target_runs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_reason: Mapped[InningsCompletionMode | None] = mapped_column(
        String(24),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    projection_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    match: Mapped[Match] = relationship(back_populates="scoring_innings")
    batting_side: Mapped[MatchSide] = relationship(
        back_populates="batting_innings",
        foreign_keys=[batting_side_id],
    )
    fielding_side: Mapped[MatchSide] = relationship(
        back_populates="fielding_innings",
        foreign_keys=[fielding_side_id],
    )
    striker: Mapped[MatchParticipant | None] = relationship(
        foreign_keys=[striker_participant_id]
    )
    non_striker: Mapped[MatchParticipant | None] = relationship(
        foreign_keys=[non_striker_participant_id]
    )
    current_bowler: Mapped[MatchParticipant | None] = relationship(
        foreign_keys=[current_bowler_participant_id]
    )
    batting_entries: Mapped[list[BattingOrderEntry]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    deliveries: Mapped[list[Delivery]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    transition_events: Mapped[list[InningsTransitionEvent]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    overs: Mapped[list[InningsOver]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    participant_summaries: Mapped[list[InningsParticipantSummary]] = relationship(
        back_populates="innings",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    match_participant_performances: Mapped[list[MatchParticipantPerformance]] = (
        relationship(back_populates="innings")
    )

    @property
    def blocking_state(self) -> dict[str, Any] | None:
        """Expose the canonical snapshot member without creating another state."""

        value = self.state_snapshot.get("blocking_state")
        return value if isinstance(value, dict) else None
