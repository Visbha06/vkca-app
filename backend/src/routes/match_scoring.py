"""Protected Match-scoring command and query routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import AuthenticatedUser, get_current_user
from src.schemas.scoring import (
    MAX_SCORING_HISTORY_LIMIT,
    AppendDeliveryRequest,
    DeliveryHistoryResponse,
    DeliveryResponse,
    InningsResponse,
    MatchConfigurationRequest,
    MatchConfigurationResponse,
    NextBowlerResponse,
    RetiredHurtReturnRequest,
    RetireHurtRequest,
    SelectNextBatterRequest,
    SelectNextBowlerRequest,
    StartInningsRequest,
)
from src.services.match_service import MatchService
from src.services.scoring.service import ScoringService

match_scoring_router = APIRouter(prefix="/matches", tags=["match-scoring"])
router = match_scoring_router


@match_scoring_router.get(
    "/{match_id}/innings/{innings_id}/next-bowler",
    response_model=NextBowlerResponse,
)
async def read_next_bowler(
    match_id: UUID,
    innings_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> NextBowlerResponse:
    user, _auth_session = current_user
    return await ScoringService(session).get_next_bowler(match_id, innings_id, user)


@match_scoring_router.post(
    "/{match_id}/innings/{innings_id}/next-bowler",
    response_model=InningsResponse,
)
async def choose_next_bowler(
    match_id: UUID,
    innings_id: UUID,
    payload: SelectNextBowlerRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> InningsResponse:
    user, _auth_session = current_user
    return await ScoringService(session).select_next_bowler(
        match_id,
        innings_id,
        payload,
        user,
        request_id=request_id,
    )


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


@match_scoring_router.post("/{match_id}/innings", response_model=InningsResponse)
async def start_match_innings(
    match_id: UUID,
    payload: StartInningsRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> InningsResponse:
    user, _auth_session = current_user
    return await ScoringService(session).start_innings(
        match_id,
        payload,
        user,
        request_id=request_id,
    )


@match_scoring_router.get(
    "/{match_id}/innings/{innings_id}", response_model=InningsResponse
)
async def read_match_innings(
    match_id: UUID,
    innings_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> InningsResponse:
    user, _auth_session = current_user
    return await ScoringService(session).get_innings(match_id, innings_id, user)


@match_scoring_router.get(
    "/{match_id}/innings/{innings_id}/deliveries",
    response_model=DeliveryHistoryResponse,
)
async def read_delivery_history(
    match_id: UUID,
    innings_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    after_sequence: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_SCORING_HISTORY_LIMIT)] = 100,
) -> DeliveryHistoryResponse:
    user, _auth_session = current_user
    return await ScoringService(session).list_delivery_history(
        match_id,
        innings_id,
        user,
        after_sequence=after_sequence,
        limit=limit,
    )


@match_scoring_router.post(
    "/{match_id}/innings/{innings_id}/deliveries",
    response_model=DeliveryResponse,
)
async def append_match_delivery(
    match_id: UUID,
    innings_id: UUID,
    payload: AppendDeliveryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> DeliveryResponse:
    user, _auth_session = current_user
    return await ScoringService(session).append_delivery(
        match_id,
        innings_id,
        payload,
        user,
        request_id=request_id,
    )


@match_scoring_router.post(
    "/{match_id}/innings/{innings_id}/next-batter",
    response_model=InningsResponse,
)
async def choose_next_batter(
    match_id: UUID,
    innings_id: UUID,
    payload: SelectNextBatterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> InningsResponse:
    user, _auth_session = current_user
    return await ScoringService(session).select_next_batter(
        match_id, innings_id, payload, user
    )


@match_scoring_router.post(
    "/{match_id}/innings/{innings_id}/retired-hurt",
    response_model=InningsResponse,
)
async def retire_batter_hurt(
    match_id: UUID,
    innings_id: UUID,
    payload: RetireHurtRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> InningsResponse:
    user, _auth_session = current_user
    return await ScoringService(session).retire_hurt(
        match_id, innings_id, payload, user
    )


@match_scoring_router.post(
    "/{match_id}/innings/{innings_id}/retired-hurt-return",
    response_model=InningsResponse,
)
async def return_retired_hurt_batter(
    match_id: UUID,
    innings_id: UUID,
    payload: RetiredHurtReturnRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> InningsResponse:
    user, _auth_session = current_user
    return await ScoringService(session).retired_hurt_return(
        match_id, innings_id, payload, user
    )
