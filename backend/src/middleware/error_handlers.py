"""Global exception handlers for API-safe error responses."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError

from src.services.occ import StaleVersionError

logger = logging.getLogger(__name__)


async def validation_error_handler(
    request: Request,
    exc: Exception,
) -> Response:
    """Use the coaches creation contract's field-oriented HTTP 400 response."""

    if not isinstance(exc, RequestValidationError):
        raise exc
    if (
        request.method == "POST"
        and request.url.path == "/api/v1/coaches"
    ):
        error = exc.errors()[0]
        field_path = ".".join(
            str(part) for part in error["loc"] if part != "body"
        )
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
