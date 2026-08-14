"""Unit coverage for RAG-only claims and sanitized operational telemetry."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_source_state import RagSourceState
from src.services.rag.contracts import RagRunMode, RagSourceStatus
from src.services.rag.embedding import EmbeddingTimeoutError
from src.services.rag.indexing import (
    RagIndexingStateService,
    failure_from_exception,
    lease_is_available,
    sanitize_technical_message,
)


def test_technical_telemetry_redacts_credentials_and_never_uses_raw_exceptions() -> (
    None
):
    sanitized = sanitize_technical_message(
        "provider failed api_key=top-secret "
        "postgresql://admin:database-password@localhost/db"
    )
    generic = failure_from_exception(
        RuntimeError("request body token=raw-secret and a full canonical document")
    )
    provider = failure_from_exception(EmbeddingTimeoutError())

    assert "top-secret" not in sanitized
    assert "database-password" not in sanitized
    assert "raw-secret" not in generic.message
    assert "canonical document" not in generic.message
    assert provider.code == "timeout"
    assert provider.message == "Embedding provider timed out."


def test_lease_availability_respects_current_owner_and_expiration() -> None:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    owner_id, other_id = uuid4(), uuid4()
    state = RagSourceState(
        source_type="player_profile",
        source_key="player-1",
        builder_version="player-v1",
        chunking_version="chunk-v1",
        provider_name="fake",
        model_name="gemini-embedding-001",
        embedding_dimension=1536,
        status=RagSourceStatus.INDEXING,
        claim_run_id=owner_id,
        lease_expires_at=now + timedelta(seconds=30),
    )

    assert lease_is_available(state, run_id=owner_id, now=now)
    assert not lease_is_available(state, run_id=other_id, now=now)
    assert lease_is_available(
        state,
        run_id=other_id,
        now=now + timedelta(seconds=31),
    )


@pytest.mark.asyncio
async def test_start_run_flushes_but_never_commits_or_writes_audit_state() -> None:
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    run = await RagIndexingStateService(session).start_run(RagRunMode.FULL)

    session.add.assert_called_once_with(run)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_awaited()
    assert run.mode is RagRunMode.FULL
    assert run.status == "indexing"
