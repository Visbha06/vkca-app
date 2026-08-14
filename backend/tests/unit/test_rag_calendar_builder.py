"""RAG Calendar builder tests use the Calendar service projection contract."""

from datetime import date, time
from uuid import uuid4

from src.enums import EventType, ScopeKind
from src.schemas.calendar import CalendarEventInstance
from src.services.rag.builders.calendar import build_calendar_occurrence_document


def test_projected_occurrence_has_a_stable_identity_and_scope() -> None:
    event_id = uuid4()
    occurrence = CalendarEventInstance(
        occurrence_id=f"{event_id}:2026-08-20",
        event_id=event_id,
        series_id=uuid4(),
        original_date=date(2026, 8, 20),
        event_date=date(2026, 8, 20),
        event_type=EventType.PRACTICE,
        name="Evening training",
        is_all_day=False,
        start_time=time(18, 0),
        end_time=time(19, 30),
        scope_kind=ScopeKind.AGE_GROUP,
        age_groups=["U13"],
        is_recurring=True,
        recurrence_summary="Weekly on Thursday",
        event_version_number=2,
        exception_id=None,
        exception_version_number=None,
    )

    document = build_calendar_occurrence_document(occurrence)

    assert document.source_key == occurrence.occurrence_id
    assert "Evening training" in document.semantic_text
    assert document.scope.age_groups == ("U13",)
    assert not document.scope.is_all_academy
    assert (
        document.document_id
        == build_calendar_occurrence_document(occurrence).document_id
    )
