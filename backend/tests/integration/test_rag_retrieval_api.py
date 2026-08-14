"""Authenticated HTTP and audit-isolation coverage for RAG retrieval."""

from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.business_audit_event import BusinessAuditEvent
from src.routes.rag import get_rag_embedding_provider
from src.services.rag.embedding import FakeEmbeddingProvider
from tests.integration.test_rag_authorization import _add_chunk


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as api_client:
        yield api_client


@pytest.mark.usefixtures("authenticated_client")
@pytest.mark.asyncio(loop_scope="session")
async def test_authenticated_route_is_bounded_redacted_and_audit_isolated(client):
    provider = FakeEmbeddingProvider()
    vector = (await provider.embed_query("academy knowledge")).values
    provider.query_call_count = 0
    app.dependency_overrides[get_rag_embedding_provider] = lambda: provider

    async with AsyncSessionFactory() as session:
        await _add_chunk(
            session,
            vector=vector,
            source_type="team",
            source_key=f"api-team-{uuid4()}",
        )
        await session.commit()
        business_before = int(
            await session.scalar(select(func.count()).select_from(BusinessAuditEvent))
            or 0
        )
        auth_before = int(
            await session.scalar(select(func.count()).select_from(AuthAuditLog)) or 0
        )

        response = await client.get(
            "/api/v1/rag/retrieval",
            params={"query": "academy knowledge", "limit": 1},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["returned_count"] <= 1
        assert payload["limit"] == 1
        assert "answer" not in payload
        assert "embedding" not in response.text
        assert "vector" not in response.text
        assert provider.query_call_count == 1
        assert (
            await session.scalar(select(func.count()).select_from(BusinessAuditEvent))
            == business_before
        )
        assert (
            await session.scalar(select(func.count()).select_from(AuthAuditLog))
            == auth_before
        )

        widened = await client.get(
            "/api/v1/rag/retrieval",
            params={
                "query": "academy knowledge",
                "limit": 1,
                "user_id": str(uuid4()),
                "team_id": str(uuid4()),
            },
        )
        assert widened.status_code == 422

    app.dependency_overrides.pop(get_rag_embedding_provider, None)
