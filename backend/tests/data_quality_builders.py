"""Isolated model and session builders for Data Quality tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, time
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import (
    BattingStyle,
    BowlingStyle,
    EventType,
    PlayerType,
    RecurrenceFrequency,
    RecurrenceTermination,
    UserRole,
)
from src.models.calendar import (
    CalendarEvent,
    OccurrenceException,
    RecurrenceSeries,
)
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User

QUALITY_REFERENCE_DATE = date(2026, 8, 1)


def build_quality_player(
    *,
    player_id: UUID | None = None,
    first_name: str = "Asha",
    last_name: str | None = None,
    date_of_birth: date = date(2013, 1, 15),
    is_active: bool = True,
) -> Player:
    """Build one complete player without persisting it."""

    resolved_id = player_id or uuid4()
    return Player(
        id=resolved_id,
        first_name=first_name,
        last_name=last_name or f"Player-{resolved_id.hex[:8]}",
        date_of_birth=date_of_birth,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=is_active,
        version_number=1,
    )


def build_quality_team(
    *,
    team_id: UUID | None = None,
    name: str | None = None,
    age_group: str = "U13",
    version_number: int = 1,
) -> Team:
    """Build one complete team without roster or coach side effects."""

    resolved_id = team_id or uuid4()
    return Team(
        id=resolved_id,
        name=name or f"Quality Team {resolved_id.hex[:8]}",
        age_group=age_group,
        version_number=version_number,
    )


def build_quality_roster_membership(
    *,
    team: Team | None = None,
    player: Player | None = None,
    team_id: UUID | None = None,
    player_id: UUID | None = None,
    roster_order: int = 1,
) -> TeamPlayer:
    """Build one exact roster relationship with a chosen persisted position."""

    resolved_team_id = team.id if team is not None else team_id
    resolved_player_id = player.id if player is not None else player_id
    if resolved_team_id is None or resolved_player_id is None:
        raise ValueError("team/team_id and player/player_id are required")
    return TeamPlayer(
        team_id=resolved_team_id,
        player_id=resolved_player_id,
        roster_order=roster_order,
        version_number=1,
    )


def build_quality_coach(
    *,
    coach_id: UUID | None = None,
    first_name: str = "Alex",
    last_name: str | None = None,
    role: UserRole = UserRole.ASSISTANT_COACH,
    is_active: bool = True,
    version_number: int = 1,
) -> User:
    """Build one coach/account record, including invalid-role test accounts."""

    resolved_id = coach_id or uuid4()
    resolved_last_name = last_name or f"Coach-{resolved_id.hex[:8]}"
    return User(
        id=resolved_id,
        first_name=first_name,
        last_name=resolved_last_name,
        email=f"quality-{resolved_id.hex}@example.com",
        hashed_password="$argon2id$quality-test-placeholder",
        role=role,
        is_active=is_active,
        version_number=version_number,
    )


def build_quality_coach_assignment(
    *,
    team: Team | None = None,
    coach: User | None = None,
    team_id: UUID | None = None,
    coach_id: UUID | None = None,
) -> TeamCoach:
    """Build one exact team/account coach assignment."""

    resolved_team_id = team.id if team is not None else team_id
    resolved_coach_id = coach.id if coach is not None else coach_id
    if resolved_team_id is None or resolved_coach_id is None:
        raise ValueError("team/team_id and coach/coach_id are required")
    return TeamCoach(
        team_id=resolved_team_id,
        user_id=resolved_coach_id,
        version_number=1,
    )


def build_quality_calendar_event(
    *,
    event_id: UUID | None = None,
    name: str | None = None,
    first_date: date = QUALITY_REFERENCE_DATE,
) -> CalendarEvent:
    """Build the owning event for one recurrence series."""

    resolved_id = event_id or uuid4()
    return CalendarEvent(
        id=resolved_id,
        event_type=EventType.PRACTICE,
        name=name or f"Quality Practice {resolved_id.hex[:8]}",
        first_date=first_date,
        is_all_day=False,
        start_time=time(17, 0),
        end_time=time(18, 30),
        version_number=1,
    )


def build_quality_calendar_series(
    *,
    series_id: UUID | None = None,
    event: CalendarEvent | None = None,
    first_date: date = QUALITY_REFERENCE_DATE,
    frequency: RecurrenceFrequency = RecurrenceFrequency.WEEKLY,
    termination: RecurrenceTermination = RecurrenceTermination.NEVER,
    end_date: date | None = None,
    occurrence_count: int | None = None,
) -> RecurrenceSeries:
    """Build one valid-shape recurrence series and its owning event."""

    owning_event = event or build_quality_calendar_event(first_date=first_date)
    return RecurrenceSeries(
        id=series_id or uuid4(),
        event_id=owning_event.id,
        event=owning_event,
        frequency=frequency,
        weekday=(owning_event.first_date.weekday() if frequency == "weekly" else None),
        month=(owning_event.first_date.month if frequency == "yearly" else None),
        month_day=(owning_event.first_date.day if frequency == "yearly" else None),
        termination=termination,
        end_date=end_date,
        occurrence_count=occurrence_count,
    )


def build_quality_calendar_exception(
    *,
    exception_id: UUID | None = None,
    series: RecurrenceSeries,
    original_date: date = QUALITY_REFERENCE_DATE,
    is_deleted: bool = True,
) -> OccurrenceException:
    """Build one complete exception snapshot for a selected series/date."""

    snapshot = (
        {
            "event_type": None,
            "name": None,
            "is_all_day": None,
            "start_time": None,
            "end_time": None,
        }
        if is_deleted
        else {
            "event_type": EventType.PRACTICE,
            "name": "Quality replacement practice",
            "is_all_day": False,
            "start_time": time(17, 0),
            "end_time": time(18, 30),
        }
    )
    return OccurrenceException(
        id=exception_id or uuid4(),
        series_id=series.id,
        series=series,
        original_date=original_date,
        replacement_date=None,
        is_deleted=is_deleted,
        version_number=1,
        **snapshot,
    )


def _mock_query_result(rows: Iterable[tuple[object, ...]]) -> Mock:
    result = Mock()
    result.all.return_value = list(rows)
    return result


def build_quality_projection_session(
    *row_sets: Iterable[tuple[object, ...]],
) -> AsyncMock:
    """Build an async session with deterministic results for projection loaders."""

    session = AsyncMock(spec=AsyncSession)
    session.execute.side_effect = [
        _mock_query_result(rows) for rows in row_sets
    ]
    return session


def assert_projection_query_count(
    session: AsyncMock,
    expected: int = 5,
) -> None:
    """Assert the fixed Data Quality projection-query budget."""

    actual = session.execute.await_count
    assert actual == expected, f"expected {expected} queries, observed {actual}"


class PersistedQualityDataBuilder:
    """Stage isolated quality records in a caller-controlled test transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _stage(self, entity: Any) -> Any:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def player(self, **values: Any) -> Player:
        return await self._stage(build_quality_player(**values))

    async def team(self, **values: Any) -> Team:
        return await self._stage(build_quality_team(**values))

    async def roster_membership(self, **values: Any) -> TeamPlayer:
        return await self._stage(build_quality_roster_membership(**values))

    async def coach(self, **values: Any) -> User:
        return await self._stage(build_quality_coach(**values))

    async def coach_assignment(self, **values: Any) -> TeamCoach:
        return await self._stage(build_quality_coach_assignment(**values))

    async def calendar_series(self, **values: Any) -> RecurrenceSeries:
        return await self._stage(build_quality_calendar_series(**values))

    async def calendar_exception(self, **values: Any) -> OccurrenceException:
        return await self._stage(build_quality_calendar_exception(**values))

    async def commit(self) -> None:
        """Release the fixture session's savepoint to API request sessions."""

        await self.session.commit()
