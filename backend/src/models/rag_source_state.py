"""Per-source synchronization, compatibility, lease, and failure state."""

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
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin
from src.services.rag.contracts import RagSourceStatus

if TYPE_CHECKING:
    from src.models.rag_document import RagDocument
    from src.models.rag_index_run import RagIndexRun


class RagSourceState(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """Latest observed and last-successful state for one registered identity."""

    __tablename__ = "rag_source_states"
    __table_args__ = (
        CheckConstraint(
            "status IN ('current', 'pending', 'stale', 'indexing', 'failed', "
            "'ineligible', 'deleted')",
            name="ck_rag_source_states_status",
        ),
        CheckConstraint(
            "embedding_dimension = 1536",
            name="ck_rag_source_states_embedding_dimension",
        ),
        CheckConstraint(
            "failure_message IS NULL OR length(failure_message) <= 500",
            name="ck_rag_source_states_failure_message_bounded",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_rag_source_states_version_positive",
        ),
        UniqueConstraint(
            "source_type",
            "source_key",
            name="uq_rag_source_states_source_identity",
        ),
        Index("ix_rag_source_states_status", "status"),
        Index("ix_rag_source_states_source_type_status", "source_type", "status"),
        Index("ix_rag_source_states_last_attempt_at", "last_attempt_at"),
        Index(
            "ix_rag_source_states_embedding_profile",
            "provider_name",
            "model_name",
            "embedding_dimension",
        ),
        Index("ix_rag_source_states_active_document_id", "active_document_id"),
        Index("ix_rag_source_states_claim_lease", "claim_run_id", "lease_expires_at"),
    )

    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_entity_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=True
    )
    observed_source_version: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    observed_dependency_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    observed_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_successful_content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    builder_version: Mapped[str] = mapped_column(String(80), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RagSourceStatus] = mapped_column(String(20), nullable=False)
    active_document_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "rag_documents.id",
            name="fk_rag_source_states_active_document_id",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "rag_index_runs.id",
            name="fk_rag_source_states_claim_run_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    claim_run: Mapped[RagIndexRun | None] = relationship(
        back_populates="claimed_source_states",
        foreign_keys=[claim_run_id],
    )
    documents: Mapped[list[RagDocument]] = relationship(
        back_populates="source_state",
        foreign_keys="RagDocument.source_state_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    active_document: Mapped[RagDocument | None] = relationship(
        foreign_keys=[active_document_id],
        post_update=True,
    )
