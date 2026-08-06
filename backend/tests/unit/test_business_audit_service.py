"""Unit coverage for the append-only business-audit transaction contract."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import date
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import AuditActionType, AuditEntityType, UserRole
from src.models.business_audit_event import BusinessAuditEvent
from src.schemas.business_audit import BusinessAuditQuery
from src.services.business_audit_service import (
    AuditActorContext,
    AuditTargetContext,
    BusinessAuditService,
)


@pytest.mark.asyncio
async def test_record_uses_caller_session_flushes_once_and_never_commits(
    business_audit_actor_factory: Callable[..., AuditActorContext],
    business_audit_target_factory: Callable[..., AuditTargetContext],
) -> None:
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    event = await BusinessAuditService(session).record(
        actor=business_audit_actor_factory(),
        action_type=AuditActionType.PLAYER_CREATED,
        target=business_audit_target_factory(),
    )

    session.add.assert_called_once_with(event)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    assert isinstance(event, BusinessAuditEvent)


def test_actor_snapshot_normalizes_string_backed_roles() -> None:
    """Persisted String columns still produce one typed immutable snapshot."""

    user = Mock(
        id=uuid4(),
        first_name="String",
        last_name="Role",
        role=UserRole.HEAD_COACH.value,
    )

    actor = AuditActorContext.from_user(user)

    assert actor.role is UserRole.HEAD_COACH
    assert actor.display_name == "String Role"


@pytest.mark.asyncio
async def test_record_allowlists_metadata_and_excludes_sensitive_values() -> None:
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()
    actor = AuditActorContext(
        user_id=uuid4(),
        display_name="Priya Shah",
        role=UserRole.ASSISTANT_COACH,
    )
    target = AuditTargetContext(
        entity_type=AuditEntityType.PLAYER,
        entity_id=uuid4(),
        label="Aryan Patel",
    )

    event = await BusinessAuditService(session).record(
        actor=actor,
        action_type=AuditActionType.PLAYER_UPDATED,
        target=target,
        metadata={
            "changed_fields": ["bio", "player_type"],
            "password": "NeverPersistThis!",
            "access_token": "secret-token",
            "raw_payload": {"bio": "unrestricted"},
            "before": {"private": "snapshot"},
        },
    )

    assert event.event_metadata == {
        "changed_fields": ["bio", "player_type"],
    }
    serialized = str(event.event_metadata)
    assert "NeverPersistThis" not in serialized
    assert "secret-token" not in serialized
    assert "unrestricted" not in serialized
    assert "snapshot" not in serialized


@pytest.mark.asyncio
async def test_record_builds_safe_summary_from_historical_snapshots() -> None:
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()
    actor_id = uuid4()
    target_id = uuid4()

    event = await BusinessAuditService(session).record(
        actor=AuditActorContext(
            user_id=actor_id,
            display_name="Alex Morgan",
            role=UserRole.HEAD_COACH,
            request_id="request-42",
        ),
        action_type=AuditActionType.TEAM_CREATED,
        target=AuditTargetContext(
            entity_type=AuditEntityType.TEAM,
            entity_id=target_id,
            label="U15 Falcons",
        ),
        metadata={"age_group": "U15", "roster_count": 12},
    )

    assert event.actor_user_id == actor_id
    assert event.actor_display_name == "Alex Morgan"
    assert event.actor_role == UserRole.HEAD_COACH.value
    assert event.target_entity_id == target_id
    assert event.target_label == "U15 Falcons"
    assert event.summary == "Alex Morgan created team U15 Falcons"
    assert event.request_id == "request-42"
    assert event.event_metadata == {"age_group": "U15", "roster_count": 12}


def test_actor_and_target_contexts_are_immutable() -> None:
    actor = AuditActorContext(
        user_id=uuid4(),
        display_name="Immutable Actor",
        role=UserRole.HEAD_COACH,
    )
    target = AuditTargetContext(
        entity_type=AuditEntityType.PLAYER,
        entity_id=uuid4(),
        label="Historical Target",
    )

    with pytest.raises(FrozenInstanceError):
        actor.display_name = "Changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        target.label = "Changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_record_rejects_registry_target_mismatch_before_staging() -> None:
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="requires target type player"):
        await BusinessAuditService(session).record(
            actor=AuditActorContext(
                user_id=uuid4(),
                display_name="Head Coach",
                role=UserRole.HEAD_COACH,
            ),
            action_type=AuditActionType.PLAYER_CREATED,
            target=AuditTargetContext(
                entity_type=AuditEntityType.TEAM,
                entity_id=uuid4(),
                label="Wrong target",
            ),
        )

    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_propagates_persistence_failure_to_outer_transaction(
    business_audit_failing_session: Mock,
    business_audit_actor_factory: Callable[..., AuditActorContext],
    business_audit_target_factory: Callable[..., AuditTargetContext],
) -> None:
    service = BusinessAuditService(business_audit_failing_session)

    with pytest.raises(RuntimeError, match="simulated audit persistence"):
        await service.record(
            actor=business_audit_actor_factory(),
            action_type=AuditActionType.PLAYER_CREATED,
            target=business_audit_target_factory(),
        )

    business_audit_failing_session.add.assert_called_once()
    business_audit_failing_session.commit.assert_not_awaited()
    business_audit_failing_session.rollback.assert_not_awaited()


def test_service_exposes_no_update_or_delete_mutation_api() -> None:
    public_methods = {
        name for name in dir(BusinessAuditService) if not name.startswith("_")
    }

    assert "record" in public_methods
    assert not public_methods.intersection(
        {"update", "update_event", "delete", "delete_event", "clear"}
    )


def test_business_audit_query_rejects_more_than_366_inclusive_dates() -> None:
    valid = BusinessAuditQuery(
        start_date=date(2025, 1, 1),
        end_date=date(2026, 1, 1),
    )
    assert (valid.end_date - valid.start_date).days + 1 == 366

    with pytest.raises(ValidationError, match="must not exceed 366"):
        BusinessAuditQuery(
            start_date=date(2025, 1, 1),
            end_date=date(2026, 1, 2),
        )
