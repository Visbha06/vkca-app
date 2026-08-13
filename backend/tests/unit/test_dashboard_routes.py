"""Route tests for the authenticated current-user dashboard capability."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException

from src.database import get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.schemas.dashboard import DashboardResponse


def dashboard_response(role: UserRole = UserRole.HEAD_COACH) -> DashboardResponse:
    player_slot = (
        {
            "status": "ready",
            "data": {"kind": "player_teams", "team_count": 0, "team_names": []},
        }
        if role is UserRole.PLAYER
        else {
            "status": "ready",
            "data": {
                "kind": "active_player_count",
                "count": 0,
                "team_count": 0,
            },
        }
    )
    context = (
        {
            "status": "ready",
            "data": {
                "kind": "recent_activity",
                "events": [],
                "view_all_path": "/audit-log",
            },
        }
        if role is UserRole.HEAD_COACH
        else {
            "status": "ready",
            "data": {"kind": "my_teams", "teams": [], "view_all_path": "/teams"},
        }
    )
    return DashboardResponse.model_validate(
        {
            "user": {
                "id": str(uuid4()),
                "display_name": "Asha Account",
                "role": role,
            },
            "dashboard_state": "ready",
            "summary": {
                "training": {"status": "empty", "message": "No training."},
                "next_match": {"status": "empty", "message": "No matches."},
                "player_slot": player_slot,
            },
            "upcoming_events": {"status": "empty", "message": "No events."},
            "context": context,
        }
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.get_dashboard = AsyncMock()
    mocker.patch("src.routes.dashboard.DashboardService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    session = Mock()
    session.add = Mock()

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return Mock(id=uuid4(), role=UserRole.HEAD_COACH), Mock(id=uuid4())

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", [UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH, UserRole.PLAYER]
)
async def test_all_authenticated_roles_receive_current_user_dashboard(
    client, service_mock, role
) -> None:
    test_client, _session = client
    user = Mock(id=uuid4(), role=role)

    async def current_user():
        return user, Mock(id=uuid4())

    app.dependency_overrides[get_current_user] = current_user
    service_mock.get_dashboard.return_value = dashboard_response(role)

    response = await test_client.get("/api/v1/dashboard")

    assert response.status_code == 200
    assert response.json()["user"]["role"] == role.value
    service_mock.get_dashboard.assert_awaited_once_with(user)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_authentication_and_authorization_failures_are_preserved(
    client, service_mock, status_code
) -> None:
    test_client, _session = client

    async def denied():
        raise HTTPException(status_code=status_code, detail="Not authorized")

    app.dependency_overrides[get_current_user] = denied

    response = await test_client.get("/api/v1/dashboard")

    assert response.status_code == status_code
    service_mock.get_dashboard.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "user_id=00000000-0000-0000-0000-000000000001",
        "player_id=00000000-0000-0000-0000-000000000001",
        "coach_id=00000000-0000-0000-0000-000000000001",
        "team_ids=00000000-0000-0000-0000-000000000001",
    ],
)
async def test_route_rejects_every_client_selected_scope(
    client, service_mock, query
) -> None:
    test_client, _session = client

    response = await test_client.get(f"/api/v1/dashboard?{query}")

    assert response.status_code == 422
    service_mock.get_dashboard.assert_not_awaited()


@pytest.mark.asyncio
async def test_reads_and_retries_create_no_business_audit_writes(
    client, service_mock
) -> None:
    test_client, session = client
    service_mock.get_dashboard.return_value = dashboard_response()

    first = await test_client.get("/api/v1/dashboard")
    retry = await test_client.get("/api/v1/dashboard")

    assert first.status_code == 200
    assert retry.status_code == 200
    assert service_mock.get_dashboard.await_count == 2
    session.add.assert_not_called()
