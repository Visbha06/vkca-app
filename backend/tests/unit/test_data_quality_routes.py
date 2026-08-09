"""Route coverage for the Head Coach-only Data Quality read API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import AuditActionType, QualityAction, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.user import User
from src.schemas.data_quality import (
    DataQualityPageResponse,
    DataQualityRemediationResult,
    DataQualitySummary,
)
from src.services.data_quality_service import (
    DataQualityRemediationConflictError,
    DataQualityRemediationValidationError,
)
from src.services.team_service import TeamNotFoundError


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
    service.remediate = AsyncMock(
        return_value=DataQualityRemediationResult(
            action=QualityAction.NORMALIZE_ROSTER_ORDER,
            message="The roster order was normalized.",
            affected_entity_id=uuid4(),
            audit_action=AuditActionType.ROSTER_REORDERED,
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


def _remediation_body(action: str) -> dict[str, object]:
    finding_id = f"quality-finding:{uuid4()}"
    if action == "normalize_roster_order":
        return {
            "finding_id": finding_id,
            "action": action,
            "team_id": str(uuid4()),
            "expected_team_version": 2,
            "confirmed": True,
        }
    if action == "remove_inactive_player":
        return {
            "finding_id": finding_id,
            "action": action,
            "team_id": str(uuid4()),
            "player_id": str(uuid4()),
            "expected_team_version": 2,
            "confirmed": True,
        }
    return {
        "finding_id": finding_id,
        "action": action,
        "coach_id": str(uuid4()),
        "team_id": str(uuid4()),
        "expected_coach_version": 2,
        "confirmed": True,
    }


@pytest.mark.asyncio
async def test_head_coach_can_apply_a_typed_remediation(
    client,
    quality_service,
) -> None:
    response = await client.post(
        "/api/v1/data-quality/remediations",
        json=_remediation_body("normalize_roster_order"),
        headers={"X-Request-ID": "quality-route-request"},
    )

    assert response.status_code == 200, response.text
    command = quality_service.remediate.await_args.args[0]
    actor = quality_service.remediate.await_args.kwargs["actor"]
    assert command.action is QualityAction.NORMALIZE_ROSTER_ORDER
    assert actor.role is UserRole.HEAD_COACH
    assert actor.request_id == "quality-route-request"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ASSISTANT_COACH, UserRole.PLAYER])
@pytest.mark.parametrize(
    "action",
    [
        "normalize_roster_order",
        "remove_inactive_player",
        "remove_inactive_assistant_assignment",
    ],
)
async def test_non_head_coaches_are_denied_before_each_remediation_capability(
    client,
    quality_service,
    role,
    action,
) -> None:
    async def override_current_user():
        return _user(role), Mock(spec=AuthSession)

    app.dependency_overrides[get_current_user] = override_current_user

    response = await client.post(
        "/api/v1/data-quality/remediations",
        json=_remediation_body(action),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}
    quality_service.remediate.assert_not_awaited()


@pytest.mark.asyncio
async def test_remediation_action_allowlist_rejects_unknown_actions(
    client,
    quality_service,
) -> None:
    response = await client.post(
        "/api/v1/data-quality/remediations",
        json={
            "finding_id": "unsafe",
            "action": "run_sql",
            "team_id": str(uuid4()),
            "confirmed": True,
        },
    )

    assert response.status_code == 422
    quality_service.remediate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,expected_status",
    [
        (DataQualityRemediationValidationError("Confirmation is required."), 400),
        (TeamNotFoundError(), 404),
        (DataQualityRemediationConflictError("The finding changed."), 409),
    ],
)
async def test_remediation_errors_use_safe_documented_status_codes(
    client,
    quality_service,
    error,
    expected_status,
) -> None:
    quality_service.remediate.side_effect = error

    response = await client.post(
        "/api/v1/data-quality/remediations",
        json=_remediation_body("normalize_roster_order"),
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)
