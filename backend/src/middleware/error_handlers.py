"""Global exception handlers for API-safe error responses."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError

from src.schemas.calendar import CalendarApiErrorResponse, CalendarErrorCode
from src.services.occ import StaleVersionError

logger = logging.getLogger(__name__)


def _calendar_validation_error(
    exc: RequestValidationError,
) -> CalendarApiErrorResponse:
    """Convert calendar schema failures into stable, non-sensitive errors."""

    errors = exc.errors()
    locations = {
        str(part) for error in errors for part in error.get("loc", ()) if part != "body"
    }
    messages = " ".join(str(error.get("msg", "")) for error in errors).lower()
    code: CalendarErrorCode | None = None
    detail = "Check the calendar details and try again."

    if "recurrence" in locations:
        code = "calendar_recurrence_invalid"
        detail = "Check the recurrence details and try again."
    elif "scope" in locations or "age_groups" in locations:
        code = "calendar_scope_invalid"
        detail = "Select at least one age group or choose All Academy."
    elif "has not passed" in messages:
        code = "calendar_event_in_past"
        detail = "Choose an academy date and time that has not passed."
    elif locations.intersection({"start_time", "end_time", "is_all_day"}) or any(
        phrase in messages
        for phrase in (
            "all-day",
            "all day",
            "end time",
            "start and end times",
            "wall-clock",
        )
    ):
        code = "calendar_event_times_invalid"
        detail = "Enter a start time and a later end time on the same academy day."

    return CalendarApiErrorResponse(detail=detail, code=code)


async def validation_error_handler(
    request: Request,
    exc: Exception,
) -> Response:
    """Use coach mutation contracts' field-oriented HTTP 400 response."""

    if not isinstance(exc, RequestValidationError):
        raise exc
    if request.url.path.startswith("/api/v1/calendar"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_calendar_validation_error(exc).model_dump(mode="json"),
        )
    is_coach_creation = (
        request.method == "POST" and request.url.path == "/api/v1/coaches"
    )
    is_assignment_update = (
        request.method == "PUT"
        and request.url.path.startswith("/api/v1/coaches/")
        and request.url.path.endswith("/teams")
    )
    if is_coach_creation or is_assignment_update:
        error = exc.errors()[0]
        field_path = ".".join(str(part) for part in error["loc"] if part != "body")
        detail = f"{field_path}: {error['msg']}" if field_path else error["msg"]
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": detail},
        )
    return await request_validation_exception_handler(request, exc)


async def stale_version_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return HTTP 409 for optimistic-concurrency conflicts."""

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def integrity_error_handler(
    _request: Request,
    _exc: Exception,
) -> JSONResponse:
    """Return HTTP 409 for database constraint conflicts."""

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "The request conflicts with an existing record."},
    )


async def unhandled_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Log unexpected failures and return a non-sensitive HTTP 500 response."""

    logger.error(
        "Unhandled application exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register application-wide exception-to-response mappings."""

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StaleVersionError, stale_version_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
