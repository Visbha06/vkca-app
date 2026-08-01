"""Authenticated read routes for the academy calendar."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import AuthenticatedUser, get_current_user
from src.schemas.calendar import (
    CalendarApiErrorResponse,
    CalendarEventInstance,
    CalendarRangeResponse,
    CalendarTodayResponse,
)
from src.services.calendar_recurrence import MAX_CALENDAR_RANGE_DATES
from src.services.calendar_service import (
    CalendarEventNotFoundError,
    CalendarRangeError,
    CalendarRangeTooLargeError,
    CalendarService,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This calendar event is no longer available.",
        ) from error
