"""Typed request and response contracts for academy calendar operations."""

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.enums import (
    AgeGroup,
    EventType,
    RecurrenceFrequency,
    RecurrenceTermination,
    ScopeKind,
)
from src.schemas.base import BaseRequestSchema

CalendarErrorCode = Literal[
    "calendar_range_too_large",
    "calendar_event_in_past",
    "calendar_event_times_invalid",
    "calendar_scope_invalid",
    "calendar_recurrence_invalid",
    "exception_removal_confirmation_required",
    "calendar_stale_version",
]


class CalendarScope(BaseRequestSchema):
    """An unambiguous academy-wide or age-group event audience."""

    scope_kind: ScopeKind
    age_groups: list[AgeGroup] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_scope(self) -> "CalendarScope":
        """Require one scope kind and reject duplicate age groups."""

        if len(set(self.age_groups)) != len(self.age_groups):
            raise ValueError("Age groups must be unique.")
        if self.scope_kind is ScopeKind.ALL_ACADEMY:
            if self.age_groups:
                raise ValueError("All Academy cannot include age groups.")
            return self
        if not self.age_groups:
            raise ValueError("Select at least one age group.")
        return self


class CalendarRecurrence(BaseRequestSchema):
    """A weekly or yearly fixed-interval recurrence request."""

    frequency: RecurrenceFrequency
    termination: RecurrenceTermination
    end_date: date | None = None
    occurrence_count: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_termination(self) -> "CalendarRecurrence":
        """Require exactly the fields belonging to the termination mode."""

        if self.termination is RecurrenceTermination.NEVER:
            if self.end_date is not None or self.occurrence_count is not None:
                raise ValueError("Never-ending recurrence cannot have a limit.")
        elif self.termination is RecurrenceTermination.END_DATE:
            if self.end_date is None or self.occurrence_count is not None:
                raise ValueError("End-date recurrence requires only an end date.")
        elif self.end_date is not None or self.occurrence_count is None:
            raise ValueError(
                "Occurrence-count recurrence requires only a positive count."
            )
        return self


class CalendarEventValues(BaseRequestSchema):
    """Complete user-editable values shared by calendar mutations."""

    event_type: EventType
    name: str = Field(min_length=1, max_length=200)
    event_date: date
    is_all_day: bool = False
    start_time: time | None = None
    end_time: time | None = None
    scope: CalendarScope

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Trim event names and reject whitespace-only input."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("Event name is required.")
        return normalized

    @model_validator(mode="after")
    def validate_time_configuration(self) -> "CalendarEventValues":
        """Enforce all-day eligibility and same-day academy-local times."""

        if self.is_all_day:
            if self.event_type is not EventType.MISCELLANEOUS:
                raise ValueError("Only Miscellaneous events can be all day.")
            if self.start_time is not None or self.end_time is not None:
                raise ValueError("All-day events cannot include times.")
            return self

        if self.start_time is None or self.end_time is None:
            raise ValueError("Timed events require start and end times.")
        if self.start_time.tzinfo is not None or self.end_time.tzinfo is not None:
            raise ValueError("Event times must use academy-local wall-clock values.")
        if self.start_time >= self.end_time:
            raise ValueError("End time must be later than start time.")
        return self


class CalendarEventCreate(CalendarEventValues):
    """Payload for atomically creating a standalone event or series."""

    recurrence: CalendarRecurrence | None = None

    @model_validator(mode="after")
    def validate_recurrence_end(self) -> "CalendarEventCreate":
        """Keep a bounded end date on or after the first occurrence."""

        if (
            self.recurrence is not None
            and self.recurrence.end_date is not None
            and self.recurrence.end_date < self.event_date
        ):
            raise ValueError("Recurrence end date cannot precede the event date.")
        return self


class CalendarStandaloneUpdate(CalendarEventValues):
    """Complete standalone replacement carrying its canonical OCC version."""

    version_number: int = Field(ge=1)


class CalendarOccurrenceUpdate(CalendarEventValues):
    """Complete occurrence snapshot and owning-event/exception versions."""

    version_number: int = Field(ge=1)
    exception_version_number: int | None = Field(default=None, ge=1)


class CalendarSeriesUpdate(CalendarEventValues):
    """Complete recurring-series replacement with impact confirmation."""

    recurrence: CalendarRecurrence
    version_number: int = Field(ge=1)
    confirm_exception_removals: bool = False

    @model_validator(mode="after")
    def validate_recurrence_end(self) -> "CalendarSeriesUpdate":
        """Keep a bounded end date on or after the first occurrence."""

        if (
            self.recurrence.end_date is not None
            and self.recurrence.end_date < self.event_date
        ):
            raise ValueError("Recurrence end date cannot precede the event date.")
        return self


class CalendarEventDelete(BaseRequestSchema):
    """Canonical owning-event version required for hard deletion."""

    version_number: int = Field(ge=1)


class CalendarOccurrenceDelete(CalendarEventDelete):
    """Owning-event and existing exception versions for one deletion."""

    exception_version_number: int | None = Field(default=None, ge=1)


class RecurrenceSeriesResponse(BaseModel):
    """Persisted recurrence identity and derived rule fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    frequency: RecurrenceFrequency
    weekday: int | None = Field(default=None, ge=0, le=6)
    month: int | None = Field(default=None, ge=1, le=12)
    month_day: int | None = Field(default=None, ge=1, le=31)
    termination: RecurrenceTermination
    end_date: date | None
    occurrence_count: int | None = Field(default=None, ge=1)
    created_at: datetime
    updated_at: datetime


class CalendarEventDefinitionResponse(CalendarEventValues):
    """Persisted event definition returned after successful mutation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int = Field(ge=1)
    recurrence: RecurrenceSeriesResponse | None = None
    created_at: datetime
    updated_at: datetime


class CalendarEventInstance(BaseModel):
    """An effective standalone or calculated recurring event instance."""

    occurrence_id: str = Field(min_length=1)
    event_id: UUID
    series_id: UUID | None
    original_date: date
    event_date: date
    event_type: EventType
    name: str = Field(min_length=1, max_length=200)
    is_all_day: bool
    start_time: time | None
    end_time: time | None
    scope_kind: ScopeKind
    age_groups: list[AgeGroup] = Field(max_length=4)
    is_recurring: bool
    recurrence_summary: str | None
    event_version_number: int = Field(ge=1)
    exception_id: UUID | None
    exception_version_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_effective_instance(self) -> "CalendarEventInstance":
        """Keep response scope, timing, and recurrence identity consistent."""

        CalendarScope(
            scope_kind=self.scope_kind,
            age_groups=self.age_groups,
        )
        CalendarEventValues(
            event_type=self.event_type,
            name=self.name,
            event_date=self.event_date,
            is_all_day=self.is_all_day,
            start_time=self.start_time,
            end_time=self.end_time,
            scope=CalendarScope(
                scope_kind=self.scope_kind,
                age_groups=self.age_groups,
            ),
        )
        if self.is_recurring != (self.series_id is not None):
            raise ValueError("Recurring instances require a series identifier.")
        if not self.is_recurring and self.recurrence_summary is not None:
            raise ValueError("Standalone events cannot have a recurrence summary.")
        if self.exception_id is None and self.exception_version_number is not None:
            raise ValueError("Exception version requires an exception identifier.")
        return self


class CalendarRangeResponse(BaseModel):
    """Inclusive bounded range of effective calendar instances."""

    academy_today: date
    start_date: date
    end_date: date
    events: list[CalendarEventInstance]

    @model_validator(mode="after")
    def validate_range(self) -> "CalendarRangeResponse":
        """Reject inverted response ranges."""

        if self.start_date > self.end_date:
            raise ValueError("Calendar range start must not follow its end.")
        return self


class CalendarTodayResponse(BaseModel):
    """Academy-local current date and its effective event instances."""

    academy_today: date
    events: list[CalendarEventInstance]


class CalendarApiErrorResponse(BaseModel):
    """Safe stable calendar error response."""

    detail: str
    code: CalendarErrorCode | None = None


class ExceptionRemovalWarningResponse(BaseModel):
    """Typed warning returned before invalid series exceptions are removed."""

    detail: str
    code: Literal["exception_removal_confirmation_required"]
    removed_exception_original_dates: list[date]
