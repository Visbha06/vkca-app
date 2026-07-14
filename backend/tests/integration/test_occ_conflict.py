"""End-to-end optimistic-concurrency conflict coverage."""

from datetime import date
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.main import app
from src.models.data_sync_log import DataSyncLog
from src.models.player import Player


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a real PostgreSQL session for the integration flow."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Route API dependencies through the integration-test session."""

    async def override_get_db():
        yield db_session

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
async def test_stale_player_update_returns_409_and_logs_conflict(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A stale version must fail without overwriting data and be audited."""

    player = Player(
        first_name="OCC",
        last_name=f"Player-{uuid4()}",
        date_of_birth=date(2001, 1, 1),
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
    )
    db_session.add(player)
    await db_session.flush()
    player_id = player.id
    await db_session.commit()

    try:
        current_update = await client.put(
            f"/api/v1/players/{player_id}",
            json={"bio": "Current update", "version_number": 1},
        )
        assert current_update.status_code == 200
        assert current_update.json()["version_number"] == 2

        stale_update = await client.put(
            f"/api/v1/players/{player_id}",
            json={"bio": "Stale update", "version_number": 1},
        )
        assert stale_update.status_code == 409
        assert "Stale version 1" in stale_update.json()["detail"]

        conflict_log = await db_session.scalar(
            select(DataSyncLog)
            .where(
                DataSyncLog.source == "player-update",
                DataSyncLog.status == "conflict",
                DataSyncLog.target_table == "players",
                DataSyncLog.error_message.contains(str(player_id)),
            )
            .order_by(DataSyncLog.created_at.desc())
        )
        assert conflict_log is not None
        assert "Stale version 1" in (conflict_log.error_message or "")

        await db_session.refresh(player)
        assert player.bio == "Current update"
        assert player.version_number == 2
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(DataSyncLog).where(
                DataSyncLog.target_table == "players",
                DataSyncLog.error_message.contains(str(player_id)),
            )
        )
        await db_session.execute(delete(Player).where(Player.id == player_id))
        await db_session.commit()
