"""Add team age-group constraint and roster ordering."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | Sequence[str] | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Constrain team age groups and add stable roster ordering."""

    op.create_check_constraint(
        "ck_teams_age_group",
        "teams",
        "age_group IN ('J', 'U11', 'U13', 'U15')",
    )
    op.add_column(
        "team_players",
        sa.Column(
            "roster_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_team_players_team_order",
        "team_players",
        ["team_id", "roster_order"],
    )


def downgrade() -> None:
    """Remove roster ordering and the age-group constraint."""

    op.drop_index("ix_team_players_team_order", table_name="team_players")
    op.drop_column("team_players", "roster_order")
    op.drop_constraint("ck_teams_age_group", "teams", type_="check")
