"""Add Player account links and unambiguous Match participants.

Revision ID: 013
Revises: 012
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: str | Sequence[str] | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _assert_legacy_matches_are_empty() -> None:
    """Refuse to invent academy participants for opponent-only records."""

    op.execute(
        sa.text(
            """
            DO $role_aware_dashboard$
            BEGIN
                IF EXISTS (SELECT 1 FROM matches) THEN
                    RAISE EXCEPTION
                        'Revision 013 cannot infer participants for existing matches';
                END IF;
            END
            $role_aware_dashboard$
            """
        )
    )


def _assert_no_internal_matches_for_downgrade() -> None:
    """Prevent a downgrade that would silently discard an academy Team."""

    op.execute(
        sa.text(
            """
            DO $role_aware_dashboard$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM matches
                    WHERE participant_type = 'internal'
                ) THEN
                    RAISE EXCEPTION
                        'Revision 013 cannot downgrade internal matches to one opponent';
                END IF;
            END
            $role_aware_dashboard$
            """
        )
    )


def upgrade() -> None:
    """Add reversible account linkage and final Match participant semantics."""

    _assert_legacy_matches_are_empty()

    op.add_column(
        "players",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_players_user_id_users",
        "players",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_players_user_id",
        "players",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    op.add_column(
        "matches",
        sa.Column("participant_type", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column(
            "home_team_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "away_team_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "external_opponent_name",
            sa.String(length=200),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_matches_home_team_id_teams",
        "matches",
        "teams",
        ["home_team_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_matches_away_team_id_teams",
        "matches",
        "teams",
        ["away_team_id"],
        ["id"],
    )
    op.drop_column("matches", "opponent_name")
    op.alter_column(
        "matches",
        "participant_type",
        existing_type=sa.String(length=8),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_matches_participant_type",
        "matches",
        "participant_type IN ('external', 'internal')",
    )
    op.create_check_constraint(
        "ck_matches_participants",
        "matches",
        "(participant_type = 'external' "
        "AND external_opponent_name IS NOT NULL "
        "AND btrim(external_opponent_name) <> '' "
        "AND ((home_team_id IS NOT NULL AND away_team_id IS NULL) "
        "OR (home_team_id IS NULL AND away_team_id IS NOT NULL))) "
        "OR (participant_type = 'internal' "
        "AND external_opponent_name IS NULL "
        "AND home_team_id IS NOT NULL "
        "AND away_team_id IS NOT NULL "
        "AND home_team_id <> away_team_id)",
    )
    op.create_index(
        "ix_matches_match_date_home_team_id_id",
        "matches",
        ["match_date", "home_team_id", "id"],
    )
    op.create_index(
        "ix_matches_match_date_away_team_id_id",
        "matches",
        ["match_date", "away_team_id", "id"],
    )


def downgrade() -> None:
    """Restore the legacy external-opponent shape when it is representable."""

    _assert_no_internal_matches_for_downgrade()

    op.add_column(
        "matches",
        sa.Column("opponent_name", sa.String(length=200), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE matches
            SET opponent_name = external_opponent_name
            WHERE participant_type = 'external'
            """
        )
    )
    op.alter_column(
        "matches",
        "opponent_name",
        existing_type=sa.String(length=200),
        nullable=False,
    )

    op.drop_index(
        "ix_matches_match_date_away_team_id_id",
        table_name="matches",
    )
    op.drop_index(
        "ix_matches_match_date_home_team_id_id",
        table_name="matches",
    )
    op.drop_constraint("ck_matches_participants", "matches", type_="check")
    op.drop_constraint("ck_matches_participant_type", "matches", type_="check")
    op.drop_constraint(
        "fk_matches_away_team_id_teams",
        "matches",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_matches_home_team_id_teams",
        "matches",
        type_="foreignkey",
    )
    op.drop_column("matches", "external_opponent_name")
    op.drop_column("matches", "away_team_id")
    op.drop_column("matches", "home_team_id")
    op.drop_column("matches", "participant_type")

    op.drop_index("uq_players_user_id", table_name="players")
    op.drop_constraint(
        "fk_players_user_id_users",
        "players",
        type_="foreignkey",
    )
    op.drop_column("players", "user_id")
