"""Global exception handlers for API-safe error responses."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from src.services.occ import StaleVersionError

logger = logging.getLogger(__name__)


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

    app.add_exception_handler(StaleVersionError, stale_version_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
