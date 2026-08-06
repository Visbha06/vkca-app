"""Cross-workflow business-audit capture and transaction integration tests."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from src.database import AsyncSessionFactory
from src.enums import AuditActionType, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.calendar import CalendarEvent
from src.models.data_sync_log import DataSyncLog
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User


@pytest_asyncio.fixture(loop_scope="session")
async def business_audit_client() -> AsyncIterator[tuple[httpx.AsyncClient, User]]:
    """Run real routes with one persisted Head Coach actor snapshot."""

    actor = User(
        id=uuid4(),
        first_name="Integration",
        last_name="Head Coach",
        email=f"business-audit-actor-{uuid4().hex}@example.com",
        hashed_password="not-used-by-dependency-override",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )
    async with AsyncSessionFactory() as setup_session:
        setup_session.add(actor)
        await setup_session.commit()

    auth_session = AuthSession(
        id=uuid4(),
        user_id=actor.id,
        token_family_id=uuid4(),
        current_token_hash="0" * 64,
        rotated_token_hashes=[],
        created_at=datetime.now(UTC),
        last_used_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=None,
        revocation_reason=None,
        ip_address=None,
        user_agent=None,
        version_number=1,
    )

    async def override_get_current_user():
        return actor, auth_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client, actor
    finally:
        app.dependency_overrides.clear()
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(BusinessAuditEvent).where(
                    BusinessAuditEvent.actor_user_id == actor.id
                )
            )
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id == actor.id)
            )
            await cleanup_session.execute(delete(User).where(User.id == actor.id))
            await cleanup_session.commit()


async def _actor_events(actor_id: UUID) -> list[BusinessAuditEvent]:
    async with AsyncSessionFactory() as session:
        return list(
            (
                await session.scalars(
                    select(BusinessAuditEvent)
                    .where(BusinessAuditEvent.actor_user_id == actor_id)
                    .order_by(
                        BusinessAuditEvent.created_at,
                        BusinessAuditEvent.id,
                    )
                )
            ).all()
        )


async def _assert_audited_request(
    client: httpx.AsyncClient,
    actor: User,
    method: str,
    path: str,
    *,
    expected_action: AuditActionType,
    expected_status: int,
    json: dict[str, Any] | None = None,
) -> tuple[httpx.Response, BusinessAuditEvent]:
    before_ids = {event.id for event in await _actor_events(actor.id)}
    request_id = f"integration-{uuid4().hex}"

    response = await client.request(
        method,
        path,
        json=json,
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == expected_status, response.text
    new_events = [
        event for event in await _actor_events(actor.id) if event.id not in before_ids
    ]
    assert len(new_events) == 1
    event = new_events[0]
    assert event.action_type == expected_action.value
    assert event.actor_display_name == "Integration Head Coach"
    assert event.actor_role == UserRole.HEAD_COACH.value
    assert event.request_id == request_id
    serialized = f"{event.summary} {event.event_metadata}"
    assert "password" not in serialized.lower()
    assert "token" not in serialized.lower()
    return response, event


async def _assert_rejected_without_event(
    client: httpx.AsyncClient,
    actor: User,
    method: str,
    path: str,
    *,
    expected_status: int,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    before_ids = {event.id for event in await _actor_events(actor.id)}
    response = await client.request(method, path, json=json)
    assert response.status_code == expected_status, response.text
    assert {event.id for event in await _actor_events(actor.id)} == before_ids
    return response


def _player_payload(run_id: str, index: int) -> dict[str, Any]:
    return {
        "first_name": f"Audit-{index}-{run_id}",
        "last_name": "Player",
        "date_of_birth": f"2008-01-{index + 1:02d}",
        "batting_style": "right",
        "bowling_style": "right-arm medium",
        "player_type": "all-rounder",
    }


def _calendar_payload(
    *,
    name: str,
    event_date: str,
    recurrence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_type": "practice",
        "name": name,
        "event_date": event_date,
        "is_all_day": False,
        "start_time": "17:00:00",
        "end_time": "18:30:00",
        "scope": {"scope_kind": "age_group", "age_groups": ["U15"]},
    }
    if recurrence is not None:
        payload["recurrence"] = recurrence
    return payload


@pytest.mark.asyncio(loop_scope="session")
async def test_business_audit_workflow_matrix_records_one_event_per_mutation(
    business_audit_client: tuple[httpx.AsyncClient, User],
) -> None:
    """Cover player, team/roster, coach/status, and calendar boundaries."""

    client, actor = business_audit_client
    run_id = uuid4().hex[:8]
    player_ids: list[UUID] = []
    team_ids: list[UUID] = []
    coach_id: UUID | None = None
    calendar_event_ids: list[UUID] = []

    try:
        for index in range(10):
            response, _event = await _assert_audited_request(
                client,
                actor,
                "POST",
                "/api/v1/players",
                expected_action=AuditActionType.PLAYER_CREATED,
                expected_status=201,
                json=_player_payload(run_id, index),
            )
            player_ids.append(UUID(response.json()["id"]))

        await _assert_rejected_without_event(
            client,
            actor,
            "POST",
            "/api/v1/players",
            expected_status=409,
            json=_player_payload(run_id, 0),
        )
        player_update, player_event = await _assert_audited_request(
            client,
            actor,
            "PUT",
            f"/api/v1/players/{player_ids[0]}",
            expected_action=AuditActionType.PLAYER_UPDATED,
            expected_status=200,
            json={"bio": "Leadership group", "version_number": 1},
        )
        assert player_event.event_metadata == {"changed_fields": ["bio"]}
        await _assert_rejected_without_event(
            client,
            actor,
            "PUT",
            f"/api/v1/players/{player_ids[0]}",
            expected_status=409,
            json={"bio": "Stale", "version_number": 1},
        )
        assert player_update.json()["version_number"] == 2

        team_response, team_event = await _assert_audited_request(
            client,
            actor,
            "POST",
            "/api/v1/teams",
            expected_action=AuditActionType.TEAM_CREATED,
            expected_status=201,
            json={
                "name": f"Audit Falcons {run_id}",
                "age_group": "U15",
                "player_ids": [str(player_id) for player_id in player_ids[:7]],
            },
        )
        team_id = UUID(team_response.json()["id"])
        team_ids.append(team_id)
        assert team_event.event_metadata["roster_count"] == 7

        _membership, add_event = await _assert_audited_request(
            client,
            actor,
            "POST",
            f"/api/v1/teams/{team_id}/players/{player_ids[7]}",
            expected_action=AuditActionType.ROSTER_ADDED,
            expected_status=201,
        )
        assert add_event.event_metadata["player_id"] == str(player_ids[7])

        removed, _event = await _assert_audited_request(
            client,
            actor,
            "PUT",
            f"/api/v1/teams/{team_id}",
            expected_action=AuditActionType.ROSTER_REMOVED,
            expected_status=200,
            json={
                "name": team_response.json()["name"],
                "age_group": "U15",
                "player_ids": [str(player_id) for player_id in player_ids[:7]],
                "version_number": 1,
            },
        )
        reordered_ids = [player_ids[1], player_ids[0], *player_ids[2:7]]
        reordered, _event = await _assert_audited_request(
            client,
            actor,
            "PUT",
            f"/api/v1/teams/{team_id}",
            expected_action=AuditActionType.ROSTER_REORDERED,
            expected_status=200,
            json={
                "name": removed.json()["name"],
                "age_group": "U15",
                "player_ids": [str(player_id) for player_id in reordered_ids],
                "version_number": 2,
            },
        )
        added_ids = [*reordered_ids, player_ids[8]]
        added, _event = await _assert_audited_request(
            client,
            actor,
            "PUT",
            f"/api/v1/teams/{team_id}",
            expected_action=AuditActionType.ROSTER_ADDED,
            expected_status=200,
            json={
                "name": reordered.json()["name"],
                "age_group": "U15",
                "player_ids": [str(player_id) for player_id in added_ids],
                "version_number": 3,
            },
        )
        composite_ids = [*reordered_ids[1:], player_ids[8], player_ids[9]]
        composite, composite_event = await _assert_audited_request(
            client,
            actor,
            "PUT",
            f"/api/v1/teams/{team_id}",
            expected_action=AuditActionType.TEAM_UPDATED,
            expected_status=200,
            json={
                "name": f"Audit Hawks {run_id}",
                "age_group": "U15",
                "player_ids": [str(player_id) for player_id in composite_ids],
                "version_number": 4,
            },
        )
        assert composite.json()["version_number"] == 5
        assert composite_event.event_metadata["roster_replaced"] is True
        async with AsyncSessionFactory() as verification_session:
            historical_team_event = await verification_session.get(
                BusinessAuditEvent,
                team_event.id,
            )
        assert historical_team_event is not None
        assert historical_team_event.target_label == f"Audit Falcons {run_id}"
        assert composite.json()["name"] == f"Audit Hawks {run_id}"

        canonical_password = "CanonicalP@ssword42"
        _canonical_coach, canonical_event = await _assert_audited_request(
            client,
            actor,
            "POST",
            "/api/v1/users",
            expected_action=AuditActionType.COACH_CREATED,
            expected_status=201,
            json={
                "first_name": "Canonical",
                "last_name": f"Coach-{run_id}",
                "email": f"canonical-{run_id}@example.com",
                "password": canonical_password,
                "role": "assistant coach",
            },
        )
        assert canonical_password not in (
            f"{canonical_event.summary} {canonical_event.event_metadata}"
        )

        coach_response, coach_event = await _assert_audited_request(
            client,
            actor,
            "POST",
            "/api/v1/coaches",
            expected_action=AuditActionType.COACH_CREATED,
            expected_status=201,
            json={
                "first_name": "Assistant",
                "last_name": f"Coach-{run_id}",
                "email": f"assistant-{run_id}@example.com",
                "team_ids": [str(team_id)],
            },
        )
        coach_id = UUID(coach_response.json()["id"])
        assert coach_event.event_metadata["assigned_team_count"] == 1
        assert coach_response.json()["temporary_password"] not in str(
            coach_event.event_metadata
        )

        assignments, _event = await _assert_audited_request(
            client,
            actor,
            "PUT",
            f"/api/v1/coaches/{coach_id}/teams",
            expected_action=AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED,
            expected_status=200,
            json={"team_ids": [], "version_number": 1},
        )
        assert assignments.json()["version_number"] == 2
        disabled, _event = await _assert_audited_request(
            client,
            actor,
            "POST",
            f"/api/v1/users/{coach_id}/disable",
            expected_action=AuditActionType.COACH_DEACTIVATED,
            expected_status=200,
            json={"version_number": 2},
        )
        assert disabled.json()["is_active"] is False
        reactivated, _event = await _assert_audited_request(
            client,
            actor,
            "POST",
            f"/api/v1/users/{coach_id}/reactivate",
            expected_action=AuditActionType.COACH_ACTIVATED,
            expected_status=200,
            json={"version_number": 3},
        )
        assert reactivated.json()["is_active"] is True
        async with AsyncSessionFactory() as verification_session:
            security_events = list(
                (
                    await verification_session.scalars(
                        select(AuthAuditLog).where(AuthAuditLog.user_id == coach_id)
                    )
                ).all()
            )
        assert [event.event_type for event in security_events] == ["user_disablement"]
        assert security_events[0].result == "success"
        assert security_events[0].target_resource == (
            f"/api/v1/users/{coach_id}/disable"
        )
        assert not {event.event_type for event in security_events} & {
            action.value for action in AuditActionType
        }

        standalone_response, standalone_created_event = await _assert_audited_request(
            client,
            actor,
            "POST",
            "/api/v1/calendar/events",
            expected_action=AuditActionType.CALENDAR_STANDALONE_CREATED,
            expected_status=201,
            json=_calendar_payload(
                name=f"Standalone {run_id}",
                event_date="2027-08-05",
            ),
        )
        standalone_id = UUID(standalone_response.json()["id"])
        calendar_event_ids.append(standalone_id)
        standalone_update = _calendar_payload(
            name=f"Standalone updated {run_id}",
            event_date="2027-08-06",
        )
        standalone_update["version_number"] = 1
        _response, standalone_deleted_event = await _assert_audited_request(
            client,
            actor,
            "PATCH",
            f"/api/v1/calendar/events/{standalone_id}",
            expected_action=AuditActionType.CALENDAR_STANDALONE_UPDATED,
            expected_status=200,
            json=standalone_update,
        )
        await _assert_audited_request(
            client,
            actor,
            "DELETE",
            f"/api/v1/calendar/events/{standalone_id}",
            expected_action=AuditActionType.CALENDAR_STANDALONE_DELETED,
            expected_status=204,
            json={"version_number": 2},
        )
        calendar_event_ids.remove(standalone_id)
        async with AsyncSessionFactory() as verification_session:
            deleted_calendar_event = await verification_session.get(
                CalendarEvent,
                standalone_id,
            )
            historical_calendar_events = list(
                (
                    await verification_session.scalars(
                        select(BusinessAuditEvent).where(
                            BusinessAuditEvent.id.in_(
                                [
                                    standalone_created_event.id,
                                    standalone_deleted_event.id,
                                ]
                            )
                        )
                    )
                ).all()
            )
        assert deleted_calendar_event is None
        assert len(historical_calendar_events) == 2
        assert {event.target_label for event in historical_calendar_events} == {
            f"Standalone {run_id}",
            f"Standalone updated {run_id}",
        }

        series_response, _event = await _assert_audited_request(
            client,
            actor,
            "POST",
            "/api/v1/calendar/events",
            expected_action=AuditActionType.CALENDAR_SERIES_CREATED,
            expected_status=201,
            json=_calendar_payload(
                name=f"Recurring {run_id}",
                event_date="2027-09-01",
                recurrence={"frequency": "weekly", "termination": "never"},
            ),
        )
        series_event_id = UUID(series_response.json()["id"])
        calendar_event_ids.append(series_event_id)
        series_id = UUID(series_response.json()["recurrence"]["id"])
        series_update = _calendar_payload(
            name=f"Recurring updated {run_id}",
            event_date="2027-09-01",
            recurrence={"frequency": "weekly", "termination": "never"},
        )
        series_update["version_number"] = 1
        series_update["confirm_exception_removals"] = False
        await _assert_audited_request(
            client,
            actor,
            "PATCH",
            f"/api/v1/calendar/series/{series_id}",
            expected_action=AuditActionType.CALENDAR_SERIES_UPDATED,
            expected_status=200,
            json=series_update,
        )

        occurrence_id = f"{series_id}:2027-09-08"
        occurrence_update = _calendar_payload(
            name=f"Occurrence updated {run_id}",
            event_date="2027-09-08",
        )
        occurrence_update["version_number"] = 2
        occurrence_update["exception_version_number"] = None
        await _assert_audited_request(
            client,
            actor,
            "PATCH",
            f"/api/v1/calendar/instances/{occurrence_id}",
            expected_action=AuditActionType.CALENDAR_OCCURRENCE_UPDATED,
            expected_status=200,
            json=occurrence_update,
        )
        occurrence_move = _calendar_payload(
            name=f"Occurrence moved {run_id}",
            event_date="2027-09-09",
        )
        occurrence_move["version_number"] = 2
        occurrence_move["exception_version_number"] = 1
        await _assert_audited_request(
            client,
            actor,
            "PATCH",
            f"/api/v1/calendar/instances/{occurrence_id}",
            expected_action=AuditActionType.CALENDAR_OCCURRENCE_MOVED,
            expected_status=200,
            json=occurrence_move,
        )
        await _assert_audited_request(
            client,
            actor,
            "DELETE",
            f"/api/v1/calendar/instances/{occurrence_id}",
            expected_action=AuditActionType.CALENDAR_OCCURRENCE_DELETED,
            expected_status=204,
            json={"version_number": 2, "exception_version_number": 2},
        )
        await _assert_audited_request(
            client,
            actor,
            "DELETE",
            f"/api/v1/calendar/series/{series_id}",
            expected_action=AuditActionType.CALENDAR_SERIES_DELETED,
            expected_status=204,
            json={"version_number": 2},
        )
        calendar_event_ids.remove(series_event_id)
        assert "user_disablement" not in {
            event.action_type for event in await _actor_events(actor.id)
        }
    finally:
        async with AsyncSessionFactory() as cleanup_session:
            cleanup_player_ids = list(
                (
                    await cleanup_session.scalars(
                        select(Player.id).where(Player.first_name.contains(run_id))
                    )
                ).all()
            )
            cleanup_team_ids = list(
                (
                    await cleanup_session.scalars(
                        select(Team.id).where(Team.name.contains(run_id))
                    )
                ).all()
            )
            cleanup_coach_ids = list(
                (
                    await cleanup_session.scalars(
                        select(User.id).where(User.email.contains(run_id))
                    )
                ).all()
            )
            cleanup_calendar_ids = list(
                (
                    await cleanup_session.scalars(
                        select(CalendarEvent.id).where(
                            CalendarEvent.name.contains(run_id)
                        )
                    )
                ).all()
            )
            await cleanup_session.execute(
                delete(BusinessAuditEvent).where(
                    BusinessAuditEvent.actor_user_id == actor.id
                )
            )
            if cleanup_coach_ids:
                await cleanup_session.execute(
                    delete(AuthAuditLog).where(
                        AuthAuditLog.user_id.in_(cleanup_coach_ids)
                    )
                )
                await cleanup_session.execute(
                    delete(TeamCoach).where(TeamCoach.user_id.in_(cleanup_coach_ids))
                )
                await cleanup_session.execute(
                    delete(User).where(User.id.in_(cleanup_coach_ids))
                )
            if cleanup_calendar_ids:
                await cleanup_session.execute(
                    delete(CalendarEvent).where(
                        CalendarEvent.id.in_(cleanup_calendar_ids)
                    )
                )
            if cleanup_team_ids:
                await cleanup_session.execute(
                    delete(TeamCoach).where(TeamCoach.team_id.in_(cleanup_team_ids))
                )
                await cleanup_session.execute(
                    delete(TeamPlayer).where(TeamPlayer.team_id.in_(cleanup_team_ids))
                )
                await cleanup_session.execute(
                    delete(Team).where(Team.id.in_(cleanup_team_ids))
                )
            if cleanup_player_ids:
                for cleanup_player_id in cleanup_player_ids:
                    await cleanup_session.execute(
                        delete(DataSyncLog).where(
                            DataSyncLog.error_message.contains(str(cleanup_player_id))
                        )
                    )
                await cleanup_session.execute(
                    delete(Player).where(Player.id.in_(cleanup_player_ids))
                )
            await cleanup_session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_persistence_failure_rolls_back_domain_mutation(
    business_audit_client: tuple[httpx.AsyncClient, User],
    mocker,
) -> None:
    """Propagate writer failure so neither the player nor event commits."""

    client, actor = business_audit_client
    run_id = uuid4().hex[:8]
    payload = _player_payload(run_id, 0)
    mocker.patch(
        "src.services.player_service.BusinessAuditService.record",
        new=AsyncMock(side_effect=RuntimeError("simulated audit persistence")),
    )

    response = await client.post("/api/v1/players", json=payload)

    assert response.status_code == 500
    async with AsyncSessionFactory() as verification_session:
        player = await verification_session.scalar(
            select(Player).where(
                Player.first_name == payload["first_name"],
                Player.last_name == payload["last_name"],
            )
        )
        event_count = await verification_session.scalar(
            select(BusinessAuditEvent).where(
                BusinessAuditEvent.actor_user_id == actor.id,
                BusinessAuditEvent.action_type == AuditActionType.PLAYER_CREATED.value,
            )
        )
    assert player is None
    assert event_count is None


@pytest.mark.asyncio(loop_scope="session")
async def test_calendar_audit_failure_rolls_back_calendar_mutation(
    business_audit_client: tuple[httpx.AsyncClient, User],
    mocker,
) -> None:
    """Keep calendar domain state atomic with a failed business-audit flush."""

    client, actor = business_audit_client
    run_id = uuid4().hex[:8]
    event_name = f"Failed calendar audit {run_id}"
    mocker.patch(
        "src.services.calendar_service.BusinessAuditService.record",
        new=AsyncMock(side_effect=RuntimeError("simulated calendar audit failure")),
    )

    response = await client.post(
        "/api/v1/calendar/events",
        json=_calendar_payload(name=event_name, event_date="2027-10-01"),
    )

    assert response.status_code == 500
    async with AsyncSessionFactory() as verification_session:
        calendar_event = await verification_session.scalar(
            select(CalendarEvent).where(CalendarEvent.name == event_name)
        )
        audit_event = await verification_session.scalar(
            select(BusinessAuditEvent).where(
                BusinessAuditEvent.actor_user_id == actor.id,
                BusinessAuditEvent.target_label == event_name,
            )
        )
    assert calendar_event is None
    assert audit_event is None
