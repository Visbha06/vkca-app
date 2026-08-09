"""Create the append-only business audit event table.

Revision ID: 012
Revises: 011
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: str | Sequence[str] | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create immutable business history without historical-ID foreign keys."""

    op.create_table(
        "business_audit_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_display_name", sa.String(length=201), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("action_category", sa.String(length=20), nullable=False),
        sa.Column("target_entity_type", sa.String(length=30), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_label", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_business_audit_events_created_at_id",
        "business_audit_events",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_business_audit_events_actor_user_id",
        "business_audit_events",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_business_audit_events_action_category",
        "business_audit_events",
        ["action_category"],
    )
    op.create_index(
        "ix_business_audit_events_action_type",
        "business_audit_events",
        ["action_type"],
    )
    op.create_index(
        "ix_business_audit_events_target",
        "business_audit_events",
        ["target_entity_type", "target_entity_id"],
    )


def downgrade() -> None:
    """Remove the business audit table and its retrieval indexes."""

    op.drop_index(
        "ix_business_audit_events_target",
        table_name="business_audit_events",
    )
    op.drop_index(
        "ix_business_audit_events_action_type",
        table_name="business_audit_events",
    )
    op.drop_index(
        "ix_business_audit_events_action_category",
        table_name="business_audit_events",
    )
    op.drop_index(
        "ix_business_audit_events_actor_user_id",
        table_name="business_audit_events",
    )
    op.drop_index(
        "ix_business_audit_events_created_at_id",
        table_name="business_audit_events",
    )
    op.drop_table("business_audit_events")
