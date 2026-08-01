"""Unit coverage for calendar range and Today read projections."""

from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.services.calendar_service import (
    CalendarEventNotFoundError,
    CalendarService,
)


def make_scope(scope_kind="age_group", age_group="U13"):
    return SimpleNamespace(scope_kind=scope_kind, age_group=age_group)


def make_event(
    *,
    event_date=date(2026, 8, 5),
    name="Practice",
    event_type="practice",
    all_day=False,
    start=time(17),
    end=time(18),
    scopes=None,
    series=None,
):
    return SimpleNamespace(
        id=uuid4(),
        event_type=event_type,
        name=name,
        first_date=event_date,
        is_all_day=all_day,
        start_time=None if all_day else start,
        end_time=None if all_day else end,
        version_number=3,
        scopes=scopes or [make_scope()],
        recurrence_series=series,
    )


def make_series(event, *, exceptions=None, frequency="weekly"):
    series = SimpleNamespace(
        id=uuid4(),
        event_id=event.id,
        frequency=frequency,
        weekday=event.first_date.weekday() if frequency == "weekly" else None,
        month=event.first_date.month if frequency == "yearly" else None,
        month_day=event.first_date.day if frequency == "yearly" else None,
        termination="never",
        end_date=None,
        occurrence_count=None,
        exceptions=exceptions or [],
    )
    event.recurrence_series = series
    return series


def make_exception(
    series,
    original_date,
    *,
    replacement_date=None,
    deleted=False,
    name="Changed practice",
    scopes=None,
):
    return SimpleNamespace(
        id=uuid4(),
        series_id=series.id,
        original_date=original_date,
        replacement_date=replacement_date,
        event_type=None if deleted else "game",
        name=None if deleted else name,
        is_all_day=None if deleted else False,
        start_time=None if deleted else time(18),
        end_time=None if deleted else time(19),
        is_deleted=deleted,
        version_number=2,
        scopes=scopes or [make_scope("age_group", "U15")],
    )


def scalar_result(events):
    scalars = Mock()
    scalars.all.return_value = events
    result = Mock()
    result.unique.return_value = result
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_range_projects_stable_occurrences_and_orders_all_day_first():
    all_day = make_event(
        event_date=date(2026, 8, 5),
        name="Academy meeting",
        event_type="miscellaneous",
        all_day=True,
        scopes=[make_scope("all_academy", None)],
    )
    timed = make_event(
        event_date=date(2026, 8, 5), name="Early practice", start=time(9)
    )
    late = make_event(
        event_date=date(2026, 8, 5),
        name="Late game",
        start=time(19),
        end=time(20),
    )
    recurring = make_event(event_date=date(2026, 8, 5), name="Weekly practice")
    series = make_series(recurring)
    moved = make_exception(
        series,
        date(2026, 8, 12),
        replacement_date=date(2026, 8, 5),
    )
    deleted = make_exception(series, date(2026, 8, 19), deleted=True)
    series.exceptions = [moved, deleted]

    session = Mock()
    session.execute = AsyncMock(
        return_value=scalar_result([all_day, late, recurring, timed])
    )
    service = CalendarService(
        session,
        now=datetime(2026, 8, 5, 12, tzinfo=UTC),
    )

    result = await service.get_range(date(2026, 8, 1), date(2026, 8, 31))

    assert [instance.name for instance in result.events] == [
        "Academy meeting",
        "Early practice",
        "Weekly practice",
        "Changed practice",
        "Late game",
        "Weekly practice",
    ]
    changed = next(
        instance for instance in result.events if instance.name == "Changed practice"
    )
    assert changed.occurrence_id == f"{series.id}:2026-08-12"
    assert changed.original_date == date(2026, 8, 12)
    assert changed.event_date == date(2026, 8, 5)
    assert changed.exception_id == moved.id
    assert changed.exception_version_number == 2
    assert all(
        instance.original_date != date(2026, 8, 19) for instance in result.events
    )


@pytest.mark.asyncio
async def test_today_uses_pacific_academy_date_independently_of_server_utc_date():
    event = make_event(event_date=date(2026, 8, 1), name="Today practice")
    session = Mock()
    session.execute = AsyncMock(return_value=scalar_result([event]))
    service = CalendarService(
        session,
        now=datetime(2026, 8, 2, 6, 30, tzinfo=UTC),
    )

    result = await service.get_today()

    assert result.academy_today == date(2026, 8, 1)
    assert [instance.name for instance in result.events] == ["Today practice"]


@pytest.mark.asyncio
async def test_instance_detail_returns_not_found_for_deleted_occurrence():
    event = make_event(event_date=date(2026, 8, 5))
    series = make_series(event)
    series.exceptions = [make_exception(series, date(2026, 8, 5), deleted=True)]
    session = Mock()
    session.execute = AsyncMock(return_value=scalar_result([event]))
    service = CalendarService(session)

    with pytest.raises(CalendarEventNotFoundError):
        await service.get_instance(f"{series.id}:2026-08-05")
