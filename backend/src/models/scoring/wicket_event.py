"""One explicit wicket event attached to an immutable delivery revision."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import DismissedEnd, ScoringDismissalType
from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.delivery_revision import DeliveryRevision
    from src.models.scoring.participant import MatchParticipant


class WicketEvent(UUIDMixin, TimestampMixin, Base):
    """Canonical zero-or-one dismissal detail for a delivery revision."""

    __tablename__ = "wicket_events"
    __table_args__ = (
        UniqueConstraint(
            "delivery_revision_id",
            name="uq_wicket_events_delivery_revision_id",
        ),
        CheckConstraint(
            "dismissal_type IN ('bowled', 'caught', 'caught_and_bowled', "
            "'lbw', 'run_out', 'stumped', 'hit_wicket', 'retired_out')",
            name="ck_wicket_events_dismissal_type",
        ),
        CheckConstraint(
            "(dismissal_type = 'run_out' AND dismissed_end IS NOT NULL) OR "
            "(dismissal_type <> 'run_out' AND dismissed_end IS NULL)",
            name="ck_wicket_events_dismissed_end",
        ),
        CheckConstraint(
            "dismissed_end IS NULL OR "
            "dismissed_end IN ('striker_end', 'non_striker_end')",
            name="ck_wicket_events_dismissed_end_value",
        ),
        CheckConstraint(
            "notes IS NULL OR length(btrim(notes)) BETWEEN 1 AND 500",
            name="ck_wicket_events_notes",
        ),
    )

    delivery_revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "delivery_revisions.id",
            ondelete="CASCADE",
            name="fk_wicket_events_revision_id_delivery_revisions",
        ),
        nullable=False,
    )
    dismissal_type: Mapped[ScoringDismissalType] = mapped_column(
        String(32),
        nullable=False,
    )
    dismissed_participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_wicket_events_dismissed_id_match_participants",
        ),
        nullable=False,
    )
    dismissed_end: Mapped[DismissedEnd | None] = mapped_column(
        String(24),
        nullable=True,
    )
    counts_as_team_wicket: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credited_to_bowler: Mapped[bool] = mapped_column(Boolean, nullable=False)
    primary_fielder_participant_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_wicket_events_primary_fielder_id_match_participants",
        ),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    delivery_revision: Mapped[DeliveryRevision] = relationship(
        back_populates="wicket_event"
    )
    dismissed_participant: Mapped[MatchParticipant] = relationship(
        foreign_keys=[dismissed_participant_id]
    )
    primary_fielder: Mapped[MatchParticipant | None] = relationship(
        foreign_keys=[primary_fielder_participant_id]
    )
