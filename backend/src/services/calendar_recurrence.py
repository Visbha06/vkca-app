"""Bounded academy-local weekly and yearly recurrence arithmetic."""

from calendar import day_name, month_name
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.enums import RecurrenceFrequency, RecurrenceTermination

ACADEMY_TIMEZONE_NAME = "America/Los_Angeles"
ACADEMY_TIMEZONE = ZoneInfo(ACADEMY_TIMEZONE_NAME)
MAX_CALENDAR_RANGE_DATES = 45


class CalendarRangeError(ValueError):
    """Raised before recurrence expansion for an invalid requested range."""


class CalendarRecurrenceError(ValueError):
    """Raised when a persisted or requested recurrence rule is inconsistent."""


def academy_now(value: datetime | None = None) -> datetime:
    """Return an aware datetime interpreted in the academy time zone.

    Explicit values must be timezone-aware so tests and callers cannot silently
    treat a browser/server-local wall clock as the academy clock.
    """

    if value is None:
        return datetime.now(tz=ACADEMY_TIMEZONE)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Academy clock values must be timezone-aware.")
    return value.astimezone(ACADEMY_TIMEZONE)


def academy_today(value: datetime | None = None) -> date:
    """Return the trusted current academy date in America/Los_Angeles."""

    return academy_now(value).date()


def validate_calendar_range(
    range_start: date,
    range_end: date,
    *,
    maximum_dates: int = MAX_CALENDAR_RANGE_DATES,
) -> int:
    """Validate an inclusive range and return its number of academy dates."""

    if maximum_dates < 1:
        raise ValueError("Maximum range length must be positive.")
    if range_start > range_end:
        raise CalendarRangeError("Calendar range start must not follow its end.")
    date_count = (range_end - range_start).days + 1
    if date_count > maximum_dates:
        raise CalendarRangeError(
            f"Calendar ranges cannot exceed {maximum_dates} dates."
        )
    return date_count


def _coerce_frequency(value: RecurrenceFrequency | str) -> RecurrenceFrequency:
    try:
        return RecurrenceFrequency(value)
    except ValueError as error:
        raise CalendarRecurrenceError("Unsupported recurrence frequency.") from error


def _coerce_termination(
    value: RecurrenceTermination | str,
) -> RecurrenceTermination:
    try:
        return RecurrenceTermination(value)
    except ValueError as error:
        raise CalendarRecurrenceError("Unsupported recurrence termination.") from error


def _validate_termination(
    *,
    first_date: date,
    termination: RecurrenceTermination,
    end_date: date | None,
    occurrence_count: int | None,
) -> None:
    if termination is RecurrenceTermination.NEVER:
        if end_date is not None or occurrence_count is not None:
            raise CalendarRecurrenceError(
                "Never-ending recurrence cannot have a limit."
            )
        return
    if termination is RecurrenceTermination.END_DATE:
        if end_date is None or occurrence_count is not None:
            raise CalendarRecurrenceError(
                "End-date recurrence requires only an end date."
            )
        if end_date < first_date:
            raise CalendarRecurrenceError(
                "Recurrence end date cannot precede the first date."
            )
        return
    if end_date is not None or occurrence_count is None or occurrence_count < 1:
        raise CalendarRecurrenceError(
            "Occurrence-count recurrence requires only a positive count."
        )


def _weekly_dates(
    *,
    first_date: date,
    range_start: date,
    range_end: date,
    termination: RecurrenceTermination,
    end_date: date | None,
    occurrence_count: int | None,
) -> list[date]:
    if range_end < first_date:
        return []

    first_requested_index = max(
        0,
        ((range_start - first_date).days + 6) // 7,
    )
    last_requested_index = (range_end - first_date).days // 7

    if termination is RecurrenceTermination.END_DATE:
        assert end_date is not None
        last_requested_index = min(
            last_requested_index,
            (end_date - first_date).days // 7,
        )
    elif termination is RecurrenceTermination.OCCURRENCE_COUNT:
        assert occurrence_count is not None
        last_requested_index = min(last_requested_index, occurrence_count - 1)

    if first_requested_index > last_requested_index:
        return []
    return [
        first_date + timedelta(days=index * 7)
        for index in range(first_requested_index, last_requested_index + 1)
    ]


def yearly_occurrence_date(first_date: date, year: int) -> date:
    """Return a yearly occurrence, applying the Feb 29 to Feb 28 fallback."""

    if year < first_date.year:
        raise CalendarRecurrenceError(
            "A recurrence occurrence cannot precede its first year."
        )
    try:
        return first_date.replace(year=year)
    except ValueError as error:
        if first_date.month == 2 and first_date.day == 29:
            return date(year, 2, 28)
        raise CalendarRecurrenceError("Invalid yearly recurrence date.") from error


def _yearly_dates(
    *,
    first_date: date,
    range_start: date,
    range_end: date,
    termination: RecurrenceTermination,
    end_date: date | None,
    occurrence_count: int | None,
) -> list[date]:
    if range_end < first_date:
        return []

    first_year = max(first_date.year, range_start.year)
    last_year = range_end.year
    dates: list[date] = []
    for year in range(first_year, last_year + 1):
        occurrence_index = year - first_date.year
        if (
            termination is RecurrenceTermination.OCCURRENCE_COUNT
            and occurrence_count is not None
            and occurrence_index >= occurrence_count
        ):
            continue
        candidate = yearly_occurrence_date(first_date, year)
        if termination is RecurrenceTermination.END_DATE:
            assert end_date is not None
            if candidate > end_date:
                continue
        if range_start <= candidate <= range_end:
            dates.append(candidate)
    return dates


def expand_recurrence(
    *,
    first_date: date,
    frequency: RecurrenceFrequency | str,
    termination: RecurrenceTermination | str,
    range_start: date,
    range_end: date,
    end_date: date | None = None,
    occurrence_count: int | None = None,
) -> list[date]:
    """Calculate occurrences only inside one validated inclusive range.

    Range validation occurs before rule work. The weekly implementation jumps
    directly to the first requested index, while the yearly implementation
    inspects only years touched by the at-most-45-date request. Neither walks or
    materializes the unrequested lifetime of a never-ending series.
    """

    validate_calendar_range(range_start, range_end)
    normalized_frequency = _coerce_frequency(frequency)
    normalized_termination = _coerce_termination(termination)
    _validate_termination(
        first_date=first_date,
        termination=normalized_termination,
        end_date=end_date,
        occurrence_count=occurrence_count,
    )

    if normalized_frequency is RecurrenceFrequency.WEEKLY:
        return _weekly_dates(
            first_date=first_date,
            range_start=range_start,
            range_end=range_end,
            termination=normalized_termination,
            end_date=end_date,
            occurrence_count=occurrence_count,
        )
    return _yearly_dates(
        first_date=first_date,
        range_start=range_start,
        range_end=range_end,
        termination=normalized_termination,
        end_date=end_date,
        occurrence_count=occurrence_count,
    )


def recurrence_occurs_on(
    occurrence_date: date,
    *,
    first_date: date,
    frequency: RecurrenceFrequency | str,
    termination: RecurrenceTermination | str,
    end_date: date | None = None,
    occurrence_count: int | None = None,
) -> bool:
    """Check one stable original date without expanding intervening years."""

    return bool(
        expand_recurrence(
            first_date=first_date,
            frequency=frequency,
            termination=termination,
            range_start=occurrence_date,
            range_end=occurrence_date,
            end_date=end_date,
            occurrence_count=occurrence_count,
        )
    )


def recurrence_summary(
    first_date: date,
    frequency: RecurrenceFrequency | str,
) -> str:
    """Return the stable user-facing summary for a recurrence frequency."""

    normalized_frequency = _coerce_frequency(frequency)
    if normalized_frequency is RecurrenceFrequency.WEEKLY:
        return f"Every week on {day_name[first_date.weekday()]}"
    summary = f"Every year on {month_name[first_date.month]} {first_date.day}"
    if first_date.month == 2 and first_date.day == 29:
        return f"{summary} (February 28 in non-leap years)"
    return summary
