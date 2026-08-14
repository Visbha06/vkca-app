"""Create the authorization-aware RAG indexing foundation.

Revision ID: 014
Revises: 013
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: str | Sequence[str] | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_primary_key() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _version_number() -> sa.Column:
    return sa.Column(
        "version_number",
        sa.Integer(),
        server_default=sa.text("1"),
        nullable=False,
    )


def _uuid_array(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
        server_default=sa.text("'{}'::uuid[]"),
        nullable=False,
    )


def _age_group_array() -> sa.Column:
    return sa.Column(
        "age_groups",
        postgresql.ARRAY(sa.String(length=10)),
        server_default=sa.text("'{}'::varchar[]"),
        nullable=False,
    )


def upgrade() -> None:
    """Enable pgvector and create run, source, document, and chunk state."""

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "rag_index_runs",
        _uuid_primary_key(),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'indexing'"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source_records_inspected",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "documents_prepared",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "chunks_generated",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "embeddings_created",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "unchanged_skipped",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "deleted_or_ineligible",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "failed_sources",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=50), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        _version_number(),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "mode IN ('full', 'incremental', 'targeted', 'repair')",
            name="ck_rag_index_runs_mode",
        ),
        sa.CheckConstraint(
            "status IN ('indexing', 'completed', 'partial', 'failed')",
            name="ck_rag_index_runs_status",
        ),
        sa.CheckConstraint(
            "source_records_inspected >= 0 AND documents_prepared >= 0 "
            "AND chunks_generated >= 0 AND embeddings_created >= 0 "
            "AND unchanged_skipped >= 0 AND deleted_or_ineligible >= 0 "
            "AND failed_sources >= 0",
            name="ck_rag_index_runs_counters_nonnegative",
        ),
        sa.CheckConstraint(
            "failure_message IS NULL OR length(failure_message) <= 500",
            name="ck_rag_index_runs_failure_message_bounded",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_rag_index_runs_version_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rag_index_runs_status_started_at",
        "rag_index_runs",
        ["status", "started_at"],
    )
    op.create_index(
        "ix_rag_index_runs_source_type",
        "rag_index_runs",
        ["source_type"],
    )

    op.create_table(
        "rag_source_states",
        _uuid_primary_key(),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column(
            "source_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "observed_source_version",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "observed_dependency_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "observed_content_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "last_successful_content_hash",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("builder_version", sa.String(length=80), nullable=False),
        sa.Column("chunking_version", sa.String(length=80), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "active_document_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_success_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("failure_code", sa.String(length=50), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "claim_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        _version_number(),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "status IN ('current', 'pending', 'stale', 'indexing', 'failed', "
            "'ineligible', 'deleted')",
            name="ck_rag_source_states_status",
        ),
        sa.CheckConstraint(
            "embedding_dimension = 1536",
            name="ck_rag_source_states_embedding_dimension",
        ),
        sa.CheckConstraint(
            "failure_message IS NULL OR length(failure_message) <= 500",
            name="ck_rag_source_states_failure_message_bounded",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_rag_source_states_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["claim_run_id"],
            ["rag_index_runs.id"],
            name="fk_rag_source_states_claim_run_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_key",
            name="uq_rag_source_states_source_identity",
        ),
    )
    op.create_index(
        "ix_rag_source_states_status", "rag_source_states", ["status"]
    )
    op.create_index(
        "ix_rag_source_states_source_type_status",
        "rag_source_states",
        ["source_type", "status"],
    )
    op.create_index(
        "ix_rag_source_states_last_attempt_at",
        "rag_source_states",
        ["last_attempt_at"],
    )
    op.create_index(
        "ix_rag_source_states_embedding_profile",
        "rag_source_states",
        ["provider_name", "model_name", "embedding_dimension"],
    )
    op.create_index(
        "ix_rag_source_states_active_document_id",
        "rag_source_states",
        ["active_document_id"],
    )
    op.create_index(
        "ix_rag_source_states_claim_lease",
        "rag_source_states",
        ["claim_run_id", "lease_expires_at"],
    )

    op.create_table(
        "rag_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_state_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column(
            "source_entity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("source_version", sa.String(length=255), nullable=True),
        sa.Column("semantic_text", sa.Text(), nullable=False),
        sa.Column(
            "provenance_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "scope_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _uuid_array("player_ids"),
        _uuid_array("team_ids"),
        _age_group_array(),
        sa.Column(
            "is_all_academy",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("builder_version", sa.String(length=80), nullable=False),
        sa.Column("chunking_version", sa.String(length=80), nullable=False),
        sa.Column(
            "prepared_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_searchable",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_state_id"],
            ["rag_source_states.id"],
            name="fk_rag_documents_source_state_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_key",
            name="uq_rag_documents_source_identity",
        ),
        sa.UniqueConstraint(
            "source_state_id",
            name="uq_rag_documents_source_state_id",
        ),
    )
    op.create_index(
        "ix_rag_documents_source_type_key",
        "rag_documents",
        ["source_type", "source_key"],
    )
    op.create_index(
        "ix_rag_documents_searchable_source",
        "rag_documents",
        ["is_searchable", "source_type"],
    )
    op.create_index(
        "ix_rag_documents_player_ids_gin",
        "rag_documents",
        ["player_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_rag_documents_team_ids_gin",
        "rag_documents",
        ["team_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_rag_documents_age_groups_gin",
        "rag_documents",
        ["age_groups"],
        postgresql_using="gin",
    )

    op.create_foreign_key(
        "fk_rag_source_states_active_document_id",
        "rag_source_states",
        "rag_documents",
        ["active_document_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "rag_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("semantic_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "provenance_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "scope_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _uuid_array("player_ids"),
        _uuid_array("team_ids"),
        _age_group_array(),
        sa.Column(
            "is_all_academy",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("builder_version", sa.String(length=80), nullable=False),
        sa.Column("chunking_version", sa.String(length=80), nullable=False),
        sa.Column(
            "is_searchable",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "ordinal >= 0",
            name="ck_rag_chunks_ordinal_nonnegative",
        ),
        sa.CheckConstraint(
            "embedding_dimension = 1536",
            name="ck_rag_chunks_embedding_dimension",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["rag_documents.id"],
            name="fk_rag_chunks_document_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "ordinal",
            name="uq_rag_chunks_document_ordinal",
        ),
    )
    op.create_index(
        "ix_rag_chunks_source_type_key",
        "rag_chunks",
        ["source_type", "source_key"],
    )
    op.create_index(
        "ix_rag_chunks_document_id",
        "rag_chunks",
        ["document_id"],
    )
    op.create_index(
        "ix_rag_chunks_searchable_source",
        "rag_chunks",
        ["is_searchable", "source_type"],
    )
    op.create_index(
        "ix_rag_chunks_embedding_profile",
        "rag_chunks",
        ["provider_name", "model_name", "embedding_dimension"],
    )
    op.create_index(
        "ix_rag_chunks_all_academy",
        "rag_chunks",
        ["is_all_academy"],
    )
    op.create_index(
        "ix_rag_chunks_player_ids_gin",
        "rag_chunks",
        ["player_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_rag_chunks_team_ids_gin",
        "rag_chunks",
        ["team_ids"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_rag_chunks_age_groups_gin",
        "rag_chunks",
        ["age_groups"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_rag_chunks_embedding_cosine_hnsw",
        "rag_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Remove disposable RAG state while retaining the shared vector extension."""

    op.drop_table("rag_chunks")
    op.drop_constraint(
        "fk_rag_source_states_active_document_id",
        "rag_source_states",
        type_="foreignkey",
    )
    op.drop_table("rag_documents")
    op.drop_table("rag_source_states")
    op.drop_table("rag_index_runs")

    # The database image and future features may also rely on pgvector. A safe
    # downgrade therefore leaves the extension installed and removes only the
    # schema objects owned by this revision.
