"""Integration coverage for login rate limiting across real API requests."""

from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.password_service import PasswordService


@pytest.mark.asyncio
async def test_login_rate_limit_reset_and_account_independence() -> None:
    """Throttle one account while preserving independent resettable counters."""

    run_id = uuid4().hex
    blocked_user_id = uuid4()
    reset_user_id = uuid4()
    blocked_email = f"blocked-{run_id}@example.com"
    reset_email = f"reset-{run_id}@example.com"
    password = "IntegrationP@ssword1"
    wrong_password = "WrongP@ssword1"
    client_ip = f"2001:db8::{run_id[:4]}"

    async with AsyncSessionFactory() as setup_session:
        setup_session.add_all(
            [
                User(
                    id=blocked_user_id,
                    first_name="Rate",
                    last_name="Limited",
                    email=blocked_email,
                    hashed_password=PasswordService.hash_password(password),
                    role=UserRole.PLAYER,
                    is_active=True,
                ),
                User(
                    id=reset_user_id,
                    first_name="Counter",
                    last_name="Reset",
                    email=reset_email,
                    hashed_password=PasswordService.hash_password(password),
                    role=UserRole.PLAYER,
                    is_active=True,
                ),
            ]
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
        ) as client:
            blocked_responses = [
                await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": blocked_email.upper(),
                        "password": wrong_password,
                    },
                )
                for _ in range(6)
            ]
            assert [response.status_code for response in blocked_responses] == [
                401,
                401,
                401,
                401,
                401,
                429,
            ]
            assert blocked_responses[-1].json() == {
                "detail": "Too many login attempts. Please try again later."
            }

            independent_attempts = [
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": reset_email, "password": wrong_password},
                )
                for _ in range(4)
            ]
            assert {response.status_code for response in independent_attempts} == {401}

            successful_login = await client.post(
                "/api/v1/auth/login",
                json={"email": reset_email, "password": password},
            )
            assert successful_login.status_code == 200, successful_login.text

            after_reset = [
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": reset_email, "password": wrong_password},
                )
                for _ in range(6)
            ]
            assert [response.status_code for response in after_reset] == [
                401,
                401,
                401,
                401,
                401,
                429,
            ]
    finally:
        app.state.rate_limiter.clear()
        app.dependency_overrides.clear()
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.ip_address == client_ip)
            )
            await cleanup_session.execute(
                delete(AuthSession).where(
                    AuthSession.user_id.in_([blocked_user_id, reset_user_id])
                )
            )
            await cleanup_session.execute(
                delete(User).where(User.id.in_([blocked_user_id, reset_user_id]))
            )
            await cleanup_session.commit()
