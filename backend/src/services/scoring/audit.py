"""Bounded Business Audit adapters for allowlisted scoring commands."""

from __future__ import annotations

from collections.abc import Sequence

from src.enums import MatchSideCode
from src.models.match import Match
from src.models.scoring.innings import Innings
from src.models.user import User
from src.services.business_audit_service import (
    AuditActorContext,
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
