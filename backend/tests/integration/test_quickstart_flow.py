"""Executable coverage for the twelve-step quickstart validation flow."""

from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.main import app
from src.models.data_sync_log import DataSyncLog
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.models.team import Team
from src.models.team_player import TeamPlayer


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide the real database session used by the quickstart client."""

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
async def test_full_twelve_step_quickstart_flow(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Create, relate, score, version, and deactivate a player end to end."""

    run_id = uuid4().hex
    player_id: UUID | None = None
    timestamp_player_id: UUID | None = None
    team_id: UUID | None = None
    match_id: UUID | None = None
    player_payload = {
        "first_name": f"Virat-{run_id}",
        "last_name": "Kohli",
        "date_of_birth": "1988-11-05",
        "batting_style": "right",
        "bowling_style": "right-arm medium",
        "player_type": "batter",
    }

    try:
        # 1. Create a player and validate SC-001.
        started_at = monotonic()
        create_player = await client.post("/api/v1/players", json=player_payload)
        assert monotonic() - started_at < 2
        assert create_player.status_code == 201, create_player.text
        player_json = create_player.json()
        player_id = UUID(player_json["id"])
        assert player_json["version_number"] == 1
        assert player_json["is_active"] is True

        # 2. Ignore supplied timestamps and validate SC-007.
        supplied_timestamp = "2020-01-01T00:00:00Z"
        timestamp_player = await client.post(
            "/api/v1/players",
            json={
                **player_payload,
                "first_name": f"Rohit-{run_id}",
                "last_name": "Sharma",
                "date_of_birth": "1987-04-30",
                "bowling_style": "right-arm off-break",
                "created_at": supplied_timestamp,
                "updated_at": supplied_timestamp,
            },
        )
        assert timestamp_player.status_code == 201
        timestamp_json = timestamp_player.json()
        timestamp_player_id = UUID(timestamp_json["id"])
        assert timestamp_json["created_at"] != supplied_timestamp
        created_at = datetime.fromisoformat(timestamp_json["created_at"])
        assert (datetime.now(UTC) - created_at).total_seconds() < 10

        # 3. Reject a duplicate identity.
        duplicate_player = await client.post("/api/v1/players", json=player_payload)
        assert duplicate_player.status_code == 409

        # 4. Create a team.
        create_team = await client.post(
            "/api/v1/teams",
            json={"name": f"Senior XI {run_id}", "age_group": "Senior"},
        )
        assert create_team.status_code == 201
        team_id = UUID(create_team.json()["id"])

        # 5. Add the player to its roster.
        add_player = await client.post(f"/api/v1/teams/{team_id}/players/{player_id}")
        assert add_player.status_code == 201
        assert add_player.json()["player_id"] == str(player_id)

        # 6. Reject duplicate membership and validate SC-008.
        duplicate_membership = await client.post(
            f"/api/v1/teams/{team_id}/players/{player_id}"
        )
        assert duplicate_membership.status_code == 409

        # 7. Create a match.
        create_match = await client.post(
            "/api/v1/matches",
            json={
                "match_date": "2026-07-01",
                "format": "T20",
                "opponent_name": f"Challengers CC {run_id}",
                "venue": "Main Ground",
                "result": "Won by 7 wickets",
            },
        )
        assert create_match.status_code == 201
        match_id = UUID(create_match.json()["id"])

        # 8. Submit batting and fielding in one atomic request.
        performance = await client.post(
            f"/api/v1/matches/{match_id}/performances",
            json={
                "performances": [
                    {
                        "player_id": str(player_id),
                        "batting": {
                            "runs_scored": 82,
                            "balls_faced": 55,
                            "dismissal": "not out",
                            "fours": 9,
                            "sixes": 3,
                        },
                        "fielding": {"catches": 2},
                    }
                ]
            },
        )
        assert performance.status_code == 201, performance.text
        assert performance.json()["performances_created"] == 1
        assert performance.json()["batting_records"] == 1
        assert performance.json()["fielding_records"] == 1

        # 9. Retrieve exact aggregates and validate SC-004 and SC-006.
        started_at = monotonic()
        stats = await client.get(
            f"/api/v1/players/{player_id}/stats/batting?format=T20"
        )
        assert monotonic() - started_at < 1
        assert stats.status_code == 200
        assert stats.json()[0]["runs"] == 82
        assert stats.json()[0]["not_outs"] == 1
        assert stats.json()[0]["fifties"] == 1

        # 10. Reject a second batting row for the same player and match.
        duplicate_performance = await client.post(
            f"/api/v1/matches/{match_id}/performances",
            json={
                "performances": [
                    {
                        "player_id": str(player_id),
                        "batting": {"runs_scored": 45, "dismissal": "caught"},
                    }
                ]
            },
        )
        assert duplicate_performance.status_code == 409

        # 11. Accept the current version, reject the stale one, and audit it.
        current_update = await client.put(
            f"/api/v1/players/{player_id}",
            json={"bio": "Updated bio", "version_number": 1},
        )
        assert current_update.status_code == 200
        assert current_update.json()["version_number"] == 2
        stale_update = await client.put(
            f"/api/v1/players/{player_id}",
            json={"bio": "Stale update", "version_number": 1},
        )
        assert stale_update.status_code == 409
        conflict_log = await db_session.scalar(
            select(DataSyncLog).where(
                DataSyncLog.status == "conflict",
                DataSyncLog.error_message.contains(str(player_id)),
            )
        )
        assert conflict_log is not None

        # 12. Hide an inactive player from lists but preserve direct history.
        deactivate = await client.put(
            f"/api/v1/players/{player_id}",
            json={"is_active": False, "version_number": 2},
        )
        assert deactivate.status_code == 200
        active_players = await client.get("/api/v1/players")
        assert str(player_id) not in {item["id"] for item in active_players.json()}
        direct_player = await client.get(f"/api/v1/players/{player_id}")
        assert direct_player.status_code == 200
        assert direct_player.json()["is_active"] is False
        historical_stats = await client.get(
            f"/api/v1/players/{player_id}/stats/batting"
        )
        assert historical_stats.status_code == 200
        assert historical_stats.json()[0]["runs"] == 82
    finally:
        await db_session.rollback()
        if player_id is not None:
            await db_session.execute(
                delete(DataSyncLog).where(
                    DataSyncLog.error_message.contains(str(player_id))
                )
            )
        if team_id is not None:
            await db_session.execute(
                delete(TeamPlayer).where(TeamPlayer.team_id == team_id)
            )
            await db_session.execute(delete(Team).where(Team.id == team_id))
        if match_id is not None:
            await db_session.execute(
                delete(MatchFieldingPerformance).where(
                    MatchFieldingPerformance.match_id == match_id
                )
            )
            await db_session.execute(
                delete(MatchBattingPerformance).where(
                    MatchBattingPerformance.match_id == match_id
                )
            )
        if player_id is not None:
            await db_session.execute(
                delete(PlayerBowlingStats).where(
                    PlayerBowlingStats.player_id == player_id
                )
            )
            await db_session.execute(
                delete(PlayerBattingStats).where(
                    PlayerBattingStats.player_id == player_id
                )
            )
        if match_id is not None:
            await db_session.execute(delete(Match).where(Match.id == match_id))
        player_ids = [
            entity_id
            for entity_id in (player_id, timestamp_player_id)
            if entity_id is not None
        ]
        if player_ids:
            await db_session.execute(delete(Player).where(Player.id.in_(player_ids)))
        await db_session.commit()
