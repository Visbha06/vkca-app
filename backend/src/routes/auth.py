"""HTTP routes for login, current-session inspection, and logout."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_db
from src.middleware.auth import AuthenticatedUser, get_current_user, get_logout_user
from src.schemas.auth import (
    CurrentSessionResponse,
    CurrentUserResponse,
    LoginRequest,
    TokenResponse,
)
from src.services.audit_service import AuditService
from src.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidSessionError,
)
from src.services.token_service import TokenService

AUTH_COOKIE_PATH = "/api/v1/auth"
SECONDS_PER_DAY = 24 * 60 * 60

router = APIRouter(prefix="/auth", tags=["auth"])


def _request_metadata(request: Request) -> tuple[str | None, str | None]:
    """Extract bounded client metadata suitable for session and audit columns."""

    ip_address = request.client.host[:45] if request.client is not None else None
    user_agent = request.headers.get("user-agent")
    return ip_address, user_agent[:512] if user_agent is not None else None


def _cookie_secure(request: Request) -> bool:
    """Use secure cookies whenever the externally visible request uses HTTPS."""

    return request.url.scheme == "https"


def _set_auth_cookies(
    response: Response,
    request: Request,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """Set refresh and double-submit CSRF cookies with matching scope."""

    max_age = get_settings().refresh_token_expire_days * SECONDS_PER_DAY
    response.set_cookie(
        "refresh_token",
        refresh_token,
        max_age=max_age,
        path=AUTH_COOKIE_PATH,
        secure=_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        max_age=max_age,
        path=AUTH_COOKIE_PATH,
        secure=_cookie_secure(request),
        httponly=False,
        samesite="lax",
    )


def _clear_auth_cookies(response: Response, request: Request) -> None:
    """Expire both authentication cookies using their original attributes."""

    response.delete_cookie(
        "refresh_token",
        path=AUTH_COOKIE_PATH,
        secure=_cookie_secure(request),
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        "csrf_token",
        path=AUTH_COOKIE_PATH,
        secure=_cookie_secure(request),
        httponly=False,
        samesite="lax",
    )


def _validate_csrf_token(request: Request) -> None:
    """Reject cookie-authenticated mutations without a matching CSRF token."""

    if not TokenService.verify_csrf_token(
        request.headers.get("X-CSRF-Token"),
        request.cookies.get("csrf_token"),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )


def _invalid_session_error() -> HTTPException:
    """Build the generic refresh-session authentication response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate credentials and establish a browser session."""

    ip_address, user_agent = _request_metadata(request)
    try:
        _, _, access_token, refresh_token, csrf_token = await AuthService(
            session
        ).login(
            payload.email,
            payload.password,
            ip_address,
            user_agent,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        ) from exc

    _set_auth_cookies(response, request, refresh_token, csrf_token)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rotate a valid refresh session and issue a new access token."""

    _validate_csrf_token(request)
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise _invalid_session_error()

    ip_address, user_agent = _request_metadata(request)
    try:
        access_token, new_refresh_token, new_csrf_token = await AuthService(
            session
        ).refresh(
            refresh_token,
            ip_address,
            user_agent,
        )
    except InvalidSessionError as exc:
        raise _invalid_session_error() from exc

    _set_auth_cookies(
        response,
        request,
        new_refresh_token,
        new_csrf_token,
    )
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Return the authenticated profile and current-session metadata."""

    user, auth_session = current
    return CurrentUserResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        session=CurrentSessionResponse(
            session_id=auth_session.id,
            created_at=auth_session.created_at,
            last_used_at=auth_session.last_used_at,
            expires_at=auth_session.expires_at,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current: Annotated[AuthenticatedUser, Depends(get_logout_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Revoke only the current server-side session and clear its cookies."""

    _validate_csrf_token(request)
    user, auth_session = current
    ip_address, user_agent = _request_metadata(request)
    auth_session.revoked_at = datetime.now(UTC)
    auth_session.revocation_reason = "logout"
    await AuditService.log_event(
        session,
        "logout",
        user_id=user.id,
        session_id=auth_session.id,
        result="success",
        ip_address=ip_address,
        user_agent=user_agent,
        target_resource="/api/v1/auth/logout",
    )
    await session.commit()
    _clear_auth_cookies(response, request)
