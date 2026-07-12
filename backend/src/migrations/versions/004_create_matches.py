"""Create the matches table.

Revision ID: 004
Revises: 003
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | Sequence[str] | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create cricket match records."""

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("match_date", sa.Date(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("opponent_name", sa.String(length=200), nullable=False),
        sa.Column("venue", sa.String(length=200), nullable=False),
        sa.Column("result", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("format IN ('T20', 'one-day', 'test', 'other')", name="ck_matches_format"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop cricket match records."""

    op.drop_table("matches")
