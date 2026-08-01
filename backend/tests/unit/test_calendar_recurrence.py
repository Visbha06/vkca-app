"""Unit coverage for bounded academy-local recurrence behavior."""

from datetime import date

import pytest

from src.services.calendar_recurrence import (
    CalendarRangeError,
    expand_recurrence,
    recurrence_occurs_on,
    recurrence_summary,
    validate_calendar_range,
    yearly_occurrence_date,
)


def test_weekly_recurrence_intersects_a_complete_grid_without_expanding_forever():
    occurrences = expand_recurrence(
        first_date=date(2026, 7, 1),
        frequency="weekly",
        termination="never",
        range_start=date(2026, 7, 26),
        range_end=date(2026, 9, 5),
    )

    assert occurrences == [
        date(2026, 7, 29),
        date(2026, 8, 5),
        date(2026, 8, 12),
        date(2026, 8, 19),
        date(2026, 8, 26),
        date(2026, 9, 2),
    ]


def test_yearly_recurrence_uses_february_28_fallback_and_summary():
    first_date = date(2024, 2, 29)

    assert yearly_occurrence_date(first_date, 2025) == date(2025, 2, 28)
    assert yearly_occurrence_date(first_date, 2028) == date(2028, 2, 29)
    assert expand_recurrence(
        first_date=first_date,
        frequency="yearly",
        termination="never",
        range_start=date(2025, 2, 20),
        range_end=date(2025, 3, 5),
    ) == [date(2025, 2, 28)]
    assert recurrence_summary(first_date, "yearly") == (
        "Every year on February 29 (February 28 in non-leap years)"
    )


@pytest.mark.parametrize(
    ("termination", "end_date", "occurrence_count", "expected"),
    [
        (
            "end_date",
            date(2026, 8, 12),
            None,
            [date(2026, 8, 5), date(2026, 8, 12)],
        ),
        (
            "occurrence_count",
            None,
            3,
            [date(2026, 8, 5), date(2026, 8, 12), date(2026, 8, 19)],
        ),
    ],
)
def test_weekly_termination_is_applied_during_range_projection(
    termination, end_date, occurrence_count, expected
):
    assert (
        expand_recurrence(
            first_date=date(2026, 8, 5),
            frequency="weekly",
            termination=termination,
            range_start=date(2026, 8, 1),
            range_end=date(2026, 8, 31),
            end_date=end_date,
            occurrence_count=occurrence_count,
        )
        == expected
    )


def test_recurrence_identity_can_be_checked_for_exception_projection():
    assert recurrence_occurs_on(
        date(2026, 8, 12),
        first_date=date(2026, 8, 5),
        frequency="weekly",
        termination="never",
    )
    assert not recurrence_occurs_on(
        date(2026, 8, 13),
        first_date=date(2026, 8, 5),
        frequency="weekly",
        termination="never",
    )


def test_range_validation_rejects_inverted_and_overlong_ranges_before_work():
    with pytest.raises(CalendarRangeError):
        validate_calendar_range(date(2026, 8, 2), date(2026, 8, 1))

    with pytest.raises(CalendarRangeError):
        expand_recurrence(
            first_date=date(2026, 1, 1),
            frequency="weekly",
            termination="never",
            range_start=date(2026, 1, 1),
            range_end=date(2026, 3, 1),
        )
