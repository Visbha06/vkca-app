"""HTTP routes for cricket team and roster management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.team import TeamCreate, TeamPlayerResponse, TeamResponse
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
) -> TeamResponse:
    """Create a cricket team."""

    team = await TeamService(session).create_team(payload)
    return TeamResponse.model_validate(team)


@router.get("", response_model=list[TeamResponse])
async def list_teams(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[TeamResponse]:
    """List all cricket teams."""

    teams = await TeamService(session).list_teams()
    return [TeamResponse.model_validate(team) for team in teams]


@router.post(
    "/{team_id}/players/{player_id}",
    response_model=TeamPlayerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_player_to_team(
    team_id: UUID,
    player_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TeamPlayerResponse:
    """Add a player to a team roster."""

    try:
        membership = await TeamService(session).add_player_to_team(
            team_id,
            player_id,
        )
    except (TeamNotFoundError, PlayerNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except TeamMembershipAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return TeamPlayerResponse.model_validate(membership)
