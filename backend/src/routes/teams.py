"""HTTP routes for cricket team summaries and roster retrieval."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.team import (
    PaginatedTeamResponse,
    TeamCreate,
    TeamPlayerResponse,
    TeamResponse,
    TeamRosterResponse,
)
from src.services.team_service import (
    PlayerNotFoundError,
    TeamMembershipAlreadyExistsError,
    TeamNotFoundError,
    TeamService,
)

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> TeamResponse:
    """Create a team; atomic roster creation is scheduled for phase five."""

    team = await TeamService(session).create_team(payload)
    return TeamResponse.model_validate(team)


@router.get("", response_model=PaginatedTeamResponse)
async def list_teams(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
) -> PaginatedTeamResponse:
    """List team summaries with server-side pagination."""

    return await TeamService(session).list_teams(page=page, page_size=page_size)


@router.get("/{team_id}/players", response_model=TeamRosterResponse)
async def get_team_roster(
    team_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> TeamRosterResponse:
    """Retrieve an ordered team roster, including inactive players."""

    try:
        return await TeamService(session).get_team_roster(team_id)
    except TeamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{team_id}/players/{player_id}",
    response_model=TeamPlayerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_player_to_team(
    team_id: UUID,
    player_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> TeamPlayerResponse:
    """Add a player to a team roster (legacy endpoint)."""

    try:
        membership = await TeamService(session).add_player_to_team(team_id, player_id)
    except (TeamNotFoundError, PlayerNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except TeamMembershipAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return TeamPlayerResponse.model_validate(membership)
