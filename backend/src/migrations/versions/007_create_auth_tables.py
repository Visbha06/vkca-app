"""Create authentication session and audit tables.

Revision ID: 007
Revises: 006
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | Sequence[str] | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_primary_key() -> sa.Column:
    """Build a PostgreSQL-generated UUID primary key column."""

    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    """Create session state and append-only authentication audit records."""

    op.create_table(
        "auth_sessions",
        _uuid_primary_key(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "rotated_token_hashes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=50), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "version_number",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "idx_auth_sessions_token_family", "auth_sessions", ["token_family_id"]
    )
    op.create_index(
        "idx_auth_sessions_current_hash", "auth_sessions", ["current_token_hash"]
    )
    op.create_index(
        "idx_auth_sessions_rotated_hashes",
        "auth_sessions",
        ["rotated_token_hashes"],
        postgresql_using="gin",
    )

    op.create_table(
        "auth_audit_log",
        _uuid_primary_key(),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("target_resource", sa.String(length=255), nullable=True),
        sa.Column(
            "event_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["auth_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_event_type", "auth_audit_log", ["event_type"])
    op.create_index("idx_audit_user_id", "auth_audit_log", ["user_id"])
    op.create_index("idx_audit_timestamp", "auth_audit_log", ["event_timestamp"])
    op.create_index(
        "idx_audit_event_type_timestamp",
        "auth_audit_log",
        ["event_type", "event_timestamp"],
    )


def downgrade() -> None:
    """Drop authentication audit records before their referenced sessions."""

    op.drop_index("idx_audit_event_type_timestamp", table_name="auth_audit_log")
    op.drop_index("idx_audit_timestamp", table_name="auth_audit_log")
    op.drop_index("idx_audit_user_id", table_name="auth_audit_log")
    op.drop_index("idx_audit_event_type", table_name="auth_audit_log")
    op.drop_table("auth_audit_log")
    op.drop_index("idx_auth_sessions_rotated_hashes", table_name="auth_sessions")
    op.drop_index("idx_auth_sessions_current_hash", table_name="auth_sessions")
    op.drop_index("idx_auth_sessions_token_family", table_name="auth_sessions")
    op.drop_index("idx_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
