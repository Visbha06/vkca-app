"""Executable coverage for the 002 authentication quickstart flow."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete

from scripts.seed_head_coach import seed_head_coach
from src.database import AsyncSessionFactory, get_db
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.player import Player
from src.models.user import User


@pytest.mark.asyncio
async def test_full_eight_scenario_authentication_quickstart_flow() -> None:
    """Run all eight authentication quickstart scenarios through the real stack."""

    run_id = uuid4().hex
    client_ip = f"2001:db8::{run_id[:8]}"
    head_coach_email = f"headcoach-{run_id}@vkca.test"
    assistant_email = f"asst-{run_id}@vkca.test"
    head_coach_password = "SuperSecur3!P@ss"
    assistant_password = "AsstP@ssword1"
    head_coach_id: UUID | None = None
    assistant_id: UUID | None = None
    player_id: UUID | None = None
    issued_secrets: set[str] = {
        head_coach_password,
        assistant_password,
        "wrong",
    }

    async with AsyncSessionFactory() as setup_session:
        head_coach, created = await seed_head_coach(
            setup_session,
            email=head_coach_email,
            password=head_coach_password,
        )
        assert created is True
        head_coach_id = head_coach.id

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
    started_at = datetime.now(UTC)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"User-Agent": "auth-quickstart-integration-test"},
        ) as client:
            # Scenario 1: login succeeds and all credential failures are identical.
            login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": head_coach_email,
                    "password": head_coach_password,
                },
            )
            assert login.status_code == 200, login.text
            access_token = login.json()["access_token"]
            issued_secrets.add(access_token)
            assert client.cookies.get("refresh_token")
            assert client.cookies.get("csrf_token")

            wrong_password = await client.post(
                "/api/v1/auth/login",
                json={"email": head_coach_email, "password": "wrong"},
            )
            unknown_email = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": f"noone-{run_id}@vkca.test",
                    "password": "anything",
                },
            )
            assert wrong_password.status_code == 401
            assert unknown_email.status_code == 401
            assert wrong_password.content == unknown_email.content
            assert wrong_password.json() == {"detail": "Invalid credentials"}

            # Scenario 2: the bearer token grants access to the protected profile.
            me = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert me.status_code == 200, me.text
            assert me.json()["role"] == "head coach"
            assert me.json()["is_active"] is True
            assert me.json()["session"]["session_id"]

            # Scenario 3: refresh rotates the access, refresh, and CSRF tokens.
            original_refresh = client.cookies["refresh_token"]
            original_csrf = client.cookies["csrf_token"]
            issued_secrets.update({original_refresh, original_csrf})
            refresh = await client.post(
                "/api/v1/auth/refresh",
                headers={"X-CSRF-Token": original_csrf},
            )
            assert refresh.status_code == 200, refresh.text
            refreshed_access_token = refresh.json()["access_token"]
            assert refreshed_access_token != access_token
            assert client.cookies["refresh_token"] != original_refresh
            assert client.cookies["csrf_token"] != original_csrf
            issued_secrets.update(
                {
                    refreshed_access_token,
                    client.cookies["refresh_token"],
                    client.cookies["csrf_token"],
                }
            )

            # Scenario 4: replaying a rotated token revokes its token family.
            replayed_refresh = client.cookies["refresh_token"]
            csrf_before_rotation = client.cookies["csrf_token"]
            second_refresh = await client.post(
                "/api/v1/auth/refresh",
                headers={"X-CSRF-Token": csrf_before_rotation},
            )
            assert second_refresh.status_code == 200, second_refresh.text
            current_csrf = client.cookies["csrf_token"]
            issued_secrets.update(
                {
                    replayed_refresh,
                    csrf_before_rotation,
                    second_refresh.json()["access_token"],
                    client.cookies["refresh_token"],
                    current_csrf,
                }
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    app=app,
                    raise_app_exceptions=False,
                    client=(client_ip, 12345),
                ),
                base_url="http://testserver",
                cookies={
                    "refresh_token": replayed_refresh,
                    "csrf_token": current_csrf,
                },
            ) as replay_client:
                replay = await replay_client.post(
                    "/api/v1/auth/refresh",
                    headers={"X-CSRF-Token": current_csrf},
                )
            assert replay.status_code == 401
            assert replay.json() == {"detail": "Invalid or expired session"}

            # Scenario 5: logout clears cookies and revokes that access token.
            logout_login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": head_coach_email,
                    "password": head_coach_password,
                },
            )
            assert logout_login.status_code == 200, logout_login.text
            logout_access_token = logout_login.json()["access_token"]
            logout_csrf = client.cookies["csrf_token"]
            issued_secrets.update(
                {
                    logout_access_token,
                    client.cookies["refresh_token"],
                    logout_csrf,
                }
            )
            logout = await client.post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": logout_csrf},
            )
            assert logout.status_code == 204, logout.text
            assert client.cookies.get("refresh_token") is None
            assert client.cookies.get("csrf_token") is None
            revoked_access = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {logout_access_token}"},
            )
            assert revoked_access.status_code == 401

            # Scenario 6: an Assistant Coach can manage cricket data, not users.
            head_coach_login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": head_coach_email,
                    "password": head_coach_password,
                },
            )
            assert head_coach_login.status_code == 200, head_coach_login.text
            head_coach_token = head_coach_login.json()["access_token"]
            issued_secrets.add(head_coach_token)
            head_coach_headers = {"Authorization": f"Bearer {head_coach_token}"}
            create_assistant = await client.post(
                "/api/v1/users",
                headers=head_coach_headers,
                json={
                    "first_name": "Asst",
                    "last_name": "Coach",
                    "email": assistant_email,
                    "password": assistant_password,
                    "role": "assistant coach",
                },
            )
            assert create_assistant.status_code == 201, create_assistant.text
            assistant_id = UUID(create_assistant.json()["id"])

            assistant_login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": assistant_email,
                    "password": assistant_password,
                },
            )
            assert assistant_login.status_code == 200, assistant_login.text
            assistant_token = assistant_login.json()["access_token"]
            issued_secrets.add(assistant_token)
            assistant_headers = {"Authorization": f"Bearer {assistant_token}"}
            create_player = await client.post(
                "/api/v1/players",
                headers=assistant_headers,
                json={
                    "first_name": f"Test-{run_id}",
                    "last_name": "Player",
                    "date_of_birth": "2000-01-01",
                    "player_type": "batter",
                    "batting_style": "right",
                    "bowling_style": "right-arm off-break",
                },
            )
            assert create_player.status_code == 201, create_player.text
            player_id = UUID(create_player.json()["id"])

            denied_user_creation = await client.post(
                "/api/v1/users",
                headers=assistant_headers,
                json={
                    "first_name": "Bad",
                    "last_name": "Actor",
                    "email": f"bad-{run_id}@vkca.test",
                    "password": "BadP@ssword1",
                    "role": "player",
                },
            )
            assert denied_user_creation.status_code == 403

            # Scenario 7: the sixth failure for one email/IP pair is throttled.
            rate_limit_email = f"ratelimit-{run_id}@vkca.test"
            rate_limit_responses = [
                await client.post(
                    "/api/v1/auth/login",
                    json={"email": rate_limit_email, "password": "wrong"},
                )
                for _ in range(6)
            ]
            assert [response.status_code for response in rate_limit_responses] == [
                401,
                401,
                401,
                401,
                401,
                429,
            ]

            # Scenario 8: the Head Coach sees a credential-free audit trail.
            audit_log = await client.get(
                "/api/v1/auth/audit-log",
                headers=head_coach_headers,
                params={"start_time": started_at.isoformat(), "limit": 100},
            )
            assert audit_log.status_code == 200, audit_log.text
            audit_records = audit_log.json()
            event_types = {record["event_type"] for record in audit_records}
            assert {
                "login",
                "failed_login",
                "token_refresh",
                "token_reuse",
                "logout",
                "authorization_denial",
                "rate_limit",
            } <= event_types
            assert all(
                record["result"] in {"success", "failure"} for record in audit_records
            )
            assert all(record["event_timestamp"] for record in audit_records)
            serialized_audit = audit_log.text
            assert not any(secret in serialized_audit for secret in issued_secrets)
            assert all(
                "hashed_password" not in record
                and "access_token" not in record
                and "refresh_token" not in record
                and "token_hash" not in record
                for record in audit_records
            )
    finally:
        app.state.rate_limiter.clear()
        app.dependency_overrides.clear()
        user_ids = [
            user_id for user_id in (head_coach_id, assistant_id) if user_id is not None
        ]
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.ip_address == client_ip)
            )
            if user_ids:
                await cleanup_session.execute(
                    delete(AuthSession).where(AuthSession.user_id.in_(user_ids))
                )
            if player_id is not None:
                await cleanup_session.execute(
                    delete(Player).where(Player.id == player_id)
                )
            if user_ids:
                await cleanup_session.execute(delete(User).where(User.id.in_(user_ids)))
            await cleanup_session.commit()
