"""Create the players table.

Revision ID: 002
Revises: 001
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | Sequence[str] | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create player profiles and their data-integrity constraints."""

    op.create_table(
        "players",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("batting_style", sa.String(length=10), nullable=False),
        sa.Column("bowling_style", sa.String(length=30), nullable=False),
        sa.Column("player_type", sa.String(length=20), nullable=False),
        sa.Column(
            "player_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.Column(
            "version_number",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "batting_style IN ('right', 'left')",
            name="ck_players_batting_style",
        ),
        sa.CheckConstraint(
            "bowling_style IN ("
            "'right-arm fast', 'right-arm medium', 'right-arm off-break', "
            "'right-arm leg-break', 'left-arm fast', 'left-arm medium', "
            "'left-arm orthodox', 'left-arm unorthodox')",
            name="ck_players_bowling_style",
        ),
        sa.CheckConstraint(
            "player_type IN ('batter', 'bowler', 'all-rounder', 'wicket-keeper')",
            name="ck_players_player_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "first_name",
            "last_name",
            "date_of_birth",
            name="uq_players_name_date_of_birth",
        ),
    )


def downgrade() -> None:
    """Drop player profiles."""

    op.drop_table("players")
