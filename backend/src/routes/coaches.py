"""Coach directory HTTP endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.coach import (
    CoachCreate,
    CoachCreateResponse,
    CoachResponse,
    PaginatedCoachResponse,
)
from src.services.coach_service import (
    CoachAlreadyExistsError,
    CoachNotFoundError,
    CoachService,
    CoachTeamValidationError,
)

router = APIRouter(prefix="/coaches", tags=["coaches"])


@router.post(
    "",
    response_model=CoachCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_coach(
    payload: CoachCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _head_coach_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
) -> CoachCreateResponse:
    """Create an Assistant Coach and return its password exactly once."""

    try:
        coach, temporary_password = await CoachService(session).create_coach(
            payload
        )
    except CoachTeamValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CoachAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return CoachCreateResponse(
        **coach.model_dump(),
        temporary_password=temporary_password,
    )


@router.get("", response_model=PaginatedCoachResponse)
async def list_coaches(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _coach_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    status: Annotated[Literal["active", "inactive", "all"], Query()] = "active",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
) -> PaginatedCoachResponse:
    """List coaches visible to a coach-role account."""

    del current_user
    return await CoachService(session).list_coaches(
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/{coach_id}", response_model=CoachResponse)
async def get_coach(
    coach_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _coach_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> CoachResponse:
    """Return one coach, withholding inactive details from Assistant Coaches."""

    try:
        coach = await CoachService(session).get_coach(coach_id)
    except CoachNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coach not found",
        ) from exc

    actor, _ = current_user
    if actor.role == UserRole.ASSISTANT_COACH and not coach.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
    return coach
