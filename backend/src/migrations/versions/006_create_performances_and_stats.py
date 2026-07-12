"""Create performance and aggregate statistics tables.

Revision ID: 006
Revises: 005
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | Sequence[str] | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_and_version_columns() -> list[sa.Column]:
    """Build the server-managed columns shared by all five tables."""

    return [
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
    ]


def _uuid_primary_key() -> sa.Column:
    """Build a PostgreSQL-generated UUID primary key column."""

    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    """Create source performance records and derived career totals."""

    op.create_table(
        "match_batting_performances",
        _uuid_primary_key(),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runs_scored", sa.Integer(), server_default="0", nullable=False),
        sa.Column("balls_faced", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "dismissal",
            sa.String(length=20),
            server_default="not out",
            nullable=False,
        ),
        sa.Column("fours", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sixes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_and_version_columns(),
        sa.CheckConstraint(
            "dismissal IN ('not out', 'caught', 'bowled', 'lbw', "
            "'run out', 'stumped', 'other')",
            name="ck_match_batting_performances_dismissal",
        ),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "match_id",
            name="uq_match_batting_performances_player_match",
        ),
    )
    op.create_index(
        "ix_match_batting_performances_match_id",
        "match_batting_performances",
        ["match_id"],
    )

    op.create_table(
        "match_bowling_performances",
        _uuid_primary_key(),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "overs_bowled",
            sa.Numeric(precision=5, scale=1),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column("maidens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("runs_conceded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wickets_taken", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wides", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_and_version_columns(),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "match_id",
            name="uq_match_bowling_performances_player_match",
        ),
    )
    op.create_index(
        "ix_match_bowling_performances_match_id",
        "match_bowling_performances",
        ["match_id"],
    )

    op.create_table(
        "match_fielding_performances",
        _uuid_primary_key(),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("catches", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stumpings", sa.Integer(), server_default="0", nullable=False),
        sa.Column("run_outs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("dropped_catches", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_and_version_columns(),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "match_id",
            name="uq_match_fielding_performances_player_match",
        ),
    )
    op.create_index(
        "ix_match_fielding_performances_match_id",
        "match_fielding_performances",
        ["match_id"],
    )

    op.create_table(
        "player_batting_stats",
        _uuid_primary_key(),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("matches", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("innings", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("not_outs", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("runs", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("balls_faced", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("high_score", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("hundreds", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("fifties", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("ducks", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("fours", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("sixes", sa.BigInteger(), server_default="0", nullable=False),
        *_timestamp_and_version_columns(),
        sa.CheckConstraint(
            "format IN ('T20', 'one-day', 'test', 'other')",
            name="ck_player_batting_stats_format",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "format",
            name="uq_player_batting_stats_player_format",
        ),
    )

    op.create_table(
        "player_bowling_stats",
        _uuid_primary_key(),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("matches", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("innings", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "overs_bowled",
            sa.Numeric(precision=7, scale=1),
            server_default="0.0",
            nullable=False,
        ),
        sa.Column("runs_conceded", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("wickets", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("best_bowled", sa.String(length=20), nullable=True),
        sa.Column("maidens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "four_wicket_hauls",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "five_wicket_hauls",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("wides", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("catches", sa.BigInteger(), server_default="0", nullable=False),
        *_timestamp_and_version_columns(),
        sa.CheckConstraint(
            "format IN ('T20', 'one-day', 'test', 'other')",
            name="ck_player_bowling_stats_format",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "format",
            name="uq_player_bowling_stats_player_format",
        ),
    )


def downgrade() -> None:
    """Drop aggregate tables before their source performance tables."""

    op.drop_table("player_bowling_stats")
    op.drop_table("player_batting_stats")
    op.drop_index(
        "ix_match_fielding_performances_match_id",
        table_name="match_fielding_performances",
    )
    op.drop_table("match_fielding_performances")
    op.drop_index(
        "ix_match_bowling_performances_match_id",
        table_name="match_bowling_performances",
    )
    op.drop_table("match_bowling_performances")
    op.drop_index(
        "ix_match_batting_performances_match_id",
        table_name="match_batting_performances",
    )
    op.drop_table("match_batting_performances")
