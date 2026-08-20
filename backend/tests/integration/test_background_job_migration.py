"""Migration coverage for durable background-processing revision 015."""

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
from sqlalchemy.exc import IntegrityError

from src.database import engine
from tests.database_safety import assert_safe_test_database_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _revision_chain() -> tuple[list[object], object]:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    baseline = list(reversed(list(scripts.iterate_revisions("014", "base"))))
    revision_015 = scripts.get_revision("015")
    assert revision_015 is not None
    return baseline, revision_015


def _exercise_revision_015(connection: Connection, schema_name: str) -> None:
    connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema_name}", public'))
    migration_context = MigrationContext.configure(connection)
    baseline, revision_015 = _revision_chain()

    with Operations.context(migration_context):
        for revision in baseline:
            revision.module.upgrade()
        revision_015.module.upgrade()

        inspector = inspect(connection)
        assert "background_work_items" in inspector.get_table_names(schema=schema_name)
        columns = {
            item["name"]: item
            for item in inspector.get_columns(
                "background_work_items", schema=schema_name
            )
        }
        assert {
            "payload",
            "payload_version",
            "state",
            "run_after",
            "lease_owner",
            "lease_expires_at",
            "last_failure_category",
            "last_failure_message",
            "manual_retry_allowed",
            "retention_until",
            "version_number",
        } <= columns.keys()
        assert columns["version_number"]["nullable"] is False

        constraints = {
            item["name"]
            for item in inspector.get_check_constraints(
                "background_work_items", schema=schema_name
            )
        }
        assert {
            "ck_background_work_items_state",
            "ck_background_work_items_payload_json_object",
            "ck_background_work_items_payload_size",
            "ck_background_work_items_counters_nonnegative",
            "ck_background_work_items_version_positive",
            "ck_background_work_items_lease_pair",
        } <= constraints

        indexes = {
            item["name"]: item
            for item in inspector.get_indexes(
                "background_work_items", schema=schema_name
            )
        }
        assert {
            "uq_background_work_items_job_idempotency",
            "uq_background_work_items_active_coalescing",
            "ix_background_work_items_eligible",
            "ix_background_work_items_recovery",
            "ix_background_work_items_retention",
        } <= indexes.keys()
        assert indexes["uq_background_work_items_job_idempotency"]["unique"]
        assert indexes["uq_background_work_items_active_coalescing"]["unique"]

        connection.execute(
            text(
                """
                INSERT INTO background_work_items (
                    id, job_type, payload_version, payload, state,
                    idempotency_key, coalescing_key, run_after,
                    manual_retry_allowed, version_number
                ) VALUES (
                    :id, 'synthetic_job', 1, '{"source_id":"player:1"}'::jsonb,
                    'pending', 'request:1', 'source:player:1', now(), true, 1
                )
                """
            ),
            {"id": uuid4()},
        )

        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """
                        INSERT INTO background_work_items (
                            job_type, payload_version, payload, state, run_after
                        ) VALUES (
                            'synthetic_job', 1, '{}'::jsonb, 'unknown', now()
                        )
                        """
                    )
                )

        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """
                        INSERT INTO background_work_items (
                            job_type, payload_version, payload, state, run_after
                        ) VALUES (
                            'synthetic_job', 1,
                            jsonb_build_object('value', repeat('x', 17000)),
                            'pending', now()
                        )
                        """
                    )
                )

        revision_015.module.downgrade()
        assert "background_work_items" not in inspect(connection).get_table_names(
            schema=schema_name
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_revision_015_upgrade_constraints_indexes_and_downgrade() -> None:
    """Upgrade a real revision-014 schema, inspect durable work, then restore it."""

    assert_safe_test_database_url(str(engine.url))
    schema_name = f"migration_015_{uuid4().hex}"
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(_exercise_revision_015, schema_name)
        finally:
            await transaction.rollback()
