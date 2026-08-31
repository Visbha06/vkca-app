"""Transactional Match-scoring application commands."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import (
    BlockingReasonCode,
    BlockingStateKind,
    MatchLifecycleState,
    MatchParticipantKind,
    MatchParticipantType,
    MatchResultCode,
    MatchSideCode,
    MatchSideKind,
    ScoringAuthority,
)
from src.models.match import Match
from src.models.scoring.match_side import MatchSide
from src.models.scoring.participant import MatchParticipant
from src.models.user import User
from src.schemas.scoring import (
    BlockingStateResponse,
    MatchConfigurationRequest,
    MatchConfigurationResponse,
    MatchParticipantResponse,
    MatchSideResponse,
    ScoringPolicyResponse,
)
from src.services.business_audit_service import BusinessAuditService
from src.services.occ import check_and_increment_version
from src.services.scoring.audit import record_scoring_initialization
from src.services.scoring.authorization import (
    ScoringAuthorizationAdapter,
    require_configuration_scope,
)
from src.services.scoring.errors import (
    ScoringAuthorityError,
    ScoringLifecycleError,
    ScoringValidationError,
    ScoringVisibilityError,
)
from src.services.scoring.policy import resolve_format_capability


def _configuration_response(match: Match) -> MatchConfigurationResponse:
    if match.scoring_policy is None or match.configured_at is None:
        raise ScoringAuthorityError("Match scoring configuration is not locked.")
    sides = sorted(match.scoring_sides, key=lambda side: str(side.side_code))
    side_codes = {side.id: str(side.side_code) for side in sides}
    participants = sorted(
        match.scoring_participants,
        key=lambda item: (
            side_codes.get(item.side_id, ""),
            item.batting_order_position,
            str(item.id),
        ),
    )
    return MatchConfigurationResponse(
        match_id=match.id,
        match_version_number=match.version_number,
        lifecycle_state=match.lifecycle_state,
        scoring_authority=match.scoring_authority,
        configured_at=match.configured_at,
        policy=ScoringPolicyResponse.model_validate(match.scoring_policy),
        sides=[MatchSideResponse.model_validate(side) for side in sides],
        participants=[
            MatchParticipantResponse.model_validate(participant)
            for participant in participants
        ],
        blocking_state=BlockingStateResponse(
            kind=BlockingStateKind.INNINGS_NOT_STARTED,
            is_blocked=True,
            reason_code=BlockingReasonCode.INNINGS_NOT_STARTED,
        ),
    )


class ScoringService:
    """Own Match-scoped scoring transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_match(self, match_id: UUID) -> Match:
        statement = (
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.scoring_policy),
                selectinload(Match.scoring_sides),
                selectinload(Match.scoring_participants),
                selectinload(Match.scoring_innings),
            )
            .where(Match.id == match_id)
            .execution_options(populate_existing=True)
        )
        match = (await self.session.scalars(statement)).one_or_none()
        if match is None:
            raise ScoringVisibilityError("Match not found.")
        return match

    @staticmethod
    def _validate_match_identity(
        match: Match,
        payload: MatchConfigurationRequest,
    ) -> dict[MatchSideCode, UUID | None]:
        """Require scoring sides to describe the existing Match exactly."""

        if match.format != payload.format:
            raise ScoringValidationError(
                "Scoring format must match the existing Match format."
            )
        sides = {side.side_code: side for side in payload.sides}
        participant_type = MatchParticipantType(match.participant_type)
        if participant_type is MatchParticipantType.INTERNAL:
            expected = {
                MatchSideCode.HOME: match.home_team_id,
                MatchSideCode.AWAY: match.away_team_id,
            }
            if any(
                sides[code].side_kind is not MatchSideKind.ACADEMY
                or sides[code].team_id != team_id
                for code, team_id in expected.items()
            ):
                raise ScoringValidationError(
                    "Configured academy sides must match the existing internal Match."
                )
            return expected

        academy_code = (
            MatchSideCode.HOME if match.home_team_id is not None else MatchSideCode.AWAY
        )
        external_code = (
            MatchSideCode.AWAY
            if academy_code is MatchSideCode.HOME
            else MatchSideCode.HOME
        )
        academy_team_id = match.home_team_id or match.away_team_id
        academy_side = sides[academy_code]
        external_side = sides[external_code]
        if (
            academy_side.side_kind is not MatchSideKind.ACADEMY
            or academy_side.team_id != academy_team_id
            or external_side.side_kind is not MatchSideKind.EXTERNAL
            or external_side.team_id is not None
            or external_side.display_name != match.external_opponent_name
        ):
            raise ScoringValidationError(
                "Configured sides must match the existing external Match."
            )
        return {academy_code: academy_team_id, external_code: None}

    @staticmethod
    def _validate_lockable(match: Match) -> None:
        authority = ScoringAuthority(match.scoring_authority)
        if (
            authority is not ScoringAuthority.LEGACY_AGGREGATE
            or match.configured_at is not None
            or match.scoring_policy is not None
            or match.scoring_sides
            or match.scoring_participants
        ):
            raise ScoringAuthorityError(
                "Match scoring configuration is already locked."
            )
        lifecycle = MatchLifecycleState(match.lifecycle_state)
        if lifecycle is not MatchLifecycleState.SCHEDULED:
            raise ScoringLifecycleError(
                "Only a scheduled Match can be configured for scoring."
            )
        if match.scoring_innings:
            raise ScoringLifecycleError(
                "A Match with an Innings cannot be reconfigured."
            )

    async def configure_match(
        self,
        match_id: UUID,
        payload: MatchConfigurationRequest,
        authenticated_user: User | UUID,
        *,
        request_id: str | None = None,
    ) -> MatchConfigurationResponse:
        """Atomically lock sides, participants, batting order, and capability."""

        try:
            authorization = ScoringAuthorizationAdapter(self.session)
            context = await authorization.load_context(authenticated_user)
            match = await self._load_match(match_id)
            self._validate_lockable(match)
            team_by_side = self._validate_match_identity(match, payload)
            academy_team_ids = {
                team_id for team_id in team_by_side.values() if team_id is not None
            }
            require_configuration_scope(context, academy_team_ids)
            capability = resolve_format_capability(payload.policy)
            if set(capability.innings_sequence) != set(team_by_side):
                raise ScoringValidationError(
                    "innings_sequence must use both configured side codes."
                )

            participant_team_assignments = {
                participant.player_id: team_by_side[participant.side_code]
                for participant in payload.participants
                if participant.participant_kind is MatchParticipantKind.INTERNAL
                and participant.player_id is not None
                and team_by_side[participant.side_code] is not None
            }
            players = await authorization.load_eligible_internal_players(
                {
                    player_id: team_id
                    for player_id, team_id in participant_team_assignments.items()
                    if team_id is not None
                }
            )

            next_version = await check_and_increment_version(
                self.session,
                Match,
                match.id,
                payload.match_version_number,
            )
            side_models: dict[MatchSideCode, MatchSide] = {}
            for side_request in payload.sides:
                team = (
                    match.home_team
                    if side_request.team_id == match.home_team_id
                    else match.away_team
                )
                display_name = (
                    team.name
                    if side_request.side_kind is MatchSideKind.ACADEMY and team
                    else side_request.display_name
                )
                if not display_name:
                    raise ScoringValidationError("Every side requires a display name.")
                side = MatchSide(
                    match_id=match.id,
                    side_code=side_request.side_code,
                    side_kind=side_request.side_kind,
                    team_id=side_request.team_id,
                    display_name_snapshot=display_name,
                )
                self.session.add(side)
                side_models[side_request.side_code] = side
            await self.session.flush()

            policy = capability.to_model(match.id)
            self.session.add(policy)
            for participant_request in payload.participants:
                player = (
                    players.get(participant_request.player_id)
                    if participant_request.player_id is not None
                    else None
                )
                display_name = (
                    f"{player.first_name} {player.last_name}".strip()
                    if player is not None
                    else participant_request.display_name
                )
                if not display_name:
                    raise ScoringValidationError(
                        "Every participant requires a display name."
                    )
                self.session.add(
                    MatchParticipant(
                        match_id=match.id,
                        side_id=side_models[participant_request.side_code].id,
                        participant_kind=participant_request.participant_kind,
                        player_id=participant_request.player_id,
                        display_name_snapshot=display_name,
                        batting_order_position=(
                            participant_request.batting_order_position
                        ),
                    )
                )

            match.version_number = next_version
            match.scoring_authority = ScoringAuthority.DELIVERY_HISTORY
            match.lifecycle_state = MatchLifecycleState.SCHEDULED
            match.result_code = MatchResultCode.PENDING
            match.result_details = {}
            match.configured_at = datetime.now(UTC)
            await record_scoring_initialization(
                BusinessAuditService(self.session),
                actor=context.user,
                match=match,
                capability_profile=capability.capability_profile.value,
                capability_version=capability.capability_version,
                innings_sequence=capability.innings_sequence,
                participant_count=len(payload.participants),
                request_id=request_id,
            )
            await self.session.commit()
            return _configuration_response(await self._load_match(match.id))
        except Exception:
            await self.session.rollback()
            raise

    async def configure_scoring(
        self,
        match_id: UUID,
        payload: MatchConfigurationRequest,
        authenticated_user: User | UUID,
        *,
        request_id: str | None = None,
    ) -> MatchConfigurationResponse:
        """Alias retaining the command name used by the MatchService seam."""

        return await self.configure_match(
            match_id,
            payload,
            authenticated_user,
            request_id=request_id,
        )


async def configure_match(
    session: AsyncSession,
    match_id: UUID,
    payload: MatchConfigurationRequest,
    authenticated_user: User | UUID,
    *,
    request_id: str | None = None,
) -> MatchConfigurationResponse:
    """Public functional configuration command."""

    return await ScoringService(session).configure_match(
        match_id,
        payload,
        authenticated_user,
        request_id=request_id,
    )


async def configure_scoring(
    session: AsyncSession,
    match_id: UUID,
    payload: MatchConfigurationRequest,
    authenticated_user: User | UUID,
    *,
    request_id: str | None = None,
) -> MatchConfigurationResponse:
    """Public synonym for callers rooted at the existing MatchService."""

    return await configure_match(
        session,
        match_id,
        payload,
        authenticated_user,
        request_id=request_id,
    )
