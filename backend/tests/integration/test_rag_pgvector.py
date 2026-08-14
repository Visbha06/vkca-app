"""PostgreSQL/pgvector persistence coverage for foundational RAG models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, StatementError

from src.database import AsyncSessionFactory
from src.enums import UserRole
from src.models.auth_audit_log import AuthAuditLog
from src.models.business_audit_event import BusinessAuditEvent
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.services.rag.canonical import (
    canonical_content_hash,
    derive_chunk_id,
    derive_document_id,
)
from src.services.rag.contracts import (
    EmbeddingProfile,
    RagRunCounters,
    RagRunMode,
    RagRunStatus,
    RagSourceStatus,
)
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import (
    RagClaimConflictError,
    RagIndexingStateService,
    report_from_run,
    technical_failure,
)
from src.services.rag.retrieval import build_retrieval_statement
from src.services.rag.scope import RagAccessScope

DIMENSION = 1536


def _unit_vector(index: int) -> list[float]:
    values = [0.0] * DIMENSION
    values[index] = 1.0
    return values


def test_authorization_predicates_precede_cosine_order_and_vectors_are_not_selected():
    team_id, player_id, user_id = uuid4(), uuid4(), uuid4()
    scope = RagAccessScope(
        user_id=user_id,
        role=UserRole.ASSISTANT_COACH,
        is_active=True,
        linked_player_id=None,
        team_ids=(team_id,),
        age_groups=("U13",),
        active_player_ids=(player_id,),
        is_unlinked_player=False,
        can_read_all_registered_sources=False,
    )
    statement = build_retrieval_statement(
        scope,
        query_vector=tuple(_unit_vector(0)),
        profile=FakeEmbeddingProvider().profile,
        limit=5,
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    selected_names = {column.key for column in statement.selected_columns}

    assert sql.index("WHERE") < sql.index("ORDER BY") < sql.index("LIMIT")
    assert "rag_chunks.player_ids &&" in sql
    assert "rag_chunks.team_ids &&" in sql
    assert "rag_chunks.age_groups &&" in sql
    assert "rag_chunks.is_all_academy IS true" in sql
    assert "embedding" not in selected_names


@pytest.mark.asyncio(loop_scope="session")
async def test_pgvector_insert_cosine_order_scope_indexes_and_safe_projection() -> None:
    source_entity_id = uuid4()
    team_id = uuid4()
    document_id = derive_document_id("player_profile", str(source_entity_id))

    async with AsyncSessionFactory() as session:
        state = RagSourceState(
            source_type="player_profile",
            source_key=str(source_entity_id),
            source_entity_id=source_entity_id,
            observed_source_version="1",
            observed_dependency_hash=canonical_content_hash("team-v1"),
            observed_content_hash=canonical_content_hash("Player: Asha"),
            last_successful_content_hash=canonical_content_hash("Player: Asha"),
            builder_version="player-v1",
            chunking_version="chunk-v1",
            provider_name="fake",
            model_name="gemini-embedding-001",
            embedding_dimension=DIMENSION,
            status=RagSourceStatus.CURRENT,
        )
        session.add(state)
        await session.flush()
        document = RagDocument(
            id=document_id,
            source_state_id=state.id,
            source_type="player_profile",
            source_key=str(source_entity_id),
            source_entity_id=source_entity_id,
            source_version="1",
            semantic_text="Player: Asha",
            provenance_metadata={
                "source_type": "player_profile",
                "source_entity_id": str(source_entity_id),
            },
            scope_metadata={"source_type": "player_profile"},
            player_ids=[source_entity_id],
            team_ids=[team_id],
            age_groups=["U15"],
            is_all_academy=False,
            content_hash=canonical_content_hash("Player: Asha"),
            builder_version="player-v1",
            chunking_version="chunk-v1",
            is_searchable=True,
        )
        session.add(document)
        await session.flush()
        state.active_document_id = document.id

        nearest = RagChunk(
            id=derive_chunk_id(document_id, 0),
            document_id=document_id,
            source_type="player_profile",
            source_key=str(source_entity_id),
            ordinal=0,
            semantic_text="Player: Asha",
            content_hash=canonical_content_hash("Player: Asha"),
            provenance_metadata={"source_type": "player_profile"},
            scope_metadata={"source_type": "player_profile"},
            player_ids=[source_entity_id],
            team_ids=[team_id],
            age_groups=["U15"],
            is_all_academy=False,
            embedding=_unit_vector(0),
            provider_name="fake",
            model_name="gemini-embedding-001",
            embedding_dimension=DIMENSION,
            builder_version="player-v1",
            chunking_version="chunk-v1",
            is_searchable=True,
        )
        farther = RagChunk(
            id=derive_chunk_id(document_id, 1),
            document_id=document_id,
            source_type="player_profile",
            source_key=str(source_entity_id),
            ordinal=1,
            semantic_text="Team: U15 Falcons",
            content_hash=canonical_content_hash("Team: U15 Falcons"),
            provenance_metadata={"source_type": "player_profile"},
            scope_metadata={"source_type": "player_profile"},
            player_ids=[source_entity_id],
            team_ids=[team_id],
            age_groups=["U15"],
            is_all_academy=False,
            embedding=_unit_vector(1),
            provider_name="fake",
            model_name="gemini-embedding-001",
            embedding_dimension=DIMENSION,
            builder_version="player-v1",
            chunking_version="chunk-v1",
            is_searchable=True,
        )
        session.add_all([nearest, farther])
        await session.flush()

        distance = RagChunk.embedding.cosine_distance(_unit_vector(0)).label("distance")
        rows = (
            (
                await session.execute(
                    select(
                        RagChunk.id,
                        RagChunk.semantic_text,
                        RagChunk.source_type,
                        distance,
                    )
                    .where(
                        RagChunk.is_searchable.is_(True),
                        RagChunk.team_ids.contains([team_id]),
                    )
                    .order_by(distance, RagChunk.id)
                )
            )
            .mappings()
            .all()
        )

        assert [row["id"] for row in rows] == [nearest.id, farther.id]
        assert rows[0]["distance"] == pytest.approx(0.0)
        assert "embedding" not in rows[0]
        assert "[1.0" not in repr(nearest)

        connection = await session.connection()

        def index_names(sync_connection) -> set[str]:
            return {
                item["name"]
                for item in inspect(sync_connection).get_indexes("rag_chunks")
            }

        indexes = await connection.run_sync(index_names)
        assert {
            "ix_rag_chunks_player_ids_gin",
            "ix_rag_chunks_team_ids_gin",
            "ix_rag_chunks_age_groups_gin",
            "ix_rag_chunks_embedding_cosine_hnsw",
            "ix_rag_chunks_embedding_profile",
        } <= indexes

        await session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_pgvector_dimension_and_duplicate_constraints_reject_bad_rows() -> None:
    source_entity_id = uuid4()
    document_id = derive_document_id("team", str(source_entity_id))

    async with AsyncSessionFactory() as session:
        state = RagSourceState(
            source_type="team",
            source_key=str(source_entity_id),
            source_entity_id=source_entity_id,
            builder_version="team-v1",
            chunking_version="chunk-v1",
            provider_name="fake",
            model_name="gemini-embedding-001",
            embedding_dimension=DIMENSION,
            status=RagSourceStatus.PENDING,
        )
        session.add(state)
        await session.flush()
        document = RagDocument(
            id=document_id,
            source_state_id=state.id,
            source_type="team",
            source_key=str(source_entity_id),
            source_entity_id=source_entity_id,
            semantic_text="Team: Falcons",
            provenance_metadata={"source_type": "team"},
            scope_metadata={"source_type": "team"},
            player_ids=[],
            team_ids=[source_entity_id],
            age_groups=["U15"],
            is_all_academy=False,
            content_hash=canonical_content_hash("Team: Falcons"),
            builder_version="team-v1",
            chunking_version="chunk-v1",
            is_searchable=True,
        )
        session.add(document)
        await session.flush()

        with pytest.raises(StatementError):
            async with session.begin_nested():
                session.add(
                    RagChunk(
                        id=uuid4(),
                        document_id=document_id,
                        source_type="team",
                        source_key=str(source_entity_id),
                        ordinal=0,
                        semantic_text="wrong dimension",
                        content_hash=canonical_content_hash("wrong dimension"),
                        provenance_metadata={},
                        scope_metadata={},
                        player_ids=[],
                        team_ids=[source_entity_id],
                        age_groups=["U15"],
                        is_all_academy=False,
                        embedding=[1.0, 0.0],
                        provider_name="fake",
                        model_name="gemini-embedding-001",
                        embedding_dimension=DIMENSION,
                        builder_version="team-v1",
                        chunking_version="chunk-v1",
                        is_searchable=True,
                    )
                )
                await session.flush()

        valid = RagChunk(
            id=derive_chunk_id(document_id, 0),
            document_id=document_id,
            source_type="team",
            source_key=str(source_entity_id),
            ordinal=0,
            semantic_text="valid",
            content_hash=canonical_content_hash("valid"),
            provenance_metadata={},
            scope_metadata={},
            player_ids=[],
            team_ids=[source_entity_id],
            age_groups=["U15"],
            is_all_academy=False,
            embedding=_unit_vector(0),
            provider_name="fake",
            model_name="gemini-embedding-001",
            embedding_dimension=DIMENSION,
            builder_version="team-v1",
            chunking_version="chunk-v1",
            is_searchable=True,
        )
        session.add(valid)
        await session.flush()

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    RagChunk(
                        id=uuid4(),
                        document_id=document_id,
                        source_type="team",
                        source_key=str(source_entity_id),
                        ordinal=0,
                        semantic_text="duplicate ordinal",
                        content_hash=canonical_content_hash("duplicate ordinal"),
                        provenance_metadata={},
                        scope_metadata={},
                        player_ids=[],
                        team_ids=[source_entity_id],
                        age_groups=["U15"],
                        is_all_academy=False,
                        embedding=_unit_vector(1),
                        provider_name="fake",
                        model_name="gemini-embedding-001",
                        embedding_dimension=DIMENSION,
                        builder_version="team-v1",
                        chunking_version="chunk-v1",
                        is_searchable=True,
                    )
                )
                await session.flush()

        await session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_source_claims_use_versions_leases_and_no_audit_writers() -> None:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    async with AsyncSessionFactory() as session:
        business_before = await session.scalar(
            select(func.count()).select_from(BusinessAuditEvent)
        )
        auth_before = await session.scalar(
            select(func.count()).select_from(AuthAuditLog)
        )
        service = RagIndexingStateService(session)
        first_run = await service.start_run(RagRunMode.INCREMENTAL, now=now)
        second_run = await service.start_run(RagRunMode.REPAIR, now=now)
        state = await service.create_source_state(
            source_type="player_profile",
            source_key=str(uuid4()),
            source_entity_id=uuid4(),
            builder_version="player-v1",
            chunking_version="chunk-v1",
            profile=EmbeddingProfile(
                "fake",
                "gemini-embedding-001",
                DIMENSION,
                "fake-v1",
            ),
        )

        first_claim = await service.claim_source(
            state.id,
            expected_version=1,
            run_id=first_run.id,
            now=now,
            lease_seconds=30,
        )
        assert first_claim.version_number == 2
        assert first_claim.claim_run_id == first_run.id
        assert first_claim.status == RagSourceStatus.INDEXING

        with pytest.raises(RagClaimConflictError):
            await service.claim_source(
                state.id,
                expected_version=2,
                run_id=second_run.id,
                now=now + timedelta(seconds=10),
                lease_seconds=30,
            )

        recovered = await service.claim_source(
            state.id,
            expected_version=2,
            run_id=second_run.id,
            now=now + timedelta(seconds=31),
            lease_seconds=30,
        )
        assert recovered.version_number == 3
        assert recovered.claim_run_id == second_run.id

        failed = await service.mark_source_failed(
            state.id,
            expected_version=3,
            run_id=second_run.id,
            failure=technical_failure(
                "timeout",
                "Embedding provider timed out.",
            ),
        )
        assert failed.version_number == 4
        assert failed.status == RagSourceStatus.FAILED
        assert failed.claim_run_id is None
        assert failed.failure_message == "Embedding provider timed out."

        failure = technical_failure("timeout", "Embedding provider timed out.")
        await service.finish_run(
            second_run,
            status=RagRunStatus.PARTIAL,
            counters=RagRunCounters(
                source_records_inspected=1,
                failed_sources=1,
            ),
            failure=failure,
            now=now + timedelta(seconds=32),
        )
        report = report_from_run(second_run)
        assert report.status is RagRunStatus.PARTIAL
        assert report.counters.source_records_inspected == 1
        assert report.counters.failed_sources == 1
        assert report.failure_message == "Embedding provider timed out."

        assert (
            await session.scalar(select(func.count()).select_from(BusinessAuditEvent))
            == business_before
        )
        assert (
            await session.scalar(select(func.count()).select_from(AuthAuditLog))
            == auth_before
        )
        await session.rollback()
