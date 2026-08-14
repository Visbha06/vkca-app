"""Persisted safe canonical RAG document and intrinsic scope facets."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.rag_chunk import RagChunk
    from src.models.rag_source_state import RagSourceState


class RagDocument(Base):
    """Current safe canonical representation for one registered source."""

    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_type", "source_key", name="uq_rag_documents_source_identity"
        ),
        UniqueConstraint("source_state_id", name="uq_rag_documents_source_state_id"),
        Index("ix_rag_documents_source_type_key", "source_type", "source_key"),
        Index("ix_rag_documents_searchable_source", "is_searchable", "source_type"),
        Index("ix_rag_documents_player_ids_gin", "player_ids", postgresql_using="gin"),
        Index("ix_rag_documents_team_ids_gin", "team_ids", postgresql_using="gin"),
        Index("ix_rag_documents_age_groups_gin", "age_groups", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    source_state_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "rag_source_states.id",
            name="fk_rag_documents_source_state_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_entity_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=True
    )
    source_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    semantic_text: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    scope_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    player_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PostgreSQLUUID(as_uuid=True)),
        nullable=False,
        default=list,
        server_default=text("'{}'::uuid[]"),
    )
    team_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PostgreSQLUUID(as_uuid=True)),
        nullable=False,
        default=list,
        server_default=text("'{}'::uuid[]"),
    )
    age_groups: Mapped[list[str]] = mapped_column(
        ARRAY(String(10)),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
    )
    is_all_academy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    builder_version: Mapped[str] = mapped_column(String(80), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prepared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_searchable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    source_state: Mapped[RagSourceState] = relationship(
        back_populates="documents",
        foreign_keys=[source_state_id],
    )
    chunks: Mapped[list[RagChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
