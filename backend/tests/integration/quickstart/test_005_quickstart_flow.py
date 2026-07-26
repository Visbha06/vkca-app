"""Executable coverage for the 005 players-interface quickstart flow."""

from math import ceil
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.main import app
from src.models.data_sync_log import DataSyncLog
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide the real PostgreSQL session used for cleanup."""

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
async def test_players_interface_quickstart_flow(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Validate pagination, filters, active state, ordering, and OCC end to end."""

    run_id = uuid4().hex
    player_ids: list[UUID] = []
    team_id: UUID | None = None
    conflict_id: UUID | None = None

    try:
        initial_list = await client.get("/api/v1/players")
        assert initial_list.status_code == 200, initial_list.text
        initial_total = initial_list.json()["total_players"]

        for index in range(22):
            created = await client.post(
                "/api/v1/players",
                json={
                    "first_name": f"Player{index:02d}",
                    "last_name": f"Quickstart-{run_id}",
                    "date_of_birth": f"2000-01-{index + 1:02d}",
                    "batting_style": "right",
                    "bowling_style": "right-arm medium",
                    "player_type": "batter",
                },
            )
            assert created.status_code == 201, created.text
            created_json = created.json()
            assert created_json["teams"] == []
            assert created_json["version_number"] == 1
            player_ids.append(UUID(created_json["id"]))

        first_page = await client.get("/api/v1/players")
        assert first_page.status_code == 200, first_page.text
        first_page_json = first_page.json()
        expected_total = initial_total + 22
        assert first_page_json["page"] == 1
        assert first_page_json["page_size"] == 20
        assert first_page_json["total_players"] == expected_total
        assert first_page_json["total_pages"] == ceil(expected_total / 20)
        assert first_page_json["has_previous"] is False
        assert first_page_json["has_next"] == (expected_total > 20)
        assert len(first_page_json["players"]) == min(expected_total, 20)

        second_page = await client.get(
            "/api/v1/players",
            params={"page": 2, "page_size": 20},
        )
        assert second_page.status_code == 200, second_page.text
        second_page_json = second_page.json()
        assert second_page_json["page"] == 2
        assert second_page_json["has_previous"] is True
        assert {
            item["id"] for item in first_page_json["players"]
        }.isdisjoint(item["id"] for item in second_page_json["players"])

        ordered = await client.get(
            "/api/v1/players",
            params={"page_size": 100},
        )
        assert ordered.status_code == 200, ordered.text
        ordering_keys = [
            (item["last_name"], item["first_name"], item["id"])
            for item in ordered.json()["players"]
        ]
        assert ordering_keys == sorted(ordering_keys)

        assigned_ids = player_ids[:7]
        created_team = await client.post(
            "/api/v1/teams",
            json={
                "name": f"Quickstart XI {run_id}",
                "age_group": "U15",
                "player_ids": [
                    str(player_id) for player_id in assigned_ids
                ],
            },
        )
        assert created_team.status_code == 201, created_team.text
        team_id = UUID(created_team.json()["id"])

        team_filtered = await client.get(
            "/api/v1/players",
            params={"team_id": str(team_id), "page_size": 100},
        )
        assert team_filtered.status_code == 200, team_filtered.text
        team_json = team_filtered.json()
        assert {UUID(item["id"]) for item in team_json["players"]} == set(
            assigned_ids
        )
        assert all(
            any(team["id"] == str(team_id) for team in item["teams"])
            for item in team_json["players"]
        )

        unassigned = await client.get(
            "/api/v1/players",
            params={"unassigned": True, "page_size": 100},
        )
        assert unassigned.status_code == 200, unassigned.text
        unassigned_ids = {UUID(item["id"]) for item in unassigned.json()["players"]}
        assert set(assigned_ids).isdisjoint(unassigned_ids)
        assert set(player_ids[7:]) <= unassigned_ids

        mutually_exclusive = await client.get(
            "/api/v1/players",
            params={"team_id": str(team_id), "unassigned": True},
        )
        assert mutually_exclusive.status_code == 422

        inactive_id = player_ids[-1]
        deactivated = await client.put(
            f"/api/v1/players/{inactive_id}",
            json={"is_active": False, "version_number": 1},
        )
        assert deactivated.status_code == 200, deactivated.text
        active_list = await client.get(
            "/api/v1/players",
            params={"page_size": 100},
        )
        assert inactive_id not in {
            UUID(item["id"]) for item in active_list.json()["players"]
        }

        conflict_id = player_ids[-2]
        current_update = await client.put(
            f"/api/v1/players/{conflict_id}",
            json={"bio": "First quickstart update", "version_number": 1},
        )
        assert current_update.status_code == 200, current_update.text
        assert current_update.json()["version_number"] == 2

        stale_update = await client.put(
            f"/api/v1/players/{conflict_id}",
            json={"bio": "Stale quickstart update", "version_number": 1},
        )
        assert stale_update.status_code == 409
        assert "Stale version" in stale_update.json()["detail"]
    finally:
        await db_session.rollback()
        if conflict_id is not None:
            await db_session.execute(
                delete(DataSyncLog).where(
                    DataSyncLog.source == "player-update",
                    DataSyncLog.error_message.contains(str(conflict_id)),
                )
            )
        if player_ids:
            await db_session.execute(
                delete(TeamPlayer).where(TeamPlayer.player_id.in_(player_ids))
            )
        if team_id is not None:
            await db_session.execute(delete(Team).where(Team.id == team_id))
        if player_ids:
            await db_session.execute(delete(Player).where(Player.id.in_(player_ids)))
        await db_session.commit()
