"""Cross-module coverage for the complete coach calendar mutation lifecycle."""

from datetime import timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.calendar import (
    CalendarEvent,
    CalendarEventScope,
    OccurrenceException,
    RecurrenceSeries,
)
from src.models.user import User
from src.services.calendar_recurrence import academy_today

CALENDAR_START_DATE = academy_today() + timedelta(days=30)


@pytest_asyncio.fixture
async def client():
    """Exercise the real routes and services with one request session each."""

    async def override_get_db():
        async with AsyncSessionFactory() as request_session:
            yield request_session

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def series_payload(name: str) -> dict[str, object]:
    return {
        "event_type": "practice",
        "name": name,
        "event_date": CALENDAR_START_DATE.isoformat(),
        "is_all_day": False,
        "start_time": "17:00:00",
        "end_time": "18:30:00",
        "scope": {
            "scope_kind": "age_group",
            "age_groups": ["U13", "U15"],
        },
        "recurrence": {
            "frequency": "weekly",
            "termination": "occurrence_count",
            "end_date": None,
            "occurrence_count": 4,
        },
    }


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_calendar_series_lifecycle_is_atomic_authorized_and_versioned(
    client: httpx.AsyncClient,
) -> None:
    """Persist a series, mutate one occurrence, deny Player, then cascade delete."""

    run_id = uuid4().hex
    event_id: UUID | None = None
    series_id: UUID | None = None
    actor_id: UUID | None = None

    try:
        created = await client.post(
            "/api/v1/calendar/events",
            json=series_payload(f"Calendar flow {run_id}"),
        )
        assert created.status_code == 201, created.text
        created_json = created.json()
        event_id = UUID(created_json["id"])
        series_id = UUID(created_json["recurrence"]["id"])
        assert created_json["version_number"] == 1
        assert created_json["recurrence"]["event_id"] == str(event_id)
        assert created_json["scope"] == {
            "scope_kind": "age_group",
            "age_groups": ["U13", "U15"],
        }

        async with AsyncSessionFactory() as verification_session:
            assert (
                await verification_session.scalar(
                    select(func.count(CalendarEvent.id)).where(
                        CalendarEvent.id == event_id
                    )
                )
                == 1
            )
            assert (
                await verification_session.scalar(
                    select(func.count(RecurrenceSeries.id)).where(
                        RecurrenceSeries.id == series_id
                    )
                )
                == 1
            )
            assert (
                await verification_session.scalar(
                    select(func.count(CalendarEventScope.id)).where(
                        CalendarEventScope.event_id == event_id
                    )
                )
                == 2
            )

        initial_range = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": (CALENDAR_START_DATE - timedelta(days=1)).isoformat(),
                "end_date": (CALENDAR_START_DATE + timedelta(days=22)).isoformat(),
            },
        )
        assert initial_range.status_code == 200, initial_range.text
        assert [item["original_date"] for item in initial_range.json()["events"]] == [
            (CALENDAR_START_DATE + timedelta(days=offset)).isoformat()
            for offset in (0, 7, 14, 21)
        ]

        occurrence_date = CALENDAR_START_DATE + timedelta(days=7)
        moved_date = occurrence_date + timedelta(days=1)
        occurrence_id = f"{series_id}:{occurrence_date.isoformat()}"
        moved_payload = {
            **series_payload(f"Moved calendar flow {run_id}"),
            "event_date": moved_date.isoformat(),
            "version_number": 1,
            "exception_version_number": None,
        }
        moved_payload.pop("recurrence")
        moved = await client.patch(
            f"/api/v1/calendar/instances/{occurrence_id}",
            json=moved_payload,
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["occurrence_id"] == occurrence_id
        assert moved.json()["original_date"] == occurrence_date.isoformat()
        assert moved.json()["event_date"] == moved_date.isoformat()
        assert moved.json()["exception_version_number"] == 1
        assert (
            moved.json()["series_definition"]["event_date"]
            == CALENDAR_START_DATE.isoformat()
        )
        assert moved.json()["series_definition"]["name"] == f"Calendar flow {run_id}"

        second_edit_payload = {
            **moved_payload,
            "name": f"Moved twice {run_id}",
            "exception_version_number": 1,
        }
        edited_again = await client.patch(
            f"/api/v1/calendar/instances/{occurrence_id}",
            json=second_edit_payload,
        )
        assert edited_again.status_code == 200, edited_again.text
        assert edited_again.json()["exception_version_number"] == 2

        stale_delete = await client.request(
            "DELETE",
            f"/api/v1/calendar/instances/{occurrence_id}",
            json={"version_number": 1, "exception_version_number": 1},
        )
        assert stale_delete.status_code == 409, stale_delete.text
        assert stale_delete.json()["code"] == "calendar_stale_version"

        deleted_occurrence = await client.request(
            "DELETE",
            f"/api/v1/calendar/instances/{occurrence_id}",
            json={"version_number": 1, "exception_version_number": 2},
        )
        assert deleted_occurrence.status_code == 204, deleted_occurrence.text

        after_occurrence_delete = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": (CALENDAR_START_DATE - timedelta(days=1)).isoformat(),
                "end_date": (CALENDAR_START_DATE + timedelta(days=22)).isoformat(),
            },
        )
        remaining_dates = [
            item["original_date"] for item in after_occurrence_delete.json()["events"]
        ]
        assert occurrence_date.isoformat() not in remaining_dates
        assert remaining_dates == [
            (CALENDAR_START_DATE + timedelta(days=offset)).isoformat()
            for offset in (0, 14, 21)
        ]

        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200, me.text
        actor_id = UUID(me.json()["id"])
        async with AsyncSessionFactory() as role_session:
            actor = await role_session.get(User, actor_id)
            assert actor is not None
            actor.role = UserRole.PLAYER
            await role_session.commit()

        denied = await client.post(
            "/api/v1/calendar/events",
            json={**series_payload(f"Denied {run_id}"), "recurrence": None},
        )
        assert denied.status_code == 403, denied.text

        async with AsyncSessionFactory() as role_session:
            actor = await role_session.get(User, actor_id)
            assert actor is not None
            actor.role = UserRole.HEAD_COACH
            await role_session.commit()

        deleted_series = await client.request(
            "DELETE",
            f"/api/v1/calendar/series/{series_id}",
            json={"version_number": 1},
        )
        assert deleted_series.status_code == 204, deleted_series.text

        async with AsyncSessionFactory() as verification_session:
            assert await verification_session.get(CalendarEvent, event_id) is None
            assert await verification_session.get(RecurrenceSeries, series_id) is None
            assert (
                await verification_session.scalar(
                    select(func.count(OccurrenceException.id)).where(
                        OccurrenceException.series_id == series_id
                    )
                )
                == 0
            )
    finally:
        if actor_id is not None:
            async with AsyncSessionFactory() as role_session:
                actor = await role_session.get(User, actor_id)
                if actor is not None:
                    actor.role = UserRole.HEAD_COACH
                    await role_session.commit()
        if event_id is not None:
            async with AsyncSessionFactory() as cleanup_session:
                await cleanup_session.execute(
                    delete(CalendarEvent).where(CalendarEvent.id == event_id)
                )
                await cleanup_session.commit()
