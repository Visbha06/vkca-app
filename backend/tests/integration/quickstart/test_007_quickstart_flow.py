"""Executable coverage for all 14 Coaches Portal quickstart scenarios."""

from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.user import User
from src.services.password_service import PasswordService


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide the real PostgreSQL session used for setup and cleanup."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client():
    """Run requests through the complete FastAPI route and service stack."""

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
@pytest.mark.usefixtures("authenticated_client")
async def test_all_fourteen_coaches_portal_quickstart_scenarios(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Validate coach queries, mutations, access lifecycle, OCC, and roles."""

    run_id = uuid4().hex
    coach_ids: list[UUID] = []
    team_ids: list[UUID] = []
    authenticated_user_id: UUID | None = None
    temporary_password: str | None = None

    try:
        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200, me.text
        authenticated_user_id = UUID(me.json()["id"])

        teams = [
            Team(name=f"Falcons-{run_id}", age_group="U13"),
            Team(name=f"Strikers-{run_id}", age_group="U15"),
        ]
        inactive_coach = User(
            first_name="Inactive",
            last_name=f"Coach-{run_id}",
            email=f"inactive-coach-{run_id}@example.com",
            hashed_password=PasswordService.hash_password("InactiveP@ssword1"),
            role=UserRole.ASSISTANT_COACH,
            is_active=False,
        )
        db_session.add_all([*teams, inactive_coach])
        await db_session.flush()
        team_ids = [team.id for team in teams]
        coach_ids.append(inactive_coach.id)
        await db_session.commit()

        # 1. List coaches with the documented active default.
        active_list = await client.get("/api/v1/coaches")
        assert active_list.status_code == 200, active_list.text
        active_json = active_list.json()
        assert active_json["page"] == 1
        assert active_json["page_size"] == 12
        assert active_json["has_previous"] is False
        assert any(
            item["id"] == str(authenticated_user_id)
            and item["role"] == UserRole.HEAD_COACH
            and item["is_active"] is True
            for item in active_json["coaches"]
        )
        assert all(item["is_active"] for item in active_json["coaches"])

        # 2. Filter inactive coaches.
        inactive_list = await client.get(
            "/api/v1/coaches",
            params={"status": "inactive", "page_size": 100},
        )
        assert inactive_list.status_code == 200, inactive_list.text
        assert any(
            item["id"] == str(inactive_coach.id)
            for item in inactive_list.json()["coaches"]
        )
        assert all(not item["is_active"] for item in inactive_list.json()["coaches"])

        # 3. Include active and inactive coaches together.
        all_coaches = await client.get(
            "/api/v1/coaches",
            params={"status": "all", "page_size": 100},
        )
        assert all_coaches.status_code == 200, all_coaches.text
        all_statuses = {item["is_active"] for item in all_coaches.json()["coaches"]}
        assert all_statuses == {False, True}

        # 4. Return stable pagination metadata and disjoint pages.
        first_page = await client.get(
            "/api/v1/coaches",
            params={"status": "all", "page": 1, "page_size": 1},
        )
        second_page = await client.get(
            "/api/v1/coaches",
            params={"status": "all", "page": 2, "page_size": 1},
        )
        assert first_page.status_code == 200, first_page.text
        assert second_page.status_code == 200, second_page.text
        assert first_page.json()["has_next"] is True
        assert second_page.json()["has_previous"] is True
        assert (
            first_page.json()["coaches"][0]["id"]
            != (second_page.json()["coaches"][0]["id"])
        )

        # 5. Keep Head Coach first, then sort Assistant Coaches by identity.
        ordered = all_coaches.json()["coaches"]
        assert ordered[0]["role"] == UserRole.HEAD_COACH
        assistant_keys = [
            (item["last_name"], item["first_name"], item["id"])
            for item in ordered
            if item["role"] == UserRole.ASSISTANT_COACH
        ]
        assert assistant_keys == sorted(assistant_keys)

        # 6. Create an Assistant Coach with an atomic initial assignment.
        create_payload = {
            "first_name": "New",
            "last_name": f"Coach-{run_id}",
            "email": f"new-coach-{run_id}@example.com",
            "team_ids": [str(team_ids[0])],
        }
        created = await client.post("/api/v1/coaches", json=create_payload)
        assert created.status_code == 201, created.text
        created_json = created.json()
        created_coach_id = UUID(created_json["id"])
        coach_ids.append(created_coach_id)
        temporary_password = created_json["temporary_password"]
        assert created_json["role"] == UserRole.ASSISTANT_COACH
        assert created_json["is_active"] is True
        assert created_json["version_number"] == 1
        assert [team["id"] for team in created_json["teams"]] == [str(team_ids[0])]
        assert temporary_password

        # 7. Reject a duplicate normalized email without creating an account.
        duplicate = await client.post(
            "/api/v1/coaches",
            json={**create_payload, "email": create_payload["email"].upper()},
        )
        assert duplicate.status_code == 409, duplicate.text
        assert "already exists" in duplicate.json()["detail"]

        # 8. Return complete coach details and assignments.
        details = await client.get(f"/api/v1/coaches/{created_coach_id}")
        assert details.status_code == 200, details.text
        details_json = details.json()
        assert details_json["email"] == create_payload["email"]
        assert details_json["teams"] == created_json["teams"]

        # 9. Atomically replace assignments and increment the version.
        updated = await client.put(
            f"/api/v1/coaches/{created_coach_id}/teams",
            json={
                "team_ids": [str(team_ids[1])],
                "version_number": details_json["version_number"],
            },
        )
        assert updated.status_code == 200, updated.text
        updated_json = updated.json()
        assert updated_json["version_number"] == 2
        assert [team["id"] for team in updated_json["teams"]] == [str(team_ids[1])]

        # 10. Reject a stale assignment write and preserve current data.
        stale = await client.put(
            f"/api/v1/coaches/{created_coach_id}/teams",
            json={
                "team_ids": [str(team_ids[0])],
                "version_number": details_json["version_number"],
            },
        )
        assert stale.status_code == 409, stale.text
        assert "Stale version" in stale.json()["detail"]
        after_stale = await client.get(f"/api/v1/coaches/{created_coach_id}")
        assert after_stale.status_code == 200, after_stale.text
        assert after_stale.json()["teams"] == updated_json["teams"]
        assert after_stale.json()["version_number"] == 2

        pre_deactivation_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": create_payload["email"],
                "password": temporary_password,
            },
        )
        assert pre_deactivation_login.status_code == 200

        # 11. Deactivate the coach, revoke sessions, and block authentication.
        disabled = await client.post(
            f"/api/v1/users/{created_coach_id}/disable",
            json={"version_number": updated_json["version_number"]},
        )
        assert disabled.status_code == 200, disabled.text
        disabled_json = disabled.json()
        assert disabled_json["is_active"] is False
        assert disabled_json["version_number"] == 3
        blocked_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": create_payload["email"],
                "password": temporary_password,
            },
        )
        assert blocked_login.status_code == 401
        revoked_sessions = list(
            (
                await db_session.scalars(
                    select(AuthSession).where(AuthSession.user_id == created_coach_id)
                )
            ).all()
        )
        assert revoked_sessions
        assert all(session.revoked_at is not None for session in revoked_sessions)

        # 12. Reactivate login without restoring any revoked session.
        reactivated = await client.post(
            f"/api/v1/users/{created_coach_id}/reactivate",
            json={"version_number": disabled_json["version_number"]},
        )
        assert reactivated.status_code == 200, reactivated.text
        assert reactivated.json()["is_active"] is True
        assert reactivated.json()["version_number"] == 4
        restored_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": create_payload["email"],
                "password": temporary_password,
            },
        )
        assert restored_login.status_code == 200, restored_login.text
        db_session.expire_all()
        prior_sessions = list(
            (
                await db_session.scalars(
                    select(AuthSession).where(
                        AuthSession.user_id == created_coach_id,
                        AuthSession.revoked_at.is_not(None),
                    )
                )
            ).all()
        )
        assert prior_sessions

        # 13. Reject Head Coach self-deactivation.
        self_disable = await client.post(
            f"/api/v1/users/{authenticated_user_id}/disable",
        )
        assert self_disable.status_code == 403, self_disable.text
        assert self_disable.json() == {"detail": "Not authorized"}

        # 14. Deny the coach directory to a valid Player-role account.
        authenticated_user = await db_session.get(User, authenticated_user_id)
        assert authenticated_user is not None
        authenticated_user.role = UserRole.PLAYER
        await db_session.commit()
        player_denied = await client.get("/api/v1/coaches")
        assert player_denied.status_code == 403, player_denied.text
        assert player_denied.json() == {"detail": "Not authorized"}
    finally:
        await db_session.rollback()
        if authenticated_user_id is not None:
            authenticated_user = await db_session.get(User, authenticated_user_id)
            if authenticated_user is not None:
                authenticated_user.role = UserRole.HEAD_COACH
                await db_session.commit()
        if coach_ids:
            await db_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id.in_(coach_ids))
            )
            await db_session.execute(
                delete(AuthSession).where(AuthSession.user_id.in_(coach_ids))
            )
            await db_session.execute(
                delete(TeamCoach).where(TeamCoach.user_id.in_(coach_ids))
            )
            await db_session.execute(delete(User).where(User.id.in_(coach_ids)))
        if team_ids:
            await db_session.execute(
                delete(TeamCoach).where(TeamCoach.team_id.in_(team_ids))
            )
            await db_session.execute(delete(Team).where(Team.id.in_(team_ids)))
        await db_session.commit()
