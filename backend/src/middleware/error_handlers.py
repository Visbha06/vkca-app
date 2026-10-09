"""Global exception handlers for API-safe error responses."""

import logging
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError

from src.schemas.calendar import CalendarApiErrorResponse, CalendarErrorCode
from src.schemas.scoring import (
    ScoringErrorCode,
    ScoringErrorResponse,
    ScoringFieldError,
)
from src.services.occ import StaleVersionError
from src.services.scoring.errors import ScoringDomainError

logger = logging.getLogger(__name__)


def _is_scoring_path(request: Request) -> bool:
    """Identify only the Match subresources owned by the scoring router."""

    parts = request.url.path.strip("/").split("/")
    return (
        len(parts) >= 5
        and parts[:3] == ["api", "v1", "matches"]
        and parts[4] in {"configuration", "innings", "scorecard", "completion"}
    )


def _request_id(request: Request) -> str | None:
    """Return a bounded caller correlation ID when one is present."""

    value = request.headers.get("X-Request-ID")
    return value[:128] if value else None


def _scoring_error_response(
    request: Request,
    *,
    status_code: int,
    code: ScoringErrorCode,
    detail: str,
    field_errors: list[ScoringFieldError] | None = None,
) -> JSONResponse:
    """Serialize the stable repository-compatible scoring error envelope."""

    body = ScoringErrorResponse(
        detail=detail[:500],
        code=code,
        request_id=_request_id(request),
        field_errors=field_errors or [],
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


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
    if _is_scoring_path(request):
        field_errors = [
            ScoringFieldError(
                field=".".join(
                    str(part) for part in error.get("loc", ()) if part != "body"
                )
                or "body",
                message=str(error.get("msg", "Invalid value."))[:500],
            )
            for error in exc.errors()[:50]
        ]
        return _scoring_error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="scoring_validation_failed",
            detail="Check the scoring request and try again.",
            field_errors=field_errors,
        )
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
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return HTTP 409 for optimistic-concurrency conflicts."""

    if _is_scoring_path(request):
        return _scoring_error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="scoring_version_conflict",
            detail=str(exc),
        )

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def integrity_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return HTTP 409 for database constraint conflicts."""

    if _is_scoring_path(request):
        constraint_name = str(
            getattr(
                getattr(getattr(exc, "orig", None), "diag", None), "constraint_name", ""
            )
            or ""
        )
        code: ScoringErrorCode = "scoring_conflict"
        if "attempted_sequence" in constraint_name:
            code = "scoring_sequence_conflict"
        elif "delivery_revisions" in constraint_name:
            code = "scoring_revision_conflict"
        return _scoring_error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code=code,
            detail="The scoring request conflicts with the current record.",
        )

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "The request conflicts with an existing record."},
    )


async def scoring_domain_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Translate typed scoring failures without leaking hidden resources."""

    if not isinstance(exc, ScoringDomainError):
        raise exc
    return _scoring_error_response(
        request,
        status_code=exc.status_code,
        code=cast(ScoringErrorCode, exc.code),
        detail=exc.detail,
        field_errors=[
            ScoringFieldError(field=item.field, message=item.message)
            for item in exc.field_errors
        ],
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
    app.add_exception_handler(ScoringDomainError, scoring_domain_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
