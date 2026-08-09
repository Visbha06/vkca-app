"""Head Coach-only current-state Data Quality read routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import require_role
from src.schemas.data_quality import DataQualityPageResponse, DataQualityQuery
from src.services.data_quality_service import DataQualityService

router = APIRouter(prefix="/data-quality", tags=["data-quality"])

HeadCoachAccess = Annotated[None, Depends(require_role(UserRole.HEAD_COACH))]


@router.get("", response_model=DataQualityPageResponse)
async def get_data_quality(
    session: Annotated[AsyncSession, Depends(get_db)],
    _head_coach_access: HeadCoachAccess,
    query: Annotated[DataQualityQuery, Query()],
) -> DataQualityPageResponse:
    """Return one bounded findings page without creating an audit event."""

    return await DataQualityService(session).list_findings(query)
