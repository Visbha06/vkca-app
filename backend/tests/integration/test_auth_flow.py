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

        logout = await client.post("/api/v1/auth/logout", headers=authorization)
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
