"""Append-only ORM model for academy business activity."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class BusinessAuditEvent(UUIDMixin, Base):
    """One immutable snapshot of a successful external business mutation.

    Historical identifiers deliberately have no foreign keys. Actor and target
    snapshots remain readable after their current domain records change or are
    removed. The model also intentionally avoids ``TimestampMixin`` because an
    audit event has no update timestamp.
    """

    __tablename__ = "business_audit_events"
    __table_args__ = (
        Index("ix_business_audit_events_created_at_id", "created_at", "id"),
        Index("ix_business_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_business_audit_events_action_category", "action_category"),
        Index("ix_business_audit_events_action_type", "action_type"),
        Index(
            "ix_business_audit_events_target",
            "target_entity_type",
            "target_entity_id",
        ),
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    actor_display_name: Mapped[str | None] = mapped_column(
        String(201),
        nullable=True,
    )
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    action_category: Mapped[str] = mapped_column(String(20), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_entity_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    target_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
