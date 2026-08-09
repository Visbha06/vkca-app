"""Route coverage for the Head Coach-only business audit read API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.user import User
from src.routes.business_audit import router as business_audit_router
from src.schemas.business_audit import (
    BusinessAuditActorOption,
    BusinessAuditActorOptionsResponse,
    BusinessAuditPageResponse,
    RecentBusinessAuditResponse,
)


def make_user(role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        first_name="Asha",
        last_name="Coach",
        email="asha@example.test",
        hashed_password="unit-test",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


@pytest.fixture
def audit_service(mocker):
    service = Mock()
    service.list_events = AsyncMock(
        return_value=BusinessAuditPageResponse(
            events=[],
            page=1,
            page_size=20,
            total_events=0,
            total_pages=0,
            has_previous=False,
            has_next=False,
        )
    )
    service.list_recent = AsyncMock(return_value=RecentBusinessAuditResponse(events=[]))
    service.list_actor_options = AsyncMock(
        return_value=BusinessAuditActorOptionsResponse(actors=[])
    )
    mocker.patch("src.routes.business_audit.BusinessAuditService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client(audit_service):
    session = AsyncMock()
    session.add = Mock()

    async def override_get_db():
        yield session

    user = make_user(UserRole.HEAD_COACH)

    async def override_current_user():
        return user, Mock(spec=AuthSession)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_head_coach_can_get_actor_options_and_full_log(
    client, audit_service
) -> None:
    actor_id = uuid4()
    target_id = uuid4()
    audit_service.list_actor_options.return_value = BusinessAuditActorOptionsResponse(
        actors=[
            BusinessAuditActorOption(
                actor_user_id=actor_id,
                actor_display_name="Alex Morgan",
                actor_role="head coach",
            )
        ]
    )

    actors = await client.get("/api/v1/audit-log/actors")
    events = await client.get(
        f"/api/v1/audit-log?actor_user_id={actor_id}&target_entity_id={target_id}&action_category=player"
        "&action_type=player.created&entity_type=player&page=2&page_size=25"
        "&start_date=2026-01-01&end_date=2026-01-02"
    )

    assert actors.status_code == 200
    assert actors.json()["actors"][0]["actor_display_name"] == "Alex Morgan"
    assert events.status_code == 200
    query = audit_service.list_events.await_args.args[0]
    assert query.actor_user_id == actor_id
    assert query.target_entity_id == target_id
    assert query.page == 2 and query.page_size == 25
    assert query.action_category.value == "player"
    assert query.action_type.value == "player.created"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ASSISTANT_COACH, UserRole.PLAYER])
@pytest.mark.parametrize("path", ["", "/actors", "/recent"])
async def test_non_head_coaches_are_denied_without_service_access(
    client, audit_service, role, path
) -> None:
    user = make_user(role)

    async def override_current_user():
        return user, Mock(spec=AuthSession)

    app.dependency_overrides[get_current_user] = override_current_user
    response = await client.get(f"/api/v1/audit-log{path}")

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}
    audit_service.list_events.assert_not_awaited()
    audit_service.list_recent.assert_not_awaited()
    audit_service.list_actor_options.assert_not_awaited()


@pytest.mark.asyncio
async def test_actor_options_are_safe_empty_when_history_has_no_actors(
    client, audit_service
) -> None:
    response = await client.get("/api/v1/audit-log/actors")

    assert response.status_code == 200
    assert response.json() == {"actors": []}


@pytest.mark.asyncio
async def test_actor_options_preserve_bounded_alphabetical_deduplicated_snapshots(
    client, audit_service
) -> None:
    actor_ids = [uuid4() for _ in range(100)]
    audit_service.list_actor_options.return_value = BusinessAuditActorOptionsResponse(
        actors=[
            BusinessAuditActorOption(
                actor_user_id=actor_id,
                actor_display_name=f"Actor {index:03d}",
                actor_role="assistant coach",
            )
            for index, actor_id in enumerate(actor_ids)
        ]
    )

    response = await client.get("/api/v1/audit-log/actors")
    actors = response.json()["actors"]

    assert response.status_code == 200
    assert len(actors) == 100
    assert [actor["actor_display_name"] for actor in actors] == sorted(
        actor["actor_display_name"] for actor in actors
    )
    assert len({actor["actor_user_id"] for actor in actors}) == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "?page=0",
        "?page_size=101",
        "?actor_user_id=not-a-uuid",
        "?action_category=security",
        "?start_date=2026-02-02&end_date=2026-02-01",
        "?start_date=2025-01-01&end_date=2026-01-02",
    ],
)
async def test_invalid_filters_are_rejected_before_retrieval(
    client, audit_service, query
) -> None:
    response = await client.get(f"/api/v1/audit-log{query}")

    assert response.status_code == 422
    audit_service.list_events.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["0", "5"])
async def test_recent_limit_is_enforced_by_route_validation(
    client, audit_service, limit
) -> None:
    response = await client.get(f"/api/v1/audit-log/recent?limit={limit}")

    assert response.status_code == 422
    audit_service.list_recent.assert_not_awaited()


@pytest.mark.asyncio
async def test_unexpected_retrieval_failure_is_safe(client, audit_service) -> None:
    audit_service.list_events.side_effect = RuntimeError("database password leaked")
    response = await client.get("/api/v1/audit-log")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}


def test_business_audit_router_has_no_update_or_delete_operations() -> None:
    methods = {
        method
        for route in business_audit_router.routes
        for method in getattr(route, "methods", set())
    }

    assert methods == {"GET"}
