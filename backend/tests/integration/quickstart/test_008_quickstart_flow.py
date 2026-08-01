"""Executable validation for the Calendar Interface quickstart journey."""

from __future__ import annotations

from calendar import isleap
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.calendar import (
    CalendarEvent,
    OccurrenceException,
    RecurrenceSeries,
)
from src.models.user import User
from src.services.password_service import PasswordService

ACADEMY_TIMEZONE = ZoneInfo("America/Los_Angeles")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide the real database session used for setup and cleanup."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> httpx.AsyncClient:
    """Run quickstart requests through the complete FastAPI stack."""

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


def timed_payload(
    *,
    name: str,
    event_date: date,
    recurrence: dict[str, Any] | None = None,
    start_time: time = time(17, 0),
    end_time: time = time(18, 30),
    age_groups: list[str] | None = None,
) -> dict[str, Any]:
    """Build a valid academy-local timed calendar payload."""

    return {
        "event_type": "practice",
        "name": name,
        "event_date": event_date.isoformat(),
        "is_all_day": False,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "scope": {
            "scope_kind": "age_group",
            "age_groups": age_groups or ["U13"],
        },
        "recurrence": recurrence,
    }


async def create_user(
    session: AsyncSession,
    *,
    role: UserRole,
    run_id: str,
) -> tuple[UUID, str, str]:
    """Create one isolated account for the quickstart flow."""

    user_id = uuid4()
    email = f"calendar-quickstart-{role.value.replace(' ', '-')}-{run_id}@example.com"
    password = "CalendarQuickstart-P@ssword1"
    session.add(
        User(
            id=user_id,
            first_name="Calendar",
            last_name=f"Quickstart {role.value}",
            email=email,
            hashed_password=PasswordService.hash_password(password),
            role=role,
            is_active=True,
        )
    )
    await session.commit()
    return user_id, email, password


async def login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
) -> str:
    """Authenticate an isolated account and return its bearer header."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return f"Bearer {response.json()['access_token']}"


def next_future_leap_date(today: date) -> date:
    """Return a February 29 that is safely after the academy today."""

    year = today.year
    while True:
        year += 1
        if isleap(year) and date(year, 2, 29) > today:
            return date(year, 2, 29)


def event_named(events: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Find one exact-name event in a range response."""

    return next(event for event in events if event["name"] == name)


@pytest.mark.asyncio
async def test_calendar_interface_quickstart_flow(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Exercise recurrence, Today, exceptions, authorization, OCC, and deletion."""

    run_id = uuid4().hex
    coach_id: UUID | None = None
    player_id: UUID | None = None
    event_ids: list[UUID] = []

    try:
        coach_id, coach_email, coach_password = await create_user(
            db_session,
            role=UserRole.HEAD_COACH,
            run_id=run_id,
        )
        player_id, player_email, player_password = await create_user(
            db_session,
            role=UserRole.PLAYER,
            run_id=run_id,
        )
        coach_authorization = await login(
            client,
            email=coach_email,
            password=coach_password,
        )
        client.headers["Authorization"] = coach_authorization

        today_response = await client.get("/api/v1/calendar/today")
        assert today_response.status_code == 200, today_response.text
        today_json = today_response.json()
        academy_today = date.fromisoformat(today_json["academy_today"])
        assert academy_today == datetime.now(ACADEMY_TIMEZONE).date()

        weekly_first = academy_today + timedelta(days=7)
        weekly_end = weekly_first + timedelta(days=21)
        weekly_name = f"Quickstart weekly {run_id}"
        weekly_create = await client.post(
            "/api/v1/calendar/events",
            json=timed_payload(
                name=weekly_name,
                event_date=weekly_first,
                recurrence={
                    "frequency": "weekly",
                    "termination": "end_date",
                    "end_date": weekly_end.isoformat(),
                    "occurrence_count": None,
                },
                age_groups=["U13", "U15"],
            ),
        )
        assert weekly_create.status_code == 201, weekly_create.text
        weekly_definition = weekly_create.json()
        weekly_event_id = UUID(weekly_definition["id"])
        weekly_series_id = UUID(weekly_definition["recurrence"]["id"])
        event_ids.append(weekly_event_id)
        assert weekly_definition["scope"] == {
            "scope_kind": "age_group",
            "age_groups": ["U13", "U15"],
        }

        weekly_range = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": weekly_first.isoformat(),
                "end_date": weekly_end.isoformat(),
            },
        )
        assert weekly_range.status_code == 200, weekly_range.text
        weekly_events = [
            event
            for event in weekly_range.json()["events"]
            if event["event_id"] == str(weekly_event_id)
        ]
        assert [event["original_date"] for event in weekly_events] == [
            (weekly_first + timedelta(days=offset)).isoformat()
            for offset in (0, 7, 14, 21)
        ]
        assert [event["event_date"] for event in weekly_events] == [
            event["original_date"] for event in weekly_events
        ]

        leap_first = next_future_leap_date(academy_today)
        leap_name = f"Quickstart leap day {run_id}"
        leap_create = await client.post(
            "/api/v1/calendar/events",
            json=timed_payload(
                name=leap_name,
                event_date=leap_first,
                recurrence={
                    "frequency": "yearly",
                    "termination": "end_date",
                    "end_date": date(leap_first.year + 1, 3, 1).isoformat(),
                    "occurrence_count": None,
                },
            ),
        )
        assert leap_create.status_code == 201, leap_create.text
        leap_definition = leap_create.json()
        leap_event_id = UUID(leap_definition["id"])
        event_ids.append(leap_event_id)

        non_leap_date = date(leap_first.year + 1, 2, 28)
        leap_range = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": non_leap_date.isoformat(),
                "end_date": non_leap_date.isoformat(),
            },
        )
        assert leap_range.status_code == 200, leap_range.text
        leap_event = event_named(leap_range.json()["events"], leap_name)
        assert leap_event["event_date"] == non_leap_date.isoformat()
        assert leap_event["original_date"] == non_leap_date.isoformat()

        excessive_range = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": academy_today.isoformat(),
                "end_date": (academy_today + timedelta(days=45)).isoformat(),
            },
        )
        assert excessive_range.status_code == 422, excessive_range.text
        assert excessive_range.json()["code"] == "calendar_range_too_large"

        today_all_day_name = f"Quickstart all day {run_id}"
        today_all_day = await client.post(
            "/api/v1/calendar/events",
            json={
                "event_type": "miscellaneous",
                "name": today_all_day_name,
                "event_date": academy_today.isoformat(),
                "is_all_day": True,
                "start_time": None,
                "end_time": None,
                "scope": {"scope_kind": "all_academy", "age_groups": []},
                "recurrence": None,
            },
        )
        assert today_all_day.status_code == 201, today_all_day.text
        event_ids.append(UUID(today_all_day.json()["id"]))

        timed_today_name: str | None = None
        academy_now = datetime.now(ACADEMY_TIMEZONE)
        candidate_start = (academy_now + timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        if candidate_start.date() == academy_today and candidate_start.time() < time(
            23
        ):
            timed_today_name = f"Quickstart timed today {run_id}"
            timed_today = await client.post(
                "/api/v1/calendar/events",
                json=timed_payload(
                    name=timed_today_name,
                    event_date=academy_today,
                    start_time=candidate_start.time(),
                    end_time=(candidate_start + timedelta(minutes=30)).time(),
                ),
            )
            assert timed_today.status_code == 201, timed_today.text
            event_ids.append(UUID(timed_today.json()["id"]))

        populated_today = await client.get("/api/v1/calendar/today")
        assert populated_today.status_code == 200, populated_today.text
        populated_today_json = populated_today.json()
        assert populated_today_json["academy_today"] == academy_today.isoformat()
        own_today_events = [
            event
            for event in populated_today_json["events"]
            if event["name"].endswith(run_id)
        ]
        assert event_named(own_today_events, today_all_day_name)["is_all_day"] is True
        if timed_today_name is not None:
            own_today_order = [event["name"] for event in own_today_events]
            assert own_today_order.index(today_all_day_name) < own_today_order.index(
                timed_today_name
            )

        impact_first = weekly_first + timedelta(days=28)
        impact_end = impact_first + timedelta(days=21)
        impact_name = f"Quickstart exception series {run_id}"
        impact_create = await client.post(
            "/api/v1/calendar/events",
            json=timed_payload(
                name=impact_name,
                event_date=impact_first,
                recurrence={
                    "frequency": "weekly",
                    "termination": "occurrence_count",
                    "end_date": None,
                    "occurrence_count": 4,
                },
            ),
        )
        assert impact_create.status_code == 201, impact_create.text
        impact_definition = impact_create.json()
        impact_event_id = UUID(impact_definition["id"])
        impact_series_id = UUID(impact_definition["recurrence"]["id"])
        event_ids.append(impact_event_id)

        async def edit_occurrence(
            original_date: date,
            name: str,
            *,
            exception_version_number: int | None = None,
            version_number: int = 1,
        ) -> httpx.Response:
            payload = timed_payload(name=name, event_date=original_date)
            payload["version_number"] = version_number
            payload["exception_version_number"] = exception_version_number
            return await client.patch(
                f"/api/v1/calendar/instances/{impact_series_id}:{original_date.isoformat()}",
                json=payload,
            )

        kept_original = impact_first
        removed_original = impact_first + timedelta(days=7)
        kept_name = f"Quickstart kept exception {run_id}"
        removed_name = f"Quickstart removed exception {run_id}"
        kept_edit = await edit_occurrence(kept_original, kept_name)
        assert kept_edit.status_code == 200, kept_edit.text
        removed_edit = await edit_occurrence(removed_original, removed_name)
        assert removed_edit.status_code == 200, removed_edit.text

        moved_original = weekly_first + timedelta(days=7)
        moved_date = moved_original + timedelta(days=1)
        moved_payload = timed_payload(
            name=f"Quickstart moved occurrence {run_id}",
            event_date=moved_date,
        )
        moved_payload.update({"version_number": 1, "exception_version_number": None})
        moved_response = await client.patch(
            f"/api/v1/calendar/instances/{weekly_series_id}:{moved_original.isoformat()}",
            json=moved_payload,
        )
        assert moved_response.status_code == 200, moved_response.text
        assert moved_response.json()["occurrence_id"] == (
            f"{weekly_series_id}:{moved_original.isoformat()}"
        )
        assert moved_response.json()["event_date"] == moved_date.isoformat()

        after_move = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": weekly_first.isoformat(),
                "end_date": weekly_end.isoformat(),
            },
        )
        assert after_move.status_code == 200, after_move.text
        weekly_after_move = [
            event
            for event in after_move.json()["events"]
            if event["event_id"] == str(weekly_event_id)
        ]
        moved_instance = event_named(
            weekly_after_move,
            f"Quickstart moved occurrence {run_id}",
        )
        assert moved_instance["original_date"] == moved_original.isoformat()
        assert moved_instance["event_date"] == moved_date.isoformat()
        assert not any(
            event["event_date"] == moved_original.isoformat()
            for event in weekly_after_move
        )
        assert any(
            event["original_date"] == (weekly_first + timedelta(days=14)).isoformat()
            for event in weekly_after_move
        )

        impact_update = timed_payload(
            name=impact_name,
            event_date=impact_first,
            recurrence={
                "frequency": "weekly",
                "termination": "occurrence_count",
                "end_date": None,
                "occurrence_count": 1,
            },
        )
        impact_update.update({"version_number": 1, "confirm_exception_removals": False})
        warning = await client.patch(
            f"/api/v1/calendar/series/{impact_series_id}",
            json=impact_update,
        )
        assert warning.status_code == 422, warning.text
        assert warning.json()["code"] == "exception_removal_confirmation_required"
        assert warning.json()["removed_exception_original_dates"] == [
            removed_original.isoformat()
        ]

        impact_update["confirm_exception_removals"] = True
        updated_series = await client.patch(
            f"/api/v1/calendar/series/{impact_series_id}",
            json=impact_update,
        )
        assert updated_series.status_code == 200, updated_series.text
        assert updated_series.json()["version_number"] == 2

        impact_range = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": impact_first.isoformat(),
                "end_date": impact_end.isoformat(),
            },
        )
        assert impact_range.status_code == 200, impact_range.text
        impact_events = [
            event
            for event in impact_range.json()["events"]
            if event["event_id"] == str(impact_event_id)
        ]
        assert len(impact_events) == 1
        assert impact_events[0]["name"] == kept_name
        assert impact_events[0]["original_date"] == kept_original.isoformat()

        latest_kept_name = f"Quickstart latest kept exception {run_id}"
        latest_kept = await edit_occurrence(
            kept_original,
            latest_kept_name,
            exception_version_number=1,
            version_number=2,
        )
        assert latest_kept.status_code == 200, latest_kept.text
        assert latest_kept.json()["exception_version_number"] == 2
        stale_exception = await edit_occurrence(
            kept_original,
            f"Quickstart stale exception {run_id}",
            exception_version_number=1,
            version_number=2,
        )
        assert stale_exception.status_code == 409, stale_exception.text
        assert stale_exception.json()["code"] == "calendar_stale_version"

        stale_series = await client.patch(
            f"/api/v1/calendar/series/{impact_series_id}",
            json={
                **impact_update,
                "name": f"Quickstart stale series {run_id}",
                "version_number": 1,
            },
        )
        assert stale_series.status_code == 409, stale_series.text
        assert stale_series.json()["code"] == "calendar_stale_version"

        player_authorization = await login(
            client,
            email=player_email,
            password=player_password,
        )
        client.headers["Authorization"] = player_authorization
        player_range = await client.get(
            "/api/v1/calendar/events",
            params={
                "start_date": weekly_first.isoformat(),
                "end_date": weekly_end.isoformat(),
            },
        )
        assert player_range.status_code == 200, player_range.text
        player_today = await client.get("/api/v1/calendar/today")
        assert player_today.status_code == 200, player_today.text
        denied_create = await client.post(
            "/api/v1/calendar/events",
            json=timed_payload(
                name=f"Quickstart denied create {run_id}",
                event_date=weekly_first,
            ),
        )
        assert denied_create.status_code == 403, denied_create.text
        denied_update = await client.patch(
            f"/api/v1/calendar/series/{impact_series_id}",
            json=impact_update,
        )
        assert denied_update.status_code == 403, denied_update.text
        denied_occurrence_delete = await client.request(
            "DELETE",
            f"/api/v1/calendar/instances/{weekly_series_id}:{weekly_first.isoformat()}",
            json={"version_number": 1, "exception_version_number": None},
        )
        assert denied_occurrence_delete.status_code == 403, (
            denied_occurrence_delete.text
        )
        denied_series_delete = await client.request(
            "DELETE",
            f"/api/v1/calendar/series/{impact_series_id}",
            json={"version_number": 2},
        )
        assert denied_series_delete.status_code == 403, denied_series_delete.text

        client.headers["Authorization"] = coach_authorization
        deleted_series = await client.request(
            "DELETE",
            f"/api/v1/calendar/series/{impact_series_id}",
            json={"version_number": 2},
        )
        assert deleted_series.status_code == 204, deleted_series.text
        assert (
            await client.get(
                f"/api/v1/calendar/instances/{impact_series_id}:{kept_original.isoformat()}"
            )
        ).status_code == 404

        async with AsyncSessionFactory() as verification_session:
            assert (
                await verification_session.get(CalendarEvent, impact_event_id) is None
            )
            assert (
                await verification_session.get(RecurrenceSeries, impact_series_id)
                is None
            )
            assert (
                await verification_session.scalar(
                    select(OccurrenceException.id).where(
                        OccurrenceException.series_id == impact_series_id
                    )
                )
                is None
            )
    finally:
        client.headers.pop("Authorization", None)
        await db_session.rollback()
        if event_ids:
            await db_session.execute(
                delete(CalendarEvent).where(CalendarEvent.id.in_(event_ids))
            )
        if coach_id is not None or player_id is not None:
            user_ids = [user_id for user_id in (coach_id, player_id) if user_id]
            await db_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id.in_(user_ids))
            )
            await db_session.execute(
                delete(AuthSession).where(AuthSession.user_id.in_(user_ids))
            )
            await db_session.execute(delete(User).where(User.id.in_(user_ids)))
        await db_session.commit()
