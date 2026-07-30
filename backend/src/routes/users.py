"""HTTP routes for authenticated user account administration."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.models.user import User
from src.schemas.coach import CoachStatusUpdate
from src.schemas.user import (
    UserCreate,
    UserPasswordChange,
    UserResponse,
    UserRoleUpdate,
)
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.occ import check_and_increment_version
from src.services.password_service import PasswordService
from src.services.user_service import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)

router = APIRouter(prefix="/users", tags=["users"])


async def _find_user(session: AsyncSession, user_id: UUID) -> User:
    """Load a target account or return the user-management 404 response."""

    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _require_hc: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
) -> UserResponse:
    """Create a user with a server-generated Argon2id password hash."""

    try:
        user = await UserService(session).create_user(payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    _require_hc: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
) -> list[UserResponse]:
    """List all accounts for an authenticated head coach."""

    users = await UserService(session).list_users()
    return [UserResponse.model_validate(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _require_hc: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
) -> UserResponse:
    """Change an account's effective role as a head coach."""

    user = await _find_user(session, user_id)
    previous_role = user.role
    user.role = payload.role
    user.version_number += 1
    await AuditService.log_event(
        session,
        "role_change",
        user_id=user.id,
        result="success",
        reason=f"{previous_role}_to_{payload.role.value}",
        target_resource=f"/api/v1/users/{user.id}/role",
    )
    await session.commit()
    return UserResponse.model_validate(user)


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _require_hc: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
    authenticated: Annotated[
        AuthenticatedUser | None,
        Depends(get_current_user),
    ] = None,
    payload: CoachStatusUpdate | None = None,
) -> UserResponse:
    """Disable an account and revoke all of its active sessions."""

    actor = authenticated[0] if authenticated is not None else None
    if actor is not None and actor.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    user = await _find_user(session, user_id)
    try:
        if payload is None:
            user.version_number += 1
        else:
            user.version_number = await check_and_increment_version(
                session,
                User,
                user_id,
                payload.version_number,
            )
        user.is_active = False
        await AuthService(session).revoke_user_sessions(
            user.id,
            reason="user_disabled",
            target_resource=f"/api/v1/users/{user.id}/disable",
        )
        await AuditService.log_event(
            session,
            "user_disablement",
            user_id=user.id,
            result="success",
            target_resource=f"/api/v1/users/{user.id}/disable",
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/reactivate", response_model=UserResponse)
async def reactivate_user(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _require_hc: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
    payload: CoachStatusUpdate | None = None,
) -> UserResponse:
    """Reactivate an account without restoring revoked sessions."""

    try:
        user = await UserService(session).reactivate_user(
            user_id,
            None if payload is None else payload.version_number,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


@router.post(
    "/{user_id}/revoke-sessions",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_user_sessions(
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _require_hc: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
) -> Response:
    """Revoke every active session for an account as a head coach."""

    user = await _find_user(session, user_id)
    await AuthService(session).revoke_user_sessions(
        user.id,
        reason="admin_revocation",
        target_resource=f"/api/v1/users/{user.id}/revoke-sessions",
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{user_id}/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def change_user_password(
    user_id: UUID,
    payload: UserPasswordChange,
    session: Annotated[AsyncSession, Depends(get_db)],
    authenticated: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Response:
    """Change a password as the account owner or a head coach."""

    actor, _ = authenticated
    if actor.id != user_id and actor.role != UserRole.HEAD_COACH:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    user = await _find_user(session, user_id)
    user.hashed_password = PasswordService.hash_password(payload.new_password)
    user.version_number += 1
    await AuthService(session).revoke_user_sessions(
        user.id,
        reason="password_change",
        target_resource=f"/api/v1/users/{user.id}/change-password",
    )
    await AuditService.log_event(
        session,
        "password_change",
        user_id=user.id,
        result="success",
        target_resource=f"/api/v1/users/{user.id}/change-password",
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
