"""Authenticated calendar reads and coach-only mutation routes."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.calendar import (
    CalendarApiErrorResponse,
    CalendarEventCreate,
    CalendarEventDefinitionResponse,
    CalendarEventDelete,
    CalendarEventInstance,
    CalendarOccurrenceDelete,
    CalendarOccurrenceUpdate,
    CalendarRangeResponse,
    CalendarSeriesUpdate,
    CalendarStandaloneUpdate,
    CalendarTodayResponse,
    ExceptionRemovalWarningResponse,
)
from src.services.business_audit_service import AuditActorContext
from src.services.calendar_recurrence import MAX_CALENDAR_RANGE_DATES
from src.services.calendar_service import (
    CalendarEventNotFoundError,
    CalendarExceptionRemovalRequiredError,
    CalendarMutationValidationError,
    CalendarRangeError,
    CalendarRangeTooLargeError,
    CalendarService,
    CalendarStaleVersionError,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _parse_query_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid academy date range.",
        ) from error


def _range_error_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=CalendarApiErrorResponse(
            detail=(
                "Unable to load that calendar range. Choose a shorter range "
                "and try again."
            ),
            code="calendar_range_too_large",
        ).model_dump(mode="json"),
    )


def _stale_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=CalendarApiErrorResponse(
            detail="This calendar event changed. Reload and try again.",
            code="calendar_stale_version",
        ).model_dump(mode="json"),
    )


def _validation_response(error: CalendarMutationValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=CalendarApiErrorResponse(
            detail=error.detail,
            code=error.code,
        ).model_dump(mode="json"),
    )


def _warning_response(
    error: CalendarExceptionRemovalRequiredError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ExceptionRemovalWarningResponse(
            detail=str(error),
            code="exception_removal_confirmation_required",
            removed_exception_original_dates=error.removed_original_dates,
        ).model_dump(mode="json"),
    )


def _not_found(error: CalendarEventNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="This calendar event is no longer available.",
    )


@router.get("/events", response_model=CalendarRangeResponse)
async def get_calendar_events(
    session: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    start_date: Annotated[str, Query()],
    end_date: Annotated[str, Query()],
) -> CalendarRangeResponse | JSONResponse:
    """Return effective event instances in one complete visible range."""

    parsed_start = _parse_query_date(start_date)
    parsed_end = _parse_query_date(end_date)
    if parsed_start > parsed_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid academy date range.",
        )
    if (parsed_end - parsed_start).days + 1 > MAX_CALENDAR_RANGE_DATES:
        return _range_error_response()

    try:
        return await CalendarService(session).get_range(parsed_start, parsed_end)
    except CalendarRangeTooLargeError:
        return _range_error_response()
    except CalendarRangeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid academy date range.",
        ) from error


@router.get("/today", response_model=CalendarTodayResponse)
async def get_calendar_today(
    session: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CalendarTodayResponse:
    """Return effective events for the current academy-local date."""

    return await CalendarService(session).get_today()


@router.get("/instances/{occurrence_id}", response_model=CalendarEventInstance)
async def get_calendar_instance(
    occurrence_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CalendarEventInstance:
    """Return one stable event instance for the shared details modal."""

    try:
        return await CalendarService(session).get_instance(occurrence_id)
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error


@router.post(
    "/events",
    response_model=CalendarEventDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_calendar_event(
    payload: CalendarEventCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> CalendarEventDefinitionResponse | JSONResponse:
    """Create a standalone event or recurring series atomically."""

    try:
        actor, _auth_session = current_user
        return await CalendarService(session).create_event(
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarMutationValidationError as error:
        return _validation_response(error)
    except CalendarStaleVersionError:
        return _stale_response()


@router.patch(
    "/events/{event_id}",
    response_model=CalendarEventDefinitionResponse,
)
async def update_standalone_calendar_event(
    event_id: UUID,
    payload: CalendarStandaloneUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> CalendarEventDefinitionResponse | JSONResponse:
    """Replace a non-recurring event using its canonical OCC version."""

    try:
        actor, _auth_session = current_user
        return await CalendarService(session).update_standalone(
            event_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error
    except CalendarMutationValidationError as error:
        return _validation_response(error)
    except CalendarStaleVersionError:
        return _stale_response()


@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_standalone_calendar_event(
    event_id: UUID,
    payload: CalendarEventDelete,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> Response | JSONResponse:
    """Hard-delete one standalone event after OCC verification."""

    try:
        actor, _auth_session = current_user
        await CalendarService(session).delete_standalone(
            event_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error
    except CalendarStaleVersionError:
        return _stale_response()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/instances/{occurrence_id}",
    response_model=CalendarEventInstance,
)
async def update_calendar_occurrence(
    occurrence_id: str,
    payload: CalendarOccurrenceUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> CalendarEventInstance | JSONResponse:
    """Persist one complete occurrence exception snapshot."""

    try:
        actor, _auth_session = current_user
        return await CalendarService(session).update_occurrence(
            occurrence_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error
    except CalendarMutationValidationError as error:
        return _validation_response(error)
    except CalendarStaleVersionError:
        return _stale_response()


@router.delete(
    "/instances/{occurrence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_calendar_occurrence(
    occurrence_id: str,
    payload: CalendarOccurrenceDelete,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> Response | JSONResponse:
    """Suppress one stable occurrence while retaining the series."""

    try:
        actor, _auth_session = current_user
        await CalendarService(session).delete_occurrence(
            occurrence_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error
    except CalendarStaleVersionError:
        return _stale_response()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/series/{series_id}",
    response_model=CalendarEventDefinitionResponse,
)
async def update_calendar_series(
    series_id: UUID,
    payload: CalendarSeriesUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> CalendarEventDefinitionResponse | JSONResponse:
    """Replace an entire series with confirmation-aware exception cleanup."""

    try:
        actor, _auth_session = current_user
        return await CalendarService(session).update_series(
            series_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error
    except CalendarExceptionRemovalRequiredError as error:
        return _warning_response(error)
    except CalendarMutationValidationError as error:
        return _validation_response(error)
    except CalendarStaleVersionError:
        return _stale_response()


@router.delete(
    "/series/{series_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_calendar_series(
    series_id: UUID,
    payload: CalendarEventDelete,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> Response | JSONResponse:
    """Hard-delete an entire series through the owning event cascade."""

    try:
        actor, _auth_session = current_user
        await CalendarService(session).delete_series(
            series_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except CalendarEventNotFoundError as error:
        raise _not_found(error) from error
    except CalendarStaleVersionError:
        return _stale_response()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
