"""Executable role-aware dashboard quickstart validation."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import (
    AuditActionCategory,
    AuditActionType,
    AuditEntityType,
    BattingStyle,
    BowlingStyle,
    PlayerType,
    UserRole,
)
from src.main import app
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.calendar import CalendarEvent, CalendarEventScope
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.services.password_service import PasswordService

ACADEMY_TZ = ZoneInfo("America/Los_Angeles")


def _account(role: UserRole, label: str, password: str) -> User:
    return User(
        id=uuid4(),
        first_name=label,
        last_name="Quickstart",
        email=f"011-{label.lower()}-{uuid4().hex}@example.com",
        hashed_password=PasswordService.hash_password(password),
        role=role,
        is_active=True,
        version_number=1,
    )


def _player(label: str, *, user_id=None) -> Player:
    return Player(
        id=uuid4(),
        user_id=user_id,
        first_name=label,
        last_name="Player",
        date_of_birth=date(2010, 1, 1),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=True,
        version_number=1,
    )


async def _login(
    client: httpx.AsyncClient, user: User, password: str
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _business_audit_count(*, target_id=None) -> int:
    async with AsyncSessionFactory() as session:
        statement = select(func.count(BusinessAuditEvent.id))
        if target_id is not None:
            statement = statement.where(
                BusinessAuditEvent.target_entity_id == target_id
            )
        return int(await session.scalar(statement) or 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_role_aware_dashboard_quickstart_flow(
    role_aware_dashboard_query_counter,
    role_aware_dashboard_query_count_assertion,
) -> None:
    """Validate role scope, participants, account audit, and session security."""

    password = "RoleAwareQuickstart-P@ssword1"
    today = datetime.now(ACADEMY_TZ).date()
    head_coach = _account(UserRole.HEAD_COACH, "Head", password)
    assistant = _account(UserRole.ASSISTANT_COACH, "Assistant", password)
    linked_account = _account(UserRole.PLAYER, "Linked", password)
    unlinked_account = _account(UserRole.PLAYER, "Unlinked", password)
    first_link_target = _account(UserRole.PLAYER, "FirstTarget", password)
    replacement_target = _account(UserRole.PLAYER, "Replacement", password)

    u15 = Team(id=uuid4(), name="011 U15 Falcons", age_group="U15")
    u13 = Team(id=uuid4(), name="011 U13 Falcons", age_group="U13")
    junior = Team(id=uuid4(), name="011 Junior Falcons", age_group="J")
    linked_player = _player("Linked", user_id=linked_account.id)
    association_player = _player("Association")
    roster_player = _player("Roster")

    calendar_records: list[object] = []
    for offset in range(6):
        event = CalendarEvent(
            id=uuid4(),
            event_type="practice",
            name=f"011 U15 Practice {offset + 1}",
            first_date=today + timedelta(days=offset),
            is_all_day=False,
            start_time=time(17),
            end_time=time(18, 30),
            version_number=1,
        )
        calendar_records.extend(
            [
                event,
                CalendarEventScope(
                    id=uuid4(),
                    event_id=event.id,
                    scope_kind="age_group",
                    age_group="U15",
                ),
            ]
        )
    academy_event = CalendarEvent(
        id=uuid4(),
        event_type="miscellaneous",
        name="011 Academy Briefing",
        first_date=today,
        is_all_day=True,
        start_time=None,
        end_time=None,
        version_number=1,
    )
    junior_event = CalendarEvent(
        id=uuid4(),
        event_type="practice",
        name="011 Junior Restricted Practice",
        first_date=today,
        is_all_day=False,
        start_time=time(15),
        end_time=time(16),
        version_number=1,
    )
    calendar_records.extend(
        [
            academy_event,
            CalendarEventScope(
                id=uuid4(),
                event_id=academy_event.id,
                scope_kind="all_academy",
                age_group=None,
            ),
            junior_event,
            CalendarEventScope(
                id=uuid4(),
                event_id=junior_event.id,
                scope_kind="age_group",
                age_group="J",
            ),
        ]
    )

    async with AsyncSessionFactory() as session:
        session.add_all(
            [
                head_coach,
                assistant,
                linked_account,
                unlinked_account,
                first_link_target,
                replacement_target,
                u15,
                u13,
                junior,
                linked_player,
                association_player,
                roster_player,
            ]
        )
        await session.flush()
        session.add_all(
            [
                TeamCoach(team_id=u15.id, user_id=assistant.id),
                TeamPlayer(
                    team_id=u15.id,
                    player_id=linked_player.id,
                    roster_order=1,
                ),
                TeamPlayer(
                    team_id=u13.id,
                    player_id=linked_player.id,
                    roster_order=1,
                ),
                TeamPlayer(
                    team_id=u15.id,
                    player_id=roster_player.id,
                    roster_order=2,
                ),
                *calendar_records,
            ]
        )
        for index in range(5):
            session.add(
                BusinessAuditEvent(
                    id=uuid4(),
                    actor_user_id=head_coach.id,
                    actor_display_name="Head Quickstart",
                    actor_role=UserRole.HEAD_COACH.value,
                    action_type=AuditActionType.PLAYER_CREATED.value,
                    action_category=AuditActionCategory.PLAYER.value,
                    target_entity_type=AuditEntityType.PLAYER.value,
                    target_entity_id=roster_player.id,
                    target_label=f"011 Activity {index}",
                    summary=f"011 activity {index}",
                    event_metadata={},
                    created_at=datetime.now(UTC) + timedelta(minutes=index),
                    request_id=f"quickstart-seed-{index}",
                )
            )
        await session.commit()

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        head_headers = await _login(client, head_coach, password)
        assistant_headers = await _login(client, assistant, password)
        linked_headers = await _login(client, linked_account, password)
        unlinked_headers = await _login(client, unlinked_account, password)

        external = await client.post(
            "/api/v1/matches",
            headers=head_headers,
            json={
                "match_date": (today + timedelta(days=1)).isoformat(),
                "format": "T20",
                "venue": "011 Academy Ground",
                "result": "Scheduled",
                "participants": {
                    "participant_type": "external",
                    "academy_team_id": str(u15.id),
                    "external_opponent_name": "011 Northside CC",
                    "academy_side": "home",
                },
            },
        )
        assert external.status_code == 201, external.text
        assert external.json()["participants"]["kind"] == "external"

        internal = await client.post(
            "/api/v1/matches",
            headers=head_headers,
            json={
                "match_date": (today + timedelta(days=2)).isoformat(),
                "format": "T20",
                "venue": "011 Academy Ground",
                "result": "Scheduled",
                "participants": {
                    "participant_type": "internal",
                    "home_team_id": str(u15.id),
                    "away_team_id": str(u13.id),
                },
            },
        )
        assert internal.status_code == 201, internal.text
        assert internal.json()["participants"]["kind"] == "internal"

        audits_before_invalid_match = await _business_audit_count()
        invalid_match = await client.post(
            "/api/v1/matches",
            headers=head_headers,
            json={
                "match_date": today.isoformat(),
                "format": "T20",
                "venue": "011 Academy Ground",
                "result": "Scheduled",
                "participants": {
                    "participant_type": "internal",
                    "home_team_id": str(u15.id),
                    "away_team_id": str(u15.id),
                    "external_opponent_name": "Mixed shape",
                },
            },
        )
        assert invalid_match.status_code == 422
        assert await _business_audit_count() == audits_before_invalid_match

        matches = await client.get("/api/v1/matches", headers=linked_headers)
        assert matches.status_code == 200
        internal_rows = [
            item for item in matches.json() if item["id"] == internal.json()["id"]
        ]
        assert len(internal_rows) == 1

        audits_before_reads = await _business_audit_count()
        head_dashboard = await client.get("/api/v1/dashboard", headers=head_headers)
        with role_aware_dashboard_query_counter.count() as query_counter:
            assistant_dashboard = await client.get(
                "/api/v1/dashboard", headers=assistant_headers
            )
        linked_dashboard = await client.get("/api/v1/dashboard", headers=linked_headers)
        unlinked_dashboard = await client.get(
            "/api/v1/dashboard", headers=unlinked_headers
        )
        for response in (
            head_dashboard,
            assistant_dashboard,
            linked_dashboard,
            unlinked_dashboard,
        ):
            assert response.status_code == 200, response.text
        role_aware_dashboard_query_count_assertion(query_counter, 15)
        assert len(head_dashboard.json()["context"]["data"]["events"]) == 4
        assert len(head_dashboard.json()["upcoming_events"]["data"]) == 5
        assert assistant_dashboard.json()["context"]["data"]["teams"][0]["id"] == str(
            u15.id
        )
        assistant_names = {
            item["name"]
            for item in assistant_dashboard.json()["upcoming_events"]["data"]
        }
        assert "011 Academy Briefing" in assistant_names
        assert "011 Junior Restricted Practice" not in assistant_names
        assert (
            linked_dashboard.json()["summary"]["player_slot"]["data"]["team_count"] == 2
        )
        assert (
            linked_dashboard.json()["summary"]["next_match"]["data"]["id"]
            == external.json()["id"]
        )
        assert unlinked_dashboard.json()["dashboard_state"] == "unlinked"
        assert unlinked_dashboard.json()["upcoming_events"]["status"] == "unlinked"
        assert await _business_audit_count() == audits_before_reads

        forbidden = await client.get(
            "/api/v1/players/account-linking/users",
            headers=assistant_headers,
        )
        assert forbidden.status_code == 403
        assert await _business_audit_count(target_id=association_player.id) == 0

        link = await client.put(
            f"/api/v1/players/{association_player.id}/account",
            headers={**head_headers, "X-Request-ID": "quickstart-link"},
            json={
                "user_id": str(first_link_target.id),
                "version_number": 1,
            },
        )
        assert link.status_code == 200, link.text
        reassign = await client.post(
            f"/api/v1/players/{association_player.id}/account/reassign",
            headers={**head_headers, "X-Request-ID": "quickstart-reassign"},
            json={
                "expected_user_id": str(first_link_target.id),
                "new_user_id": str(replacement_target.id),
                "version_number": link.json()["player_version_number"],
            },
        )
        assert reassign.status_code == 200, reassign.text
        unlink = await client.request(
            "DELETE",
            f"/api/v1/players/{association_player.id}/account",
            headers={**head_headers, "X-Request-ID": "quickstart-unlink"},
            json={"version_number": reassign.json()["player_version_number"]},
        )
        assert unlink.status_code == 200, unlink.text
        assert unlink.json()["account"] is None

        stale = await client.put(
            f"/api/v1/players/{association_player.id}/account",
            headers=head_headers,
            json={
                "user_id": str(first_link_target.id),
                "version_number": 1,
            },
        )
        assert stale.status_code == 409
        assert await _business_audit_count(target_id=association_player.id) == 3

        me_before = await client.get("/api/v1/auth/me", headers=linked_headers)
        assert me_before.status_code == 200
        old_session_id = me_before.json()["session"]["session_id"]
        deactivate = await client.put(
            f"/api/v1/players/{linked_player.id}",
            headers=head_headers,
            json={"is_active": False, "version_number": 1},
        )
        assert deactivate.status_code == 200, deactivate.text
        assert (
            await client.get("/api/v1/dashboard", headers=linked_headers)
        ).status_code == 401
        rejected_login = await client.post(
            "/api/v1/auth/login",
            json={"email": linked_account.email, "password": password},
        )
        assert rejected_login.status_code == 401

        async with AsyncSessionFactory() as session:
            old_session = await session.get(AuthSession, old_session_id)
            assert old_session is not None
            assert old_session.revoked_at is not None
            assert old_session.revocation_reason == "linked_player_inactive"

        reactivate = await client.put(
            f"/api/v1/players/{linked_player.id}",
            headers=head_headers,
            json={
                "is_active": True,
                "version_number": deactivate.json()["version_number"],
            },
        )
        assert reactivate.status_code == 200, reactivate.text
        new_linked_headers = await _login(client, linked_account, password)
        assert (
            await client.get("/api/v1/dashboard", headers=new_linked_headers)
        ).status_code == 200
        assert (
            await client.get("/api/v1/dashboard", headers=linked_headers)
        ).status_code == 401

    async with AsyncSessionFactory() as session:
        events = list(
            (
                await session.scalars(
                    select(BusinessAuditEvent)
                    .where(BusinessAuditEvent.target_entity_id == association_player.id)
                    .order_by(BusinessAuditEvent.created_at)
                )
            ).all()
        )
    assert [event.action_type for event in events] == [
        AuditActionType.PLAYER_ACCOUNT_LINKED.value,
        AuditActionType.PLAYER_ACCOUNT_REASSIGNED.value,
        AuditActionType.PLAYER_ACCOUNT_UNLINKED.value,
    ]
    assert [event.request_id for event in events] == [
        "quickstart-link",
        "quickstart-reassign",
        "quickstart-unlink",
    ]
