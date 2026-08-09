"""Shared fixtures for authenticated integration API requests."""

from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, engine, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.password_service import PasswordService
from tests.database_safety import assert_safe_test_database_url


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def isolated_test_database() -> AsyncIterator[None]:
    """Contain every integration test inside one rollback-only transaction."""

    assert_safe_test_database_url(str(engine.url))
    async with engine.connect() as connection:
        outer_transaction = await connection.begin()
        AsyncSessionFactory.configure(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )

        async def override_get_db() -> AsyncIterator[AsyncSession]:
            async with AsyncSessionFactory() as request_session:
                yield request_session

        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = override_get_db
        try:
            yield
        finally:
            app.dependency_overrides.clear()
            transaction_was_active = outer_transaction.is_active
            try:
                if transaction_was_active:
                    await outer_transaction.rollback()
            finally:
                AsyncSessionFactory.configure(
                    bind=engine,
                    join_transaction_mode="conditional_savepoint",
                )
            if not transaction_was_active:
                raise RuntimeError(
                    "Integration test code escaped the rollback-only outer "
                    "database transaction."
                )


@pytest_asyncio.fixture
async def business_audit_transaction_session() -> AsyncIterator[AsyncSession]:
    """Yield a caller-owned transaction for flush/rollback audit assertions."""

    async with AsyncSessionFactory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_client(
    client: httpx.AsyncClient,
) -> AsyncIterator[None]:
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
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
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
