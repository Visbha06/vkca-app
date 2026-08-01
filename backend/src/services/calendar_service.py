"""Calendar read projections and transactional event mutations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, time
from uuid import UUID, uuid4

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
    CalendarErrorCode,
    CalendarEventCreate,
    CalendarEventDefinitionResponse,
    CalendarEventDelete,
    CalendarEventInstance,
    CalendarEventValues,
    CalendarOccurrenceDelete,
    CalendarOccurrenceUpdate,
    CalendarRangeResponse,
    CalendarRecurrence,
    CalendarScope,
    CalendarSeriesUpdate,
    CalendarStandaloneUpdate,
    CalendarTodayResponse,
    RecurrenceSeriesResponse,
)
from src.services.calendar_recurrence import (
    ACADEMY_TIMEZONE,
    MAX_CALENDAR_RANGE_DATES,
    CalendarRangeError,
    academy_now,
    expand_recurrence,
    recurrence_occurs_on,
    recurrence_summary,
    validate_calendar_range,
)


class CalendarEventNotFoundError(LookupError):
    """Raised when an event instance no longer exists."""


class CalendarRangeTooLargeError(CalendarRangeError):
    """Raised when a request would exceed the bounded calendar range."""


class CalendarStaleVersionError(Exception):
    """Raised when an owning-event or exception mutation version is stale."""


class CalendarMutationValidationError(ValueError):
    """A safe calendar validation failure with a stable API error code."""

    def __init__(self, code: CalendarErrorCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


class CalendarExceptionRemovalRequiredError(Exception):
    """Raised before a series edit would discard occurrence exceptions."""

    def __init__(self, removed_original_dates: list[date]) -> None:
        self.removed_original_dates = sorted(removed_original_dates)
        count = len(self.removed_original_dates)
        occurrence_label = "occurrence" if count == 1 else "occurrences"
        super().__init__(
            f"This change will remove saved changes for {count} {occurrence_label}."
        )


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

    async def create_event(
        self,
        payload: CalendarEventCreate,
    ) -> CalendarEventDefinitionResponse:
        """Create one standalone event or recurring definition atomically."""

        try:
            self._validate_mutation_schedule(payload)
            event = CalendarEvent(
                id=uuid4(),
                event_type=payload.event_type,
                name=payload.name,
                first_date=payload.event_date,
                is_all_day=payload.is_all_day,
                start_time=payload.start_time,
                end_time=payload.end_time,
                version_number=1,
            )
            event.scopes = self._event_scope_rows(event.id, payload.scope)
            if payload.recurrence is not None:
                event.recurrence_series = self._new_series(
                    event.id,
                    payload.event_date,
                    payload.recurrence,
                )
            else:
                # Mark the one-to-one relationship as loaded for the response
                # built before commit.  Async SQLAlchemy cannot lazy-load this
                # newly-created empty relationship outside a greenlet.
                event.recurrence_series = None
            self.session.add(event)
            await self.session.flush()
            response = self._definition_response(event)
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def update_standalone(
        self,
        event_id: UUID,
        payload: CalendarStandaloneUpdate,
    ) -> CalendarEventDefinitionResponse:
        """Replace a standalone event when its canonical version is current."""

        try:
            event = await self._load_event_for_update(event_id)
            if event is None or event.recurrence_series is not None:
                raise CalendarEventNotFoundError
            self._check_version(event.version_number, payload.version_number)
            self._validate_mutation_schedule(
                payload,
                previous=self._event_schedule(event),
            )
            await self._replace_event_values(event, payload)
            event.version_number += 1
            await self.session.flush()
            await self._refresh_definition_timestamps(event)
            response = self._definition_response(event)
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def delete_standalone(
        self,
        event_id: UUID,
        payload: CalendarEventDelete,
    ) -> None:
        """Hard-delete one standalone event and its scope rows atomically."""

        try:
            event = await self._load_event_for_update(event_id)
            if event is None or event.recurrence_series is not None:
                raise CalendarEventNotFoundError
            self._check_version(event.version_number, payload.version_number)
            await self.session.delete(event)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def update_occurrence(
        self,
        occurrence_id: str,
        payload: CalendarOccurrenceUpdate,
    ) -> CalendarEventInstance:
        """Create or replace one complete occurrence-exception snapshot."""

        try:
            (
                event,
                series,
                original_date,
                exception,
            ) = await self._load_occurrence_for_update(occurrence_id)
            self._check_version(event.version_number, payload.version_number)
            self._check_exception_version(
                exception,
                payload.exception_version_number,
            )
            self._validate_mutation_schedule(
                payload,
                previous=self._occurrence_schedule(
                    event,
                    original_date,
                    exception,
                ),
            )

            is_new_exception = exception is None
            if exception is None:
                exception = OccurrenceException(
                    id=uuid4(),
                    series_id=series.id,
                    original_date=original_date,
                    version_number=1,
                )
                series.exceptions.append(exception)
                self.session.add(exception)
            else:
                exception.version_number += 1

            if not is_new_exception:
                exception.scopes.clear()
                await self.session.flush()
            self._apply_exception_values(exception, original_date, payload)
            await self.session.flush()
            instance = self._recurring_instance(
                event,
                series,
                original_date,
                payload.event_date,
                exception,
            )
            await self.session.commit()
            return instance
        except Exception:
            await self.session.rollback()
            raise

    async def delete_occurrence(
        self,
        occurrence_id: str,
        payload: CalendarOccurrenceDelete,
    ) -> None:
        """Persist a deletion exception while leaving its series untouched."""

        try:
            (
                event,
                series,
                original_date,
                exception,
            ) = await self._load_occurrence_for_update(occurrence_id)
            self._check_version(event.version_number, payload.version_number)
            self._check_exception_version(
                exception,
                payload.exception_version_number,
            )

            if exception is None:
                exception = OccurrenceException(
                    id=uuid4(),
                    series_id=series.id,
                    original_date=original_date,
                    version_number=1,
                )
                series.exceptions.append(exception)
                self.session.add(exception)
            else:
                exception.version_number += 1
            exception.replacement_date = None
            exception.event_type = None
            exception.name = None
            exception.is_all_day = None
            exception.start_time = None
            exception.end_time = None
            exception.is_deleted = True
            exception.scopes = []
            await self.session.flush()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def update_series(
        self,
        series_id: UUID,
        payload: CalendarSeriesUpdate,
    ) -> CalendarEventDefinitionResponse:
        """Replace a series and confirmation-gate invalid exception cleanup."""

        try:
            event, series = await self._load_series_for_update(series_id)
            self._check_version(event.version_number, payload.version_number)
            self._validate_mutation_schedule(
                payload,
                previous=self._event_schedule(event),
            )
            invalid_exceptions = self._invalid_exceptions_for_rule(
                series,
                payload.event_date,
                payload.recurrence,
            )
            if invalid_exceptions and not payload.confirm_exception_removals:
                raise CalendarExceptionRemovalRequiredError(
                    [exception.original_date for exception in invalid_exceptions]
                )

            for exception in invalid_exceptions:
                await self.session.delete(exception)
                series.exceptions.remove(exception)

            await self._replace_event_values(event, payload)
            self._apply_series_rule(
                series,
                payload.event_date,
                payload.recurrence,
            )
            event.version_number += 1
            await self.session.flush()
            await self._refresh_definition_timestamps(event)
            response = self._definition_response(event)
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def delete_series(
        self,
        series_id: UUID,
        payload: CalendarEventDelete,
    ) -> None:
        """Delete the owning event so database cascades remove all series data."""

        try:
            event, _series = await self._load_series_for_update(series_id)
            self._check_version(event.version_number, payload.version_number)
            await self.session.delete(event)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _check_version(current: int, incoming: int) -> None:
        if current != incoming:
            raise CalendarStaleVersionError

    @staticmethod
    def _check_exception_version(
        exception: OccurrenceException | None,
        incoming: int | None,
    ) -> None:
        if exception is None:
            if incoming is not None:
                raise CalendarStaleVersionError
            return
        if incoming != exception.version_number:
            raise CalendarStaleVersionError

    @staticmethod
    def _event_schedule(
        event: CalendarEvent,
    ) -> tuple[date, bool, time | None, time | None]:
        return (
            event.first_date,
            event.is_all_day,
            event.start_time,
            event.end_time,
        )

    @staticmethod
    def _occurrence_schedule(
        event: CalendarEvent,
        original_date: date,
        exception: OccurrenceException | None,
    ) -> tuple[date, bool, time | None, time | None]:
        if exception is None or exception.is_deleted:
            return (
                original_date,
                event.is_all_day,
                event.start_time,
                event.end_time,
            )
        return (
            exception.replacement_date or original_date,
            bool(exception.is_all_day),
            exception.start_time,
            exception.end_time,
        )

    def _validate_mutation_schedule(
        self,
        payload: CalendarEventValues,
        *,
        previous: tuple[date, bool, time | None, time | None] | None = None,
    ) -> None:
        """Reject newly-past academy-local schedules independently of schemas."""

        candidate = (
            payload.event_date,
            payload.is_all_day,
            payload.start_time,
            payload.end_time,
        )
        if previous == candidate:
            return

        current = academy_now(self.now)
        is_past = payload.event_date < current.date()
        if (
            not is_past
            and payload.event_date == current.date()
            and not payload.is_all_day
            and payload.start_time is not None
        ):
            candidate_start = datetime.combine(
                payload.event_date,
                payload.start_time,
                tzinfo=ACADEMY_TIMEZONE,
            )
            is_past = candidate_start < current
        if is_past:
            raise CalendarMutationValidationError(
                "calendar_event_in_past",
                "Choose an academy date and time that has not passed.",
            )

    @staticmethod
    def _event_scope_rows(
        event_id: UUID,
        scope: CalendarScope,
    ) -> list[CalendarEventScope]:
        if scope.scope_kind is ScopeKind.ALL_ACADEMY:
            return [
                CalendarEventScope(
                    id=uuid4(),
                    event_id=event_id,
                    scope_kind=ScopeKind.ALL_ACADEMY,
                    age_group=None,
                )
            ]
        return [
            CalendarEventScope(
                id=uuid4(),
                event_id=event_id,
                scope_kind=ScopeKind.AGE_GROUP,
                age_group=age_group,
            )
            for age_group in scope.age_groups
        ]

    @staticmethod
    def _exception_scope_rows(
        exception_id: UUID,
        scope: CalendarScope,
    ) -> list[OccurrenceExceptionScope]:
        if scope.scope_kind is ScopeKind.ALL_ACADEMY:
            return [
                OccurrenceExceptionScope(
                    id=uuid4(),
                    exception_id=exception_id,
                    scope_kind=ScopeKind.ALL_ACADEMY,
                    age_group=None,
                )
            ]
        return [
            OccurrenceExceptionScope(
                id=uuid4(),
                exception_id=exception_id,
                scope_kind=ScopeKind.AGE_GROUP,
                age_group=age_group,
            )
            for age_group in scope.age_groups
        ]

    @classmethod
    def _new_series(
        cls,
        event_id: UUID,
        first_date: date,
        recurrence: CalendarRecurrence,
    ) -> RecurrenceSeries:
        series = RecurrenceSeries(
            id=uuid4(),
            event_id=event_id,
            frequency=recurrence.frequency,
            termination=recurrence.termination,
            end_date=recurrence.end_date,
            occurrence_count=recurrence.occurrence_count,
        )
        cls._apply_series_rule(series, first_date, recurrence)
        return series

    @staticmethod
    def _apply_series_rule(
        series: RecurrenceSeries,
        first_date: date,
        recurrence: CalendarRecurrence,
    ) -> None:
        series.frequency = recurrence.frequency
        series.termination = recurrence.termination
        series.end_date = recurrence.end_date
        series.occurrence_count = recurrence.occurrence_count
        if recurrence.frequency.value == "weekly":
            series.weekday = first_date.weekday()
            series.month = None
            series.month_day = None
        else:
            series.weekday = None
            series.month = first_date.month
            series.month_day = first_date.day

    async def _replace_event_values(
        self,
        event: CalendarEvent,
        payload: CalendarEventValues,
    ) -> None:
        event.event_type = payload.event_type
        event.name = payload.name
        event.first_date = payload.event_date
        event.is_all_day = payload.is_all_day
        event.start_time = payload.start_time
        event.end_time = payload.end_time
        event.scopes.clear()
        await self.session.flush()
        event.scopes.extend(self._event_scope_rows(event.id, payload.scope))

    def _apply_exception_values(
        self,
        exception: OccurrenceException,
        original_date: date,
        payload: CalendarEventValues,
    ) -> None:
        exception.replacement_date = (
            payload.event_date if payload.event_date != original_date else None
        )
        exception.event_type = payload.event_type
        exception.name = payload.name
        exception.is_all_day = payload.is_all_day
        exception.start_time = payload.start_time
        exception.end_time = payload.end_time
        exception.is_deleted = False
        exception.scopes.extend(self._exception_scope_rows(exception.id, payload.scope))

    @staticmethod
    def _invalid_exceptions_for_rule(
        series: RecurrenceSeries,
        first_date: date,
        recurrence: CalendarRecurrence,
    ) -> list[OccurrenceException]:
        invalid: list[OccurrenceException] = []
        for exception in list(series.exceptions or []):
            try:
                is_valid = recurrence_occurs_on(
                    exception.original_date,
                    first_date=first_date,
                    frequency=recurrence.frequency,
                    termination=recurrence.termination,
                    end_date=recurrence.end_date,
                    occurrence_count=recurrence.occurrence_count,
                )
            except (CalendarRangeError, ValueError):
                is_valid = False
            if not is_valid:
                invalid.append(exception)
        return invalid

    def _definition_response(
        self,
        event: CalendarEvent,
    ) -> CalendarEventDefinitionResponse:
        scope_kind, age_groups = self._scope_values(event.scopes)
        recurrence = event.recurrence_series
        recurrence_response = (
            None if recurrence is None else self._recurrence_response(recurrence)
        )
        return CalendarEventDefinitionResponse(
            id=event.id,
            event_type=event.event_type,
            name=event.name,
            event_date=event.first_date,
            is_all_day=event.is_all_day,
            start_time=event.start_time,
            end_time=event.end_time,
            scope=CalendarScope(
                scope_kind=scope_kind,
                age_groups=age_groups,
            ),
            version_number=event.version_number,
            recurrence=recurrence_response,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )

    async def _refresh_definition_timestamps(
        self,
        event: CalendarEvent,
    ) -> None:
        """Load server-updated timestamps without triggering implicit async IO."""

        await self.session.refresh(event, attribute_names=["updated_at"])
        if event.recurrence_series is not None:
            await self.session.refresh(
                event.recurrence_series,
                attribute_names=["updated_at"],
            )

    async def _load_event_for_update(
        self,
        event_id: UUID,
    ) -> CalendarEvent | None:
        statement = (
            select(CalendarEvent)
            .where(CalendarEvent.id == event_id)
            .options(*self._options())
            .with_for_update()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _load_series_for_update(
        self,
        series_id: UUID,
    ) -> tuple[CalendarEvent, RecurrenceSeries]:
        statement = (
            select(CalendarEvent)
            .join(CalendarEvent.recurrence_series)
            .where(RecurrenceSeries.id == series_id)
            .options(*self._options())
            .with_for_update()
        )
        result = await self.session.execute(statement)
        event = result.unique().scalar_one_or_none()
        if event is None or event.recurrence_series is None:
            raise CalendarEventNotFoundError
        return event, event.recurrence_series

    async def _load_occurrence_for_update(
        self,
        occurrence_id: str,
    ) -> tuple[
        CalendarEvent,
        RecurrenceSeries,
        date,
        OccurrenceException | None,
    ]:
        try:
            series_text, original_text = occurrence_id.rsplit(":", 1)
            series_id = UUID(series_text)
            original_date = date.fromisoformat(original_text)
        except ValueError as error:
            raise CalendarEventNotFoundError from error

        event, series = await self._load_series_for_update(series_id)
        if not self._series_occurs_on(series, event.first_date, original_date):
            raise CalendarEventNotFoundError

        statement = (
            select(OccurrenceException)
            .where(
                OccurrenceException.series_id == series_id,
                OccurrenceException.original_date == original_date,
            )
            .options(selectinload(OccurrenceException.scopes))
            .with_for_update()
        )
        result = await self.session.execute(statement)
        exception = result.scalar_one_or_none()
        return event, series, original_date, exception

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
        try:
            series_text, original_text = occurrence_id.rsplit(":", 1)
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
            series_definition=None,
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
            series_definition=self._definition_response(event),
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
    def _recurrence_response(
        recurrence: RecurrenceSeries,
    ) -> RecurrenceSeriesResponse:
        return RecurrenceSeriesResponse(
            id=recurrence.id,
            event_id=recurrence.event_id,
            frequency=recurrence.frequency,
            weekday=recurrence.weekday,
            month=recurrence.month,
            month_day=recurrence.month_day,
            termination=recurrence.termination,
            end_date=recurrence.end_date,
            occurrence_count=recurrence.occurrence_count,
            created_at=recurrence.created_at,
            updated_at=recurrence.updated_at,
        )

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
