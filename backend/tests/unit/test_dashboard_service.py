"""Unit coverage for role scope and dashboard section selection."""

from datetime import UTC, date, datetime, time
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import AgeGroup, EventType, MatchFormat, ScopeKind, UserRole
from src.models.match import Match
from src.models.player import Player
from src.models.team import Team
from src.models.user import User
from src.schemas.calendar import CalendarEventInstance, CalendarRangeResponse
from src.schemas.dashboard import (
    DashboardActivePlayerCount,
    DashboardRecentActivity,
)
from src.services.dashboard_service import (
    DashboardCalendarProjection,
    DashboardScope,
    DashboardService,
)

NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


def make_user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        first_name="Asha",
        last_name="Account",
        email=f"{uuid4().hex}@example.com",
        hashed_password="hash",
        role=role,
        is_active=True,
        version_number=1,
    )


def make_team(name: str, age_group: AgeGroup = AgeGroup.U15) -> Team:
    return Team(id=uuid4(), name=name, age_group=age_group, version_number=1)


def make_event(
    occurrence_id: str,
    event_date: date,
    *,
    event_type: EventType = EventType.PRACTICE,
    age_groups: list[AgeGroup] | None = None,
    scope_kind: ScopeKind = ScopeKind.AGE_GROUP,
) -> CalendarEventInstance:
    return CalendarEventInstance(
        occurrence_id=occurrence_id,
        event_id=uuid4(),
        series_id=None,
        original_date=event_date,
        event_date=event_date,
        event_type=event_type,
        name=f"{occurrence_id} event",
        is_all_day=False,
        start_time=time(17),
        end_time=time(18, 30),
        scope_kind=scope_kind,
        age_groups=age_groups or [],
        is_recurring=False,
        recurrence_summary=None,
        event_version_number=1,
        exception_id=None,
        exception_version_number=None,
    )


def scalar_result(*values: object) -> Mock:
    result = Mock()
    result.all.return_value = list(values)
    return result


@pytest.mark.asyncio
async def test_scope_is_derived_for_head_coach_and_assistant_coach() -> None:
    team = make_team("U15 Falcons")
    session = Mock()
    session.scalars = AsyncMock(return_value=scalar_result(team))
    service = DashboardService(session, now=NOW)

    head_scope = await service._resolve_scope(make_user(UserRole.HEAD_COACH))
    assistant = make_user(UserRole.ASSISTANT_COACH)
    assistant_scope = await service._resolve_scope(assistant)

    assert head_scope.role is UserRole.HEAD_COACH
    assert head_scope.team_ids == (team.id,)
    assert assistant_scope.role is UserRole.ASSISTANT_COACH
    assert assistant_scope.team_ids == (team.id,)
    assistant_statement = session.scalars.await_args_list[1].args[0]
    assert "team_coaches.user_id" in str(assistant_statement)


@pytest.mark.asyncio
async def test_player_scope_uses_only_explicit_profile_memberships() -> None:
    user = make_user(UserRole.PLAYER)
    player = Player(id=uuid4(), user_id=user.id, is_active=True)
    team = make_team("U13 Falcons", AgeGroup.U13)
    session = Mock()
    session.scalar = AsyncMock(return_value=player)
    session.scalars = AsyncMock(return_value=scalar_result(team))

    scope = await DashboardService(session, now=NOW)._resolve_scope(user)

    assert scope.linked_player_id == player.id
    assert scope.team_ids == (team.id,)
    assert scope.age_groups == frozenset({AgeGroup.U13})


@pytest.mark.asyncio
async def test_unlinked_player_gets_no_academy_fallback() -> None:
    user = make_user(UserRole.PLAYER)
    session = Mock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock()

    response = await DashboardService(session, now=NOW).get_dashboard(user)

    assert response.dashboard_state == "unlinked"
    assert response.summary.training.status == "unlinked"
    assert response.summary.next_match.status == "unlinked"
    assert response.summary.player_slot.status == "unlinked"
    assert response.upcoming_events.status == "unlinked"
    assert response.context.status == "unlinked"
    assert "Head Coach" in response.context.message
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_projection_filters_deduplicates_and_orders(mocker) -> None:
    team = make_team("U15 Falcons")
    scope = DashboardScope(
        role=UserRole.ASSISTANT_COACH,
        teams=(team,),
        linked_player_id=None,
    )
    all_academy = make_event(
        "all-academy",
        date(2026, 8, 11),
        scope_kind=ScopeKind.ALL_ACADEMY,
    )
    relevant = make_event("relevant", date(2026, 8, 12), age_groups=[AgeGroup.U15])
    unrelated = make_event("unrelated", date(2026, 8, 10), age_groups=[AgeGroup.J])
    calendar = mocker.Mock()
    calendar.get_range = AsyncMock(
        return_value=CalendarRangeResponse(
            academy_today=date(2026, 8, 10),
            start_date=date(2026, 8, 10),
            end_date=date(2026, 9, 23),
            events=[relevant, all_academy, relevant, unrelated],
        )
    )
    mocker.patch(
        "src.services.dashboard_service.CalendarService",
        return_value=calendar,
    )

    projection = await DashboardService(Mock(), now=NOW)._load_calendar_projection(
        scope
    )

    assert [event.occurrence_id for event in projection.events] == [
        "all-academy",
        "relevant",
    ]
    calendar.get_range.assert_awaited_once_with(
        date(2026, 8, 10), date(2026, 9, 23)
    )


@pytest.mark.asyncio
async def test_summary_selects_nearest_training_and_keeps_partial_failures(
    mocker,
) -> None:
    team = make_team("U15 Falcons")
    scope = DashboardScope(
        role=UserRole.HEAD_COACH,
        teams=(team,),
        linked_player_id=None,
    )
    event = make_event("nearest", date(2026, 8, 11), age_groups=[AgeGroup.U15])
    projection = DashboardCalendarProjection(instances=(event,))
    service = DashboardService(Mock(), now=NOW)
    mocker.patch.object(service, "_resolve_scope", AsyncMock(return_value=scope))
    mocker.patch.object(
        service,
        "_load_calendar_projection",
        AsyncMock(return_value=projection),
    )
    mocker.patch.object(
        service,
        "_load_next_match",
        AsyncMock(side_effect=RuntimeError("match database unavailable")),
    )
    mocker.patch.object(
        service,
        "_load_player_slot",
        AsyncMock(return_value=DashboardActivePlayerCount(count=9, team_count=1)),
    )
    mocker.patch.object(
        service,
        "_load_context",
        AsyncMock(return_value=DashboardRecentActivity(events=[])),
    )

    response = await service.get_dashboard(make_user(UserRole.HEAD_COACH))

    assert response.summary.training.status == "ready"
    assert response.summary.training.data.occurrence_id == "nearest"
    assert response.summary.next_match.status == "unavailable"
    assert response.summary.player_slot.status == "ready"
    assert response.upcoming_events.status == "ready"


@pytest.mark.asyncio
async def test_internal_match_uses_one_or_predicate_and_one_result() -> None:
    home = make_team("U13 Falcons", AgeGroup.U13)
    away = make_team("U15 Falcons", AgeGroup.U15)
    timestamp = datetime(2026, 8, 1, tzinfo=UTC)
    match = Match(
        id=uuid4(),
        match_date=date(2026, 8, 12),
        format=MatchFormat.T20,
        participant_type="internal",
        home_team_id=home.id,
        away_team_id=away.id,
        external_opponent_name=None,
        venue="Academy Ground",
        result="Scheduled",
        created_at=timestamp,
        updated_at=timestamp,
        version_number=1,
        home_team=home,
        away_team=away,
    )
    session = Mock()
    session.scalar = AsyncMock(return_value=match)
    scope = DashboardScope(
        role=UserRole.PLAYER,
        teams=(home, away),
        linked_player_id=uuid4(),
    )

    result = await DashboardService(session, now=NOW)._load_next_match(
        scope, date(2026, 8, 10)
    )

    assert result is not None
    assert result.id == match.id
    assert result.participants.kind == "internal"
    statement = session.scalar.await_args.args[0]
    statement_text = str(statement)
    assert "matches.home_team_id IN" in statement_text
    assert " OR matches.away_team_id IN" in statement_text
    assert "ORDER BY matches.match_date, matches.id" in statement_text
