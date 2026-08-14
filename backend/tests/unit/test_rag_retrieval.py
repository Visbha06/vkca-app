"""Unit coverage for bounded, authorization-first RAG retrieval."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from src.enums import UserRole
from src.models.user import User
from src.schemas.rag import RagRetrievalRequest
from src.services.rag.embedding import (
    EmbeddingCompatibilityError,
    FakeEmbeddingProvider,
)
from src.services.rag.retrieval import (
    RagRetrievalService,
    build_retrieval_statement,
)
from src.services.rag.scope import RagAccessScope


class Rows:
    def __init__(self, rows) -> None:
        self.rows = tuple(rows)

    def all(self):
        return self.rows


def _user() -> User:
    return User(
        id=uuid4(),
        first_name="Head",
        last_name="Coach",
        email=f"rag-retrieval-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )


def _scope(*, unlinked: bool = False) -> RagAccessScope:
    return RagAccessScope(
        user_id=uuid4(),
        role=UserRole.PLAYER if unlinked else UserRole.HEAD_COACH,
        is_active=True,
        linked_player_id=None,
        team_ids=(),
        age_groups=(),
        active_player_ids=(),
        is_unlinked_player=unlinked,
        can_read_all_registered_sources=not unlinked,
    )


def test_request_rejects_client_scope_and_invalid_result_limits():
    with pytest.raises(ValidationError):
        RagRetrievalRequest(query="practice", limit=5, team_id=str(uuid4()))
    with pytest.raises(ValidationError):
        RagRetrievalRequest(query="practice", limit=0)
    with pytest.raises(ValidationError):
        RagRetrievalRequest(query="practice", limit=21)


@pytest.mark.asyncio
async def test_unlinked_scope_returns_empty_without_embedding_or_candidate_query():
    session = AsyncMock()
    session.scalar.return_value = False
    provider = FakeEmbeddingProvider()
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=_scope(unlinked=True)))
    service = RagRetrievalService(
        session,
        provider=provider,
        scope_resolver=resolver,
        query_max_characters=100,
        result_limit_default=5,
        result_limit_max=20,
        timeout_seconds=5,
    )

    response = await service.retrieve(_user(), RagRetrievalRequest(query="practice"))

    assert response.results == []
    assert response.returned_count == 0
    assert response.limit == 5
    assert provider.query_call_count == 0
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_embeds_query_returns_safe_provenance_and_enforces_bounds():
    chunk_id, document_id, source_id = uuid4(), uuid4(), uuid4()
    session = AsyncMock()
    session.scalar.return_value = False
    session.execute.return_value = Rows(
        (
            (
                chunk_id,
                document_id,
                "player_profile",
                "player-1",
                "Player: Asha Khan",
                source_id,
                0.125,
            ),
        )
    )
    provider = FakeEmbeddingProvider()
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=_scope()))
    service = RagRetrievalService(
        session,
        provider=provider,
        scope_resolver=resolver,
        query_max_characters=20,
        result_limit_default=2,
        result_limit_max=3,
        timeout_seconds=5,
    )

    response = await service.retrieve(
        _user(), RagRetrievalRequest(query="  recent practice  ", limit=3)
    )

    assert provider.query_call_count == 1
    assert response.returned_count == 1
    assert response.limit == 3
    assert response.results[0].chunk_id == chunk_id
    assert response.results[0].document_id == document_id
    assert response.results[0].provenance.source_entity_id == source_id
    assert "embedding" not in response.results[0].model_dump()
    assert "vector" not in response.results[0].model_dump()

    with pytest.raises(ValueError, match="query"):
        await service.retrieve(_user(), RagRetrievalRequest(query="x" * 21, limit=2))
    with pytest.raises(ValueError, match="limit"):
        await service.retrieve(_user(), RagRetrievalRequest(query="practice", limit=4))


@pytest.mark.asyncio
async def test_authorized_scope_with_no_candidates_returns_a_safe_empty_result():
    session = AsyncMock()
    session.scalar.return_value = False
    session.execute.return_value = Rows(())
    provider = FakeEmbeddingProvider()
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=_scope()))
    response = await RagRetrievalService(
        session,
        provider=provider,
        scope_resolver=resolver,
        query_max_characters=100,
        result_limit_default=5,
        result_limit_max=20,
        timeout_seconds=5,
    ).retrieve(_user(), RagRetrievalRequest(query="nothing matches"))

    assert response.results == []
    assert response.returned_count == 0
    assert provider.query_call_count == 1
    session.execute.assert_awaited_once()


def test_candidate_statement_filters_before_cosine_order_with_stable_tie_breaker():
    statement = build_retrieval_statement(
        _scope(),
        query_vector=(1.0,) + (0.0,) * 1535,
        profile=FakeEmbeddingProvider().profile,
        limit=5,
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "WHERE" in sql
    assert "rag_chunks.is_searchable IS true" in sql
    assert "rag_chunks.embedding <=>" in sql
    assert sql.index("WHERE") < sql.index("ORDER BY") < sql.index("LIMIT")
    assert "rag_chunks.id" in sql[sql.index("ORDER BY") :]
    assert "rag_chunks.embedding," not in sql.partition("FROM")[0]


@pytest.mark.asyncio
async def test_incompatible_searchable_profile_fails_before_query_embedding():
    session = AsyncMock()
    session.scalar.return_value = True
    provider = FakeEmbeddingProvider()
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=_scope()))
    service = RagRetrievalService(
        session,
        provider=provider,
        scope_resolver=resolver,
        query_max_characters=100,
        result_limit_default=5,
        result_limit_max=20,
        timeout_seconds=5,
    )

    with pytest.raises(EmbeddingCompatibilityError):
        await service.retrieve(_user(), RagRetrievalRequest(query="practice"))

    assert provider.query_call_count == 0
    session.execute.assert_not_awaited()
