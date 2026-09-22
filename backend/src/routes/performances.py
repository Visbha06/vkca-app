"""HTTP route for atomic match performance submissions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.performance import (
    BatchPerformanceRequest,
    BatchPerformanceResponse,
    MatchPerformanceResponse,
)
from src.services.performance_service import (
    MatchNotFoundError,
    PerformanceService,
    PlayerNotFoundError,
)

router = APIRouter(prefix="/matches", tags=["performances"])


@router.get("/{match_id}/performances", response_model=MatchPerformanceResponse)
async def read_match_performances(
    match_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> MatchPerformanceResponse:
    """Read legacy aggregates or delivery-derived participant projections."""

    try:
        return await PerformanceService(session).get_match_performances(
            match_id, current_user[0]
        )
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{match_id}/performances",
    response_model=BatchPerformanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_batch_performance(
    match_id: UUID,
    payload: BatchPerformanceRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> BatchPerformanceResponse:
    """Submit a validated performance batch in one transaction."""

    try:
        return await PerformanceService(session).submit_batch_performance(
            match_id,
            payload.performances,
            current_user[0],
        )
    except (MatchNotFoundError, PlayerNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
