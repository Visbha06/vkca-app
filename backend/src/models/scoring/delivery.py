"""Stable attempted-delivery parents."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.delivery_revision import DeliveryRevision
    from src.models.scoring.innings import Innings


class Delivery(UUIDMixin, Base):
    """Immutable identity for one observed attempt in an Innings."""

    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint(
            "innings_id",
            "attempted_sequence",
            name="uq_deliveries_innings_attempted_sequence",
        ),
        CheckConstraint(
            "attempted_sequence >= 1",
            name="ck_deliveries_attempted_sequence_positive",
        ),
        Index(
            "ix_deliveries_innings_sequence",
            "innings_id",
            "attempted_sequence",
        ),
    )

    innings_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "innings.id",
            ondelete="CASCADE",
            name="fk_deliveries_innings_id_innings",
        ),
        nullable=False,
    )
    attempted_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    innings: Mapped[Innings] = relationship(back_populates="deliveries")
    revisions: Mapped[list[DeliveryRevision]] = relationship(
        back_populates="delivery",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DeliveryRevision.revision_number",
    )
