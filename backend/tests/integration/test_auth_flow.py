"""Integration coverage for the complete Phase 3 authentication journey."""

from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.password_service import PasswordService


@pytest_asyncio.fixture
async def client():
    """Exercise routes against the configured PostgreSQL test database."""

    async def override_get_db():
        async with AsyncSessionFactory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_access_logout_rejects_revoked_token(
    client: httpx.AsyncClient,
) -> None:
    """Log in, access /me, log out, then reject the same access token."""

    run_id = uuid4().hex
    user_id = uuid4()
    email = f"auth-flow-{run_id}@example.com"
    password = "IntegrationP@ssword1"

    async with AsyncSessionFactory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                first_name="Integration",
                last_name="Coach",
                email=email,
                hashed_password=PasswordService.hash_password(password),
                role=UserRole.HEAD_COACH,
                is_active=True,
            )
        )
        await setup_session.commit()

    try:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email.upper(), "password": password},
        )
        assert login.status_code == 200, login.text
        access_token = login.json()["access_token"]
        authorization = {"Authorization": f"Bearer {access_token}"}

        protected = await client.get("/api/v1/auth/me", headers=authorization)
        assert protected.status_code == 200, protected.text
        assert protected.json()["id"] == str(user_id)
        session_id = protected.json()["session"]["session_id"]

        logout_headers = {
            **authorization,
            "X-CSRF-Token": client.cookies["csrf_token"],
        }
        logout = await client.post("/api/v1/auth/logout", headers=logout_headers)
        assert logout.status_code == 204, logout.text

        rejected = await client.get("/api/v1/auth/me", headers=authorization)
        assert rejected.status_code == 401
        assert rejected.json() == {"detail": "Not authenticated"}

        async with AsyncSessionFactory() as verification_session:
            auth_session = await verification_session.scalar(
                select(AuthSession).where(AuthSession.id == UUID(session_id))
            )
            assert auth_session is not None
            assert auth_session.revoked_at is not None
            assert auth_session.revocation_reason == "logout"
    finally:
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id)
            )
            await cleanup_session.execute(
                delete(AuthSession).where(AuthSession.user_id == user_id)
            )
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()


@pytest.mark.asyncio
async def test_multiple_sessions_selective_logout_then_full_password_revocation(
    client: httpx.AsyncClient,
) -> None:
    """Keep sibling sessions active on logout, then revoke them on password change."""

    run_id = uuid4().hex
    user_id = uuid4()
    email = f"multi-session-{run_id}@example.com"
    password = "IntegrationP@ssword1"

    async with AsyncSessionFactory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                first_name="Multi",
                last_name="Session",
                email=email,
                hashed_password=PasswordService.hash_password(password),
                role=UserRole.HEAD_COACH,
                is_active=True,
            )
        )
        await setup_session.commit()

    transport_options = {"app": app, "raise_app_exceptions": False}
    try:
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(**transport_options),
                base_url="http://testserver",
            ) as mobile_client,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(**transport_options),
                base_url="http://testserver",
            ) as tablet_client,
        ):
            device_clients = (client, mobile_client, tablet_client)
            authorizations: list[dict[str, str]] = []
            for device_client in device_clients:
                login = await device_client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": password},
                )
                assert login.status_code == 200, login.text
                authorizations.append(
                    {"Authorization": (f"Bearer {login.json()['access_token']}")}
                )

            desktop_logout = await client.post(
                "/api/v1/auth/logout",
                headers={
                    **authorizations[0],
                    "X-CSRF-Token": client.cookies["csrf_token"],
                },
            )
            assert desktop_logout.status_code == 204, desktop_logout.text

            desktop_me = await client.get(
                "/api/v1/auth/me",
                headers=authorizations[0],
            )
            mobile_me = await mobile_client.get(
                "/api/v1/auth/me",
                headers=authorizations[1],
            )
            tablet_me = await tablet_client.get(
                "/api/v1/auth/me",
                headers=authorizations[2],
            )
            assert desktop_me.status_code == 401
            assert mobile_me.status_code == 200
            assert tablet_me.status_code == 200

            password_change = await mobile_client.post(
                f"/api/v1/users/{user_id}/change-password",
                json={"new_password": "ChangedP@ssword2"},
                headers=authorizations[1],
            )
            assert password_change.status_code == 204, password_change.text

            rejected_mobile = await mobile_client.get(
                "/api/v1/auth/me",
                headers=authorizations[1],
            )
            rejected_tablet = await tablet_client.get(
                "/api/v1/auth/me",
                headers=authorizations[2],
            )
            assert rejected_mobile.status_code == 401
            assert rejected_tablet.status_code == 401

        async with AsyncSessionFactory() as verification_session:
            auth_sessions = list(
                (
                    await verification_session.scalars(
                        select(AuthSession).where(AuthSession.user_id == user_id)
                    )
                ).all()
            )
            assert len(auth_sessions) == 3
            assert all(item.revoked_at is not None for item in auth_sessions)
            assert [item.revocation_reason for item in auth_sessions].count(
                "logout"
            ) == 1
            assert [item.revocation_reason for item in auth_sessions].count(
                "password_change"
            ) == 2
    finally:
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id)
            )
            await cleanup_session.execute(
                delete(AuthSession).where(AuthSession.user_id == user_id)
            )
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
