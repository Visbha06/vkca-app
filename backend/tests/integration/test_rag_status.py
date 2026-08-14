"""Operational status, repair, and redaction behavior against RAG persistence."""

from uuid import uuid4

import pytest

from src.database import AsyncSessionFactory
from src.services.rag.embedding import EmbeddingUnavailableError, FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from tests.fixtures.rag_synthetic import (
    SYNTHETIC_SOURCE_TYPE,
    SyntheticNote,
    synthetic_registry,
)


class UnavailableProvider(FakeEmbeddingProvider):
    async def embed_documents(self, *args, **kwargs):
        del args, kwargs
        raise EmbeddingUnavailableError()


@pytest.mark.asyncio(loop_scope="session")
async def test_status_reports_partial_failure_repair_and_deletion_without_content():
    note = SyntheticNote(
        id=uuid4(),
        title="Private training title",
        summary="Private semantic body",
    )
    registry, loader = synthetic_registry((note,))

    async with AsyncSessionFactory() as session:
        failed = RagIndexingService(
            session,
            provider=UnavailableProvider(),
            batch_size=8,
            timeout_seconds=5,
            registry=registry,
        )
        partial = await failed.run_full()
        partial_status = await failed.inspect_status(source_type=SYNTHETIC_SOURCE_TYPE)
        assert partial.status.value == "partial"
        assert partial_status.recoverable_source_count == 1
        assert partial_status.sources[0].failure_code == "provider_unavailable"

        repaired = RagIndexingService(
            session,
            provider=FakeEmbeddingProvider(),
            batch_size=8,
            timeout_seconds=5,
            registry=registry,
        )
        completed = await repaired.run_repair()
        assert completed.status.value == "completed"

        loader.notes = ()
        deleted = await repaired.run_incremental()
        status = await repaired.inspect_status(source_type=SYNTHETIC_SOURCE_TYPE)
        assert deleted.counters.deleted_or_ineligible == 1
        assert status.sources[0].status.value == "deleted"
        serialized = repr(status)
        assert "Private training title" not in serialized
        assert "Private semantic body" not in serialized
        assert "embedding=" not in serialized
        await session.rollback()
