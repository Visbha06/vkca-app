"""HTTP routes for player profile management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.player import PlayerCreate, PlayerResponse, PlayerUpdate
from src.services.player_service import (
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    PlayerService,
)

router = APIRouter(prefix="/players", tags=["players"])


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(
    payload: PlayerCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> PlayerResponse:
    """Create a player profile unless its identity is already registered."""

    try:
        player = await PlayerService(session).create_player(payload)
    except PlayerAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A player with this name and date of birth already exists.",
        ) from exc
    return PlayerResponse.model_validate(player)


@router.get("", response_model=list[PlayerResponse])
async def list_players(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[PlayerResponse]:
    """List active player profiles."""

    players = await PlayerService(session).list_players()
    return [PlayerResponse.model_validate(player) for player in players]


@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player(
    player_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> PlayerResponse:
    """Retrieve an individual player, including inactive profiles."""

    try:
        player = await PlayerService(session).get_player_by_id(player_id)
    except PlayerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found.",
        ) from exc
    return PlayerResponse.model_validate(player)


@router.put("/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: UUID,
    payload: PlayerUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
) -> PlayerResponse:
    """Update a player profile when its OCC version is current."""

    try:
        player = await PlayerService(session).update_player(player_id, payload)
    except PlayerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found.",
        ) from exc
    return PlayerResponse.model_validate(player)
