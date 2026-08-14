"""Unit contract coverage for the authenticated RAG retrieval route."""

from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.user import User
from src.routes.rag import get_rag_retrieval_service
from src.schemas.rag import (
    RagRetrievalProvenance,
    RagRetrievalResponse,
    RagRetrievalResult,
)
from src.services.rag.embedding import EmbeddingTimeoutError


@pytest.fixture
def current_user() -> User:
    return User(
        id=uuid4(),
        first_name="Route",
        last_name="Head",
        email=f"rag-route-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )


@pytest.fixture
def retrieval_service():
    service = AsyncMock()
    service.retrieve.return_value = RagRetrievalResponse(
        results=[
            RagRetrievalResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                source_type="team",
                source_key="team-1",
                text="Team: U13 Blue",
                score=0.1,
                provenance=RagRetrievalProvenance(
                    source_type="team",
                    source_entity_id=uuid4(),
                ),
            )
        ],
        returned_count=1,
        limit=5,
    )
    return service


@pytest_asyncio.fixture
async def client(current_user, retrieval_service):
    async def authenticated():
        return current_user, object()

    app.dependency_overrides[get_current_user] = authenticated
    app.dependency_overrides[get_rag_retrieval_service] = lambda: retrieval_service
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as api_client:
        yield api_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_route_returns_bounded_results_without_answer_or_vector(
    client,
    retrieval_service,
):
    response = await client.get(
        "/api/v1/rag/retrieval",
        params={"query": "practice", "limit": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["returned_count"] == 1
    assert "answer" not in payload
    assert "embedding" not in payload["results"][0]
    assert "vector" not in payload["results"][0]
    retrieval_service.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_returns_valid_empty_result_for_unlinked_player(
    client,
    retrieval_service,
):
    retrieval_service.retrieve.return_value = RagRetrievalResponse(
        results=[],
        returned_count=0,
        limit=5,
    )

    response = await client.get(
        "/api/v1/rag/retrieval",
        params={"query": "practice", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"results": [], "returned_count": 0, "limit": 5}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"query": "", "limit": 5},
        {"query": "practice", "limit": 0},
        {"query": "practice", "limit": 21},
        {"query": "practice", "limit": 5, "team_id": str(uuid4())},
        {"query": "practice", "limit": 5, "role": "head coach"},
        {"query": "practice", "limit": 5, "scope": "academy"},
    ],
)
async def test_route_rejects_invalid_or_client_selected_scope(client, params):
    response = await client.get("/api/v1/rag/retrieval", params=params)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_route_maps_provider_failures_to_sanitized_503(
    client,
    retrieval_service,
):
    retrieval_service.retrieve.side_effect = EmbeddingTimeoutError()

    response = await client.get(
        "/api/v1/rag/retrieval",
        params={"query": "practice", "limit": 5},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "RAG retrieval is temporarily unavailable."}


@pytest.mark.asyncio
async def test_route_requires_existing_authentication_dependency():
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as unauthenticated:
        response = await unauthenticated.get(
            "/api/v1/rag/retrieval",
            params={"query": "practice", "limit": 5},
        )

    assert response.status_code == 401
