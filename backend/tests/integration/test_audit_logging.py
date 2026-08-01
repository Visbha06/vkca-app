"""Integration coverage for the complete authentication audit trail."""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, select

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.password_service import PasswordService


@pytest.mark.asyncio
async def test_full_auth_flow_records_all_audit_events() -> None:
    """Fail login, then login, refresh, and logout with a complete audit trail."""

    user_id = uuid4()
    email = f"audit-flow-{user_id.hex}@example.com"
    password = "IntegrationP@ssword1"
    client_ip = "203.0.113.25"

    async with AsyncSessionFactory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                first_name="Audit",
                last_name="Integration",
                email=email,
                hashed_password=PasswordService.hash_password(password),
                role=UserRole.HEAD_COACH,
                is_active=True,
            )
        )
        await setup_session.commit()

    async def override_get_db():
        async with AsyncSessionFactory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_get_db
    app.state.rate_limiter.clear()
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
        client=(client_ip, 12345),
    )

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"User-Agent": "audit-integration-test"},
        ) as client:
            failed_login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongP@ssword1"},
            )
            assert failed_login.status_code == 401, failed_login.text

            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert login.status_code == 200, login.text

            refresh = await client.post(
                "/api/v1/auth/refresh",
                headers={"X-CSRF-Token": client.cookies["csrf_token"]},
            )
            assert refresh.status_code == 200, refresh.text

            audit_page = await client.get(
                "/api/v1/auth/audit-log",
                params={"user_id": str(user_id), "limit": 10, "offset": 0},
                headers={"Authorization": f"Bearer {refresh.json()['access_token']}"},
            )
            assert audit_page.status_code == 200, audit_page.text
            assert {item["event_type"] for item in audit_page.json()} == {
                "failed_login",
                "login",
                "token_refresh",
            }

            logout = await client.post(
                "/api/v1/auth/logout",
                headers={
                    "Authorization": f"Bearer {refresh.json()['access_token']}",
                    "X-CSRF-Token": client.cookies["csrf_token"],
                },
            )
            assert logout.status_code == 204, logout.text

        async with AsyncSessionFactory() as verification_session:
            records = list(
                (
                    await verification_session.scalars(
                        select(AuthAuditLog)
                        .where(AuthAuditLog.user_id == user_id)
                        .order_by(AuthAuditLog.event_timestamp)
                    )
                ).all()
            )

        assert [record.event_type for record in records] == [
            "failed_login",
            "login",
            "token_refresh",
            "logout",
        ]
        assert all(record.event_timestamp is not None for record in records)
        assert all(record.result in {"success", "failure"} for record in records)
        assert all(record.ip_address == client_ip for record in records)
        assert all(record.user_agent == "audit-integration-test" for record in records)
        serialized = " ".join(
            str(
                {
                    column.name: getattr(record, column.name)
                    for column in AuthAuditLog.__table__.columns
                }
            )
            for record in records
        )
        assert password not in serialized
        assert "WrongP@ssword1" not in serialized
        assert login.json()["access_token"] not in serialized
    finally:
        app.state.rate_limiter.clear()
        app.dependency_overrides.clear()
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id)
            )
            await cleanup_session.execute(
                delete(AuthSession).where(AuthSession.user_id == user_id)
            )
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
