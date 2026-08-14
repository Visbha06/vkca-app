"""Persisted embedded RAG chunk with denormalized intrinsic scope facets."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.models.rag_document import RagDocument


class RagChunk(TimestampMixin, Base):
    """One searchable, deterministic child with a validated vector(1536)."""

    __tablename__ = "rag_chunks"
    __table_args__ = (
        CheckConstraint("ordinal >= 0", name="ck_rag_chunks_ordinal_nonnegative"),
        CheckConstraint(
            "embedding_dimension = 1536",
            name="ck_rag_chunks_embedding_dimension",
        ),
        UniqueConstraint(
            "document_id", "ordinal", name="uq_rag_chunks_document_ordinal"
        ),
        Index("ix_rag_chunks_source_type_key", "source_type", "source_key"),
        Index("ix_rag_chunks_document_id", "document_id"),
        Index("ix_rag_chunks_searchable_source", "is_searchable", "source_type"),
        Index(
            "ix_rag_chunks_embedding_profile",
            "provider_name",
            "model_name",
            "embedding_dimension",
        ),
        Index("ix_rag_chunks_all_academy", "is_all_academy"),
        Index("ix_rag_chunks_player_ids_gin", "player_ids", postgresql_using="gin"),
        Index("ix_rag_chunks_team_ids_gin", "team_ids", postgresql_using="gin"),
        Index("ix_rag_chunks_age_groups_gin", "age_groups", postgresql_using="gin"),
        Index(
            "ix_rag_chunks_embedding_cosine_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "rag_documents.id",
            name="fk_rag_chunks_document_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    semantic_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
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
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    builder_version: Mapped[str] = mapped_column(String(80), nullable=False)
    chunking_version: Mapped[str] = mapped_column(String(80), nullable=False)
    is_searchable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    document: Mapped[RagDocument] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        """Expose identity only; never render semantic text or raw vectors."""

        return (
            f"RagChunk(id={self.id!r}, source_type={self.source_type!r}, "
            f"ordinal={self.ordinal!r})"
        )
