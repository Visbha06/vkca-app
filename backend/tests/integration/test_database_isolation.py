"""Regression coverage for committed API and business-audit test isolation."""

from collections.abc import AsyncIterator
from datetime import date
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text

from src.config import (
    DEFAULT_ENV_FILE,
    TEST_ENV_FILE,
    get_settings,
    get_settings_env_file,
)
from src.database import AsyncSessionFactory, engine, get_db
from src.enums import UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.models.user import User
from tests.database_safety import database_name_from_url

ISOLATION_RUN_ID = uuid4().hex
ISOLATION_FIRST_NAME = f"Isolation-{ISOLATION_RUN_ID}"
ISOLATION_LAST_NAME = "Sentinel"
ISOLATION_TARGET_LABEL = f"{ISOLATION_FIRST_NAME} {ISOLATION_LAST_NAME}"


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[tuple[httpx.AsyncClient, User]]:
    """Use the shared test get_db override with an authenticated Head Coach."""

    actor = User(
        id=uuid4(),
        first_name="Isolation",
        last_name="Head Coach",
        email=f"isolation-{ISOLATION_RUN_ID}@example.test",
        hashed_password="unused-dependency-override",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )
    auth_session = Mock(spec=AuthSession)

    async def override_get_current_user():
        return actor, auth_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client, actor
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_committed_api_mutation_uses_only_test_database(
    api_client: tuple[httpx.AsyncClient, User],
) -> None:
    """A successful API commit persists domain and audit rows only in test DB."""

    client, actor = api_client
    assert get_db in app.dependency_overrides
    assert get_settings_env_file() == TEST_ENV_FILE
    assert get_settings_env_file("development") == DEFAULT_ENV_FILE

    test_database = database_name_from_url(str(get_settings().database_url))
    assert engine.url.database == test_database

    response = await client.post(
        "/api/v1/players",
        json={
            "first_name": ISOLATION_FIRST_NAME,
            "last_name": ISOLATION_LAST_NAME,
            "date_of_birth": date(2008, 1, 2).isoformat(),
            "batting_style": "right",
            "bowling_style": "right-arm medium",
            "player_type": "all-rounder",
        },
    )

    assert response.status_code == 201, response.text
    player_id = UUID(response.json()["id"])
    async with AsyncSessionFactory() as verification_session:
        connected_database = await verification_session.scalar(
            text("SELECT current_database()")
        )
        player = await verification_session.get(Player, player_id)
        audit_event = await verification_session.scalar(
            select(BusinessAuditEvent).where(
                BusinessAuditEvent.actor_user_id == actor.id,
                BusinessAuditEvent.target_entity_id == player_id,
            )
        )

    assert connected_database == test_database
    assert player is not None
    assert audit_event is not None
    assert audit_event.target_label == ISOLATION_TARGET_LABEL


@pytest.mark.asyncio
async def test_committed_rows_do_not_leak_into_the_next_test() -> None:
    """The preceding test's committed player and audit event must be gone."""

    async with AsyncSessionFactory() as verification_session:
        player = await verification_session.scalar(
            select(Player).where(
                Player.first_name == ISOLATION_FIRST_NAME,
                Player.last_name == ISOLATION_LAST_NAME,
            )
        )
        audit_event = await verification_session.scalar(
            select(BusinessAuditEvent).where(
                BusinessAuditEvent.target_label == ISOLATION_TARGET_LABEL
            )
        )

    assert player is None
    assert audit_event is None
