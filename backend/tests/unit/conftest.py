"""Reusable unit-test builders and fixed academy-time values."""

from collections.abc import Callable
from datetime import date, time
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from src.models.calendar import OccurrenceException, RecurrenceSeries
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from tests.data_quality_builders import (
    assert_projection_query_count,
    build_quality_calendar_exception,
    build_quality_calendar_series,
    build_quality_coach,
    build_quality_coach_assignment,
    build_quality_player,
    build_quality_projection_session,
    build_quality_roster_membership,
    build_quality_team,
)

ACADEMY_TIMEZONE_NAME = "America/Los_Angeles"
ACADEMY_TIMEZONE = ZoneInfo(ACADEMY_TIMEZONE_NAME)
# Fixed values keep unit tests deterministic while exercising academy-local rules.
ACADEMY_REFERENCE_DATE = date(2026, 8, 1)
ACADEMY_REFERENCE_TIME = time(12, 0)


def build_calendar_event_payload(
    *,
    name: str = "U13 Wednesday Practice",
    event_type: str = "practice",
    event_date: date = ACADEMY_REFERENCE_DATE,
    start_time: time | None = time(17, 0),
    end_time: time | None = time(18, 30),
    scope_kind: str = "age_group",
    age_groups: list[str] | None = None,
) -> dict[str, Any]:
    """Build a valid calendar event request payload for unit tests."""

    return {
        "name": name,
        "event_type": event_type,
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "scope": build_scope_payload(
            scope_kind=scope_kind,
            age_groups=age_groups,
        ),
    }


def build_scope_payload(
    *,
    scope_kind: str = "age_group",
    age_groups: list[str] | None = None,
) -> dict[str, Any]:
    """Build an event scope payload with the requested audience."""

    return {
        "scope_kind": scope_kind,
        "age_groups": (
            ["U13"]
            if age_groups is None and scope_kind == "age_group"
            else age_groups or []
        ),
    }


def build_recurrence_payload(
    *,
    frequency: str = "weekly",
    termination: str = "never",
    end_date: date | None = None,
    occurrence_count: int | None = None,
) -> dict[str, Any]:
    """Build a recurrence rule payload for bounded recurrence tests."""

    return {
        "frequency": frequency,
        "termination": termination,
        "end_date": end_date,
        "occurrence_count": occurrence_count,
    }


@pytest.fixture
def calendar_event_builder() -> Callable[..., dict[str, Any]]:
    """Expose the standard event builder to calendar unit tests."""

    return build_calendar_event_payload


@pytest.fixture
def quality_player_builder() -> Callable[..., Player]:
    """Expose isolated player records for rule and projection tests."""

    return build_quality_player


@pytest.fixture
def quality_team_builder() -> Callable[..., Team]:
    """Expose isolated team records for rule and projection tests."""

    return build_quality_team


@pytest.fixture
def quality_roster_membership_builder() -> Callable[..., TeamPlayer]:
    """Expose exact roster relationship records with controllable positions."""

    return build_quality_roster_membership


@pytest.fixture
def quality_coach_builder() -> Callable[..., User]:
    """Expose coach and invalid-role account records."""

    return build_quality_coach


@pytest.fixture
def quality_coach_assignment_builder() -> Callable[..., TeamCoach]:
    """Expose exact account/team assignment records."""

    return build_quality_coach_assignment


@pytest.fixture
def quality_calendar_series_builder() -> Callable[..., RecurrenceSeries]:
    """Expose recurrence series with complete owning events."""

    return build_quality_calendar_series


@pytest.fixture
def quality_calendar_exception_builder() -> Callable[..., OccurrenceException]:
    """Expose complete occurrence exception snapshots."""

    return build_quality_calendar_exception


@pytest.fixture
def quality_projection_session_builder() -> Callable[..., AsyncMock]:
    """Expose fixed row sets for the five projection loader queries."""

    return build_quality_projection_session


@pytest.fixture
def projection_query_count_assertion() -> Callable[[AsyncMock, int], None]:
    """Expose the fixed-query regression assertion."""

    return assert_projection_query_count
