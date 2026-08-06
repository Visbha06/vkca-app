"""HTTP routes for cricket team summaries and roster retrieval."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
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
    TeamUpdate,
)
from src.services.business_audit_service import AuditActorContext
from src.services.occ import StaleVersionError
from src.services.team_service import (
    PlayerNotFoundError,
    TeamMembershipAlreadyExistsError,
    TeamNameConflictError,
    TeamNotFoundError,
    TeamService,
    TeamValidationError,
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
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> TeamResponse:
    """Create a team and its complete ordered roster atomically."""

    try:
        actor, _auth_session = current_user
        return await TeamService(session).create_team(
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except TeamValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PlayerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TeamNameConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    payload: TeamUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> TeamResponse:
    """Atomically replace team details and roster when its version is current."""

    try:
        actor, _auth_session = current_user
        return await TeamService(session).update_team(
            team_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except TeamValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (TeamNotFoundError, PlayerNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (TeamNameConflictError, StaleVersionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


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
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> TeamPlayerResponse:
    """Add a player to a team roster (legacy endpoint)."""

    try:
        actor, _auth_session = current_user
        membership = await TeamService(session).add_player_to_team(
            team_id,
            player_id,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except (TeamNotFoundError, PlayerNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except TeamMembershipAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return TeamPlayerResponse.model_validate(membership)
