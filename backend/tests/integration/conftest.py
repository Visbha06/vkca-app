"""Shared fixtures for authenticated integration API requests."""

from uuid import uuid4

import httpx
import pytest_asyncio
from sqlalchemy import delete

from src.database import AsyncSessionFactory
from src.enums import UserRole
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.password_service import PasswordService


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_client(client: httpx.AsyncClient) -> None:
    """Authenticate the module's API client as a temporary Head Coach."""

    user_id = uuid4()
    email = f"integration-head-coach-{user_id.hex}@example.com"
    password = "IntegrationP@ssword1"

    async with AsyncSessionFactory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                first_name="Integration",
                last_name="Head Coach",
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
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = (
            f"Bearer {login.json()['access_token']}"
        )
        yield
    finally:
        client.headers.pop("Authorization", None)
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id)
            )
            await cleanup_session.execute(
                delete(AuthSession).where(AuthSession.user_id == user_id)
            )
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()
