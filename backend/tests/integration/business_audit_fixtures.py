"""Reusable real-database scenarios for business-audit integration coverage."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.enums import (
    AuditActionCategory,
    AuditActionType,
    AuditEntityType,
    UserRole,
)
from src.models.business_audit_event import BusinessAuditEvent


def make_business_audit_event(
    *,
    actor_user_id: UUID | None = None,
    target_entity_id: UUID | None = None,
    action_type: AuditActionType = AuditActionType.PLAYER_CREATED,
    action_category: AuditActionCategory = AuditActionCategory.PLAYER,
    target_entity_type: AuditEntityType = AuditEntityType.PLAYER,
    created_at: datetime | None = None,
    actor_display_name: str = "Historical Coach",
    target_label: str = "Historical Player",
) -> BusinessAuditEvent:
    """Create an event with IDs that do not require live linked records."""

    return BusinessAuditEvent(
        id=uuid4(),
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


def make_equal_timestamp_events(
    count: int = 3,
    *,
    created_at: datetime | None = None,
) -> list[BusinessAuditEvent]:
    """Create stable-ID tie-break fixtures sharing one creation instant."""

    shared_timestamp = created_at or datetime.now(UTC)
    return [
        make_business_audit_event(created_at=shared_timestamp) for _ in range(count)
    ]
