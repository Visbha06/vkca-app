"""Integration coverage for bounded legacy player-directory responses."""

from datetime import date
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.main import app
from src.models.player import Player
from src.schemas.player import (
    PLAYER_BIO_MAX_LENGTH,
    PLAYER_METADATA_MAX_STRING_LENGTH,
)


@pytest_asyncio.fixture(loop_scope="session")
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.usefixtures("authenticated_client")
async def test_directory_bounds_oversized_legacy_profile_without_mutating_row(
    client: httpx.AsyncClient,
) -> None:
    unique_name = f"Legacy{uuid4().hex[:12]}"
    legacy_bio = "b" * (PLAYER_BIO_MAX_LENGTH + 500)
    legacy_metadata = {
        "legacy": "m" * (PLAYER_METADATA_MAX_STRING_LENGTH + 500),
    }
    player = Player(
        first_name=unique_name,
        last_name="Oversized",
        date_of_birth=date(1990, 1, 1),
        bio=legacy_bio,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata=legacy_metadata,
    )
    async with AsyncSessionFactory() as session:
        session.add(player)
        await session.commit()
        player_id = player.id

    response = await client.get(
        "/api/v1/players",
        params={"search": unique_name, "page_size": 1},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["players"]) == 1
    assert body["players"][0]["bio"] == legacy_bio[:PLAYER_BIO_MAX_LENGTH]
    assert body["players"][0]["player_metadata"] == {}
    assert len(response.content) < 16 * 1_024

    async with AsyncSessionFactory() as verification_session:
        stored = await verification_session.get(Player, player_id)
        assert stored is not None
        assert stored.bio == legacy_bio
        assert stored.player_metadata == legacy_metadata
