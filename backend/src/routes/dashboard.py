"""Authenticated current-user dashboard route."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import AuthenticatedUser, get_current_user
from src.schemas.dashboard import DashboardResponse, RoleAwareApiErrorResponse
from src.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "",
    response_model=DashboardResponse,
    operation_id="get_role_aware_dashboard",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": RoleAwareApiErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": RoleAwareApiErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": RoleAwareApiErrorResponse
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": RoleAwareApiErrorResponse
        },
    },
)
async def get_dashboard(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DashboardResponse:
    """Return only the authenticated User's server-derived dashboard scope."""

    if request.query_params:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Dashboard scope parameters are not accepted.",
        )
    user, _auth_session = current_user
    return await DashboardService(session).get_dashboard(user)
