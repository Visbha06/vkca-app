"""Add durable background-processing state.

Revision ID: 015
Revises: 014
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the versioned transactional-outbox work table and indexes."""

    op.create_table(
        "background_work_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("payload_version", sa.SmallInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "state",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("coalescing_key", sa.String(length=255), nullable=True),
        sa.Column(
            "correlation_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_key", sa.String(length=255), nullable=True),
        sa.Column(
            "safe_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "run_after",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "dispatch_attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "execution_attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "manual_retry_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("arq_job_id", sa.String(length=255), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_category", sa.String(length=50), nullable=True),
        sa.Column("last_failure_message", sa.Text(), nullable=True),
        sa.Column(
            "manual_retry_allowed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version_number",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'scheduled', 'dispatching', 'dispatched', "
            "'running', 'retrying', 'completed', 'dead')",
            name="ck_background_work_items_state",
        ),
        sa.CheckConstraint(
            "job_type ~ '^[a-z][a-z0-9_]{0,79}$'",
            name="ck_background_work_items_job_type_format",
        ),
        sa.CheckConstraint(
            "payload_version BETWEEN 1 AND 32767",
            name="ck_background_work_items_payload_version_positive",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_background_work_items_payload_json_object",
        ),
        sa.CheckConstraint(
            "octet_length(payload::text) <= 16384",
            name="ck_background_work_items_payload_size",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(safe_metadata) = 'object'",
            name="ck_background_work_items_safe_metadata_json_object",
        ),
        sa.CheckConstraint(
            "octet_length(safe_metadata::text) <= 4096",
            name="ck_background_work_items_safe_metadata_size",
        ),
        sa.CheckConstraint(
            "dispatch_attempt_count >= 0 AND execution_attempt_count >= 0 "
            "AND manual_retry_count >= 0",
            name="ck_background_work_items_counters_nonnegative",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_background_work_items_version_positive",
        ),
        sa.CheckConstraint(
            "(lease_owner IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_background_work_items_lease_pair",
        ),
        sa.CheckConstraint(
            "last_failure_message IS NULL OR length(last_failure_message) <= 500",
            name="ck_background_work_items_failure_message_bounded",
        ),
        sa.CheckConstraint(
            "retention_until IS NULL OR state IN ('completed', 'dead')",
            name="ck_background_work_items_retention_terminal",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_background_work_items"),
    )
    op.create_index(
        "uq_background_work_items_job_idempotency",
        "background_work_items",
        ["job_type", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_background_work_items_active_coalescing",
        "background_work_items",
        ["job_type", "coalescing_key"],
        unique=True,
        postgresql_where=sa.text(
            "coalescing_key IS NOT NULL AND state IN "
            "('pending', 'scheduled', 'dispatching', 'dispatched', 'retrying')"
        ),
    )
    op.create_index(
        "ix_background_work_items_eligible",
        "background_work_items",
        ["state", "run_after", "created_at"],
        unique=False,
        postgresql_where=sa.text("state IN ('pending', 'scheduled', 'retrying')"),
    )
    op.create_index(
        "ix_background_work_items_recovery",
        "background_work_items",
        ["state", "lease_expires_at"],
        unique=False,
        postgresql_where=sa.text("lease_expires_at IS NOT NULL"),
    )
    op.create_index(
        "ix_background_work_items_retention",
        "background_work_items",
        ["state", "retention_until"],
        unique=False,
        postgresql_where=sa.text("retention_until IS NOT NULL"),
    )
    op.create_index(
        "ix_background_work_items_source",
        "background_work_items",
        ["source_type", "source_key"],
        unique=False,
    )


def downgrade() -> None:
    """Remove durable processing state while preserving revision 014 data."""

    op.drop_table("background_work_items")
