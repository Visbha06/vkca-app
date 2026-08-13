"""Database-backed coverage for the bounded role-aware dashboard projection."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import (
    AuditActionCategory,
    AuditActionType,
    AuditEntityType,
    MatchParticipantType,
    UserRole,
)
from src.models.business_audit_event import BusinessAuditEvent
from src.models.calendar import (
    CalendarEvent,
    CalendarEventScope,
    OccurrenceException,
    OccurrenceExceptionScope,
    RecurrenceSeries,
)
from src.models.match import Match
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.services.dashboard_service import DashboardService
from tests.data_quality_builders import build_quality_player

REFERENCE_NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)
REFERENCE_DATE = date(2026, 8, 10)


def account(role: UserRole, label: str) -> User:
    return User(
        id=uuid4(),
        first_name=label,
        last_name="Account",
        email=f"dashboard-{label.lower()}-{uuid4().hex}@example.com",
        hashed_password="dashboard-test-hash",
        role=role,
        is_active=True,
        version_number=1,
    )


def event(
    name: str,
    event_date: date,
    *,
    age_group: str | None,
    start_hour: int = 17,
) -> tuple[CalendarEvent, CalendarEventScope]:
    calendar_event = CalendarEvent(
        id=uuid4(),
        event_type="practice",
        name=name,
        first_date=event_date,
        is_all_day=False,
        start_time=time(start_hour),
        end_time=time(start_hour + 1),
        version_number=1,
    )
    scope = CalendarEventScope(
        id=uuid4(),
        event_id=calendar_event.id,
        scope_kind="all_academy" if age_group is None else "age_group",
        age_group=age_group,
    )
    return calendar_event, scope


@pytest.mark.asyncio
async def test_projection_reuses_effective_calendar_scope_and_stays_bounded(
    role_aware_dashboard_query_counter,
    role_aware_dashboard_query_count_assertion,
) -> None:
    head_coach = account(UserRole.HEAD_COACH, "Head")
    assistant = account(UserRole.ASSISTANT_COACH, "Assistant")
    player_account = account(UserRole.PLAYER, "Player")
    unlinked_account = account(UserRole.PLAYER, "Unlinked")
    u15 = Team(id=uuid4(), name="U15 Falcons", age_group="U15", version_number=1)
    u13 = Team(id=uuid4(), name="U13 Falcons", age_group="U13", version_number=1)
    junior = Team(id=uuid4(), name="Junior Falcons", age_group="J", version_number=1)
    additional_teams = [
        Team(
            id=uuid4(),
            name=f"Z Extra Team {index:02d}",
            age_group="U15",
            version_number=1,
        )
        for index in range(13)
    ]
    linked_player = build_quality_player(
        first_name="Linked", date_of_birth=date(2012, 1, 1)
    )
    linked_player.user_id = player_account.id
    u15_player = build_quality_player(first_name="U15", date_of_birth=date(2011, 1, 1))
    u13_player = build_quality_player(first_name="U13", date_of_birth=date(2010, 1, 1))
    inactive_player = build_quality_player(
        first_name="Inactive",
        date_of_birth=date(2009, 1, 1),
        is_active=False,
    )

    recurring_event, recurring_scope = event(
        "Weekly U15 practice", REFERENCE_DATE, age_group="U15"
    )
    series = RecurrenceSeries(
        id=uuid4(),
        event_id=recurring_event.id,
        frequency="weekly",
        weekday=REFERENCE_DATE.weekday(),
        month=None,
        month_day=None,
        termination="occurrence_count",
        end_date=None,
        occurrence_count=4,
    )
    moved = OccurrenceException(
        id=uuid4(),
        series_id=series.id,
        original_date=REFERENCE_DATE + timedelta(days=7),
        replacement_date=REFERENCE_DATE + timedelta(days=1),
        event_type="practice",
        name="Moved U15 practice",
        is_all_day=False,
        start_time=time(18),
        end_time=time(19),
        is_deleted=False,
        version_number=1,
    )
    moved_scope = OccurrenceExceptionScope(
        id=uuid4(),
        exception_id=moved.id,
        scope_kind="age_group",
        age_group="U15",
    )
    deleted = OccurrenceException(
        id=uuid4(),
        series_id=series.id,
        original_date=REFERENCE_DATE + timedelta(days=14),
        replacement_date=None,
        event_type=None,
        name=None,
        is_all_day=None,
        start_time=None,
        end_time=None,
        is_deleted=True,
        version_number=1,
    )
    all_academy, all_academy_scope = event(
        "Academy briefing", REFERENCE_DATE, age_group=None, start_hour=16
    )
    unrelated, unrelated_scope = event(
        "Junior-only practice", REFERENCE_DATE, age_group="J", start_hour=15
    )
    extra_events = [
        event(
            f"Extra U15 practice {offset}",
            REFERENCE_DATE + timedelta(days=offset),
            age_group="U15",
        )
        for offset in (2, 3, 4)
    ]

    unrelated_match = Match(
        id=uuid4(),
        match_date=REFERENCE_DATE + timedelta(days=1),
        format="T20",
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=junior.id,
        away_team_id=None,
        external_opponent_name="Junior Rivals",
        venue="Junior Ground",
        result="Scheduled",
        version_number=1,
    )
    internal_match = Match(
        id=uuid4(),
        match_date=REFERENCE_DATE + timedelta(days=2),
        format="T20",
        participant_type=MatchParticipantType.INTERNAL,
        home_team_id=u15.id,
        away_team_id=u13.id,
        external_opponent_name=None,
        venue="Academy Ground",
        result="Scheduled",
        version_number=1,
    )
    later_match = Match(
        id=uuid4(),
        match_date=REFERENCE_DATE + timedelta(days=3),
        format="one-day",
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=u15.id,
        away_team_id=None,
        external_opponent_name="Northside CC",
        venue="Academy Ground",
        result="Scheduled",
        version_number=1,
    )
    audits = [
        BusinessAuditEvent(
            id=uuid4(),
            actor_user_id=head_coach.id,
            actor_display_name="Head Account",
            actor_role=UserRole.HEAD_COACH.value,
            action_type=AuditActionType.PLAYER_CREATED.value,
            action_category=AuditActionCategory.PLAYER.value,
            target_entity_type=AuditEntityType.PLAYER.value,
            target_entity_id=linked_player.id,
            target_label=f"Player {index}",
            summary=f"Added Player {index}",
            event_metadata={},
            created_at=REFERENCE_NOW + timedelta(minutes=index),
            request_id=None,
        )
        for index in range(6)
    ]

    async with AsyncSessionFactory() as session:
        session.add_all(
            [
                head_coach,
                assistant,
                player_account,
                unlinked_account,
                u15,
                u13,
                junior,
                *additional_teams,
                linked_player,
                u15_player,
                u13_player,
                inactive_player,
            ]
        )
        await session.flush()
        session.add_all(
            [
                TeamCoach(team_id=u15.id, user_id=assistant.id, version_number=1),
                *(
                    TeamCoach(
                        team_id=team.id,
                        user_id=assistant.id,
                        version_number=1,
                    )
                    for team in additional_teams
                ),
                TeamPlayer(team_id=u15.id, player_id=linked_player.id, roster_order=1),
                TeamPlayer(team_id=u13.id, player_id=linked_player.id, roster_order=1),
                TeamPlayer(team_id=u15.id, player_id=u15_player.id, roster_order=2),
                TeamPlayer(team_id=u13.id, player_id=u13_player.id, roster_order=2),
                TeamPlayer(
                    team_id=u15.id,
                    player_id=inactive_player.id,
                    roster_order=3,
                ),
                recurring_event,
                recurring_scope,
                series,
                moved,
                moved_scope,
                deleted,
                all_academy,
                all_academy_scope,
                unrelated,
                unrelated_scope,
                internal_match,
                unrelated_match,
                later_match,
                *audits,
                *(item for pair in extra_events for item in pair),
            ]
        )
        await session.flush()

        service = DashboardService(session, now=REFERENCE_NOW)
        head = await service.get_dashboard(head_coach)
        with role_aware_dashboard_query_counter.count() as counter:
            assistant_dashboard = await service.get_dashboard(assistant)
        player = await service.get_dashboard(player_account)
        unlinked = await service.get_dashboard(unlinked_account)

        role_aware_dashboard_query_count_assertion(counter, 12)
        assert len(head.upcoming_events.data) == 5
        assert len(head.context.data.events) == 4
        assert len(assistant_dashboard.context.data.teams) == 12
        assert assistant_dashboard.summary.next_match.data.id == internal_match.id
        assert player.summary.next_match.data.id == internal_match.id
        assert player.summary.next_match.data.participants.kind == "internal"
        assert assistant_dashboard.summary.player_slot.data.count == 2
        assert player.summary.player_slot.data.team_count == 2
        assert {team.name for team in player.context.data.teams} == {
            "U13 Falcons",
            "U15 Falcons",
        }

        assistant_events = assistant_dashboard.upcoming_events.data
        assert len(assistant_events) == 5
        assert all("Junior-only" not in item.name for item in assistant_events)
        moved_occurrence_id = f"{series.id}:{moved.original_date.isoformat()}"
        moved_event = next(
            item
            for item in assistant_events
            if item.occurrence_id == moved_occurrence_id
        )
        assert moved_event.event_date == moved.replacement_date
        deleted_occurrence_id = f"{series.id}:{deleted.original_date.isoformat()}"
        assert all(
            item.occurrence_id != deleted_occurrence_id
            for item in assistant_events
        )
        assert unlinked.dashboard_state == "unlinked"
        assert unlinked.upcoming_events.status == "unlinked"

        audit_count = await session.scalar(select(func.count(BusinessAuditEvent.id)))
        await service.get_dashboard(head_coach)
        assert (
            await session.scalar(select(func.count(BusinessAuditEvent.id)))
            == audit_count
        )
