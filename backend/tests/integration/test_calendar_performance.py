"""Bounded-range performance validation for the Calendar Interface."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil
from time import monotonic
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.main import app
from src.models.calendar import CalendarEvent

ACADEMY_TIMEZONE = ZoneInfo("America/Los_Angeles")
SAMPLE_COUNT = 20
SUCCESS_THRESHOLD_SECONDS = 2.0


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a transaction-scoped cleanup session."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> httpx.AsyncClient:
    """Run benchmark requests through the real API and service layers."""

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
    recurrence: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build one valid future timed-event payload."""

    return {
        "event_type": "practice",
        "name": name,
        "event_date": event_date.isoformat(),
        "is_all_day": False,
        "start_time": "17:00:00",
        "end_time": "18:30:00",
        "scope": {"scope_kind": "age_group", "age_groups": ["U13"]},
        "recurrence": recurrence,
    }


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_calendar_six_week_range_p95_is_within_two_seconds(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Validate repeated six-week projection under the documented success target."""

    run_id = uuid4().hex
    try:
        grid_start = datetime.now(ACADEMY_TIMEZONE).date()
        grid_end = grid_start + timedelta(days=41)

        for offset in range(1, 7):
            response = await client.post(
                "/api/v1/calendar/events",
                json=timed_payload(
                    name=f"Performance standalone {run_id}-{offset}",
                    event_date=grid_start + timedelta(days=offset),
                ),
            )
            assert response.status_code == 201, response.text

        weekly = await client.post(
            "/api/v1/calendar/events",
            json=timed_payload(
                name=f"Performance weekly {run_id}",
                event_date=grid_start + timedelta(days=1),
                recurrence={
                    "frequency": "weekly",
                    "termination": "never",
                    "end_date": None,
                    "occurrence_count": None,
                },
            ),
        )
        assert weekly.status_code == 201, weekly.text
        weekly_json = weekly.json()
        weekly_event_id = UUID(weekly_json["id"])
        weekly_series_id = UUID(weekly_json["recurrence"]["id"])

        yearly = await client.post(
            "/api/v1/calendar/events",
            json=timed_payload(
                name=f"Performance yearly {run_id}",
                event_date=grid_start + timedelta(days=2),
                recurrence={
                    "frequency": "yearly",
                    "termination": "never",
                    "end_date": None,
                    "occurrence_count": None,
                },
            ),
        )
        assert yearly.status_code == 201, yearly.text

        moved_original = grid_start + timedelta(days=8)
        moved = await client.patch(
            f"/api/v1/calendar/instances/{weekly_series_id}:{moved_original.isoformat()}",
            json={
                **timed_payload(
                    name=f"Performance moved exception {run_id}",
                    event_date=moved_original + timedelta(days=1),
                ),
                "version_number": 1,
                "exception_version_number": None,
            },
        )
        assert moved.status_code == 200, moved.text

        deleted_original = grid_start + timedelta(days=15)
        deleted = await client.request(
            "DELETE",
            f"/api/v1/calendar/instances/{weekly_series_id}:{deleted_original.isoformat()}",
            json={"version_number": 1, "exception_version_number": None},
        )
        assert deleted.status_code == 204, deleted.text

        elapsed_samples: list[float] = []
        for _ in range(SAMPLE_COUNT):
            started_at = monotonic()
            response = await client.get(
                "/api/v1/calendar/events",
                params={
                    "start_date": grid_start.isoformat(),
                    "end_date": grid_end.isoformat(),
                },
            )
            elapsed_samples.append(monotonic() - started_at)
            assert response.status_code == 200, response.text
            assert response.json()["start_date"] == grid_start.isoformat()
            assert response.json()["end_date"] == grid_end.isoformat()
            event_ids = {event["event_id"] for event in response.json()["events"]}
            assert str(weekly_event_id) in event_ids

        ordered_samples = sorted(elapsed_samples)
        p95_index = max(0, ceil(0.95 * len(ordered_samples)) - 1)
        p95_seconds = ordered_samples[p95_index]
        successful_samples = sum(
            elapsed <= SUCCESS_THRESHOLD_SECONDS for elapsed in elapsed_samples
        )
        required_successes = ceil(SAMPLE_COUNT * 0.95)
        print(
            "calendar_range_performance "
            f"samples={[round(sample, 4) for sample in elapsed_samples]} "
            f"p95={p95_seconds:.4f}s "
            f"under_two_seconds={successful_samples}/{SAMPLE_COUNT}"
        )
        assert successful_samples >= required_successes, (
            f"Only {successful_samples}/{SAMPLE_COUNT} six-week calendar requests "
            f"completed within {SUCCESS_THRESHOLD_SECONDS:.1f}s; p95="
            f"{p95_seconds:.4f}s"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(CalendarEvent).where(CalendarEvent.name.contains(run_id))
        )
        await db_session.commit()
