"""Reusable unit-test builders and fixed academy-time values."""

from collections.abc import Callable
from datetime import date, time
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from tests.data_quality_builders import (
    assert_projection_query_count,
    build_quality_projection_session,
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


@pytest.fixture
def quality_projection_session_builder() -> Callable[..., AsyncMock]:
    """Expose fixed row sets for the five projection loader queries."""

    return build_quality_projection_session


@pytest.fixture
def projection_query_count_assertion() -> Callable[[AsyncMock, int], None]:
    """Expose the fixed-query regression assertion."""

    return assert_projection_query_count
