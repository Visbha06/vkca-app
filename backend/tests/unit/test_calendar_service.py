"""Unit coverage for calendar read projections and atomic mutations."""

from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventDelete,
    CalendarOccurrenceDelete,
    CalendarOccurrenceUpdate,
    CalendarSeriesUpdate,
    CalendarStandaloneUpdate,
)
from src.services.calendar_service import (
    CalendarEventNotFoundError,
    CalendarExceptionRemovalRequiredError,
    CalendarService,
    CalendarStaleVersionError,
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
    timestamp = datetime(2026, 8, 1, 12, tzinfo=UTC)
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
        created_at=timestamp,
        updated_at=timestamp,
    )


def make_series(event, *, exceptions=None, frequency="weekly"):
    timestamp = datetime(2026, 8, 1, 12, tzinfo=UTC)
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
        created_at=timestamp,
        updated_at=timestamp,
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


def mutation_values(**overrides):
    values = {
        "event_type": "practice",
        "name": "Evening practice",
        "event_date": date(2026, 8, 10),
        "is_all_day": False,
        "start_time": time(17),
        "end_time": time(18, 30),
        "scope": {"scope_kind": "age_group", "age_groups": ["U13", "U15"]},
    }
    values.update(overrides)
    return values


def mutation_session():
    session = Mock()
    session.add = Mock()
    session.add_all = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_creation_persists_event_scope_and_uuid_series_atomically(mocker):
    session = mutation_session()
    service = CalendarService(
        session,
        now=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    expected = Mock()
    mocker.patch.object(service, "_definition_response", return_value=expected)
    payload = CalendarEventCreate(
        **mutation_values(
            recurrence={
                "frequency": "weekly",
                "termination": "occurrence_count",
                "occurrence_count": 4,
            }
        )
    )

    result = await service.create_event(payload)

    assert result is expected
    persisted_event = session.add.call_args.args[0]
    assert persisted_event.name == "Evening practice"
    assert {scope.age_group for scope in persisted_event.scopes} == {"U13", "U15"}
    assert persisted_event.recurrence_series is not None
    assert persisted_event.recurrence_series.event_id == persisted_event.id
    assert persisted_event.recurrence_series.id.version == 4
    assert persisted_event.recurrence_series.occurrence_count == 4
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_creation_rolls_back_every_related_row_when_flush_fails():
    session = mutation_session()
    session.flush.side_effect = RuntimeError("database unavailable")
    service = CalendarService(
        session,
        now=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )

    with pytest.raises(RuntimeError):
        await service.create_event(
            CalendarEventCreate(**mutation_values(recurrence=None))
        )

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_standalone_update_and_delete_use_owning_event_occ(mocker):
    session = mutation_session()
    event = make_event(event_date=date(2026, 8, 10), name="Original")
    event.version_number = 1
    service = CalendarService(
        session,
        now=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    mocker.patch.object(
        service,
        "_load_event_for_update",
        AsyncMock(return_value=event),
    )
    expected = Mock()
    mocker.patch.object(service, "_definition_response", return_value=expected)

    updated = await service.update_standalone(
        event.id,
        CalendarStandaloneUpdate(**mutation_values(name="Updated", version_number=1)),
    )

    assert updated is expected
    assert event.name == "Updated"
    assert event.version_number == 2
    assert {scope.age_group for scope in event.scopes} == {"U13", "U15"}

    await service.delete_standalone(
        event.id,
        CalendarEventDelete(version_number=2),
    )
    session.delete.assert_awaited_once_with(event)
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_standalone_update_rejects_a_stale_version_without_saving(mocker):
    session = mutation_session()
    event = make_event(event_date=date(2026, 8, 10))
    event.version_number = 3
    service = CalendarService(session)
    mocker.patch.object(
        service,
        "_load_event_for_update",
        AsyncMock(return_value=event),
    )

    with pytest.raises(CalendarStaleVersionError):
        await service.update_standalone(
            event.id,
            CalendarStandaloneUpdate(**mutation_values(version_number=2)),
        )

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_occurrence_mutation_treats_a_malformed_identity_as_not_found():
    session = mutation_session()
    service = CalendarService(session)

    with pytest.raises(CalendarEventNotFoundError):
        await service.update_occurrence(
            "not-an-occurrence",
            CalendarOccurrenceUpdate(
                **mutation_values(
                    version_number=1,
                    exception_version_number=None,
                )
            ),
        )

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_occurrence_move_creates_a_complete_stable_exception_snapshot(mocker):
    session = mutation_session()
    event = make_event(event_date=date(2026, 8, 5), name="Series practice")
    event.version_number = 2
    series = make_series(event)
    service = CalendarService(
        session,
        now=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    mocker.patch.object(
        service,
        "_load_occurrence_for_update",
        AsyncMock(return_value=(event, series, date(2026, 8, 12), None)),
    )

    result = await service.update_occurrence(
        f"{series.id}:2026-08-12",
        CalendarOccurrenceUpdate(
            **mutation_values(
                name="Moved practice",
                event_date=date(2026, 8, 13),
                version_number=2,
                exception_version_number=None,
            )
        ),
    )

    exception = session.add.call_args.args[0]
    assert exception.series_id == series.id
    assert exception.original_date == date(2026, 8, 12)
    assert exception.replacement_date == date(2026, 8, 13)
    assert exception.name == "Moved practice"
    assert exception.version_number == 1
    assert result.occurrence_id == f"{series.id}:2026-08-12"
    assert result.event_date == date(2026, 8, 13)
    assert result.series_definition is not None
    assert result.series_definition.event_date == date(2026, 8, 5)
    assert result.series_definition.name == "Series practice"
    assert event.name == "Series practice"
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_occurrence_delete_updates_only_its_exception_version(mocker):
    session = mutation_session()
    event = make_event(event_date=date(2026, 8, 5))
    event.version_number = 4
    series = make_series(event)
    exception = make_exception(series, date(2026, 8, 12))
    exception.version_number = 2
    service = CalendarService(session)
    mocker.patch.object(
        service,
        "_load_occurrence_for_update",
        AsyncMock(return_value=(event, series, date(2026, 8, 12), exception)),
    )

    await service.delete_occurrence(
        f"{series.id}:2026-08-12",
        CalendarOccurrenceDelete(
            version_number=4,
            exception_version_number=2,
        ),
    )

    assert exception.is_deleted is True
    assert exception.version_number == 3
    assert exception.event_type is None
    assert exception.scopes == []
    assert event.version_number == 4
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_series_update_requires_confirmation_then_removes_only_invalid_exceptions(
    mocker,
):
    session = mutation_session()
    event = make_event(event_date=date(2026, 8, 5))
    event.version_number = 2
    series = make_series(event)
    kept = make_exception(series, date(2026, 8, 13))
    removed = make_exception(series, date(2026, 8, 12))
    series.exceptions = [kept, removed]
    service = CalendarService(
        session,
        now=datetime(2026, 8, 1, 12, tzinfo=UTC),
    )
    mocker.patch.object(
        service,
        "_load_series_for_update",
        AsyncMock(return_value=(event, series)),
    )
    expected = Mock()
    mocker.patch.object(service, "_definition_response", return_value=expected)
    base_payload = mutation_values(
        event_date=date(2026, 8, 6),
        recurrence={"frequency": "weekly", "termination": "never"},
        version_number=2,
    )

    with pytest.raises(CalendarExceptionRemovalRequiredError) as warning:
        await service.update_series(
            series.id,
            CalendarSeriesUpdate(
                **base_payload,
                confirm_exception_removals=False,
            ),
        )
    assert warning.value.removed_original_dates == [date(2026, 8, 12)]
    session.commit.assert_not_awaited()

    result = await service.update_series(
        series.id,
        CalendarSeriesUpdate(
            **base_payload,
            confirm_exception_removals=True,
        ),
    )

    assert result is expected
    session.delete.assert_awaited_once_with(removed)
    assert kept in series.exceptions
    assert removed not in series.exceptions
    assert event.first_date == date(2026, 8, 6)
    assert event.version_number == 3
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_entire_series_delete_removes_the_owning_event_for_database_cascade(
    mocker,
):
    session = mutation_session()
    event = make_event(event_date=date(2026, 8, 5))
    event.version_number = 5
    series = make_series(event)
    service = CalendarService(session)
    mocker.patch.object(
        service,
        "_load_series_for_update",
        AsyncMock(return_value=(event, series)),
    )

    await service.delete_series(
        series.id,
        CalendarEventDelete(version_number=5),
    )

    session.delete.assert_awaited_once_with(event)
    session.commit.assert_awaited_once_with()
