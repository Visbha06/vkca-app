"""Safe operational status projections for RAG indexing runs."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from scripts.rag_index import _safe_status_report
from src.models.rag_index_run import RagIndexRun
from src.models.rag_source_state import RagSourceState
from src.services.rag.contracts import RagRunMode, RagRunStatus, RagSourceStatus
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService


class ScalarRows:
    def __init__(self, values):
        self.values = tuple(values)

    def all(self):
        return self.values


@pytest.mark.asyncio
async def test_status_projects_only_bounded_run_and_source_telemetry():
    now = datetime(2026, 8, 14, tzinfo=UTC)
    run = RagIndexRun(
        id=uuid4(),
        mode=RagRunMode.REPAIR,
        status=RagRunStatus.PARTIAL,
        started_at=now - timedelta(minutes=1),
        finished_at=now,
        failed_sources=1,
    )
    state = RagSourceState(
        id=uuid4(),
        source_type="synthetic_note",
        source_key="note-1",
        builder_version="synthetic-v1",
        chunking_version="chunk-v1",
        provider_name="fake",
        model_name="gemini-embedding-001",
        embedding_dimension=1536,
        status=RagSourceStatus.FAILED,
        failure_code="timeout",
        failure_message="token=raw-secret",
        last_attempt_at=now,
    )
    session = AsyncMock()
    session.scalars = AsyncMock(side_effect=(ScalarRows((run,)), ScalarRows((state,))))
    service = RagIndexingService(
        session,
        provider=FakeEmbeddingProvider(),
        batch_size=8,
        timeout_seconds=5,
    )

    report = await service.inspect_status(source_type="synthetic_note", now=now)

    assert report.runs[0].status is RagRunStatus.PARTIAL
    assert report.status_counts == {"failed": 1}
    assert report.recoverable_source_count == 1
    assert report.sources[0].failure_message == "token=[redacted]"
    serialized = repr(report)
    for forbidden in ("semantic_text", "embedding=", "raw-secret", "password"):
        assert forbidden not in serialized
    command_output = _safe_status_report(report)
    assert command_output["repair_guidance"] is not None
    assert "raw-secret" not in repr(command_output)
    assert "semantic_text" not in repr(command_output)
    assert "embedding=" not in repr(command_output)


@pytest.mark.asyncio
async def test_expired_interrupted_claim_is_reported_as_recoverable():
    now = datetime(2026, 8, 14, tzinfo=UTC)
    state = RagSourceState(
        id=uuid4(),
        source_type="synthetic_note",
        source_key="note-1",
        builder_version="synthetic-v1",
        chunking_version="chunk-v1",
        provider_name="fake",
        model_name="gemini-embedding-001",
        embedding_dimension=1536,
        status=RagSourceStatus.INDEXING,
        lease_expires_at=now - timedelta(seconds=1),
    )
    session = AsyncMock()
    session.scalars = AsyncMock(side_effect=(ScalarRows(()), ScalarRows((state,))))
    service = RagIndexingService(
        session,
        provider=FakeEmbeddingProvider(),
        batch_size=8,
        timeout_seconds=5,
    )

    report = await service.inspect_status(now=now)

    assert report.sources[0].recoverable
    assert report.recoverable_source_count == 1
