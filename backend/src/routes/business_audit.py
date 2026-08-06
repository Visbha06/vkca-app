"""Head Coach-only read routes for academy business activity."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import require_role
from src.schemas.business_audit import (
    BusinessAuditActorOptionsResponse,
    BusinessAuditPageResponse,
    BusinessAuditQuery,
    BusinessAuditRecentQuery,
    RecentBusinessAuditResponse,
)
from src.services.business_audit_service import BusinessAuditService

router = APIRouter(prefix="/audit-log", tags=["business-audit"])

HeadCoachAccess = Annotated[None, Depends(require_role(UserRole.HEAD_COACH))]


@router.get("/recent", response_model=RecentBusinessAuditResponse)
async def get_recent_business_activity(
    session: Annotated[AsyncSession, Depends(get_db)],
    _head_coach_access: HeadCoachAccess,
    query: Annotated[BusinessAuditRecentQuery, Query()],
) -> RecentBusinessAuditResponse:
    """Return the latest one to four immutable business events."""

    return await BusinessAuditService(session).list_recent(limit=query.limit)


@router.get("/actors", response_model=BusinessAuditActorOptionsResponse)
async def get_business_audit_actor_options(
    session: Annotated[AsyncSession, Depends(get_db)],
    _head_coach_access: HeadCoachAccess,
) -> BusinessAuditActorOptionsResponse:
    """Return bounded, deduplicated historical actor snapshots."""

    return await BusinessAuditService(session).list_actor_options()


@router.get("", response_model=BusinessAuditPageResponse)
async def get_business_audit_log(
    session: Annotated[AsyncSession, Depends(get_db)],
    _head_coach_access: HeadCoachAccess,
    query: Annotated[BusinessAuditQuery, Query()],
) -> BusinessAuditPageResponse:
    """Return a validated, filtered, deterministic page of business events."""

    return await BusinessAuditService(session).list_events(query)
