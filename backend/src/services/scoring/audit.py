"""Bounded Business Audit adapters for allowlisted scoring commands."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from src.enums import (
    AuditActionType,
    AuditEntityType,
    MatchLifecycleState,
    MatchSideCode,
)
from src.models.match import Match
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.models.user import User
from src.services.business_audit_service import (
    AuditActorContext,
    AuditTargetContext,
    BusinessAuditService,
)


async def record_scoring_initialization(
    audit_service: BusinessAuditService,
    *,
    actor: User,
    match: Match,
    capability_profile: str,
    capability_version: int,
    innings_sequence: Sequence[MatchSideCode],
    participant_count: int,
    request_id: str | None = None,
) -> None:
    """Stage one safe scoring-initialization event in the caller transaction."""

    await audit_service.record_scoring_initialization(
        actor=AuditActorContext.from_user(actor, request_id=request_id),
        match_id=match.id,
        match_label=f"Match {match.match_date.isoformat()} at {match.venue}"[:255],
        capability_profile=capability_profile,
        capability_version=capability_version,
        innings_sequence=[value.value for value in innings_sequence],
        participant_count=participant_count,
    )


audit_scoring_initialization = record_scoring_initialization


async def record_innings_started(
    audit_service: BusinessAuditService,
    *,
    actor: User,
    match: Match,
    innings: Innings,
    request_id: str | None = None,
) -> None:
    """Stage one bounded Innings-start event owned by the command transaction."""

    await audit_service.record_scoring_innings_started(
        actor=AuditActorContext.from_user(actor, request_id=request_id),
        match_id=match.id,
        match_label=f"Match {match.match_date.isoformat()} at {match.venue}"[:255],
        innings_id=innings.id,
        innings_number=innings.innings_number,
        batting_side_id=innings.batting_side_id,
        fielding_side_id=innings.fielding_side_id,
    )


audit_innings_started = record_innings_started


async def record_delivery_corrected(
    audit_service: BusinessAuditService,
    *,
    actor: User,
    match: Match,
    innings: Innings,
    delivery_id: UUID,
    prior_revision_id: UUID,
    revision: DeliveryRevision,
    prior_lifecycle: MatchLifecycleState,
    request_id: str | None = None,
) -> None:
    """Record bounded supersession provenance within the correction transaction."""
    await audit_service.record(
        actor=AuditActorContext.from_user(actor, request_id=request_id),
        action_type=AuditActionType.SCORING_DELIVERY_CORRECTED,
        target=AuditTargetContext(
            entity_type=AuditEntityType.MATCH,
            entity_id=match.id,
            label=f"Match {match.match_date.isoformat()} at {match.venue}"[:255],
        ),
        metadata={
            "innings_id": str(innings.id),
            "delivery_id": str(delivery_id),
            "prior_revision_id": str(prior_revision_id),
            "revision_id": str(revision.id),
            "revision_number": revision.revision_number,
            "reason": revision.replacement_reason,
            "prior_lifecycle": prior_lifecycle.value,
            "final_lifecycle": str(match.lifecycle_state),
        },
    )
