"""Append-only writer and bounded snapshot retrieval for business activity."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from math import isfinite
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.enums import (
    AuditActionCategory,
    AuditActionType,
    AuditEntityType,
    UserRole,
)
from src.models.business_audit_event import BusinessAuditEvent
from src.schemas.business_audit import (
    BusinessAuditActorOption,
    BusinessAuditActorOptionsResponse,
    BusinessAuditEventResponse,
    BusinessAuditMetadataScalar,
    BusinessAuditMetadataValue,
    BusinessAuditPageResponse,
    BusinessAuditQuery,
    RecentBusinessAuditResponse,
)
from src.services.business_audit_registry import get_action_definition

if TYPE_CHECKING:
    from src.models.user import User

MAX_METADATA_ITEMS = 100
MAX_METADATA_STRING_LENGTH = 500


@dataclass(frozen=True, slots=True)
class AuditActorContext:
    """Immutable authenticated actor snapshot passed into a mutation service."""

    user_id: UUID | None
    display_name: str | None
    role: UserRole | None
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.user_id is not None and (
            self.display_name is None or self.role is None
        ):
            raise ValueError("identified audit actors require name and role snapshots")
        if self.request_id is not None and len(self.request_id) > 128:
            object.__setattr__(self, "request_id", self.request_id[:128])

    @classmethod
    def from_user(
        cls,
        user: "User",
        *,
        request_id: str | None = None,
    ) -> "AuditActorContext":
        """Copy safe actor fields without retaining the mutable ORM entity."""

        display_name = f"{user.first_name} {user.last_name}".strip()
        return cls(
            user_id=user.id,
            display_name=display_name,
            role=UserRole(user.role),
            request_id=request_id,
        )


@dataclass(frozen=True, slots=True)
class AuditTargetContext:
    """Immutable historical target identity captured at the mutation boundary."""

    entity_type: AuditEntityType
    entity_id: UUID | None
    label: str | None


def _safe_scalar(value: object) -> BusinessAuditMetadataScalar | None:
    """Normalize one JSON-safe scalar, returning ``None`` for unsafe values."""

    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, Enum):
        return str(value.value)[:MAX_METADATA_STRING_LENGTH]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, str):
        return value[:MAX_METADATA_STRING_LENGTH]
    return None


def _safe_metadata_value(value: object) -> BusinessAuditMetadataValue | None:
    scalar = _safe_scalar(value)
    if scalar is not None or value is None:
        return scalar
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        normalized: list[BusinessAuditMetadataScalar] = []
        for item in value[:MAX_METADATA_ITEMS]:
            safe_item = _safe_scalar(item)
            if safe_item is not None or item is None:
                normalized.append(safe_item)
        return normalized
    return None


def sanitize_metadata(
    action_type: AuditActionType,
    metadata: Mapping[str, object] | None,
) -> dict[str, BusinessAuditMetadataValue]:
    """Retain only action-specific allowlisted fields with safe scalar values."""

    if not metadata:
        return {}
    allowed_fields = get_action_definition(action_type).metadata_fields
    sanitized: dict[str, BusinessAuditMetadataValue] = {}
    for key in allowed_fields:
        if key not in metadata:
            continue
        safe_value = _safe_metadata_value(metadata[key])
        if safe_value is not None or metadata[key] is None:
            sanitized[key] = safe_value
    return sanitized


class BusinessAuditService:
    """Stage one event in a caller transaction and retrieve bounded snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        actor: AuditActorContext,
        action_type: AuditActionType,
        target: AuditTargetContext,
        metadata: Mapping[str, object] | None = None,
    ) -> BusinessAuditEvent:
        """Add and flush exactly one event without committing independently."""

        action_type = AuditActionType(action_type)
        definition = get_action_definition(action_type)
        if target.entity_type is not definition.target_entity_type:
            raise ValueError(
                f"{action_type.value} requires target type "
                f"{definition.target_entity_type.value}"
            )

        actor_label = (actor.display_name or "The system")[:201]
        target_label = (target.label or target.entity_type.value.replace("_", " "))[
            :255
        ]
        summary = definition.summary_template.format(
            actor=actor_label,
            target=target_label,
        )[:500]
        event = BusinessAuditEvent(
            actor_user_id=actor.user_id,
            actor_display_name=(
                actor.display_name[:201] if actor.display_name is not None else None
            ),
            actor_role=actor.role.value if actor.role is not None else None,
            action_type=action_type.value,
            action_category=definition.category.value,
            target_entity_type=target.entity_type.value,
            target_entity_id=target.entity_id,
            target_label=target.label[:255] if target.label is not None else None,
            summary=summary,
            event_metadata=sanitize_metadata(action_type, metadata),
            request_id=actor.request_id,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def record_scoring_initialization(
        self,
        *,
        actor: AuditActorContext,
        match_id: UUID,
        match_label: str,
        capability_profile: str,
        capability_version: int,
        innings_sequence: Sequence[str],
        participant_count: int,
    ) -> BusinessAuditEvent:
        """Stage the allowlisted scoring lock event in the caller transaction."""

        return await self.record(
            actor=actor,
            action_type=AuditActionType.SCORING_INITIALIZED,
            target=AuditTargetContext(
                entity_type=AuditEntityType.MATCH,
                entity_id=match_id,
                label=match_label,
            ),
            metadata={
                "capability_profile": capability_profile,
                "capability_version": capability_version,
                "innings_sequence": list(innings_sequence),
                "participant_count": participant_count,
            },
        )

    async def record_scoring_innings_started(
        self,
        *,
        actor: AuditActorContext,
        match_id: UUID,
        match_label: str,
        innings_id: UUID,
        innings_number: int,
        batting_side_id: UUID,
        fielding_side_id: UUID,
    ) -> BusinessAuditEvent:
        """Stage the allowlisted Innings-start event in the caller transaction."""

        return await self.record(
            actor=actor,
            action_type=AuditActionType.SCORING_INNINGS_STARTED,
            target=AuditTargetContext(
                entity_type=AuditEntityType.MATCH,
                entity_id=match_id,
                label=match_label,
            ),
            metadata={
                "innings_id": str(innings_id),
                "innings_number": innings_number,
                "batting_side_id": str(batting_side_id),
                "fielding_side_id": str(fielding_side_id),
            },
        )

    async def list_events(
        self,
        query: BusinessAuditQuery,
    ) -> BusinessAuditPageResponse:
        """Return one filtered page in deterministic newest-first order."""

        filters = self._filters(query)
        total_events = int(
            await self.session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(*filters)
            )
            or 0
        )
        statement = (
            select(BusinessAuditEvent)
            .where(*filters)
            .order_by(
                BusinessAuditEvent.created_at.desc(),
                BusinessAuditEvent.id.desc(),
            )
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        events = list((await self.session.scalars(statement)).all())
        total_pages = (total_events + query.page_size - 1) // query.page_size
        return BusinessAuditPageResponse(
            events=[self._event_response(event) for event in events],
            page=query.page,
            page_size=query.page_size,
            total_events=total_events,
            total_pages=total_pages,
            has_previous=query.page > 1,
            has_next=query.page < total_pages,
        )

    async def list_recent(self, *, limit: int = 4) -> RecentBusinessAuditResponse:
        """Return at most four events using the full log's stable ordering."""

        if not 1 <= limit <= 4:
            raise ValueError("limit must be between 1 and 4")
        statement = (
            select(BusinessAuditEvent)
            .order_by(
                BusinessAuditEvent.created_at.desc(),
                BusinessAuditEvent.id.desc(),
            )
            .limit(limit)
        )
        events = list((await self.session.scalars(statement)).all())
        return RecentBusinessAuditResponse(
            events=[self._event_response(event) for event in events]
        )

    async def list_actor_options(self) -> BusinessAuditActorOptionsResponse:
        """Return the latest snapshot for at most 100 distinct historical actors."""

        snapshot_rank = func.row_number().over(
            partition_by=BusinessAuditEvent.actor_user_id,
            order_by=(
                BusinessAuditEvent.created_at.desc(),
                BusinessAuditEvent.id.desc(),
            ),
        )
        ranked = (
            select(
                BusinessAuditEvent.actor_user_id.label("actor_user_id"),
                BusinessAuditEvent.actor_display_name.label("actor_display_name"),
                BusinessAuditEvent.actor_role.label("actor_role"),
                snapshot_rank.label("snapshot_rank"),
            )
            .where(
                BusinessAuditEvent.actor_user_id.is_not(None),
                BusinessAuditEvent.actor_display_name.is_not(None),
            )
            .subquery()
        )
        statement = (
            select(
                ranked.c.actor_user_id,
                ranked.c.actor_display_name,
                ranked.c.actor_role,
            )
            .where(ranked.c.snapshot_rank == 1)
            .order_by(
                func.lower(ranked.c.actor_display_name),
                ranked.c.actor_display_name,
                ranked.c.actor_user_id,
            )
            .limit(100)
        )
        rows = (await self.session.execute(statement)).all()
        return BusinessAuditActorOptionsResponse(
            actors=[
                BusinessAuditActorOption(
                    actor_user_id=actor_user_id,
                    actor_display_name=actor_display_name,
                    actor_role=actor_role,
                )
                for actor_user_id, actor_display_name, actor_role in rows
            ]
        )

    @staticmethod
    def _filters(query: BusinessAuditQuery) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if query.actor_user_id is not None:
            filters.append(BusinessAuditEvent.actor_user_id == query.actor_user_id)
        if query.action_category is not None:
            filters.append(
                BusinessAuditEvent.action_category == query.action_category.value
            )
        if query.action_type is not None:
            filters.append(BusinessAuditEvent.action_type == query.action_type.value)
        if query.entity_type is not None:
            filters.append(
                BusinessAuditEvent.target_entity_type == query.entity_type.value
            )
        if query.target_entity_id is not None:
            filters.append(
                BusinessAuditEvent.target_entity_id == query.target_entity_id
            )
        lower, upper = query.utc_date_bounds()
        if lower is not None:
            filters.append(BusinessAuditEvent.created_at >= lower)
        if upper is not None:
            filters.append(BusinessAuditEvent.created_at < upper)
        return filters

    @staticmethod
    def _event_response(event: BusinessAuditEvent) -> BusinessAuditEventResponse:
        return BusinessAuditEventResponse(
            id=event.id,
            actor_user_id=event.actor_user_id,
            actor_display_name=event.actor_display_name,
            actor_role=event.actor_role,
            action_type=AuditActionType(event.action_type),
            action_category=AuditActionCategory(event.action_category),
            target_entity_type=AuditEntityType(event.target_entity_type),
            target_entity_id=event.target_entity_id,
            target_label=event.target_label,
            summary=event.summary,
            metadata=event.event_metadata,
            created_at=event.created_at,
            request_id=event.request_id,
        )
