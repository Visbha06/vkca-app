"""HTTP routes for cricket match management."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.match import MatchCreate, MatchResponse
from src.services.match_service import MatchService

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def create_match(
    payload: MatchCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MatchResponse:
    """Record a cricket match."""

    match = await MatchService(session).create_match(payload)
    return MatchResponse.model_validate(match)


@router.get("", response_model=list[MatchResponse])
async def list_matches(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MatchResponse]:
    """List all recorded cricket matches."""

    matches = await MatchService(session).list_matches()
    return [MatchResponse.model_validate(match) for match in matches]
