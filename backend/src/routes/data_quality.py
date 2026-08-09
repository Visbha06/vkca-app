"""Head Coach-only current-state Data Quality read and remediation routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import UserRole
from src.middleware.auth import AuthenticatedUser, get_current_user, require_role
from src.schemas.data_quality import (
    DataQualityPageResponse,
    DataQualityQuery,
    DataQualityRemediationRequest,
    DataQualityRemediationResult,
)
from src.services.business_audit_service import AuditActorContext
from src.services.coach_service import (
    CoachNotFoundError,
    CoachRemediationConflictError,
    CoachTeamValidationError,
)
from src.services.data_quality_service import (
    DataQualityRemediationConflictError,
    DataQualityRemediationValidationError,
    DataQualityService,
)
from src.services.occ import StaleVersionError
from src.services.team_service import (
    PlayerNotFoundError,
    TeamNotFoundError,
    TeamRemediationConflictError,
    TeamValidationError,
)

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


@router.post(
    "/remediations",
    response_model=DataQualityRemediationResult,
    operation_id="apply_data_quality_remediation",
)
async def apply_data_quality_remediation(
    command: DataQualityRemediationRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    _head_coach_access: HeadCoachAccess,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> DataQualityRemediationResult:
    """Apply one exact correction through its normal domain transaction."""

    actor, _auth_session = current_user
    try:
        return await DataQualityService(session).remediate(
            command,
            actor=AuditActorContext.from_user(actor, request_id=x_request_id),
        )
    except (
        DataQualityRemediationValidationError,
        TeamValidationError,
        CoachTeamValidationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (TeamNotFoundError, PlayerNotFoundError, CoachNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        DataQualityRemediationConflictError,
        TeamRemediationConflictError,
        CoachRemediationConflictError,
        StaleVersionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
