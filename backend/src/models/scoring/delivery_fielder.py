"""Canonical ordered fielder associations for one delivery revision."""

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
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import FielderRole
from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.delivery_revision import DeliveryRevision
    from src.models.scoring.participant import MatchParticipant


class DeliveryFielder(UUIDMixin, Base):
    """A Match participant's ordered role in a delivery's wicket detail."""

    __tablename__ = "delivery_fielders"
    __table_args__ = (
        UniqueConstraint(
            "delivery_revision_id",
            "ordinal",
            name="uq_delivery_fielders_revision_ordinal",
        ),
        UniqueConstraint(
            "delivery_revision_id",
            "participant_id",
            "role",
            name="uq_delivery_fielders_revision_participant_role",
        ),
        CheckConstraint(
            "ordinal >= 1",
            name="ck_delivery_fielders_ordinal_positive",
        ),
        CheckConstraint(
            "role IN ('bowler', 'catcher', 'thrower', 'keeper', 'assister', 'other')",
            name="ck_delivery_fielders_role",
        ),
        Index(
            "ix_delivery_fielders_revision_order",
            "delivery_revision_id",
            "ordinal",
        ),
        Index("ix_delivery_fielders_participant_id", "participant_id"),
    )

    delivery_revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "delivery_revisions.id",
            ondelete="CASCADE",
            name="fk_delivery_fielders_revision_id_delivery_revisions",
        ),
        nullable=False,
    )
    participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_delivery_fielders_participant_id_match_participants",
        ),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[FielderRole] = mapped_column(String(16), nullable=False)

    delivery_revision: Mapped[DeliveryRevision] = relationship(
        back_populates="fielders"
    )
    participant: Mapped[MatchParticipant] = relationship()
