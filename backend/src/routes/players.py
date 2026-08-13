"""HTTP routes for player profile management."""

from typing import Annotated, Never
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.player import (
    PaginatedPlayerResponse,
    PlayerCreate,
    PlayerResponse,
    PlayerUpdate,
)
from src.schemas.player_account import (
    PaginatedPlayerAccountResponse,
    PlayerAccountAssociationResponse,
    PlayerAccountLinkRequest,
    PlayerAccountLookupQuery,
    PlayerAccountReassignRequest,
    PlayerAccountUnlinkRequest,
)
from src.services.business_audit_service import AuditActorContext
from src.services.player_account_service import (
    PlayerAccountAuthorizationError,
    PlayerAccountConflictError,
    PlayerAccountNotFoundError,
    PlayerAccountService,
    PlayerAccountValidationError,
)
from src.services.player_service import (
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    PlayerService,
)

router = APIRouter(prefix="/players", tags=["players"])


def _raise_account_error(exc: Exception) -> Never:
    """Map account-association domain errors to stable API responses."""

    if isinstance(exc, PlayerAccountAuthorizationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    if isinstance(exc, PlayerAccountNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, PlayerAccountConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if isinstance(exc, PlayerAccountValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    raise exc


@router.post("", response_model=PlayerResponse, status_code=status.HTTP_201_CREATED)
async def create_player(
    payload: PlayerCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _write_access: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> PlayerResponse:
    """Create a player profile unless its identity is already registered."""

    try:
        actor, _auth_session = current_user
        player = await PlayerService(session).create_player(
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except PlayerAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A player with this name and date of birth already exists.",
        ) from exc
    return PlayerResponse.model_validate(player)


@router.get("", response_model=PaginatedPlayerResponse)
async def list_players(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    team_id: UUID | None = None,
    unassigned: bool = False,
    search: str | None = None,
) -> PaginatedPlayerResponse:
    """List a filtered page of active player profiles."""

    if team_id is not None and unassigned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="team_id and unassigned are mutually exclusive",
        )

    return await PlayerService(session).list_players(
        page=page,
        page_size=page_size,
        team_id=team_id,
        unassigned=unassigned,
        search=search,
    )


@router.get(
    "/account-linking/users",
    response_model=PaginatedPlayerAccountResponse,
)
async def list_eligible_player_accounts(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _head_coach: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
    search: Annotated[str | None, Query(max_length=255)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedPlayerAccountResponse:
    """List safe unlinked Player-role accounts for a Head Coach."""

    actor, _auth_session = current_user
    try:
        return await PlayerAccountService(session).list_eligible_accounts(
            PlayerAccountLookupQuery(
                search=search,
                page=page,
                page_size=page_size,
            ),
            actor=AuditActorContext.from_user(actor),
        )
    except Exception as exc:
        _raise_account_error(exc)


@router.get(
    "/{player_id}/account",
    response_model=PlayerAccountAssociationResponse,
)
async def get_player_account_association(
    player_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _head_coach: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
) -> PlayerAccountAssociationResponse:
    """Return a protected safe snapshot of one Player's linked account."""

    actor, _auth_session = current_user
    try:
        return await PlayerAccountService(session).get_association(
            player_id,
            actor=AuditActorContext.from_user(actor),
        )
    except Exception as exc:
        _raise_account_error(exc)


@router.put(
    "/{player_id}/account",
    response_model=PlayerAccountAssociationResponse,
)
async def link_player_account(
    player_id: UUID,
    payload: PlayerAccountLinkRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _head_coach: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> PlayerAccountAssociationResponse:
    """Associate one explicitly selected Player-role account."""

    actor, _auth_session = current_user
    try:
        return await PlayerAccountService(session).link_account(
            player_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except Exception as exc:
        _raise_account_error(exc)


@router.delete(
    "/{player_id}/account",
    response_model=PlayerAccountAssociationResponse,
)
async def unlink_player_account(
    player_id: UUID,
    payload: PlayerAccountUnlinkRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _head_coach: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> PlayerAccountAssociationResponse:
    """Remove one association after explicit frontend confirmation."""

    actor, _auth_session = current_user
    try:
        return await PlayerAccountService(session).unlink_account(
            player_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except Exception as exc:
        _raise_account_error(exc)


@router.post(
    "/{player_id}/account/reassign",
    response_model=PlayerAccountAssociationResponse,
)
async def reassign_player_account(
    player_id: UUID,
    payload: PlayerAccountReassignRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    _head_coach: Annotated[
        None,
        Depends(require_role(UserRole.HEAD_COACH)),
    ],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> PlayerAccountAssociationResponse:
    """Correct an exact existing association as one audited mutation."""

    actor, _auth_session = current_user
    try:
        return await PlayerAccountService(session).reassign_account(
            player_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except Exception as exc:
        _raise_account_error(exc)


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
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> PlayerResponse:
    """Update a player profile when its OCC version is current."""

    try:
        actor, _auth_session = current_user
        player = await PlayerService(session).update_player(
            player_id,
            payload,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except PlayerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found.",
        ) from exc
    return PlayerResponse.model_validate(player)
