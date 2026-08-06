"""Shared pytest environment configuration."""

import os
from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import (
    AuditActionCategory,
    AuditActionType,
    AuditEntityType,
    UserRole,
)
from src.models.business_audit_event import BusinessAuditEvent
from src.services.business_audit_service import (
    AuditActorContext,
    AuditTargetContext,
)

# Settings are loaded while route and integration test modules are imported.
# Keep the production secret mandatory while giving tests an isolated signing key.
os.environ.setdefault("JWT_SECRET", "pytest-only-jwt-secret-never-use-in-production")

# Business-audit fixtures live in feature-specific modules. This marker keeps
# future feature tests discoverable without altering security-audit fixtures.
BUSINESS_AUDIT_FEATURE = "business-audit"


@pytest.fixture
def business_audit_actor_factory() -> Callable[..., AuditActorContext]:
    """Build immutable actor snapshots without using security-audit fixtures."""

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
