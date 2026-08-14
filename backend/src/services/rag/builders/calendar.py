"""Projected Calendar occurrence adapter; recurrence stays in CalendarService."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.enums import ScopeKind
from src.schemas.calendar import CalendarEventInstance
from src.services.calendar_recurrence import MAX_CALENDAR_RANGE_DATES
from src.services.calendar_service import CalendarService
from src.services.rag.builders._common import build_document, enum_value
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

CALENDAR_OCCURRENCE_BUILDER_VERSION = "calendar-occurrence-v1"


def build_calendar_occurrence_document(
    occurrence: CalendarEventInstance,
) -> CanonicalRagDocument:
    """Build one safe effective occurrence; raw event definitions are never indexed."""

    is_all_academy = (
        occurrence.scope_kind is ScopeKind.ALL_ACADEMY
        or str(occurrence.scope_kind) == "all_academy"
    )
    dependency = stable_component_hash(
        occurrence.event_id,
        occurrence.series_id,
        occurrence.original_date,
        occurrence.event_version_number,
        occurrence.exception_id,
        occurrence.exception_version_number,
        occurrence.event_date,
        tuple(occurrence.age_groups),
        occurrence.scope_kind,
    )
    source_version = (
        f"event:{occurrence.event_version_number}:"
        f"exception:{occurrence.exception_version_number or 0}"
    )
    return build_document(
        source_type="calendar_occurrence",
        source_key=occurrence.occurrence_id,
        source_entity_id=occurrence.event_id,
        source_version=source_version,
        dependency_fingerprint=dependency,
        fields=[
            ("Calendar event", occurrence.name),
            ("Event type", enum_value(occurrence.event_type)),
            ("Event date", occurrence.event_date),
            ("All day", occurrence.is_all_day),
            ("Start time", occurrence.start_time),
            ("End time", occurrence.end_time),
            ("Audience", "all academy" if is_all_academy else occurrence.age_groups),
            ("Recurrence", occurrence.recurrence_summary),
        ],
        provenance={
            "entity": "calendar_occurrence",
            "event_id": str(occurrence.event_id),
            "occurrence_id": occurrence.occurrence_id,
        },
        scope=RagScopeMetadata(
            source_type="calendar_occurrence",
            age_groups=tuple(str(item) for item in occurrence.age_groups),
            is_all_academy=is_all_academy,
        ),
        builder_version=CALENDAR_OCCURRENCE_BUILDER_VERSION,
        model=occurrence,
    )


async def load_projected_calendar_occurrences(
    service: CalendarService,
    *,
    now: datetime,
) -> tuple[CalendarEventInstance, ...]:
    """Delegate occurrence semantics and bounded horizon selection to Calendar."""

    start = now.date()
    result = await service.get_range(
        start, start + timedelta(days=MAX_CALENDAR_RANGE_DATES - 1)
    )
    return tuple(result.events)
