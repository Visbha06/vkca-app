"""Technical run-level state for RAG indexing operations."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin
from src.services.rag.contracts import RagRunMode, RagRunStatus

if TYPE_CHECKING:
    from src.models.rag_source_state import RagSourceState


class RagIndexRun(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """One bounded technical indexing operation with aggregate safe counters."""

    __tablename__ = "rag_index_runs"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('full', 'incremental', 'targeted', 'repair')",
            name="ck_rag_index_runs_mode",
        ),
        CheckConstraint(
            "status IN ('indexing', 'completed', 'partial', 'failed')",
            name="ck_rag_index_runs_status",
        ),
        CheckConstraint(
            "source_records_inspected >= 0 AND documents_prepared >= 0 "
            "AND chunks_generated >= 0 AND embeddings_created >= 0 "
            "AND unchanged_skipped >= 0 AND deleted_or_ineligible >= 0 "
            "AND failed_sources >= 0",
            name="ck_rag_index_runs_counters_nonnegative",
        ),
        CheckConstraint(
            "failure_message IS NULL OR length(failure_message) <= 500",
            name="ck_rag_index_runs_failure_message_bounded",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_rag_index_runs_version_positive",
        ),
        Index("ix_rag_index_runs_status_started_at", "status", "started_at"),
        Index("ix_rag_index_runs_source_type", "source_type"),
    )

    mode: Mapped[RagRunMode] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[RagRunStatus] = mapped_column(
        String(20),
        nullable=False,
        default=RagRunStatus.INDEXING,
        server_default=text("'indexing'"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_records_inspected: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    documents_prepared: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    chunks_generated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    embeddings_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    unchanged_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    deleted_or_ineligible: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failed_sources: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    claimed_source_states: Mapped[list[RagSourceState]] = relationship(
        back_populates="claim_run",
        foreign_keys="RagSourceState.claim_run_id",
        passive_deletes=True,
    )
