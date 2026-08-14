"""Integration coverage for the Head Coach-only Data Quality boundary."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.user import User

RequestAsRole = Callable[..., Awaitable[httpx.Response]]


@pytest_asyncio.fixture(loop_scope="session")
async def request_as_role() -> RequestAsRole:
    """Issue requests with persisted users and sessions for real denial logging."""

    actors: dict[UserRole, tuple[User, AuthSession]] = {}
    async with AsyncSessionFactory() as setup_session:
        pending_sessions: list[AuthSession] = []
        for role in UserRole:
            user = User(
                id=uuid4(),
                first_name="Authorization",
                last_name=role.value.title(),
                email=(
                    "data-quality-auth-"
                    f"{role.value.replace(' ', '-')}-{uuid4().hex}@example.test"
                ),
                hashed_password="unused-test-hash",
                role=role,
                is_active=True,
            )
            auth_session = AuthSession(
                id=uuid4(),
                user_id=user.id,
                token_family_id=uuid4(),
                current_token_hash=uuid4().hex + uuid4().hex,
                rotated_token_hashes=[],
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            setup_session.add(user)
            pending_sessions.append(auth_session)
            actors[role] = (user, auth_session)
        await setup_session.flush()
        setup_session.add_all(pending_sessions)
        await setup_session.commit()

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:

        async def request(
            role: UserRole,
            method: str,
            path: str,
            **kwargs: Any,
        ) -> httpx.Response:
            actor, auth_session = actors[role]

            async def override_current_user():
                return actor, auth_session

            app.dependency_overrides[get_current_user] = override_current_user
            return await client.request(method, path, **kwargs)

        try:
            yield request
        finally:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ASSISTANT_COACH, UserRole.PLAYER])
@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/api/v1/data-quality", {}),
        (
            "POST",
            "/api/v1/data-quality/remediations",
            {
                "json": {
                    "finding_id": "authorization-test-finding",
                    "action": "remove_inactive_assistant_assignment",
                    "coach_id": str(uuid4()),
                    "team_id": str(uuid4()),
                    "expected_coach_version": 1,
                    "confirmed": True,
                }
            },
        ),
    ],
)
async def test_non_head_coaches_are_forbidden_on_every_data_quality_endpoint(
    request_as_role: RequestAsRole,
    role: UserRole,
    method: str,
    path: str,
    request_kwargs: dict[str, Any],
) -> None:
    """Authorization denies before evaluation/mutation and logs security only."""

    async with AsyncSessionFactory() as session:
        business_before = await session.scalar(
            select(func.count(BusinessAuditEvent.id))
        )
        security_before = await session.scalar(
            select(func.count(AuthAuditLog.id)).where(
                AuthAuditLog.event_type == "authorization_denial",
            )
        )

    response = await request_as_role(role, method, path, **request_kwargs)

    assert response.status_code == 403, response.text
    async with AsyncSessionFactory() as session:
        business_after = await session.scalar(select(func.count(BusinessAuditEvent.id)))
        security_after = await session.scalar(
            select(func.count(AuthAuditLog.id)).where(
                AuthAuditLog.event_type == "authorization_denial",
            )
        )

    assert business_after == business_before
    assert security_after == security_before + 1


@pytest.mark.asyncio
async def test_head_coach_can_read_and_remediate_without_security_denial(
    request_as_role: RequestAsRole,
    quality_data_builder,
) -> None:
    """Both protected capabilities remain callable for a Head Coach."""

    team = await quality_data_builder.team(name="Authorization Falcons")
    coach = await quality_data_builder.coach(
        first_name="Inactive",
        last_name="Assistant",
        role=UserRole.ASSISTANT_COACH,
        is_active=False,
        version_number=3,
    )
    await quality_data_builder.coach_assignment(team=team, coach=coach)
    await quality_data_builder.commit()

    read = await request_as_role(
        UserRole.HEAD_COACH,
        "GET",
        "/api/v1/data-quality",
        params={"rule_id": "coach.inactive_assigned"},
    )
    assert read.status_code == 200, read.text
    finding = read.json()["findings"][0]
    remediation = finding["direct_remediation"]
    assert remediation is not None

    applied = await request_as_role(
        UserRole.HEAD_COACH,
        "POST",
        "/api/v1/data-quality/remediations",
        json={
            "finding_id": finding["finding_id"],
            "action": remediation["action"],
            "coach_id": remediation["coach_id"],
            "team_id": remediation["team_id"],
            "expected_coach_version": remediation["expected_coach_version"],
            "confirmed": True,
        },
    )
    assert applied.status_code == 200, applied.text

    async with AsyncSessionFactory() as session:
        security_events = list(
            (
                await session.scalars(
                    select(AuthAuditLog).where(
                        AuthAuditLog.event_type == "authorization_denial",
                    )
                )
            ).all()
        )
        business_events = list(
            (await session.scalars(select(BusinessAuditEvent))).all()
        )

    assert security_events == []
    assert len(business_events) == 1
