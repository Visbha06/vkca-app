"""Protected Match-scoring command and query routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import AuthenticatedUser, get_current_user
from src.schemas.scoring import MatchConfigurationRequest, MatchConfigurationResponse
from src.services.match_service import MatchService

match_scoring_router = APIRouter(prefix="/matches", tags=["match-scoring"])
router = match_scoring_router


@match_scoring_router.put(
    "/{match_id}/configuration",
    response_model=MatchConfigurationResponse,
)
async def configure_match_scoring(
    match_id: UUID,
    payload: MatchConfigurationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> MatchConfigurationResponse:
    """Lock one Match's scoring policy, side snapshots, and batting order."""

    user, _auth_session = current_user
    return await MatchService(session).configure_scoring(
        match_id,
        payload,
        user,
        request_id=request_id,
    )
