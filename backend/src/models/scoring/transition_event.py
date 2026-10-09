"""Append-only explicit transition events used by deterministic replay."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import InningsTransitionType
from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.delivery_revision import DeliveryRevision
    from src.models.scoring.innings import Innings
    from src.models.scoring.participant import MatchParticipant
    from src.models.user import User


class InningsTransitionEvent(UUIDMixin, Base):
    """A scorer choice anchored to one stable delivery-history boundary."""

    __tablename__ = "innings_transition_events"
    __table_args__ = (
        CheckConstraint(
            "event_kind IN ('innings_started', 'next_batter', 'next_bowler', "
            "'retired_hurt', 'retired_hurt_return', 'innings_completed')",
            name="ck_innings_transition_events_kind",
        ),
        CheckConstraint(
            "anchored_attempted_sequence IS NULL OR anchored_attempted_sequence >= 1",
            name="ck_innings_transition_events_attempted_sequence",
        ),
        CheckConstraint(
            "over_number IS NULL OR over_number >= 0",
            name="ck_innings_transition_events_over_number",
        ),
        CheckConstraint(
            "reason IS NULL OR length(btrim(reason)) BETWEEN 1 AND 500",
            name="ck_innings_transition_events_reason",
        ),
        Index(
            "ix_innings_transition_events_replay_order",
            "innings_id",
            "anchored_attempted_sequence",
            "created_at",
            "id",
        ),
    )

    innings_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "innings.id",
            ondelete="CASCADE",
            name="fk_innings_transition_events_innings_id_innings",
        ),
        nullable=False,
    )
    event_kind: Mapped[InningsTransitionType] = mapped_column(
        String(32),
        nullable=False,
    )
    participant_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_transition_events_participant_id_match_participants",
        ),
        nullable=True,
    )
    anchored_attempted_sequence: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    anchored_revision_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "delivery_revisions.id",
            name="fk_innings_transition_events_revision_id_delivery_revisions",
        ),
        nullable=True,
    )
    over_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_innings_transition_events_created_by_user_id_users",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    innings: Mapped[Innings] = relationship(back_populates="transition_events")
    participant: Mapped[MatchParticipant | None] = relationship()
    anchored_revision: Mapped[DeliveryRevision | None] = relationship()
    created_by: Mapped[User] = relationship()
