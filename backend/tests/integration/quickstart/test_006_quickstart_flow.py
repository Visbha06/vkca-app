"""Executable coverage for all 12 teams-interface quickstart scenarios."""

from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.models.user import User


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


async def create_active_players(
    client: httpx.AsyncClient,
    run_id: str,
    count: int = 8,
) -> list[UUID]:
    """Create a distinct active roster through the public player API."""

    player_ids: list[UUID] = []
    for index in range(count):
        response = await client.post(
            "/api/v1/players",
            json={
                "first_name": f"TeamFlow{index + 1}",
                "last_name": f"Quickstart-{run_id}",
                "date_of_birth": f"2000-01-{index + 1:02d}",
                "batting_style": "right",
                "bowling_style": "right-arm medium",
                "player_type": "all-rounder",
            },
        )
        assert response.status_code == 201, response.text
        player_ids.append(UUID(response.json()["id"]))
    return player_ids


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_all_twelve_teams_interface_quickstart_scenarios(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Validate atomic writes, ordering, conflicts, authorization, and history."""

    run_id = uuid4().hex
    player_ids: list[UUID] = []
    team_ids: list[UUID] = []
    authenticated_user_id: UUID | None = None

    try:
        player_ids = await create_active_players(client, run_id)
        original_order = [str(player_id) for player_id in player_ids]

        # 1. Create a team and its ordered roster in one request.
        created = await client.post(
            "/api/v1/teams",
            json={
                "name": f"Falcons-{run_id}",
                "age_group": "U13",
                "player_ids": original_order,
            },
        )
        assert created.status_code == 201, created.text
        created_json = created.json()
        team_id = UUID(created_json["id"])
        team_ids.append(team_id)
        assert created_json["name"] == f"Falcons-{run_id}"
        assert created_json["age_group"] == "U13"
        assert created_json["player_count"] == 8
        assert created_json["version_number"] == 1

        # 2. List teams with the documented metadata and stable ordering.
        listed = await client.get(
            "/api/v1/teams",
            params={"page": 1, "page_size": 100},
        )
        assert listed.status_code == 200, listed.text
        listed_json = listed.json()
        assert listed_json["page"] == 1
        assert listed_json["page_size"] == 100
        assert listed_json["total_pages"] >= 1
        assert any(item["id"] == str(team_id) for item in listed_json["teams"])
        ordering_keys = [
            (item["name"], item["age_group"], item["id"])
            for item in listed_json["teams"]
        ]
        assert ordering_keys == sorted(ordering_keys)

        # 3. Retrieve all roster members in the creation order.
        roster = await client.get(f"/api/v1/teams/{team_id}/players")
        assert roster.status_code == 200, roster.text
        roster_json = roster.json()
        assert roster_json["team_id"] == str(team_id)
        assert [item["player_id"] for item in roster_json["players"]] == original_order
        assert [item["roster_order"] for item in roster_json["players"]] == list(
            range(1, 9)
        )
        assert all(item["is_active"] for item in roster_json["players"])

        # 4. Atomically update details and replace the ordered roster.
        updated_order = [
            original_order[7],
            original_order[0],
            original_order[2],
            original_order[4],
            original_order[1],
            original_order[3],
            original_order[5],
            original_order[6],
        ]
        updated = await client.put(
            f"/api/v1/teams/{team_id}",
            json={
                "name": f"Eagles-{run_id}",
                "age_group": "U15",
                "player_ids": updated_order,
                "version_number": 1,
            },
        )
        assert updated.status_code == 200, updated.text
        updated_json = updated.json()
        assert updated_json["name"] == f"Eagles-{run_id}"
        assert updated_json["age_group"] == "U15"
        assert updated_json["player_count"] == 8
        assert updated_json["version_number"] == 2

        # 5. The updated roster order remains stable across repeated reads.
        for _ in range(2):
            persisted = await client.get(f"/api/v1/teams/{team_id}/players")
            assert persisted.status_code == 200, persisted.text
            assert [
                item["player_id"] for item in persisted.json()["players"]
            ] == updated_order

        # 6. Reject a stale version and preserve the current team data.
        stale = await client.put(
            f"/api/v1/teams/{team_id}",
            json={
                "name": f"ShouldFail-{run_id}",
                "age_group": "U13",
                "player_ids": original_order[:7],
                "version_number": 1,
            },
        )
        assert stale.status_code == 409, stale.text
        assert "Stale version" in stale.json()["detail"]
        after_stale = await client.get(
            "/api/v1/teams",
            params={"page": 1, "page_size": 100},
        )
        current_team = next(
            item for item in after_stale.json()["teams"] if item["id"] == str(team_id)
        )
        assert current_team["name"] == f"Eagles-{run_id}"
        assert current_team["version_number"] == 2

        # 7. Reject rosters below the seven-player schema minimum.
        too_small = await client.post(
            "/api/v1/teams",
            json={
                "name": f"Tiny-{run_id}",
                "age_group": "U11",
                "player_ids": original_order[:2],
            },
        )
        assert too_small.status_code == 422, too_small.text

        # 8. Reject duplicate players without persisting a team.
        duplicates = await client.post(
            "/api/v1/teams",
            json={
                "name": f"Dups-{run_id}",
                "age_group": "U11",
                "player_ids": [original_order[0], *original_order[:6]],
            },
        )
        assert duplicates.status_code in {400, 422}, duplicates.text
        assert "duplicate" in str(duplicates.json()).lower()

        # 9. Reject normalized duplicate names in the same age group.
        duplicate_name = await client.post(
            "/api/v1/teams",
            json={
                "name": f"  eAgLeS-{run_id}  ",
                "age_group": "U15",
                "player_ids": original_order[:7],
            },
        )
        assert duplicate_name.status_code == 409, duplicate_name.text

        # 10. Permit the same normalized name in a different age group.
        different_age = await client.post(
            "/api/v1/teams",
            json={
                "name": f"Eagles-{run_id}",
                "age_group": "U13",
                "player_ids": original_order[:7],
            },
        )
        assert different_age.status_code == 201, different_age.text
        team_ids.append(UUID(different_age.json()["id"]))

        # 11. Keep team writes unavailable to player-role users.
        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200, me.text
        authenticated_user_id = UUID(me.json()["id"])
        authenticated_user = await db_session.get(User, authenticated_user_id)
        assert authenticated_user is not None
        authenticated_user.role = UserRole.PLAYER
        await db_session.commit()
        unauthorized = await client.post(
            "/api/v1/teams",
            json={
                "name": f"NoAuth-{run_id}",
                "age_group": "U11",
                "player_ids": original_order[:7],
            },
        )
        assert unauthorized.status_code == 403, unauthorized.text
        assert unauthorized.json() == {"detail": "Not authorized"}
        authenticated_user.role = UserRole.HEAD_COACH
        await db_session.commit()

        # 12. Preserve an inactive roster member and expose its active flag.
        inactive_id = updated_order[0]
        deactivated = await client.put(
            f"/api/v1/players/{inactive_id}",
            json={"is_active": False, "version_number": 1},
        )
        assert deactivated.status_code == 200, deactivated.text
        inactive_roster = await client.get(f"/api/v1/teams/{team_id}/players")
        assert inactive_roster.status_code == 200, inactive_roster.text
        inactive_entry = next(
            item
            for item in inactive_roster.json()["players"]
            if item["player_id"] == str(inactive_id)
        )
        assert inactive_entry["is_active"] is False
    finally:
        await db_session.rollback()
        if authenticated_user_id is not None:
            authenticated_user = await db_session.get(User, authenticated_user_id)
            if authenticated_user is not None:
                authenticated_user.role = UserRole.HEAD_COACH
                await db_session.commit()
        if team_ids:
            await db_session.execute(
                delete(TeamPlayer).where(TeamPlayer.team_id.in_(team_ids))
            )
            await db_session.execute(delete(Team).where(Team.id.in_(team_ids)))
        if player_ids:
            await db_session.execute(delete(Player).where(Player.id.in_(player_ids)))
        await db_session.commit()
