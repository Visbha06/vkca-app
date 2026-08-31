"""Innings-specific batting order and participation state."""

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

from src.enums import ParticipationState
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.scoring.delivery import Delivery
    from src.models.scoring.innings import Innings
    from src.models.scoring.participant import MatchParticipant


class BattingOrderEntry(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A fixed participant's ordered and mutable state in one Innings."""

    __tablename__ = "innings_batting_entries"
    __table_args__ = (
        UniqueConstraint(
            "innings_id",
            "participant_id",
            name="uq_innings_batting_entries_participant",
        ),
        UniqueConstraint(
            "innings_id",
            "batting_order_position",
            name="uq_innings_batting_entries_position",
        ),
        CheckConstraint(
            "batting_order_position >= 1",
            name="ck_innings_batting_entries_position_positive",
        ),
        CheckConstraint(
            "participation_state IN ('not_batted', 'active', 'dismissed', "
            "'retired_hurt', 'retired_out', 'completed')",
            name="ck_innings_batting_entries_state",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_innings_batting_entries_version_positive",
        ),
        Index(
            "ix_innings_batting_entries_state",
            "innings_id",
            "participation_state",
        ),
        Index(
            "ix_innings_batting_entries_active",
            "innings_id",
            unique=False,
            postgresql_where=text("participation_state = 'active'"),
        ),
    )

    innings_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "innings.id",
            ondelete="CASCADE",
            name="fk_innings_batting_entries_innings_id_innings",
        ),
        nullable=False,
    )
    participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_innings_batting_entries_participant_id_match_participants",
        ),
        nullable=False,
    )
    batting_order_position: Mapped[int] = mapped_column(Integer, nullable=False)
    participation_state: Mapped[ParticipationState] = mapped_column(
        String(20),
        nullable=False,
        default=ParticipationState.NOT_BATTED,
        server_default=text("'not_batted'"),
    )
    dismissal_delivery_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "deliveries.id",
            name="fk_innings_batting_entries_dismissal_delivery_id_deliveries",
        ),
        nullable=True,
    )

    innings: Mapped[Innings] = relationship(back_populates="batting_entries")
    participant: Mapped[MatchParticipant] = relationship(
        back_populates="batting_entries"
    )
    dismissal_delivery: Mapped[Delivery | None] = relationship()
