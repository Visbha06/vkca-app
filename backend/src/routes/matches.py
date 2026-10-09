"""HTTP routes for cricket match management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.match import MatchCreate, MatchResponse, MatchUpdate
from src.services.match_service import (
    MatchNotFoundError,
    MatchService,
    TeamNotFoundError,
)
from src.services.occ import StaleVersionError
from src.services.scoring.authorization import load_scoring_command_context

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def create_match(
    payload: MatchCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> MatchResponse:
    """Record a cricket match."""

    try:
        match = await MatchService(session).create_match(payload)
    except TeamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return MatchResponse.from_match(match)


@router.get("", response_model=list[MatchResponse])
async def list_matches(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[MatchResponse]:
    """List all recorded cricket matches."""

    matches = await MatchService(session).list_matches()
    return [MatchResponse.from_match(match) for match in matches]


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> MatchResponse:
    """Read one Match after applying current database Team scope."""

    try:
        match = await MatchService(session).get_match(match_id)
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    context = await load_scoring_command_context(session, current_user[0])
    context.require_read_scope(
        {
            team_id
            for team_id in (match.home_team_id, match.away_team_id)
            if team_id is not None
        }
    )
    return MatchResponse.from_match(match)


@router.put("/{match_id}", response_model=MatchResponse)
async def update_match(
    match_id: UUID,
    payload: MatchUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> MatchResponse:
    """Completely replace a Match when the submitted version remains current."""

    try:
        match = await MatchService(session).update_match(match_id, payload)
    except (MatchNotFoundError, TeamNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return MatchResponse.from_match(match)
