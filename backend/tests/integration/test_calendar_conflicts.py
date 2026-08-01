"""Calendar failure, rollback, authorization, and OCC integration coverage."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, get_db
from src.enums import UserRole
from src.main import app
from src.models.calendar import CalendarEvent, OccurrenceException, RecurrenceSeries
from src.models.user import User


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Exercise real calendar routes with a transaction-scoped request session."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
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
        "event_date": "2030-08-07",
        "is_all_day": False,
        "start_time": "17:00:00",
        "end_time": "18:30:00",
        "scope": {
            "scope_kind": "age_group",
            "age_groups": ["U13"],
        },
        "recurrence": {
            "frequency": "weekly",
            "termination": "occurrence_count",
            "end_date": None,
            "occurrence_count": 4,
        },
    }


async def remove_event(event_id: UUID | None) -> None:
    if event_id is None:
        return
    async with AsyncSessionFactory() as cleanup_session:
        await cleanup_session.execute(
            delete(CalendarEvent).where(CalendarEvent.id == event_id)
        )
        await cleanup_session.commit()


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_calendar_guards_return_safe_codes_and_player_writes_change_nothing(
    client: httpx.AsyncClient,
) -> None:
    """Reject unsafe ranges, recurrence, past dates, and Player mutations."""

    run_id = uuid4().hex
    actor_id: UUID | None = None

    excessive = await client.get(
        "/api/v1/calendar/events",
        params={"start_date": "2030-01-01", "end_date": "2030-03-01"},
    )
    assert excessive.status_code == 422
    assert excessive.json() == {
        "detail": (
            "Unable to load that calendar range. Choose a shorter range and try again."
        ),
        "code": "calendar_range_too_large",
    }

    malformed_payload = series_payload(f"Malformed recurrence {run_id}")
    malformed_payload["recurrence"] = {
        "frequency": "weekly",
        "termination": "end_date",
        "end_date": None,
        "occurrence_count": None,
    }
    malformed = await client.post(
        "/api/v1/calendar/events",
        json=malformed_payload,
    )
    assert malformed.status_code == 422
    assert malformed.json() == {
        "detail": "Check the recurrence details and try again.",
        "code": "calendar_recurrence_invalid",
    }

    past_payload = series_payload(f"Past calendar event {run_id}")
    past_payload.update({"event_date": "2020-01-01", "recurrence": None})
    past = await client.post("/api/v1/calendar/events", json=past_payload)
    assert past.status_code == 422
    assert past.json() == {
        "detail": "Choose an academy date and time that has not passed.",
        "code": "calendar_event_in_past",
    }

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    actor_id = UUID(me.json()["id"])
    try:
        async with AsyncSessionFactory() as role_session:
            actor = await role_session.get(User, actor_id)
            assert actor is not None
            actor.role = UserRole.PLAYER
            await role_session.commit()

        denied = await client.post(
            "/api/v1/calendar/events",
            json={
                **series_payload(f"Denied calendar event {run_id}"),
                "recurrence": None,
            },
        )
        assert denied.status_code == 403

        async with AsyncSessionFactory() as verification_session:
            persisted = await verification_session.scalar(
                select(func.count(CalendarEvent.id)).where(
                    CalendarEvent.name.contains(run_id)
                )
            )
            assert persisted == 0
    finally:
        if actor_id is not None:
            async with AsyncSessionFactory() as role_session:
                actor = await role_session.get(User, actor_id)
                if actor is not None:
                    actor.role = UserRole.HEAD_COACH
                    await role_session.commit()


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_stale_owning_event_and_exception_versions_preserve_newer_data(
    client: httpx.AsyncClient,
) -> None:
    """Return 409 for stale series/exception writes without overwriting data."""

    run_id = uuid4().hex
    event_id: UUID | None = None

    try:
        created = await client.post(
            "/api/v1/calendar/events",
            json=series_payload(f"Original series {run_id}"),
        )
        assert created.status_code == 201, created.text
        event_id = UUID(created.json()["id"])
        series_id = UUID(created.json()["recurrence"]["id"])
        occurrence_id = f"{series_id}:2030-08-14"

        occurrence_payload = {
            **series_payload(f"First occurrence edit {run_id}"),
            "event_date": "2030-08-14",
            "version_number": 1,
            "exception_version_number": None,
        }
        occurrence_payload.pop("recurrence")
        first_edit = await client.patch(
            f"/api/v1/calendar/instances/{occurrence_id}",
            json=occurrence_payload,
        )
        assert first_edit.status_code == 200, first_edit.text
        assert first_edit.json()["exception_version_number"] == 1

        second_edit = await client.patch(
            f"/api/v1/calendar/instances/{occurrence_id}",
            json={
                **occurrence_payload,
                "name": f"Latest occurrence edit {run_id}",
                "exception_version_number": 1,
            },
        )
        assert second_edit.status_code == 200, second_edit.text
        assert second_edit.json()["exception_version_number"] == 2

        stale_exception = await client.patch(
            f"/api/v1/calendar/instances/{occurrence_id}",
            json={
                **occurrence_payload,
                "name": f"Stale occurrence overwrite {run_id}",
                "exception_version_number": 1,
            },
        )
        assert stale_exception.status_code == 409
        assert stale_exception.json()["code"] == "calendar_stale_version"

        current_detail = await client.get(f"/api/v1/calendar/instances/{occurrence_id}")
        assert current_detail.status_code == 200
        assert current_detail.json()["name"] == f"Latest occurrence edit {run_id}"
        assert current_detail.json()["exception_version_number"] == 2

        current_series_payload = {
            **series_payload(f"Latest series name {run_id}"),
            "version_number": 1,
            "confirm_exception_removals": False,
        }
        current_series = await client.patch(
            f"/api/v1/calendar/series/{series_id}",
            json=current_series_payload,
        )
        assert current_series.status_code == 200, current_series.text
        assert current_series.json()["version_number"] == 2

        stale_series = await client.patch(
            f"/api/v1/calendar/series/{series_id}",
            json={
                **current_series_payload,
                "name": f"Stale series overwrite {run_id}",
            },
        )
        assert stale_series.status_code == 409
        assert stale_series.json()["code"] == "calendar_stale_version"

        untouched_detail = await client.get(
            f"/api/v1/calendar/instances/{series_id}:2030-08-21"
        )
        assert untouched_detail.status_code == 200
        assert untouched_detail.json()["name"] == f"Latest series name {run_id}"
        assert untouched_detail.json()["event_version_number"] == 2
    finally:
        await remove_event(event_id)


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_failed_atomic_create_and_series_delete_roll_back_all_rows(
    client: httpx.AsyncClient,
    mocker,
) -> None:
    """Rollback flushed create/delete work when response or commit fails."""

    run_id = uuid4().hex
    failed_name = f"Rolled back create {run_id}"
    event_id: UUID | None = None

    with patch(
        "src.services.calendar_service.CalendarService._definition_response",
        side_effect=RuntimeError("injected response failure"),
    ):
        failed_create = await client.post(
            "/api/v1/calendar/events",
            json=series_payload(failed_name),
        )
    assert failed_create.status_code == 500
    assert failed_create.json() == {"detail": "Internal server error."}

    async with AsyncSessionFactory() as verification_session:
        assert (
            await verification_session.scalar(
                select(func.count(CalendarEvent.id)).where(
                    CalendarEvent.name == failed_name
                )
            )
            == 0
        )

    try:
        created = await client.post(
            "/api/v1/calendar/events",
            json=series_payload(f"Rollback delete {run_id}"),
        )
        assert created.status_code == 201, created.text
        event_id = UUID(created.json()["id"])
        series_id = UUID(created.json()["recurrence"]["id"])

        edited = await client.patch(
            f"/api/v1/calendar/instances/{series_id}:2030-08-14",
            json={
                "event_type": "practice",
                "name": f"Rollback exception {run_id}",
                "event_date": "2030-08-14",
                "is_all_day": False,
                "start_time": "17:00:00",
                "end_time": "18:30:00",
                "scope": {
                    "scope_kind": "age_group",
                    "age_groups": ["U13"],
                },
                "version_number": 1,
                "exception_version_number": None,
            },
        )
        assert edited.status_code == 200, edited.text

        previous_override = app.dependency_overrides[get_db]
        async with AsyncSessionFactory() as failing_session:
            original_flush = failing_session.flush

            async def flush_then_fail() -> None:
                await original_flush()
                raise RuntimeError("injected commit failure")

            commit_mock = mocker.patch.object(
                failing_session,
                "commit",
                new=AsyncMock(side_effect=flush_then_fail),
            )
            rollback_spy = mocker.spy(failing_session, "rollback")

            async def override_failing_db() -> AsyncIterator[AsyncSession]:
                yield failing_session

            app.dependency_overrides[get_db] = override_failing_db
            try:
                failed_delete = await client.request(
                    "DELETE",
                    f"/api/v1/calendar/series/{series_id}",
                    json={"version_number": 1},
                )
            finally:
                app.dependency_overrides[get_db] = previous_override

            assert failed_delete.status_code == 500
            commit_mock.assert_awaited_once_with()
            rollback_spy.assert_awaited_once_with()

        async with AsyncSessionFactory() as verification_session:
            assert await verification_session.get(CalendarEvent, event_id) is not None
            assert (
                await verification_session.get(RecurrenceSeries, series_id) is not None
            )
            assert (
                await verification_session.scalar(
                    select(func.count(OccurrenceException.id)).where(
                        OccurrenceException.series_id == series_id
                    )
                )
                == 1
            )
    finally:
        await remove_event(event_id)
