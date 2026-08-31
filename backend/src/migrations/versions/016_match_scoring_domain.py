"""Add the authoritative Match scoring domain.

Revision ID: 016
Revises: 015
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


def _version_column() -> sa.Column:
    return sa.Column(
        "version_number",
        sa.Integer(),
        server_default=sa.text("1"),
        nullable=False,
    )


def upgrade() -> None:
    """Create parent-to-child scoring storage and Match compatibility fields."""

    op.add_column(
        "matches",
        sa.Column(
            "lifecycle_state",
            sa.String(length=32),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "scoring_authority",
            sa.String(length=24),
            server_default=sa.text("'legacy_aggregate'"),
            nullable=False,
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "result_code",
            sa.String(length=24),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "matches",
        sa.Column(
            "result_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "matches",
        sa.Column("configured_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_matches_lifecycle_state",
        "matches",
        "lifecycle_state IN ('scheduled', 'in_progress', 'completed', "
        "'abandoned', 'correction_reprocessing')",
    )
    op.create_check_constraint(
        "ck_matches_scoring_authority",
        "matches",
        "scoring_authority IN ('legacy_aggregate', 'delivery_history')",
    )
    op.create_check_constraint(
        "ck_matches_result_code",
        "matches",
        "result_code IN ('pending', 'win_by_runs', 'win_by_wickets', 'tie', "
        "'draw', 'no_result', 'declared', 'manual')",
    )
    op.create_check_constraint(
        "ck_matches_result_details_object",
        "matches",
        "jsonb_typeof(result_details) = 'object'",
    )
    op.create_check_constraint(
        "ck_matches_result_details_bounded",
        "matches",
        "octet_length(result_details::text) <= 4096",
    )
    op.create_check_constraint(
        "ck_matches_scoring_configuration_state",
        "matches",
        "(scoring_authority = 'legacy_aggregate' AND configured_at IS NULL) OR "
        "(scoring_authority = 'delivery_history' AND configured_at IS NOT NULL)",
    )
    op.create_index(
        "ix_matches_lifecycle_state",
        "matches",
        ["lifecycle_state"],
        unique=False,
    )

    op.create_table(
        "match_sides",
        _id_column(),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side_code", sa.String(length=8), nullable=False),
        sa.Column("side_kind", sa.String(length=12), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=200), nullable=False),
        _version_column(),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "side_code IN ('home', 'away')",
            name="ck_match_sides_side_code",
        ),
        sa.CheckConstraint(
            "side_kind IN ('academy', 'external')",
            name="ck_match_sides_side_kind",
        ),
        sa.CheckConstraint(
            "(side_kind = 'academy' AND team_id IS NOT NULL) OR "
            "(side_kind = 'external' AND team_id IS NULL)",
            name="ck_match_sides_identity",
        ),
        sa.CheckConstraint(
            "length(btrim(display_name_snapshot)) > 0",
            name="ck_match_sides_display_name_not_blank",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_match_sides_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_sides_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            name="fk_match_sides_team_id_teams",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_sides"),
        sa.UniqueConstraint(
            "match_id",
            "side_code",
            name="uq_match_sides_match_side_code",
        ),
    )
    op.create_index(
        "uq_match_sides_match_team_id",
        "match_sides",
        ["match_id", "team_id"],
        unique=True,
        postgresql_where=sa.text("team_id IS NOT NULL"),
    )
    op.create_index(
        "ix_match_sides_team_id",
        "match_sides",
        ["team_id"],
        unique=False,
    )

    op.create_table(
        "match_scoring_policies",
        _id_column(),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_code", sa.String(length=20), nullable=False),
        sa.Column(
            "policy_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("capability_profile", sa.String(length=20), nullable=False),
        sa.Column(
            "capability_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "innings_sequence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("innings_per_side", sa.Integer(), nullable=False),
        sa.Column("legal_ball_limit", sa.Integer(), nullable=True),
        sa.Column("over_length_legal_balls", sa.Integer(), nullable=False),
        sa.Column("bowler_quota_legal_balls", sa.Integer(), nullable=True),
        sa.Column("wicket_limit", sa.Integer(), nullable=False),
        sa.Column("consecutive_overs_prohibited", sa.Boolean(), nullable=False),
        sa.Column("target_mode", sa.String(length=32), nullable=False),
        sa.Column(
            "allowed_dismissal_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "allowed_transition_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "allowed_innings_completion_modes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "allowed_match_completion_modes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "allowed_result_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "allow_declaration",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "allow_draw",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "explicit_match_completion_boundary",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "allow_manual_completion",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        _version_column(),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "policy_code IN ('T20', 'one-day', 'test', 'other')",
            name="ck_match_scoring_policies_policy_code",
        ),
        sa.CheckConstraint(
            "capability_profile IN ('T20', 'one-day', 'test', 'other')",
            name="ck_match_scoring_policies_capability_profile",
        ),
        sa.CheckConstraint(
            "policy_code = capability_profile",
            name="ck_match_scoring_policies_canonical_profile",
        ),
        sa.CheckConstraint(
            "policy_version >= 1 AND capability_version >= 1 "
            "AND innings_per_side >= 1 AND over_length_legal_balls >= 1 "
            "AND wicket_limit >= 1 AND version_number >= 1",
            name="ck_match_scoring_policies_positive_values",
        ),
        sa.CheckConstraint(
            "legal_ball_limit IS NULL OR legal_ball_limit >= 1",
            name="ck_match_scoring_policies_legal_ball_limit_positive",
        ),
        sa.CheckConstraint(
            "bowler_quota_legal_balls IS NULL OR bowler_quota_legal_balls >= 1",
            name="ck_match_scoring_policies_bowler_quota_positive",
        ),
        sa.CheckConstraint(
            "target_mode IN ('prior_innings_plus_one', 'none')",
            name="ck_match_scoring_policies_target_mode",
        ),
        sa.CheckConstraint(
            "explicit_match_completion_boundary IN "
            "('none', 'after_completed_innings', 'any_nonterminal_state')",
            name="ck_match_scoring_policies_completion_boundary",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(innings_sequence) = 'array' "
            "AND jsonb_array_length(innings_sequence) >= 2",
            name="ck_match_scoring_policies_innings_sequence",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_dismissal_types) = 'array' "
            "AND jsonb_array_length(allowed_dismissal_types) >= 1 "
            "AND jsonb_typeof(allowed_transition_types) = 'array' "
            "AND jsonb_typeof(allowed_innings_completion_modes) = 'array' "
            "AND jsonb_array_length(allowed_innings_completion_modes) >= 1 "
            "AND jsonb_typeof(allowed_match_completion_modes) = 'array' "
            "AND jsonb_array_length(allowed_match_completion_modes) >= 1 "
            "AND jsonb_typeof(allowed_result_codes) = 'array' "
            "AND jsonb_array_length(allowed_result_codes) >= 1",
            name="ck_match_scoring_policies_capability_sets",
        ),
        sa.CheckConstraint(
            "capability_profile <> 'one-day' OR "
            "(legal_ball_limit > 0 AND legal_ball_limit % 30 = 0 "
            "AND over_length_legal_balls = 6 "
            "AND bowler_quota_legal_balls = legal_ball_limit / 5 "
            "AND wicket_limit = 10)",
            name="ck_match_scoring_policies_one_day_policy",
        ),
        sa.CheckConstraint(
            "capability_profile <> 'T20' OR "
            "(innings_per_side = 1 AND legal_ball_limit = 120 "
            "AND over_length_legal_balls = 6 "
            "AND bowler_quota_legal_balls = 24 AND wicket_limit = 10 "
            "AND consecutive_overs_prohibited "
            "AND target_mode = 'prior_innings_plus_one' "
            "AND explicit_match_completion_boundary = 'none')",
            name="ck_match_scoring_policies_t20_policy",
        ),
        sa.CheckConstraint(
            "capability_profile <> 'test' OR "
            "(innings_per_side = 2 AND legal_ball_limit IS NULL "
            "AND over_length_legal_balls = 6 "
            "AND bowler_quota_legal_balls IS NULL AND wicket_limit = 10 "
            "AND consecutive_overs_prohibited AND target_mode = 'none' "
            "AND explicit_match_completion_boundary = 'after_completed_innings')",
            name="ck_match_scoring_policies_test_policy",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_scoring_policies_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_scoring_policies"),
        sa.UniqueConstraint(
            "match_id",
            name="uq_match_scoring_policies_match_id",
        ),
    )

    op.create_table(
        "match_participants",
        _id_column(),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_kind", sa.String(length=12), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("batting_order_position", sa.Integer(), nullable=False),
        _version_column(),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "participant_kind IN ('internal', 'external')",
            name="ck_match_participants_kind",
        ),
        sa.CheckConstraint(
            "(participant_kind = 'internal' AND player_id IS NOT NULL) OR "
            "(participant_kind = 'external' AND player_id IS NULL)",
            name="ck_match_participants_identity",
        ),
        sa.CheckConstraint(
            "length(btrim(display_name_snapshot)) > 0",
            name="ck_match_participants_display_name_not_blank",
        ),
        sa.CheckConstraint(
            "batting_order_position >= 1",
            name="ck_match_participants_batting_order_positive",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_match_participants_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_participants_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["side_id"],
            ["match_sides.id"],
            name="fk_match_participants_side_id_match_sides",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name="fk_match_participants_player_id_players",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_participants"),
    )
    op.create_index(
        "uq_match_participants_side_batting_order",
        "match_participants",
        ["side_id", "batting_order_position"],
        unique=True,
    )
    op.create_index(
        "uq_match_participants_match_player_id",
        "match_participants",
        ["match_id", "player_id"],
        unique=True,
        postgresql_where=sa.text("player_id IS NOT NULL"),
    )
    op.create_index(
        "ix_match_participants_match_side_order",
        "match_participants",
        ["match_id", "side_id", "batting_order_position"],
        unique=False,
    )

    op.create_table(
        "innings",
        _id_column(),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("innings_number", sa.Integer(), nullable=False),
        sa.Column("batting_side_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fielding_side_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "lifecycle_state",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("reconciliation_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "striker_participant_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "non_striker_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "current_bowler_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "legal_balls",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "total_runs",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "wickets_lost",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("target_runs", sa.Integer(), nullable=True),
        sa.Column("completion_reason", sa.String(length=24), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "state_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "projection_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        _version_column(),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "innings_number >= 1",
            name="ck_innings_number_positive",
        ),
        sa.CheckConstraint(
            "batting_side_id <> fielding_side_id",
            name="ck_innings_distinct_sides",
        ),
        sa.CheckConstraint(
            "lifecycle_state IN ('pending', 'in_progress', 'completed', "
            "'reconciliation_required')",
            name="ck_innings_lifecycle_state",
        ),
        sa.CheckConstraint(
            "(lifecycle_state = 'reconciliation_required' "
            "AND reconciliation_reason IS NOT NULL) OR "
            "(lifecycle_state <> 'reconciliation_required' "
            "AND reconciliation_reason IS NULL)",
            name="ck_innings_reconciliation_reason",
        ),
        sa.CheckConstraint(
            "reconciliation_reason IS NULL OR "
            "reconciliation_reason = 'incompatible_replay'",
            name="ck_innings_reconciliation_reason_value",
        ),
        sa.CheckConstraint(
            "striker_participant_id IS NULL OR "
            "non_striker_participant_id IS NULL OR "
            "striker_participant_id <> non_striker_participant_id",
            name="ck_innings_distinct_active_batters",
        ),
        sa.CheckConstraint(
            "legal_balls >= 0 AND total_runs BETWEEN 0 AND 2147483647 "
            "AND wickets_lost >= 0 AND projection_revision >= 0 "
            "AND version_number >= 1",
            name="ck_innings_projection_values",
        ),
        sa.CheckConstraint(
            "target_runs IS NULL OR target_runs BETWEEN 1 AND 2147483647",
            name="ck_innings_target_runs",
        ),
        sa.CheckConstraint(
            "completion_reason IS NULL OR completion_reason IN ('all_out', "
            "'legal_ball_limit', 'target_reached', 'declaration', 'manual')",
            name="ck_innings_completion_reason",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(state_snapshot) = 'object'",
            name="ck_innings_state_snapshot_object",
        ),
        sa.CheckConstraint(
            "octet_length(state_snapshot::text) <= 16384",
            name="ck_innings_state_snapshot_bounded",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_innings_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["batting_side_id"],
            ["match_sides.id"],
            name="fk_innings_batting_side_id_match_sides",
        ),
        sa.ForeignKeyConstraint(
            ["fielding_side_id"],
            ["match_sides.id"],
            name="fk_innings_fielding_side_id_match_sides",
        ),
        sa.ForeignKeyConstraint(
            ["striker_participant_id"],
            ["match_participants.id"],
            name="fk_innings_striker_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["non_striker_participant_id"],
            ["match_participants.id"],
            name="fk_innings_non_striker_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["current_bowler_participant_id"],
            ["match_participants.id"],
            name="fk_innings_current_bowler_id_match_participants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_innings"),
        sa.UniqueConstraint(
            "match_id",
            "innings_number",
            name="uq_innings_match_number",
        ),
    )
    op.create_index(
        "ix_innings_match_lifecycle",
        "innings",
        ["match_id", "lifecycle_state"],
        unique=False,
    )

    op.create_table(
        "deliveries",
        _id_column(),
        sa.Column("innings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempted_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempted_sequence >= 1",
            name="ck_deliveries_attempted_sequence_positive",
        ),
        sa.ForeignKeyConstraint(
            ["innings_id"],
            ["innings.id"],
            name="fk_deliveries_innings_id_innings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deliveries"),
        sa.UniqueConstraint(
            "innings_id",
            "attempted_sequence",
            name="uq_deliveries_innings_attempted_sequence",
        ),
    )
    op.create_index(
        "ix_deliveries_innings_sequence",
        "deliveries",
        ["innings_id", "attempted_sequence"],
        unique=False,
    )

    op.create_table(
        "delivery_revisions",
        _id_column(),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column(
            "revision_state",
            sa.String(length=16),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "striker_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "non_striker_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "bowler_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "runs_off_bat", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "wide_runs", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "no_ball_penalty_runs",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "bye_runs", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "leg_bye_runs", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "penalty_runs", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("total_runs", sa.Integer(), nullable=False),
        sa.Column("is_legal", sa.Boolean(), nullable=False),
        sa.Column("completed_runs", sa.Integer(), nullable=False),
        sa.Column("balls_faced", sa.Boolean(), nullable=False),
        sa.Column("bowler_conceded_runs", sa.Integer(), nullable=False),
        sa.Column("over_number", sa.Integer(), nullable=False),
        sa.Column("ball_in_over", sa.Integer(), nullable=False),
        sa.Column("replacement_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "supersedes_revision_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name="ck_delivery_revisions_number_positive",
        ),
        sa.CheckConstraint(
            "revision_state IN ('active', 'superseded')",
            name="ck_delivery_revisions_state",
        ),
        sa.CheckConstraint(
            "striker_participant_id <> non_striker_participant_id",
            name="ck_delivery_revisions_distinct_batters",
        ),
        sa.CheckConstraint(
            "runs_off_bat BETWEEN 0 AND 2147483647 "
            "AND wide_runs BETWEEN 0 AND 2147483647 "
            "AND no_ball_penalty_runs BETWEEN 0 AND 1 "
            "AND bye_runs BETWEEN 0 AND 2147483647 "
            "AND leg_bye_runs BETWEEN 0 AND 2147483647 "
            "AND penalty_runs BETWEEN 0 AND 2147483647",
            name="ck_delivery_revisions_component_bounds",
        ),
        sa.CheckConstraint(
            "NOT (bye_runs > 0 AND leg_bye_runs > 0) "
            "AND NOT (wide_runs > 0 AND no_ball_penalty_runs > 0)",
            name="ck_delivery_revisions_extras_exclusive",
        ),
        sa.CheckConstraint(
            "total_runs BETWEEN 0 AND 2147483647 "
            "AND completed_runs BETWEEN 0 AND 2147483647 "
            "AND bowler_conceded_runs BETWEEN 0 AND 2147483647",
            name="ck_delivery_revisions_derived_run_bounds",
        ),
        sa.CheckConstraint(
            "total_runs::bigint = runs_off_bat::bigint + wide_runs::bigint + "
            "no_ball_penalty_runs::bigint + bye_runs::bigint + "
            "leg_bye_runs::bigint + penalty_runs::bigint",
            name="ck_delivery_revisions_total_components",
        ),
        sa.CheckConstraint(
            "is_legal = (wide_runs = 0 AND no_ball_penalty_runs = 0)",
            name="ck_delivery_revisions_legal_derivation",
        ),
        sa.CheckConstraint(
            "over_number >= 0 AND ball_in_over >= 1",
            name="ck_delivery_revisions_over_position",
        ),
        sa.CheckConstraint(
            "(revision_number = 1 AND replacement_reason IS NULL "
            "AND supersedes_revision_id IS NULL) OR "
            "(revision_number > 1 AND replacement_reason IS NOT NULL "
            "AND length(btrim(replacement_reason)) BETWEEN 1 AND 500 "
            "AND supersedes_revision_id IS NOT NULL)",
            name="ck_delivery_revisions_replacement_provenance",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["deliveries.id"],
            name="fk_delivery_revisions_delivery_id_deliveries",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["striker_participant_id"],
            ["match_participants.id"],
            name="fk_delivery_revisions_striker_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["non_striker_participant_id"],
            ["match_participants.id"],
            name="fk_delivery_revisions_non_striker_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["bowler_participant_id"],
            ["match_participants.id"],
            name="fk_delivery_revisions_bowler_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_revision_id"],
            ["delivery_revisions.id"],
            name="fk_delivery_revisions_supersedes_id_delivery_revisions",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name="fk_delivery_revisions_recorded_by_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_delivery_revisions"),
        sa.UniqueConstraint(
            "delivery_id",
            "revision_number",
            name="uq_delivery_revisions_delivery_number",
        ),
    )
    op.create_index(
        "uq_delivery_revisions_active_delivery",
        "delivery_revisions",
        ["delivery_id"],
        unique=True,
        postgresql_where=sa.text("revision_state = 'active'"),
    )
    op.create_index(
        "uq_delivery_revisions_supersedes_revision_id",
        "delivery_revisions",
        ["supersedes_revision_id"],
        unique=True,
        postgresql_where=sa.text("supersedes_revision_id IS NOT NULL"),
    )
    op.create_index(
        "ix_delivery_revisions_delivery_state",
        "delivery_revisions",
        ["delivery_id", "revision_state"],
        unique=False,
    )

    op.create_table(
        "innings_batting_entries",
        _id_column(),
        sa.Column("innings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batting_order_position", sa.Integer(), nullable=False),
        sa.Column(
            "participation_state",
            sa.String(length=20),
            server_default=sa.text("'not_batted'"),
            nullable=False,
        ),
        sa.Column(
            "dismissal_delivery_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        _version_column(),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "batting_order_position >= 1",
            name="ck_innings_batting_entries_position_positive",
        ),
        sa.CheckConstraint(
            "participation_state IN ('not_batted', 'active', 'dismissed', "
            "'retired_hurt', 'retired_out', 'completed')",
            name="ck_innings_batting_entries_state",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_innings_batting_entries_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["innings_id"],
            ["innings.id"],
            name="fk_innings_batting_entries_innings_id_innings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_innings_batting_entries_participant_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["dismissal_delivery_id"],
            ["deliveries.id"],
            name="fk_innings_batting_entries_dismissal_delivery_id_deliveries",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_innings_batting_entries"),
        sa.UniqueConstraint(
            "innings_id",
            "participant_id",
            name="uq_innings_batting_entries_participant",
        ),
        sa.UniqueConstraint(
            "innings_id",
            "batting_order_position",
            name="uq_innings_batting_entries_position",
        ),
    )
    op.create_index(
        "ix_innings_batting_entries_state",
        "innings_batting_entries",
        ["innings_id", "participation_state"],
        unique=False,
    )
    op.create_index(
        "ix_innings_batting_entries_active",
        "innings_batting_entries",
        ["innings_id"],
        unique=False,
        postgresql_where=sa.text("participation_state = 'active'"),
    )

    op.create_table(
        "innings_transition_events",
        _id_column(),
        sa.Column("innings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_kind", sa.String(length=32), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("anchored_attempted_sequence", sa.Integer(), nullable=True),
        sa.Column(
            "anchored_revision_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("over_number", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_kind IN ('innings_started', 'next_batter', 'next_bowler', "
            "'retired_hurt', 'retired_hurt_return', 'innings_completed')",
            name="ck_innings_transition_events_kind",
        ),
        sa.CheckConstraint(
            "anchored_attempted_sequence IS NULL OR "
            "anchored_attempted_sequence >= 1",
            name="ck_innings_transition_events_attempted_sequence",
        ),
        sa.CheckConstraint(
            "over_number IS NULL OR over_number >= 0",
            name="ck_innings_transition_events_over_number",
        ),
        sa.CheckConstraint(
            "reason IS NULL OR length(btrim(reason)) BETWEEN 1 AND 500",
            name="ck_innings_transition_events_reason",
        ),
        sa.ForeignKeyConstraint(
            ["innings_id"],
            ["innings.id"],
            name="fk_innings_transition_events_innings_id_innings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_innings_transition_events_participant_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["anchored_revision_id"],
            ["delivery_revisions.id"],
            name="fk_innings_transition_events_revision_id_delivery_revisions",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_innings_transition_events_created_by_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_innings_transition_events"),
    )
    op.create_index(
        "ix_innings_transition_events_replay_order",
        "innings_transition_events",
        ["innings_id", "anchored_attempted_sequence", "created_at", "id"],
        unique=False,
    )

    op.create_table(
        "wicket_events",
        _id_column(),
        sa.Column(
            "delivery_revision_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("dismissal_type", sa.String(length=32), nullable=False),
        sa.Column(
            "dismissed_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("dismissed_end", sa.String(length=24), nullable=True),
        sa.Column("counts_as_team_wicket", sa.Boolean(), nullable=False),
        sa.Column("credited_to_bowler", sa.Boolean(), nullable=False),
        sa.Column(
            "primary_fielder_participant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "dismissal_type IN ('bowled', 'caught', 'caught_and_bowled', "
            "'lbw', 'run_out', 'stumped', 'hit_wicket', 'retired_out')",
            name="ck_wicket_events_dismissal_type",
        ),
        sa.CheckConstraint(
            "(dismissal_type = 'run_out' AND dismissed_end IS NOT NULL) OR "
            "(dismissal_type <> 'run_out' AND dismissed_end IS NULL)",
            name="ck_wicket_events_dismissed_end",
        ),
        sa.CheckConstraint(
            "dismissed_end IS NULL OR "
            "dismissed_end IN ('striker_end', 'non_striker_end')",
            name="ck_wicket_events_dismissed_end_value",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR length(btrim(notes)) BETWEEN 1 AND 500",
            name="ck_wicket_events_notes",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_revision_id"],
            ["delivery_revisions.id"],
            name="fk_wicket_events_revision_id_delivery_revisions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dismissed_participant_id"],
            ["match_participants.id"],
            name="fk_wicket_events_dismissed_id_match_participants",
        ),
        sa.ForeignKeyConstraint(
            ["primary_fielder_participant_id"],
            ["match_participants.id"],
            name="fk_wicket_events_primary_fielder_id_match_participants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wicket_events"),
        sa.UniqueConstraint(
            "delivery_revision_id",
            name="uq_wicket_events_delivery_revision_id",
        ),
    )

    op.create_table(
        "delivery_fielders",
        _id_column(),
        sa.Column(
            "delivery_revision_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 1",
            name="ck_delivery_fielders_ordinal_positive",
        ),
        sa.CheckConstraint(
            "role IN ('bowler', 'catcher', 'thrower', 'keeper', "
            "'assister', 'other')",
            name="ck_delivery_fielders_role",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_revision_id"],
            ["delivery_revisions.id"],
            name="fk_delivery_fielders_revision_id_delivery_revisions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_delivery_fielders_participant_id_match_participants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_delivery_fielders"),
        sa.UniqueConstraint(
            "delivery_revision_id",
            "ordinal",
            name="uq_delivery_fielders_revision_ordinal",
        ),
        sa.UniqueConstraint(
            "delivery_revision_id",
            "participant_id",
            "role",
            name="uq_delivery_fielders_revision_participant_role",
        ),
    )
    op.create_index(
        "ix_delivery_fielders_revision_order",
        "delivery_fielders",
        ["delivery_revision_id", "ordinal"],
        unique=False,
    )
    op.create_index(
        "ix_delivery_fielders_participant_id",
        "delivery_fielders",
        ["participant_id"],
        unique=False,
    )

    op.create_table(
        "innings_overs",
        _id_column(),
        sa.Column("innings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("over_number", sa.Integer(), nullable=False),
        sa.Column(
            "bowler_participant_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "legal_ball_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "total_runs",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "runs_conceded",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "wickets",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_complete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "projection_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "over_number >= 0 AND legal_ball_count >= 0 "
            "AND total_runs BETWEEN 0 AND 2147483647 "
            "AND runs_conceded BETWEEN 0 AND 2147483647 "
            "AND wickets >= 0 AND projection_revision >= 0",
            name="ck_innings_overs_projection_values",
        ),
        sa.ForeignKeyConstraint(
            ["innings_id"],
            ["innings.id"],
            name="fk_innings_overs_innings_id_innings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bowler_participant_id"],
            ["match_participants.id"],
            name="fk_innings_overs_bowler_id_match_participants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_innings_overs"),
        sa.UniqueConstraint(
            "innings_id",
            "over_number",
            name="uq_innings_overs_innings_number",
        ),
    )
    op.create_index(
        "ix_innings_overs_projection",
        "innings_overs",
        ["innings_id", "projection_revision"],
        unique=False,
    )

    op.create_table(
        "innings_participant_summaries",
        _id_column(),
        sa.Column("innings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "participation_state",
            sa.String(length=20),
            server_default=sa.text("'not_batted'"),
            nullable=False,
        ),
        sa.Column("dismissal_type", sa.String(length=32), nullable=True),
        sa.Column(
            "batting_runs",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "balls_faced",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "fours", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "sixes", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "bowling_legal_balls",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "bowling_overs_completed",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "bowling_balls_in_partial_over",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "runs_conceded",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "bowling_wickets",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "wides", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "no_balls", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "fielding_dismissals",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "projection_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "participation_state IN ('not_batted', 'active', 'dismissed', "
            "'retired_hurt', 'retired_out', 'completed')",
            name="ck_innings_participant_summaries_state",
        ),
        sa.CheckConstraint(
            "dismissal_type IS NULL OR dismissal_type IN ('bowled', 'caught', "
            "'caught_and_bowled', 'lbw', 'run_out', 'stumped', 'hit_wicket', "
            "'retired_out')",
            name="ck_innings_participant_summaries_dismissal",
        ),
        sa.CheckConstraint(
            "batting_runs BETWEEN 0 AND 2147483647 "
            "AND runs_conceded BETWEEN 0 AND 2147483647",
            name="ck_innings_participant_summaries_run_bounds",
        ),
        sa.CheckConstraint(
            "balls_faced >= 0 AND fours >= 0 AND sixes >= 0 "
            "AND bowling_legal_balls >= 0 AND bowling_overs_completed >= 0 "
            "AND bowling_balls_in_partial_over >= 0 AND bowling_wickets >= 0 "
            "AND wides >= 0 AND no_balls >= 0 AND fielding_dismissals >= 0 "
            "AND projection_revision >= 0",
            name="ck_innings_participant_summaries_counts",
        ),
        sa.ForeignKeyConstraint(
            ["innings_id"],
            ["innings.id"],
            name="fk_innings_participant_summaries_innings_id_innings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_innings_participant_summaries_participant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_innings_participant_summaries"),
        sa.UniqueConstraint(
            "innings_id",
            "participant_id",
            name="uq_innings_participant_summaries_participant",
        ),
    )
    op.create_index(
        "ix_innings_participant_summaries_projection",
        "innings_participant_summaries",
        ["innings_id", "projection_revision"],
        unique=False,
    )

    op.create_table(
        "match_participant_performances",
        _id_column(),
        sa.Column("match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("innings_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "batting_runs",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "balls_faced",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "fours", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "sixes", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("dismissal_type", sa.String(length=32), nullable=True),
        sa.Column(
            "bowling_legal_balls",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "runs_conceded",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "bowling_wickets",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "wides", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "no_balls", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "extras_conceded",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "catches", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "stumpings", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "run_out_involvements",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "projection_revision",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "provenance",
            sa.String(length=24),
            server_default=sa.text("'delivery_derived'"),
            nullable=False,
        ),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "dismissal_type IS NULL OR dismissal_type IN ('bowled', 'caught', "
            "'caught_and_bowled', 'lbw', 'run_out', 'stumped', 'hit_wicket', "
            "'retired_out')",
            name="ck_match_participant_performances_dismissal",
        ),
        sa.CheckConstraint(
            "provenance = 'delivery_derived'",
            name="ck_match_participant_performances_provenance",
        ),
        sa.CheckConstraint(
            "batting_runs BETWEEN 0 AND 2147483647 "
            "AND runs_conceded BETWEEN 0 AND 2147483647 "
            "AND extras_conceded BETWEEN 0 AND 2147483647",
            name="ck_match_participant_performances_run_bounds",
        ),
        sa.CheckConstraint(
            "balls_faced >= 0 AND fours >= 0 AND sixes >= 0 "
            "AND bowling_legal_balls >= 0 AND bowling_wickets >= 0 "
            "AND wides >= 0 AND no_balls >= 0 AND catches >= 0 "
            "AND stumpings >= 0 AND run_out_involvements >= 0 "
            "AND projection_revision >= 0",
            name="ck_match_participant_performances_counts",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name="fk_match_participant_performances_match_id_matches",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["innings_id"],
            ["innings.id"],
            name="fk_match_participant_performances_innings_id_innings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["match_participants.id"],
            name="fk_match_participant_performances_participant",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_match_participant_performances"),
        sa.UniqueConstraint(
            "match_id",
            "innings_id",
            "participant_id",
            name="uq_match_participant_performances_innings_participant",
        ),
    )
    op.create_index(
        "ix_match_participant_performances_match_projection",
        "match_participant_performances",
        ["match_id", "projection_revision"],
        unique=False,
    )
    op.create_index(
        "ix_match_participant_performances_participant",
        "match_participant_performances",
        ["participant_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop scoring children before parents and restore revision 015 Matches."""

    op.drop_table("match_participant_performances")
    op.drop_table("innings_participant_summaries")
    op.drop_table("innings_overs")
    op.drop_table("delivery_fielders")
    op.drop_table("wicket_events")
    op.drop_table("innings_transition_events")
    op.drop_table("innings_batting_entries")
    op.drop_table("delivery_revisions")
    op.drop_table("deliveries")
    op.drop_table("innings")
    op.drop_table("match_participants")
    op.drop_table("match_scoring_policies")
    op.drop_table("match_sides")

    op.drop_index("ix_matches_lifecycle_state", table_name="matches")
    op.drop_constraint(
        "ck_matches_scoring_configuration_state", "matches", type_="check"
    )
    op.drop_constraint("ck_matches_result_details_bounded", "matches", type_="check")
    op.drop_constraint("ck_matches_result_details_object", "matches", type_="check")
    op.drop_constraint("ck_matches_result_code", "matches", type_="check")
    op.drop_constraint("ck_matches_scoring_authority", "matches", type_="check")
    op.drop_constraint("ck_matches_lifecycle_state", "matches", type_="check")
    op.drop_column("matches", "configured_at")
    op.drop_column("matches", "result_details")
    op.drop_column("matches", "result_code")
    op.drop_column("matches", "scoring_authority")
    op.drop_column("matches", "lifecycle_state")
