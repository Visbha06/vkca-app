"""Migration upgrade/downgrade coverage for RAG revision 014."""

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


def _revision_chain() -> tuple[list[object], object]:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    baseline = list(reversed(list(scripts.iterate_revisions("013", "base"))))
    revision_014 = scripts.get_revision("014")
    assert revision_014 is not None
    return baseline, revision_014


def _exercise_revision_014(connection: Connection, schema_name: str) -> None:
    connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema_name}", public'))
    migration_context = MigrationContext.configure(connection)
    baseline, revision_014 = _revision_chain()

    with Operations.context(migration_context):
        for revision in baseline:
            revision.module.upgrade()
        revision_014.module.upgrade()

        inspector = inspect(connection)
        tables = set(inspector.get_table_names(schema=schema_name))
        assert {
            "rag_index_runs",
            "rag_source_states",
            "rag_documents",
            "rag_chunks",
        } <= tables
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            == 1
        )

        chunk_columns = {
            item["name"]: item
            for item in inspector.get_columns("rag_chunks", schema=schema_name)
        }
        assert "vector(1536)" in str(chunk_columns["embedding"]["type"]).casefold()
        chunk_indexes = {
            item["name"]: item
            for item in inspector.get_indexes("rag_chunks", schema=schema_name)
        }
        assert {
            "ix_rag_chunks_player_ids_gin",
            "ix_rag_chunks_team_ids_gin",
            "ix_rag_chunks_age_groups_gin",
            "ix_rag_chunks_embedding_cosine_hnsw",
            "ix_rag_chunks_embedding_profile",
        } <= set(chunk_indexes)
        assert {
            item["name"]
            for item in inspector.get_unique_constraints(
                "rag_chunks", schema=schema_name
            )
        } >= {"uq_rag_chunks_document_ordinal"}
        assert {
            item["name"]
            for item in inspector.get_check_constraints(
                "rag_source_states", schema=schema_name
            )
        } >= {
            "ck_rag_source_states_status",
            "ck_rag_source_states_embedding_dimension",
            "ck_rag_source_states_version_positive",
        }

        revision_014.module.downgrade()

        downgraded = inspect(connection)
        downgraded_tables = set(downgraded.get_table_names(schema=schema_name))
        assert "players" in downgraded_tables
        assert not {
            "rag_index_runs",
            "rag_source_states",
            "rag_documents",
            "rag_chunks",
        }.intersection(downgraded_tables)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            == 1
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_revision_014_upgrade_vector_schema_and_safe_downgrade() -> None:
    """Upgrade a real revision-013 schema, inspect RAG state, then restore 013."""

    assert_safe_test_database_url(str(engine.url))
    schema_name = f"migration_014_{uuid4().hex}"
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(_exercise_revision_014, schema_name)
        finally:
            await transaction.rollback()
