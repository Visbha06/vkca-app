"""Shared pytest environment configuration."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

# Pytest loads parent conftests before child conftests and test modules. Select the
# test environment here so their application imports cannot initialize .env.
os.environ["VKCA_ENV"] = "test"

if TYPE_CHECKING:
    from src.models.business_audit_event import BusinessAuditEvent
    from src.services.business_audit_service import (
        AuditActorContext,
        AuditTargetContext,
    )

# Business-audit fixtures live in feature-specific modules. This marker keeps
# future feature tests discoverable without altering security-audit fixtures.
BUSINESS_AUDIT_FEATURE = "business-audit"


@pytest.fixture
def rag_fake_provider_config() -> dict[str, object]:
    """Return deterministic provider settings without constructing a client."""

    return {
        "provider": "fake",
        "model": "gemini-embedding-001",
        "dimension": 1536,
        "batch_size": 32,
        "timeout_seconds": 30.0,
    }


@pytest.fixture
def rag_isolated_state() -> dict[str, object]:
    """Provide caller-owned state for RAG tests without shared persistence."""

    return {"provider_calls": 0, "indexed_keys": set()}


def pytest_configure(config: pytest.Config) -> None:
    """Select and validate test settings before pytest imports application code."""

    from src.config import TEST_ENV_FILE, get_settings, get_settings_env_file
    from tests.database_safety import (
        UnsafeTestDatabaseError,
        assert_safe_test_database_url,
    )

    if get_settings_env_file() != TEST_ENV_FILE:
        raise pytest.UsageError(
            "Backend tests must load the project-root .env.test settings file."
        )
    try:
        settings = get_settings()
    except ValidationError:
        raise pytest.UsageError(
            "Unable to load required backend test settings from the project-root "
            ".env.test file."
        ) from None
    try:
        assert_safe_test_database_url(str(settings.database_url))
    except UnsafeTestDatabaseError as exc:
        raise pytest.UsageError(str(exc)) from None


@pytest.fixture
def business_audit_actor_factory() -> Callable[..., AuditActorContext]:
    """Build immutable actor snapshots without using security-audit fixtures."""

    from src.enums import UserRole
    from src.services.business_audit_service import AuditActorContext

    def build(
        *,
        user_id: UUID | None = None,
        display_name: str = "Asha Head Coach",
        role: UserRole = UserRole.HEAD_COACH,
        request_id: str | None = "request-test-1",
    ) -> AuditActorContext:
        return AuditActorContext(
            user_id=user_id or uuid4(),
            display_name=display_name,
            role=role,
            request_id=request_id,
        )

    return build


@pytest.fixture
def business_audit_target_factory() -> Callable[..., AuditTargetContext]:
    """Build historical polymorphic target snapshots for isolated tests."""

    from src.enums import AuditEntityType
    from src.services.business_audit_service import AuditTargetContext

    def build(
        *,
        entity_type: AuditEntityType = AuditEntityType.PLAYER,
        entity_id: UUID | None = None,
        label: str = "Historical Player",
    ) -> AuditTargetContext:
        return AuditTargetContext(
            entity_type=entity_type,
            entity_id=entity_id or uuid4(),
            label=label,
        )

    return build


@pytest.fixture
def business_audit_event_factory() -> Callable[..., BusinessAuditEvent]:
    """Build persisted-shape snapshots for filters and equal-time ordering."""

    from src.enums import (
        AuditActionCategory,
        AuditActionType,
        AuditEntityType,
        UserRole,
    )
    from src.models.business_audit_event import BusinessAuditEvent

    def build(
        *,
        event_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        target_entity_id: UUID | None = None,
        action_type: AuditActionType = AuditActionType.PLAYER_CREATED,
        action_category: AuditActionCategory = AuditActionCategory.PLAYER,
        target_entity_type: AuditEntityType = AuditEntityType.PLAYER,
        created_at: datetime | None = None,
        actor_display_name: str = "Historical Coach",
        target_label: str = "Historical Player",
    ) -> BusinessAuditEvent:
        return BusinessAuditEvent(
            id=event_id or uuid4(),
            actor_user_id=actor_user_id or uuid4(),
            actor_display_name=actor_display_name,
            actor_role=UserRole.HEAD_COACH.value,
            action_type=action_type.value,
            action_category=action_category.value,
            target_entity_type=target_entity_type.value,
            target_entity_id=target_entity_id or uuid4(),
            target_label=target_label,
            summary=f"{actor_display_name} changed {target_label}",
            event_metadata={},
            created_at=created_at or datetime.now(UTC),
            request_id=None,
        )

    return build


@pytest.fixture
def business_audit_failing_session() -> Mock:
    """Return a caller-owned session whose audit flush fails deterministically."""

    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock(side_effect=RuntimeError("simulated audit persistence"))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session
