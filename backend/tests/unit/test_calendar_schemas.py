"""Validation coverage for calendar mutation request contracts."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from src.enums import EventType, RecurrenceFrequency, RecurrenceTermination
from src.schemas.calendar import (
    CalendarEventCreate,
    CalendarOccurrenceDelete,
    CalendarOccurrenceUpdate,
    CalendarSeriesUpdate,
    CalendarStandaloneUpdate,
)


def event_payload(**overrides):
    payload = {
        "event_type": "practice",
        "name": "  Wednesday practice  ",
        "event_date": date(2030, 8, 7),
        "is_all_day": False,
        "start_time": time(17),
        "end_time": time(18, 30),
        "scope": {"scope_kind": "age_group", "age_groups": ["U13"]},
        "recurrence": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("event_type", list(EventType))
def test_create_accepts_each_event_type_and_normalizes_name(event_type):
    payload = event_payload(event_type=event_type)
    if event_type is EventType.MISCELLANEOUS:
        payload.update(is_all_day=True, start_time=None, end_time=None)

    request = CalendarEventCreate(**payload)

    assert request.event_type is event_type
    assert request.name == "Wednesday practice"


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_time": None},
        {"end_time": None},
        {"start_time": time(18), "end_time": time(18)},
        {"start_time": time(19), "end_time": time(18)},
        {
            "event_type": "practice",
            "is_all_day": True,
            "start_time": None,
            "end_time": None,
        },
        {
            "event_type": "miscellaneous",
            "is_all_day": True,
            "start_time": time(9),
            "end_time": time(10),
        },
    ],
)
def test_create_rejects_invalid_timed_and_all_day_configurations(overrides):
    with pytest.raises(ValidationError):
        CalendarEventCreate(**event_payload(**overrides))


@pytest.mark.parametrize(
    "scope",
    [
        {"scope_kind": "age_group", "age_groups": []},
        {"scope_kind": "age_group", "age_groups": ["U13", "U13"]},
        {"scope_kind": "all_academy", "age_groups": ["U13"]},
    ],
)
def test_create_rejects_empty_duplicate_and_mixed_scope(scope):
    with pytest.raises(ValidationError):
        CalendarEventCreate(**event_payload(scope=scope))


def test_create_accepts_unambiguous_all_academy_scope():
    request = CalendarEventCreate(
        **event_payload(
            event_type="miscellaneous",
            is_all_day=True,
            start_time=None,
            end_time=None,
            scope={"scope_kind": "all_academy", "age_groups": []},
        )
    )

    assert request.scope.age_groups == []


@pytest.mark.parametrize(
    ("termination", "end_date", "occurrence_count"),
    [
        (RecurrenceTermination.NEVER, None, None),
        (RecurrenceTermination.END_DATE, date(2030, 9, 30), None),
        (RecurrenceTermination.OCCURRENCE_COUNT, None, 4),
    ],
)
def test_create_accepts_exactly_one_recurrence_termination(
    termination, end_date, occurrence_count
):
    request = CalendarEventCreate(
        **event_payload(
            recurrence={
                "frequency": RecurrenceFrequency.WEEKLY,
                "termination": termination,
                "end_date": end_date,
                "occurrence_count": occurrence_count,
            }
        )
    )

    assert request.recurrence is not None
    assert request.recurrence.termination is termination


@pytest.mark.parametrize(
    "recurrence",
    [
        {"frequency": "weekly", "termination": "never", "end_date": date(2030, 9, 1)},
        {"frequency": "weekly", "termination": "end_date", "end_date": None},
        {
            "frequency": "weekly",
            "termination": "occurrence_count",
            "occurrence_count": 0,
        },
        {
            "frequency": "weekly",
            "termination": "occurrence_count",
            "end_date": date(2030, 9, 1),
            "occurrence_count": 3,
        },
    ],
)
def test_create_rejects_invalid_recurrence_termination(recurrence):
    with pytest.raises(ValidationError):
        CalendarEventCreate(**event_payload(recurrence=recurrence))


def test_yearly_february_29_is_a_valid_series_input():
    request = CalendarEventCreate(
        **event_payload(
            event_date=date(2032, 2, 29),
            recurrence={
                "frequency": "yearly",
                "termination": "occurrence_count",
                "occurrence_count": 3,
            },
        )
    )

    assert request.event_date == date(2032, 2, 29)
    assert request.recurrence is not None
    assert request.recurrence.frequency is RecurrenceFrequency.YEARLY


@pytest.mark.parametrize(
    "overrides",
    [
        {"event_date": date(2030, 8, 6)},
        {
            "event_date": date(2030, 8, 7),
            "start_time": time(11),
            "end_time": time(12),
        },
        {
            "event_type": "miscellaneous",
            "event_date": date(2030, 8, 6),
            "is_all_day": True,
            "start_time": None,
            "end_time": None,
        },
    ],
)
def test_create_rejects_past_academy_dates_and_times(mocker, overrides):
    mocker.patch(
        "src.schemas.calendar.academy_now",
        return_value=datetime(
            2030,
            8,
            7,
            12,
            tzinfo=ZoneInfo("America/Los_Angeles"),
        ),
    )

    with pytest.raises(ValidationError, match="has not passed"):
        CalendarEventCreate(**event_payload(**overrides))


@pytest.mark.parametrize(
    ("schema", "extra"),
    [
        (CalendarStandaloneUpdate, {"version_number": 0}),
        (
            CalendarOccurrenceUpdate,
            {"version_number": 1, "exception_version_number": 0},
        ),
        (
            CalendarSeriesUpdate,
            {
                "version_number": 0,
                "confirm_exception_removals": False,
                "recurrence": {
                    "frequency": "weekly",
                    "termination": "never",
                },
            },
        ),
    ],
)
def test_mutation_schemas_require_positive_versions(schema, extra):
    payload = event_payload()
    payload.pop("recurrence")
    payload.update(extra)

    with pytest.raises(ValidationError):
        schema(**payload)


def test_occurrence_delete_allows_no_exception_version_for_first_mutation():
    request = CalendarOccurrenceDelete(
        version_number=2,
        exception_version_number=None,
    )

    assert request.version_number == 2
    assert request.exception_version_number is None
