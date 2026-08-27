"""Authenticated read and coach mutation route coverage for the calendar API."""

from datetime import UTC, date, datetime, time
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import AgeGroup, EventType, ScopeKind, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.schemas.calendar import (
    CalendarEventDefinitionResponse,
    CalendarEventInstance,
    CalendarRangeResponse,
    CalendarTodayResponse,
)
from src.services.calendar_service import (
    CalendarExceptionRemovalRequiredError,
    CalendarMutationValidationError,
    CalendarStaleVersionError,
)


def make_instance(name="Practice"):
    return CalendarEventInstance(
        occurrence_id=str(uuid4()),
        event_id=uuid4(),
        series_id=None,
        original_date=date(2026, 8, 5),
        event_date=date(2026, 8, 5),
        event_type=EventType.PRACTICE,
        name=name,
        is_all_day=False,
        start_time=time(17),
        end_time=time(18),
        scope_kind=ScopeKind.AGE_GROUP,
        age_groups=[AgeGroup.U13],
        is_recurring=False,
        recurrence_summary=None,
        event_version_number=1,
        exception_id=None,
        exception_version_number=None,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.get_range = AsyncMock()
    service.get_today = AsyncMock()
    service.get_instance = AsyncMock()
    service.create_event = AsyncMock()
    service.update_standalone = AsyncMock()
    service.delete_standalone = AsyncMock()
    service.update_occurrence = AsyncMock()
    service.delete_occurrence = AsyncMock()
    service.update_series = AsyncMock()
    service.delete_series = AsyncMock()
    mocker.patch("src.routes.calendar.CalendarService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return Mock(role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role", [UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH, UserRole.PLAYER]
)
async def test_all_authenticated_roles_can_read_range_today_and_details(
    client, service_mock, role
):
    instance = make_instance()
    service_mock.get_range.return_value = CalendarRangeResponse(
        academy_today=date(2026, 8, 1),
        start_date=date(2026, 7, 26),
        end_date=date(2026, 9, 5),
        events=[instance],
    )
    service_mock.get_today.return_value = CalendarTodayResponse(
        academy_today=date(2026, 8, 1), events=[instance]
    )
    service_mock.get_instance.return_value = instance

    async def override_get_current_user():
        return Mock(role=role), Mock()

    app.dependency_overrides[get_current_user] = override_get_current_user

    range_response = await client.get(
        "/api/v1/calendar/events?start_date=2026-07-26&end_date=2026-09-05"
    )
    today_response = await client.get("/api/v1/calendar/today")
    detail_response = await client.get(
        f"/api/v1/calendar/instances/{instance.occurrence_id}"
    )

    assert range_response.status_code == 200
    assert today_response.status_code == 200
    assert detail_response.status_code == 200
    service_mock.get_range.assert_awaited_once_with(date(2026, 7, 26), date(2026, 9, 5))
    service_mock.get_today.assert_awaited_once_with()
    service_mock.get_instance.assert_awaited_once_with(instance.occurrence_id)


@pytest.mark.asyncio
async def test_range_route_rejects_malformed_and_overlong_ranges(client, service_mock):
    malformed = await client.get(
        "/api/v1/calendar/events?start_date=not-a-date&end_date=2026-08-01"
    )
    overlong = await client.get(
        "/api/v1/calendar/events?start_date=2026-01-01&end_date=2026-03-01"
    )
    inverted = await client.get(
        "/api/v1/calendar/events?start_date=2026-08-02&end_date=2026-08-01"
    )

    assert malformed.status_code == 400
    assert overlong.status_code == 422
    assert overlong.json()["code"] == "calendar_range_too_large"
    assert inverted.status_code == 400
    service_mock.get_range.assert_not_awaited()


def make_definition():
    timestamp = datetime(2026, 8, 1, 12, tzinfo=UTC)
    return CalendarEventDefinitionResponse(
        id=uuid4(),
        event_type=EventType.PRACTICE,
        name="Practice",
        event_date=date(2027, 8, 5),
        is_all_day=False,
        start_time=time(17),
        end_time=time(18),
        scope={"scope_kind": "age_group", "age_groups": ["U13"]},
        version_number=1,
        recurrence=None,
        created_at=timestamp,
        updated_at=timestamp,
    )


def mutation_payload(**overrides):
    payload = {
        "event_type": "practice",
        "name": "Practice",
        "event_date": "2027-08-05",
        "is_all_day": False,
        "start_time": "17:00:00",
        "end_time": "18:00:00",
        "scope": {"scope_kind": "age_group", "age_groups": ["U13"]},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH])
async def test_coaches_can_create_update_and_delete_calendar_events(
    client, service_mock, role
):
    definition = make_definition()
    service_mock.create_event.return_value = definition
    service_mock.update_standalone.return_value = definition.model_copy(
        update={"version_number": 2}
    )

    actor_id = uuid4()

    async def override_get_current_user():
        return (
            Mock(
                id=actor_id,
                first_name="Calendar",
                last_name="Coach",
                role=role,
            ),
            Mock(),
        )

    app.dependency_overrides[get_current_user] = override_get_current_user

    created = await client.post(
        "/api/v1/calendar/events",
        json=mutation_payload(recurrence=None),
        headers={"X-Request-ID": "calendar-create-request"},
    )
    updated = await client.patch(
        f"/api/v1/calendar/events/{definition.id}",
        json=mutation_payload(version_number=1),
    )
    deleted = await client.request(
        "DELETE",
        f"/api/v1/calendar/events/{definition.id}",
        json={"version_number": 2},
    )

    assert created.status_code == 201
    assert updated.status_code == 200
    assert deleted.status_code == 204
    service_mock.create_event.assert_awaited_once()
    service_mock.update_standalone.assert_awaited_once()
    service_mock.delete_standalone.assert_awaited_once()
    create_actor = service_mock.create_event.await_args.kwargs["actor"]
    assert create_actor.user_id == actor_id
    assert create_actor.display_name == "Calendar Coach"
    assert create_actor.role is role
    assert create_actor.request_id == "calendar-create-request"


@pytest.mark.asyncio
async def test_player_mutations_return_403_without_calling_calendar_service(
    client, service_mock
):
    async def override_get_current_user():
        return Mock(role=UserRole.PLAYER), Mock(id=uuid4())

    app.dependency_overrides[get_current_user] = override_get_current_user

    response = await client.post(
        "/api/v1/calendar/events",
        json=mutation_payload(recurrence=None),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}
    service_mock.create_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_mutation_routes_map_stale_versions_and_validation_safely(
    client, service_mock
):
    event_id = uuid4()
    series_id = uuid4()
    service_mock.update_standalone.side_effect = CalendarStaleVersionError
    stale = await client.patch(
        f"/api/v1/calendar/events/{event_id}",
        json=mutation_payload(version_number=1),
    )
    service_mock.update_occurrence.side_effect = CalendarStaleVersionError
    stale_exception = await client.patch(
        f"/api/v1/calendar/instances/{series_id}:2026-08-05",
        json=mutation_payload(
            version_number=1,
            exception_version_number=1,
        ),
    )

    service_mock.update_standalone.side_effect = CalendarMutationValidationError(
        "calendar_event_in_past",
        "Choose an academy date and time that has not passed.",
    )
    invalid = await client.patch(
        f"/api/v1/calendar/events/{event_id}",
        json=mutation_payload(version_number=1),
    )

    assert stale.status_code == 409
    assert stale.json() == {
        "detail": "This calendar event changed. Reload and try again.",
        "code": "calendar_stale_version",
    }
    assert stale_exception.status_code == 409
    assert stale_exception.json()["code"] == "calendar_stale_version"
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "calendar_event_in_past"
    assert "traceback" not in str(invalid.json()).lower()


@pytest.mark.asyncio
async def test_series_update_returns_typed_exception_removal_warning(
    client, service_mock
):
    series_id = uuid4()
    service_mock.update_series.side_effect = CalendarExceptionRemovalRequiredError(
        [date(2026, 8, 5), date(2026, 8, 12)]
    )

    response = await client.patch(
        f"/api/v1/calendar/series/{series_id}",
        json=mutation_payload(
            recurrence={"frequency": "weekly", "termination": "never"},
            version_number=2,
            confirm_exception_removals=False,
        ),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "This change will remove saved changes for 2 occurrences.",
        "code": "exception_removal_confirmation_required",
        "removed_exception_original_dates": ["2026-08-05", "2026-08-12"],
    }


@pytest.mark.asyncio
async def test_occurrence_and_series_delete_routes_forward_both_version_shapes(
    client, service_mock
):
    series_id = uuid4()
    occurrence_id = f"{series_id}:2026-08-05"

    occurrence_response = await client.request(
        "DELETE",
        f"/api/v1/calendar/instances/{occurrence_id}",
        json={"version_number": 2, "exception_version_number": 1},
    )
    series_response = await client.request(
        "DELETE",
        f"/api/v1/calendar/series/{series_id}",
        json={"version_number": 2},
    )

    assert occurrence_response.status_code == 204
    assert series_response.status_code == 204
    occurrence_payload = service_mock.delete_occurrence.await_args.args[1]
    assert occurrence_payload.exception_version_number == 1
    series_payload = service_mock.delete_series.await_args.args[1]
    assert series_payload.version_number == 2
