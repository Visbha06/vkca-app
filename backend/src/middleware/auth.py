"""FastAPI dependencies for access-token and session authentication."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.token_service import TokenService

AuthenticatedUser = tuple[User, AuthSession]
RoleDependency = Callable[[AuthenticatedUser], Awaitable[None]]
bearer_scheme = HTTPBearer(auto_error=False)


def _authentication_error() -> HTTPException:
    """Build the one response used for every access-authentication failure."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _session_is_active(auth_session: AuthSession) -> bool:
    """Return whether a session is neither revoked nor absolutely expired."""

    return auth_session.revoked_at is None and auth_session.expires_at > datetime.now(
        UTC
    )


async def _authenticate_access_token(
    credentials: HTTPAuthorizationCredentials | None,
    session: AsyncSession,
) -> AuthenticatedUser:
    """Resolve one bearer token to its active user and server-side session."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()

    try:
        claims = TokenService().decode_and_verify_access_token(credentials.credentials)
        user_id = UUID(claims["sub"])
        session_id = UUID(claims["sid"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise _authentication_error() from exc

    auth_session = await session.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
        )
    )
    if auth_session is None or not _session_is_active(auth_session):
        raise _authentication_error()

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise _authentication_error()
    return user, auth_session


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthenticatedUser:
    """Authenticate a request from its bearer JWT and active session row."""

    return await _authenticate_access_token(credentials, session)


def require_role(*roles: UserRole) -> RoleDependency:
    """Require the database-loaded user to hold one of the allowed roles.

    An empty role set intentionally denies access, keeping authorization rules
    default-deny. The JWT role claim is not consulted because role changes must
    take effect on the next request without issuing a new token.
    """

    async def role_dependency(
        authenticated: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> None:
        user, _ = authenticated
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized",
            )

    return role_dependency


async def get_logout_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> AuthenticatedUser:
    """Authenticate logout with access JWT, falling back to its refresh cookie."""

    if credentials is not None:
        try:
            return await _authenticate_access_token(credentials, session)
        except HTTPException:
            pass

    if not refresh_token:
        raise _authentication_error()

    token_hash = TokenService.hash_token(refresh_token)
    auth_session = await session.scalar(
        select(AuthSession).where(AuthSession.current_token_hash == token_hash)
    )
    if auth_session is None or not _session_is_active(auth_session):
        raise _authentication_error()

    user = await session.scalar(select(User).where(User.id == auth_session.user_id))
    if user is None or not user.is_active:
        raise _authentication_error()
    return user, auth_session
