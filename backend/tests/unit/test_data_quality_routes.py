"""Route coverage for the Head Coach-only Data Quality read API."""

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
from src.schemas.data_quality import DataQualityPageResponse, DataQualitySummary


def _user(role: UserRole) -> User:
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
def quality_service(mocker):
    service = Mock()
    service.list_findings = AsyncMock(
        return_value=DataQualityPageResponse(
            findings=[],
            summary=DataQualitySummary(
                total_findings=0,
                critical_count=0,
                warning_count=0,
                info_count=0,
                domain_counts={
                    "players": 0,
                    "teams": 0,
                    "rosters": 0,
                    "coaches": 0,
                    "calendar": 0,
                },
            ),
            page=1,
            page_size=20,
            total_findings=0,
            total_pages=0,
            has_previous=False,
            has_next=False,
        )
    )
    mocker.patch("src.routes.data_quality.DataQualityService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client(quality_service):
    session = Mock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()

    async def override_get_db():
        yield session

    async def override_current_user():
        return _user(UserRole.HEAD_COACH), Mock(spec=AuthSession)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_head_coach_receives_bounded_page_and_typed_filters(
    client, quality_service
) -> None:
    response = await client.get(
        "/api/v1/data-quality?severity=warning&domain=players&rule_id=player.active_unassigned&page=2&page_size=25"
    )

    assert response.status_code == 200
    query = quality_service.list_findings.await_args.args[0]
    assert query.page == 2 and query.page_size == 25
    assert query.severity.value == "warning" and query.domain.value == "players"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ASSISTANT_COACH, UserRole.PLAYER])
async def test_non_head_coaches_are_denied_before_service_evaluation(
    client, quality_service, role
) -> None:
    async def override_current_user():
        return _user(role), Mock(spec=AuthSession)

    app.dependency_overrides[get_current_user] = override_current_user

    response = await client.get("/api/v1/data-quality")

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}
    quality_service.list_findings.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query", ["?page=0", "?page_size=101", "?severity=unsafe", "?rule_id=all.rules"]
)
async def test_invalid_filters_are_rejected_before_evaluation(
    client, quality_service, query
) -> None:
    response = await client.get(f"/api/v1/data-quality{query}")

    assert response.status_code == 422
    quality_service.list_findings.assert_not_awaited()
