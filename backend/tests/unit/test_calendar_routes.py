"""Authenticated read-route coverage for the calendar API."""

from datetime import date, time
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
    CalendarEventInstance,
    CalendarRangeResponse,
    CalendarTodayResponse,
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
    mocker.patch("src.routes.calendar.CalendarService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    async def override_get_db():
        yield Mock()

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

    assert malformed.status_code == 400
    assert overlong.status_code == 422
    assert overlong.json()["code"] == "calendar_range_too_large"
    service_mock.get_range.assert_not_awaited()
