"""Read-side calendar range, Today, and occurrence projections."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import AgeGroup, ScopeKind
from src.models.calendar import (
    CalendarEvent,
    CalendarEventScope,
    OccurrenceException,
    OccurrenceExceptionScope,
    RecurrenceSeries,
)
from src.schemas.calendar import (
    CalendarEventInstance,
    CalendarRangeResponse,
    CalendarTodayResponse,
)
from src.services.calendar_recurrence import (
    MAX_CALENDAR_RANGE_DATES,
    CalendarRangeError,
    expand_recurrence,
    recurrence_occurs_on,
    recurrence_summary,
    validate_calendar_range,
)


class CalendarEventNotFoundError(LookupError):
    """Raised when an event instance no longer exists."""


class CalendarRangeTooLargeError(CalendarRangeError):
    """Raised when a request would exceed the bounded calendar range."""


class CalendarService:
    """Project persisted event definitions into effective calendar instances."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> None:
        self.session = session
        self.now = now

    async def get_range(
        self,
        range_start: date,
        range_end: date,
    ) -> CalendarRangeResponse:
        """Return sorted effective instances intersecting one bounded range."""

        self._validate_range(range_start, range_end)
        events = await self._load_events(range_end)
        instances: list[CalendarEventInstance] = []

        for event in events:
            series = event.recurrence_series
            if series is None:
                if range_start <= event.first_date <= range_end:
                    instances.append(self._standalone_instance(event, event.first_date))
                continue
            instances.extend(
                self._project_series(
                    event,
                    series,
                    range_start=range_start,
                    range_end=range_end,
                )
            )

        instances.sort(key=self._sort_key)
        return CalendarRangeResponse(
            academy_today=self._academy_today(),
            start_date=range_start,
            end_date=range_end,
            events=instances,
        )

    async def get_today(self) -> CalendarTodayResponse:
        """Return the effective instances on the current academy-local date."""

        today = self._academy_today()
        result = await self.get_range(today, today)
        return CalendarTodayResponse(
            academy_today=result.academy_today,
            events=result.events,
        )

    async def get_instance(self, occurrence_id: str) -> CalendarEventInstance:
        """Resolve one stable standalone or recurring occurrence identity."""

        if ":" in occurrence_id:
            return await self._get_recurring_instance(occurrence_id)

        try:
            event_id = UUID(occurrence_id)
        except ValueError as error:
            raise CalendarEventNotFoundError from error

        event = await self._load_event(event_id)
        if event is None or event.recurrence_series is not None:
            raise CalendarEventNotFoundError
        return self._standalone_instance(event, event.first_date)

    @staticmethod
    def _validate_range(range_start: date, range_end: date) -> None:
        if range_start > range_end:
            raise CalendarRangeError("Calendar range start must not follow its end.")
        date_count = (range_end - range_start).days + 1
        if date_count > MAX_CALENDAR_RANGE_DATES:
            raise CalendarRangeTooLargeError(
                f"Calendar ranges cannot exceed {MAX_CALENDAR_RANGE_DATES} dates."
            )
        validate_calendar_range(range_start, range_end)

    @staticmethod
    def _options():
        return (
            selectinload(CalendarEvent.scopes),
            selectinload(CalendarEvent.recurrence_series)
            .selectinload(RecurrenceSeries.exceptions)
            .selectinload(OccurrenceException.scopes),
        )

    async def _load_events(self, range_end: date) -> list[CalendarEvent]:
        statement = (
            select(CalendarEvent)
            .where(CalendarEvent.first_date <= range_end)
            .options(*self._options())
        )
        result = await self.session.execute(statement)
        return list(result.unique().scalars().all())

    async def _load_event(self, event_id: UUID) -> CalendarEvent | None:
        statement = (
            select(CalendarEvent)
            .where(CalendarEvent.id == event_id)
            .options(*self._options())
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_recurring_instance(
        self,
        occurrence_id: str,
    ) -> CalendarEventInstance:
        series_text, original_text = occurrence_id.rsplit(":", 1)
        try:
            series_id = UUID(series_text)
            original_date = date.fromisoformat(original_text)
        except ValueError as error:
            raise CalendarEventNotFoundError from error

        events = await self._load_events(original_date)
        event = next(
            (
                candidate
                for candidate in events
                if candidate.recurrence_series is not None
                and candidate.recurrence_series.id == series_id
            ),
            None,
        )
        if event is None or event.recurrence_series is None:
            raise CalendarEventNotFoundError

        series = event.recurrence_series
        if not self._series_occurs_on(series, event.first_date, original_date):
            raise CalendarEventNotFoundError
        exception = next(
            (
                candidate
                for candidate in (series.exceptions or [])
                if candidate.original_date == original_date
            ),
            None,
        )
        if exception is not None and exception.is_deleted:
            raise CalendarEventNotFoundError
        effective_date = (
            exception.replacement_date
            if exception is not None and exception.replacement_date is not None
            else original_date
        )
        return self._recurring_instance(
            event,
            series,
            original_date,
            effective_date,
            exception,
        )

    def _project_series(
        self,
        event: CalendarEvent,
        series: RecurrenceSeries,
        *,
        range_start: date,
        range_end: date,
    ) -> list[CalendarEventInstance]:
        original_dates = set(
            expand_recurrence(
                first_date=event.first_date,
                frequency=series.frequency,
                termination=series.termination,
                range_start=range_start,
                range_end=range_end,
                end_date=series.end_date,
                occurrence_count=series.occurrence_count,
            )
        )
        exceptions = {
            exception.original_date: exception
            for exception in (series.exceptions or [])
            if self._series_occurs_on(
                series,
                event.first_date,
                exception.original_date,
            )
        }

        # A moved occurrence can enter the requested range from just outside its
        # original date. Exceptions are already bounded to one series and are
        # checked against the recurrence identity before they are considered.
        for original_date, exception in exceptions.items():
            if (
                exception.replacement_date is not None
                and range_start <= exception.replacement_date <= range_end
            ):
                original_dates.add(original_date)

        instances: list[CalendarEventInstance] = []
        for original_date in sorted(original_dates):
            candidate_exception = exceptions.get(original_date)
            if candidate_exception is not None and candidate_exception.is_deleted:
                continue
            effective_date = (
                candidate_exception.replacement_date
                if candidate_exception is not None
                and candidate_exception.replacement_date is not None
                else original_date
            )
            if not range_start <= effective_date <= range_end:
                continue
            instances.append(
                self._recurring_instance(
                    event,
                    series,
                    original_date,
                    effective_date,
                    candidate_exception,
                )
            )
        return instances

    @staticmethod
    def _series_occurs_on(
        series: RecurrenceSeries,
        first_date: date,
        candidate: date,
    ) -> bool:
        try:
            return recurrence_occurs_on(
                candidate,
                first_date=first_date,
                frequency=series.frequency,
                termination=series.termination,
                end_date=series.end_date,
                occurrence_count=series.occurrence_count,
            )
        except (CalendarRangeError, ValueError):
            return False

    def _standalone_instance(
        self,
        event: CalendarEvent,
        event_date: date,
    ) -> CalendarEventInstance:
        scope_kind, age_groups = self._scope_values(event.scopes)
        return CalendarEventInstance(
            occurrence_id=str(event.id),
            event_id=event.id,
            series_id=None,
            original_date=event.first_date,
            event_date=event_date,
            event_type=event.event_type,
            name=event.name,
            is_all_day=event.is_all_day,
            start_time=event.start_time,
            end_time=event.end_time,
            scope_kind=scope_kind,
            age_groups=age_groups,
            is_recurring=False,
            recurrence_summary=None,
            event_version_number=event.version_number,
            exception_id=None,
            exception_version_number=None,
        )

    def _recurring_instance(
        self,
        event: CalendarEvent,
        series: RecurrenceSeries,
        original_date: date,
        effective_date: date,
        exception: OccurrenceException | None,
    ) -> CalendarEventInstance:
        scopes: Sequence[CalendarEventScope | OccurrenceExceptionScope]
        if exception is None:
            event_type = event.event_type
            name = event.name
            is_all_day = event.is_all_day
            start_time = event.start_time
            end_time = event.end_time
            scopes = event.scopes
        else:
            if (
                exception.event_type is None
                or exception.name is None
                or exception.is_all_day is None
            ):
                raise CalendarEventNotFoundError
            event_type = exception.event_type
            name = exception.name
            is_all_day = exception.is_all_day
            start_time = exception.start_time
            end_time = exception.end_time
            scopes = exception.scopes
        scope_kind, age_groups = self._scope_values(scopes)
        return CalendarEventInstance(
            occurrence_id=f"{series.id}:{original_date.isoformat()}",
            event_id=event.id,
            series_id=series.id,
            original_date=original_date,
            event_date=effective_date,
            event_type=event_type,
            name=name,
            is_all_day=is_all_day,
            start_time=start_time,
            end_time=end_time,
            scope_kind=scope_kind,
            age_groups=age_groups,
            is_recurring=True,
            recurrence_summary=recurrence_summary(event.first_date, series.frequency),
            event_version_number=event.version_number,
            exception_id=exception.id if exception is not None else None,
            exception_version_number=(
                exception.version_number if exception is not None else None
            ),
        )

    @staticmethod
    def _scope_values(
        scopes: Sequence[CalendarEventScope | OccurrenceExceptionScope] | None,
    ) -> tuple[ScopeKind, list[AgeGroup]]:
        if not scopes:
            return ScopeKind.ALL_ACADEMY, []
        first = scopes[0]
        scope_kind = ScopeKind(first.scope_kind)
        if scope_kind is ScopeKind.ALL_ACADEMY:
            return ScopeKind.ALL_ACADEMY, []
        age_groups = sorted(
            {
                AgeGroup(scope.age_group)
                for scope in scopes
                if scope.age_group is not None
            },
            key=lambda age_group: age_group.value,
        )
        return ScopeKind.AGE_GROUP, age_groups

    @staticmethod
    def _sort_key(instance: CalendarEventInstance):
        return (
            instance.event_date,
            0 if instance.is_all_day else 1,
            instance.start_time if instance.start_time is not None else time.min,
            instance.occurrence_id,
        )

    def _academy_today(self) -> date:
        from src.services.calendar_recurrence import academy_today

        return academy_today(self.now)
