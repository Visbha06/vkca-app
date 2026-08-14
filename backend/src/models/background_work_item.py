"""Durable transactional-outbox and background-processing state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin
from src.services.background_jobs.contracts import BackgroundWorkState


class BackgroundWorkItem(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """One authoritative background-work intent and its processing lifecycle."""

    __tablename__ = "background_work_items"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'scheduled', 'dispatching', 'dispatched', "
            "'running', 'retrying', 'completed', 'dead')",
            name="ck_background_work_items_state",
        ),
        CheckConstraint(
            "job_type ~ '^[a-z][a-z0-9_]{0,79}$'",
            name="ck_background_work_items_job_type_format",
        ),
        CheckConstraint(
            "payload_version BETWEEN 1 AND 32767",
            name="ck_background_work_items_payload_version_positive",
        ),
        CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_background_work_items_payload_json_object",
        ),
        CheckConstraint(
            "octet_length(payload::text) <= 16384",
            name="ck_background_work_items_payload_size",
        ),
        CheckConstraint(
            "jsonb_typeof(safe_metadata) = 'object'",
            name="ck_background_work_items_safe_metadata_json_object",
        ),
        CheckConstraint(
            "octet_length(safe_metadata::text) <= 4096",
            name="ck_background_work_items_safe_metadata_size",
        ),
        CheckConstraint(
            "dispatch_attempt_count >= 0 AND execution_attempt_count >= 0 "
            "AND manual_retry_count >= 0",
            name="ck_background_work_items_counters_nonnegative",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_background_work_items_version_positive",
        ),
        CheckConstraint(
            "(lease_owner IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_background_work_items_lease_pair",
        ),
        CheckConstraint(
            "last_failure_message IS NULL OR length(last_failure_message) <= 500",
            name="ck_background_work_items_failure_message_bounded",
        ),
        CheckConstraint(
            "retention_until IS NULL OR state IN ('completed', 'dead')",
            name="ck_background_work_items_retention_terminal",
        ),
        Index(
            "uq_background_work_items_job_idempotency",
            "job_type",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "uq_background_work_items_active_coalescing",
            "job_type",
            "coalescing_key",
            unique=True,
            postgresql_where=text(
                "coalescing_key IS NOT NULL AND state IN "
                "('pending', 'scheduled', 'dispatching', 'dispatched', 'retrying')"
            ),
        ),
        Index(
            "ix_background_work_items_eligible",
            "state",
            "run_after",
            "created_at",
            postgresql_where=text("state IN ('pending', 'scheduled', 'retrying')"),
        ),
        Index(
            "ix_background_work_items_recovery",
            "state",
            "lease_expires_at",
            postgresql_where=text("lease_expires_at IS NOT NULL"),
        ),
        Index(
            "ix_background_work_items_retention",
            "state",
            "retention_until",
            postgresql_where=text("retention_until IS NOT NULL"),
        ),
        Index(
            "ix_background_work_items_source",
            "source_type",
            "source_key",
        ),
    )

    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    state: Mapped[BackgroundWorkState] = mapped_column(
        String(20),
        nullable=False,
        default=BackgroundWorkState.PENDING,
        server_default=text("'pending'"),
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    coalescing_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=True
    )
    source_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    dispatch_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    execution_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    manual_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    arq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_retry_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
