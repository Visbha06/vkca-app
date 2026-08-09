"""Integration coverage for bounded Data Quality reads and filters."""

from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.user import User


@pytest_asyncio.fixture
async def client():
    """Exercise the registered route with a Head Coach identity override."""

    actor = User(
        id=uuid4(),
        first_name="Integration",
        last_name="Head Coach",
        email=f"quality-read-{uuid4().hex}@example.test",
        hashed_password="unused-dependency-override",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )

    async def override_current_user():
        return actor, Mock(spec=AuthSession)

    app.dependency_overrides[get_current_user] = override_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_read_filters_are_bounded_deterministic_and_audit_free(
    client: httpx.AsyncClient,
    quality_data_builder,
) -> None:
    """Filters affect only the page while the global summary remains intact."""

    await quality_data_builder.player(first_name="Zoe", last_name="Unassigned")
    await quality_data_builder.player(first_name="Ada", last_name="Unassigned")
    await quality_data_builder.team(name="U13 Uncovered")
    await quality_data_builder.commit()

    async with AsyncSessionFactory() as session:
        audit_count_before = await session.scalar(
            select(func.count(BusinessAuditEvent.id))
        )

    first = await client.get(
        "/api/v1/data-quality",
        params={"severity": "warning", "domain": "players", "page_size": 1},
    )
    second = await client.get(
        "/api/v1/data-quality",
        params={"severity": "warning", "domain": "players", "page_size": 1},
    )
    by_rule = await client.get(
        "/api/v1/data-quality",
        params={"rule_id": "player.active_unassigned"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert by_rule.status_code == 200, by_rule.text
    first_body = first.json()
    assert first_body["page_size"] == 1
    assert first_body["total_findings"] == 2
    assert first_body["total_pages"] == 2
    assert first_body["has_next"] is True
    assert first_body["summary"]["total_findings"] > first_body["total_findings"]
    assert first_body["findings"] == second.json()["findings"]
    assert [item["rule_id"] for item in by_rule.json()["findings"]] == [
        "player.active_unassigned",
        "player.active_unassigned",
    ]

    invalid = await client.get("/api/v1/data-quality?domain=invalid")
    assert invalid.status_code == 422

    async with AsyncSessionFactory() as session:
        audit_count_after = await session.scalar(
            select(func.count(BusinessAuditEvent.id))
        )
    assert audit_count_after == audit_count_before
