"""Revision 016 migration coverage in an isolated PostgreSQL schema."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from src.database import engine
from tests.database_safety import assert_safe_test_database_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _revisions_through_015() -> tuple[list[object], object]:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    baseline = list(reversed(list(scripts.iterate_revisions("015", "base"))))
    revision_016 = scripts.get_revision("016")
    assert revision_016 is not None
    return baseline, revision_016


def _exercise_revision_016(connection: Connection, schema_name: str) -> None:
    connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema_name}", public'))
    migration_context = MigrationContext.configure(connection)
    baseline, revision_016 = _revisions_through_015()

    with Operations.context(migration_context):
        for revision in baseline:
            revision.module.upgrade()
        revision_016.module.upgrade()

        inspector = inspect(connection)
        tables = set(inspector.get_table_names(schema=schema_name))
        required_tables = {
            "match_sides",
            "match_scoring_policies",
            "match_participants",
            "innings",
            "innings_batting_entries",
            "deliveries",
            "delivery_revisions",
            "innings_transition_events",
            "wicket_events",
            "delivery_fielders",
            "innings_overs",
            "innings_participant_summaries",
            "match_participant_performances",
        }
        assert required_tables <= tables

        match_columns = {
            column["name"]
            for column in inspector.get_columns("matches", schema=schema_name)
        }
        assert {
            "lifecycle_state",
            "scoring_authority",
            "result_code",
            "result_details",
            "configured_at",
        } <= match_columns
        policy_columns = {
            column["name"]
            for column in inspector.get_columns(
                "match_scoring_policies", schema=schema_name
            )
        }
        assert {
            "policy_code",
            "capability_profile",
            "capability_version",
            "innings_sequence",
            "explicit_match_completion_boundary",
            "legal_ball_limit",
            "bowler_quota_legal_balls",
        } <= policy_columns
        innings_columns = {
            column["name"]
            for column in inspector.get_columns("innings", schema=schema_name)
        }
        assert "state_snapshot" in innings_columns
        assert "reconciliation_required" not in innings_columns
        assert "abandoned" not in innings_columns

        policy_checks = {
            item["name"]: item["sqltext"]
            for item in inspector.get_check_constraints(
                "match_scoring_policies", schema=schema_name
            )
        }
        assert "ck_match_scoring_policies_canonical_profile" in policy_checks
        assert "ck_match_scoring_policies_one_day_policy" in policy_checks
        assert (
            "(legal_ball_limit % 30) = 0"
            in policy_checks["ck_match_scoring_policies_one_day_policy"]
        )
        assert (
            "bowler_quota_legal_balls = (legal_ball_limit / 5)"
            in policy_checks["ck_match_scoring_policies_one_day_policy"]
        )
        boundary_check = policy_checks["ck_match_scoring_policies_completion_boundary"]
        assert "after_completed_innings" in boundary_check
        assert "any_nonterminal_state" in boundary_check

        revision_checks = {
            item["name"]: item["sqltext"]
            for item in inspector.get_check_constraints(
                "delivery_revisions", schema=schema_name
            )
        }
        component_check = revision_checks["ck_delivery_revisions_component_bounds"]
        assert all(
            field in component_check
            for field in (
                "runs_off_bat",
                "wide_runs",
                "no_ball_penalty_runs",
                "bye_runs",
                "leg_bye_runs",
                "penalty_runs",
                "2147483647",
            )
        )
        assert "ck_delivery_revisions_derived_run_bounds" in revision_checks
        assert "ck_delivery_revisions_total_components" in revision_checks
        innings_checks = {
            item["name"]: item["sqltext"]
            for item in inspector.get_check_constraints("innings", schema=schema_name)
        }
        innings_run_check = innings_checks["ck_innings_projection_values"]
        assert "total_runs >= 0" in innings_run_check
        assert "total_runs <= 2147483647" in innings_run_check
        assert not any(
            "abandoned" in value.lower() for value in innings_checks.values()
        )

        innings_state_check = innings_checks["ck_innings_lifecycle_state"]
        assert "reconciliation_required" in innings_state_check
        assert "abandoned" not in innings_state_check

        fielders_constraints = {
            item["name"]: item
            for item in inspector.get_unique_constraints(
                "delivery_fielders", schema=schema_name
            )
        }
        assert fielders_constraints["uq_delivery_fielders_revision_ordinal"][
            "column_names"
        ] == ["delivery_revision_id", "ordinal"]
        assert fielders_constraints["uq_delivery_fielders_revision_participant_role"][
            "column_names"
        ] == ["delivery_revision_id", "participant_id", "role"]
        active_index = next(
            item
            for item in inspector.get_indexes("delivery_revisions", schema=schema_name)
            if item["name"] == "uq_delivery_revisions_active_delivery"
        )
        assert active_index["unique"] is True
        assert "revision_state" in active_index["dialect_options"]["postgresql_where"]

        revision_016.module.downgrade()
        downgraded = inspect(connection)
        assert "match_sides" not in set(downgraded.get_table_names(schema=schema_name))
        assert "lifecycle_state" not in {
            column["name"]
            for column in downgraded.get_columns("matches", schema=schema_name)
        }

        revision_016.module.upgrade()
        upgraded_again = inspect(connection)
        assert required_tables <= set(
            upgraded_again.get_table_names(schema=schema_name)
        )
        assert "explicit_match_completion_boundary" in {
            column["name"]
            for column in upgraded_again.get_columns(
                "match_scoring_policies", schema=schema_name
            )
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_revision_016_upgrade_constraints_downgrade_and_reupgrade() -> None:
    """Apply the real PostgreSQL revision chain and safely repeat revision 016."""

    assert_safe_test_database_url(str(engine.url))
    schema_name = f"migration_016_{uuid4().hex}"
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(_exercise_revision_016, schema_name)
        finally:
            await transaction.rollback()
