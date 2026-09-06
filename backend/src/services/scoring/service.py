"""Transactional Match-scoring application commands."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import (
    BlockingReasonCode,
    BlockingStateKind,
    DeliveryRevisionState,
    FormatCapabilityProfile,
    InningsCompletionMode,
    InningsLifecycleState,
    InningsTransitionType,
    MatchLifecycleState,
    MatchParticipantKind,
    MatchParticipantType,
    MatchResultCode,
    MatchSideCode,
    MatchSideKind,
    ParticipationState,
    ScoringAuthority,
)
from src.models.match import Match
from src.models.scoring.batting_entry import BattingOrderEntry
from src.models.scoring.delivery import Delivery
from src.models.scoring.delivery_fielder import DeliveryFielder
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.models.scoring.match_side import MatchSide
from src.models.scoring.participant import MatchParticipant
from src.models.scoring.transition_event import InningsTransitionEvent
from src.models.scoring.wicket_event import WicketEvent
from src.models.user import User
from src.schemas.scoring import (
    AppendDeliveryRequest,
    BlockingStateResponse,
    DeliveryCorrectionRequest,
    DeliveryCorrectionResponse,
    DeliveryExtrasRequest,
    DeliveryExtrasResponse,
    DeliveryFactsRequest,
    DeliveryFielderRequest,
    DeliveryFielderResponse,
    DeliveryHistoryResponse,
    DeliveryResponse,
    DeliveryRevisionResponse,
    InningsOverResponse,
    InningsResponse,
    MatchConfigurationRequest,
    MatchConfigurationResponse,
    MatchParticipantResponse,
    MatchSideResponse,
    NextBowlerResponse,
    OverProgressResponse,
    ParticipantSummaryResponse,
    RetiredHurtReturnRequest,
    RetireHurtRequest,
    ScoringPolicyResponse,
    SelectNextBatterRequest,
    SelectNextBowlerRequest,
    StartInningsRequest,
    WicketRequest,
    WicketResponse,
)
from src.services.background_jobs.outbox import stage_scoring_refresh
from src.services.business_audit_service import BusinessAuditService
from src.services.occ import check_and_increment_version
from src.services.scoring.audit import (
    record_delivery_corrected,
    record_innings_started,
    record_scoring_initialization,
)
from src.services.scoring.authorization import (
    ScoringAuthorizationAdapter,
    next_bowler_options,
    require_configuration_scope,
    require_scoring_mutation_scope,
    require_scoring_read_scope,
    validate_innings_selections,
)
from src.services.scoring.errors import (
    ScoringAuthorityError,
    ScoringConflictError,
    ScoringLifecycleError,
    ScoringReconciliationError,
    ScoringRevisionError,
    ScoringSequenceError,
    ScoringValidationError,
    ScoringVisibilityError,
)
from src.services.scoring.policy import (
    bowler_eligibility,
    capability_from_locked_policy,
    resolve_format_capability,
)
from src.services.scoring.projections import persist_innings_projection
from src.services.scoring.replay import (
    ReplayDelivery,
    ReplayInnings,
    ReplayParticipant,
    ReplaySeed,
    ReplayState,
    ReplayTransition,
    derive_innings_blocking_state,
    replay_innings,
    replay_match,
)
from src.services.scoring.rules import checked_scoring_add, classify_delivery

logger = logging.getLogger(__name__)


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


def _blocking_response(innings: Innings, match: Match) -> BlockingStateResponse:
    stored = innings.blocking_state
    if stored is not None and MatchLifecycleState(match.lifecycle_state) not in {
        MatchLifecycleState.COMPLETED,
        MatchLifecycleState.ABANDONED,
    }:
        return BlockingStateResponse.model_validate(stored)
    derived = derive_innings_blocking_state(
        match_lifecycle_state=MatchLifecycleState(match.lifecycle_state),
        innings_lifecycle_state=InningsLifecycleState(innings.lifecycle_state),
        striker_participant_id=innings.striker_participant_id,
        non_striker_participant_id=innings.non_striker_participant_id,
        current_bowler_participant_id=innings.current_bowler_participant_id,
    )
    return BlockingStateResponse.model_validate(derived.as_dict())


def _innings_response(innings: Innings, match: Match) -> InningsResponse:
    return InningsResponse(
        id=innings.id,
        match_id=innings.match_id,
        innings_number=innings.innings_number,
        batting_side_id=innings.batting_side_id,
        fielding_side_id=innings.fielding_side_id,
        lifecycle_state=innings.lifecycle_state,
        reconciliation_reason=innings.reconciliation_reason,
        reconciliation_sequence=innings.state_snapshot.get("reconciliation", {}).get(
            "attempted_sequence"
        ),
        unreplayed_attempts=innings.state_snapshot.get("reconciliation", {}).get(
            "unreplayed_attempts", 0
        ),
        striker_participant_id=innings.striker_participant_id,
        non_striker_participant_id=innings.non_striker_participant_id,
        current_bowler_participant_id=innings.current_bowler_participant_id,
        legal_balls=innings.legal_balls,
        total_runs=innings.total_runs,
        wickets_lost=innings.wickets_lost,
        target_runs=innings.target_runs,
        completion_reason=innings.completion_reason,
        completed_at=innings.completed_at,
        projection_revision=innings.projection_revision,
        version_number=innings.version_number,
        blocking_state=_blocking_response(innings, match),
        policy=(
            ScoringPolicyResponse.model_validate(match.scoring_policy)
            if match.scoring_policy is not None
            else None
        ),
        over_progress=_over_progress(innings, match),
        completed_bowler_participant_ids=_completed_bowlers(innings),
        overs=[
            InningsOverResponse.model_validate(over)
            for over in sorted(innings.overs, key=lambda value: value.over_number)
        ],
        participant_summaries=[
            ParticipantSummaryResponse.model_validate(summary)
            for summary in sorted(
                innings.participant_summaries,
                key=lambda value: str(value.participant_id),
            )
        ],
    )


def _completed_bowlers(innings: Innings) -> list[UUID]:
    return [
        over.bowler_participant_id
        for over in sorted(innings.overs, key=lambda value: value.over_number)
        if over.is_complete
    ]


def _over_progress(innings: Innings, match: Match) -> OverProgressResponse:
    if match.scoring_policy is None:
        raise ScoringAuthorityError("Match scoring policy is not locked.")
    length = capability_from_locked_policy(match.scoring_policy).over_length_legal_balls
    return OverProgressResponse(
        over_length_legal_balls=length,
        overs_completed=innings.legal_balls // length,
        balls_in_partial_over=innings.legal_balls % length,
        next_ball_in_over=innings.legal_balls % length + 1,
    )


def _next_bowler_response(innings: Innings, match: Match) -> NextBowlerResponse:
    if match.scoring_policy is None:
        raise ScoringAuthorityError("Match scoring policy is not locked.")
    history = _completed_bowlers(innings)
    options = next_bowler_options(
        capability_from_locked_policy(match.scoring_policy),
        match.scoring_participants,
        match_id=match.id,
        fielding_side_id=innings.fielding_side_id,
        legal_balls_by_bowler={
            s.participant_id: s.bowling_legal_balls
            for s in innings.participant_summaries
        },
        completed_bowler_ids=tuple(history),
    )
    return NextBowlerResponse(
        match_id=match.id,
        innings_id=innings.id,
        match_version_number=match.version_number,
        innings_version_number=innings.version_number,
        policy=ScoringPolicyResponse.model_validate(match.scoring_policy),
        over_progress=_over_progress(innings, match),
        completed_bowler_participant_ids=history,
        current_bowler_participant_id=innings.current_bowler_participant_id,
        suggested_bowler_participant_id=options.suggested_bowler_participant_id,
        candidates=list(options.candidates),
        reason_code=options.reason_code,
        blocking_state=_blocking_response(innings, match),
    )


def _delivery_response(
    delivery: Delivery,
    innings: Innings,
    match: Match,
) -> DeliveryResponse:
    active = next(
        revision
        for revision in delivery.revisions
        if DeliveryRevisionState(revision.revision_state)
        is DeliveryRevisionState.ACTIVE
    )
    ordered_fielders = sorted(active.fielders, key=lambda value: value.ordinal)
    wicket = active.wicket_event
    wicket_response = (
        WicketResponse(
            dismissal_type=wicket.dismissal_type,
            dismissed_participant_id=wicket.dismissed_participant_id,
            dismissed_end=wicket.dismissed_end,
            counts_as_team_wicket=wicket.counts_as_team_wicket,
            credited_to_bowler=wicket.credited_to_bowler,
            fielders=[
                DeliveryFielderResponse.model_validate(item)
                for item in ordered_fielders
            ],
            primary_fielder_participant_id=(
                ordered_fielders[0].participant_id if ordered_fielders else None
            ),
            notes=wicket.notes,
        )
        if wicket is not None
        else None
    )
    if match.scoring_policy is None:
        raise ScoringAuthorityError("Match scoring policy is not locked.")
    legal_balls_before = sum(
        ScoringService._active_revision(item).is_legal
        for item in innings.deliveries
        if item.attempted_sequence < delivery.attempted_sequence
    )
    over_length = match.scoring_policy.over_length_legal_balls
    revision_response = DeliveryRevisionResponse(
        id=active.id,
        revision_number=active.revision_number,
        revision_state=active.revision_state,
        striker_participant_id=active.striker_participant_id,
        non_striker_participant_id=active.non_striker_participant_id,
        bowler_participant_id=active.bowler_participant_id,
        runs_off_bat=active.runs_off_bat,
        extras=DeliveryExtrasResponse(
            wide_runs=active.wide_runs,
            no_ball_penalty_runs=active.no_ball_penalty_runs,
            bye_runs=active.bye_runs,
            leg_bye_runs=active.leg_bye_runs,
            penalty_runs=active.penalty_runs,
        ),
        total_runs=active.total_runs,
        is_legal=active.is_legal,
        completed_runs=active.completed_runs,
        balls_faced=active.balls_faced,
        bowler_conceded_runs=active.bowler_conceded_runs,
        over_number=(legal_balls_before // over_length),
        ball_in_over=(legal_balls_before % over_length + 1),
        wicket=wicket_response,
        replacement_reason=active.replacement_reason,
        supersedes_revision_id=active.supersedes_revision_id,
        recorded_by_user_id=active.recorded_by_user_id,
        recorded_at=active.recorded_at,
    )
    return DeliveryResponse(
        id=delivery.id,
        innings_id=delivery.innings_id,
        attempted_sequence=delivery.attempted_sequence,
        active_revision=revision_response,
        innings_version_number=innings.version_number,
        innings_total_runs=innings.total_runs,
        innings_legal_balls=innings.legal_balls,
        innings_wickets_lost=innings.wickets_lost,
        striker_participant_id=innings.striker_participant_id,
        non_striker_participant_id=innings.non_striker_participant_id,
        current_bowler_participant_id=innings.current_bowler_participant_id,
        blocking_state=_blocking_response(innings, match),
    )


class ScoringService:
    """Own Match-scoped scoring transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_match(self, match_id: UUID, *, for_update: bool = False) -> Match:
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
        if for_update:
            statement = statement.with_for_update(of=Match)
        match = (await self.session.scalars(statement)).one_or_none()
        if match is None:
            raise ScoringVisibilityError("Match not found.")
        return match

    async def _load_innings(
        self, match_id: UUID, innings_id: UUID, *, include_history: bool = True
    ) -> Innings:
        history_options = (
            [
                selectinload(Innings.deliveries)
                .selectinload(Delivery.revisions)
                .selectinload(DeliveryRevision.wicket_event),
                selectinload(Innings.deliveries)
                .selectinload(Delivery.revisions)
                .selectinload(DeliveryRevision.fielders),
                selectinload(Innings.transition_events),
            ]
            if include_history
            else []
        )
        statement = (
            select(Innings)
            .options(
                selectinload(Innings.batting_entries),
                *history_options,
                selectinload(Innings.overs),
                selectinload(Innings.participant_summaries),
            )
            .where(Innings.id == innings_id, Innings.match_id == match_id)
            .execution_options(populate_existing=True)
        )
        innings = (await self.session.scalars(statement)).one_or_none()
        if innings is None:
            raise ScoringVisibilityError("Innings not found.")
        return innings

    async def _claim_innings_version(
        self, match: Match, innings: Innings, expected_version: int
    ) -> int:
        self._require_progression(match)
        match.version_number = await check_and_increment_version(
            self.session, Match, match.id, match.version_number
        )
        return await check_and_increment_version(
            self.session, Innings, innings.id, expected_version
        )

    @staticmethod
    def _require_progression(match: Match) -> None:
        if MatchLifecycleState(match.lifecycle_state) not in {
            MatchLifecycleState.SCHEDULED,
            MatchLifecycleState.IN_PROGRESS,
        }:
            raise ScoringLifecycleError(
                "A terminal or reprocessing Match cannot progress."
            )
        if any(
            InningsLifecycleState(value.lifecycle_state)
            is InningsLifecycleState.RECONCILIATION_REQUIRED
            for value in match.scoring_innings
        ):
            raise ScoringReconciliationError(
                "An Innings requires correction before Match progression."
            )

    @staticmethod
    def _active_revision(delivery: Delivery) -> DeliveryRevision:
        active = [
            revision
            for revision in delivery.revisions
            if DeliveryRevisionState(revision.revision_state)
            is DeliveryRevisionState.ACTIVE
        ]
        if len(active) != 1:
            raise ScoringReconciliationError(
                "Every delivery must have exactly one active revision."
            )
        return active[0]

    @staticmethod
    def _revision_facts(revision: DeliveryRevision) -> DeliveryFactsRequest:
        wicket = revision.wicket_event
        return DeliveryFactsRequest(
            striker_participant_id=revision.striker_participant_id,
            non_striker_participant_id=revision.non_striker_participant_id,
            bowler_participant_id=revision.bowler_participant_id,
            runs_off_bat=revision.runs_off_bat,
            extras=DeliveryExtrasRequest(
                wide_runs=revision.wide_runs,
                no_ball_penalty_runs=revision.no_ball_penalty_runs,
                bye_runs=revision.bye_runs,
                leg_bye_runs=revision.leg_bye_runs,
                penalty_runs=revision.penalty_runs,
            ),
            wicket=(
                WicketRequest(
                    dismissal_type=wicket.dismissal_type,
                    dismissed_participant_id=wicket.dismissed_participant_id,
                    dismissed_end=wicket.dismissed_end,
                    fielders=[
                        DeliveryFielderRequest(
                            participant_id=item.participant_id,
                            role=item.role,
                        )
                        for item in sorted(
                            revision.fielders, key=lambda value: value.ordinal
                        )
                    ],
                    notes=wicket.notes,
                )
                if wicket is not None
                else None
            ),
        )

    @classmethod
    def _replay_input(cls, match: Match, innings: Innings) -> ReplayInnings:
        if match.scoring_policy is None:
            raise ScoringAuthorityError("Match scoring policy is not locked.")
        capability = capability_from_locked_policy(match.scoring_policy)
        batting = sorted(
            (
                participant
                for participant in match.scoring_participants
                if participant.side_id == innings.batting_side_id
            ),
            key=lambda value: value.batting_order_position,
        )
        fielding_ids = frozenset(
            participant.id
            for participant in match.scoring_participants
            if participant.side_id == innings.fielding_side_id
        )
        deliveries = sorted(
            innings.deliveries, key=lambda value: value.attempted_sequence
        )
        stored_opening = innings.state_snapshot.get("opening_selections")
        if isinstance(stored_opening, dict):
            try:
                opening_striker_id = UUID(str(stored_opening["striker_participant_id"]))
                opening_non_striker_id = UUID(
                    str(stored_opening["non_striker_participant_id"])
                )
                opening_bowler_id = UUID(str(stored_opening["bowler_participant_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ScoringReconciliationError(
                    "The stored opening selections are invalid."
                ) from exc
        elif deliveries:
            # The first recorded revision preserves the original opening actors.
            opening = min(
                deliveries[0].revisions, key=lambda item: item.revision_number
            )
            opening_striker_id = opening.striker_participant_id
            opening_non_striker_id = opening.non_striker_participant_id
            opening_bowler_id = opening.bowler_participant_id
        elif (
            innings.striker_participant_id is not None
            and innings.non_striker_participant_id is not None
            and innings.current_bowler_participant_id is not None
        ):
            opening_striker_id = innings.striker_participant_id
            opening_non_striker_id = innings.non_striker_participant_id
            opening_bowler_id = innings.current_bowler_participant_id
        else:
            raise ScoringReconciliationError(
                "An unscored Innings must retain its opening selections."
            )
        seed = ReplaySeed(
            capability=capability,
            batting_participants=tuple(
                ReplayParticipant(participant.id, participant.batting_order_position)
                for participant in batting
            ),
            fielding_participant_ids=fielding_ids,
            opening_striker_participant_id=opening_striker_id,
            opening_non_striker_participant_id=opening_non_striker_id,
            opening_bowler_participant_id=opening_bowler_id,
            lifecycle_state=InningsLifecycleState(innings.lifecycle_state),
            match_lifecycle_state=MatchLifecycleState(match.lifecycle_state),
            target_runs=innings.target_runs,
        )
        replay_deliveries = [
            ReplayDelivery(
                attempted_sequence=delivery.attempted_sequence,
                facts=cls._revision_facts(cls._active_revision(delivery)),
            )
            for delivery in deliveries
        ]
        replay_transitions = [
            ReplayTransition(
                event_kind=InningsTransitionType(event.event_kind),
                participant_id=event.participant_id,
                anchored_attempted_sequence=event.anchored_attempted_sequence,
                completion_kind=cls._completion_kind_from_history(
                    match, innings, event
                ),
            )
            for event in sorted(
                innings.transition_events,
                key=lambda value: (
                    value.anchored_attempted_sequence or 0,
                    value.created_at or datetime.max.replace(tzinfo=UTC),
                    str(value.id),
                ),
            )
        ]
        # Anchors may refer to superseded revisions, but must stay in their own slot.
        revisions_by_id = {
            revision.id: delivery.attempted_sequence
            for delivery in deliveries
            for revision in delivery.revisions
        }
        for event in innings.transition_events:
            if (
                event.anchored_revision_id is not None
                and revisions_by_id.get(event.anchored_revision_id)
                != event.anchored_attempted_sequence
            ):
                raise ScoringReconciliationError(
                    "Transition revision anchor is outside its delivery boundary."
                )
        side = next(
            (
                side
                for side in match.scoring_sides
                if side.id == innings.batting_side_id
            ),
            None,
        )
        side_code = (
            side.side_code
            if side
            else capability.innings_sequence[innings.innings_number - 1]
        )
        return ReplayInnings(
            innings.innings_number,
            side_code,
            seed,
            tuple(replay_deliveries),
            tuple(replay_transitions),
        )

    @staticmethod
    def _completion_kind_from_history(
        match: Match,
        innings: Innings,
        event: InningsTransitionEvent,
    ) -> InningsCompletionMode | None:
        if event.event_kind != InningsTransitionType.INNINGS_COMPLETED:
            return None
        if match.scoring_policy is None:
            raise ScoringAuthorityError("Match scoring policy is not locked.")
        capability = capability_from_locked_policy(match.scoring_policy)
        if capability.capability_profile is FormatCapabilityProfile.OTHER:
            return InningsCompletionMode.MANUAL
        if capability.capability_profile is not FormatCapabilityProfile.TEST:
            return None  # Fixed-over completion is always derived again.
        # Test permits all-out or declaration. Recover the original distinction
        # from revisions as they stood when the completion was recorded; a prior
        # correction may have cleared the current completion projection.
        wickets = 0
        for delivery in innings.deliveries:
            if delivery.attempted_sequence > (event.anchored_attempted_sequence or 0):
                continue
            revisions = [
                revision
                for revision in delivery.revisions
                if revision.recorded_at <= event.created_at
            ]
            if not revisions:
                raise ScoringReconciliationError(
                    "Completion predates its delivery history."
                )
            revision = max(revisions, key=lambda item: item.revision_number)
            if (
                revision.wicket_event is not None
                and revision.wicket_event.counts_as_team_wicket
            ):
                wickets += 1
        return (
            InningsCompletionMode.ALL_OUT
            if wickets >= capability.wicket_limit
            else InningsCompletionMode.DECLARATION
        )

    @classmethod
    def _replay_orm(cls, match: Match, innings: Innings) -> ReplayState:
        source = cls._replay_input(match, innings)
        return replay_innings(source.seed, source.deliveries, source.transitions)

    @staticmethod
    def _last_replay_anchor(
        innings: Innings,
    ) -> tuple[int | None, UUID | None]:
        if not innings.deliveries:
            return None, None
        delivery = max(innings.deliveries, key=lambda value: value.attempted_sequence)
        return delivery.attempted_sequence, ScoringService._active_revision(delivery).id

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
            match = await self._load_match(match_id, for_update=True)
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

    async def start_innings(
        self,
        match_id: UUID,
        payload: StartInningsRequest,
        authenticated_user: User | UUID,
        *,
        request_id: str | None = None,
    ) -> InningsResponse:
        """Atomically create the next capability-ordered Innings and opening state."""

        try:
            context = await ScoringAuthorizationAdapter(self.session).load_context(
                authenticated_user
            )
            match = await self._load_match(match_id, for_update=True)
            require_scoring_mutation_scope(context, match)
            if match.scoring_policy is None:
                raise ScoringAuthorityError("Match scoring is not configured.")
            if MatchLifecycleState(match.lifecycle_state) not in {
                MatchLifecycleState.SCHEDULED,
                MatchLifecycleState.IN_PROGRESS,
            }:
                raise ScoringLifecycleError(
                    "A terminal Match cannot start another Innings."
                )
            capability = capability_from_locked_policy(match.scoring_policy)
            if payload.innings_number > len(capability.innings_sequence):
                raise ScoringSequenceError(
                    "Innings number exceeds the locked sequence."
                )
            self._require_progression(match)
            existing = sorted(
                match.scoring_innings, key=lambda value: value.innings_number
            )
            if payload.innings_number != len(existing) + 1:
                raise ScoringSequenceError("Only the next locked Innings may start.")
            if existing and InningsLifecycleState(existing[-1].lifecycle_state) is not (
                InningsLifecycleState.COMPLETED
            ):
                raise ScoringLifecycleError(
                    "The prior Innings must complete before the next one starts."
                )

            side_code = capability.innings_sequence[payload.innings_number - 1]
            side_by_code = {
                MatchSideCode(side.side_code): side for side in match.scoring_sides
            }
            batting_side = side_by_code[side_code]
            fielding_side = next(
                side for code, side in side_by_code.items() if code is not side_code
            )
            innings = Innings(
                match_id=match.id,
                innings_number=payload.innings_number,
                batting_side_id=batting_side.id,
                fielding_side_id=fielding_side.id,
                lifecycle_state=InningsLifecycleState.IN_PROGRESS,
                striker_participant_id=payload.opening_striker_participant_id,
                non_striker_participant_id=payload.opening_non_striker_participant_id,
                current_bowler_participant_id=payload.opening_bowler_participant_id,
                target_runs=None,
                state_snapshot={},
            )
            batting_participants = sorted(
                (
                    participant
                    for participant in match.scoring_participants
                    if participant.side_id == batting_side.id
                ),
                key=lambda value: value.batting_order_position,
            )
            innings.batting_entries = [
                BattingOrderEntry(
                    participant_id=participant.id,
                    batting_order_position=participant.batting_order_position,
                    participation_state=(
                        ParticipationState.ACTIVE
                        if participant.id
                        in {
                            payload.opening_striker_participant_id,
                            payload.opening_non_striker_participant_id,
                        }
                        else ParticipationState.NOT_BATTED
                    ),
                )
                for participant in batting_participants
            ]
            innings.deliveries = []
            innings.overs = []
            innings.participant_summaries = []
            innings.transition_events = [
                InningsTransitionEvent(
                    event_kind=InningsTransitionType.INNINGS_STARTED,
                    participant_id=payload.opening_striker_participant_id,
                    created_by_user_id=context.user.id,
                    created_at=datetime.now(UTC),
                )
            ]
            validate_innings_selections(
                innings,
                match.scoring_participants,
                striker_participant_id=payload.opening_striker_participant_id,
                non_striker_participant_id=payload.opening_non_striker_participant_id,
                bowler_participant_id=payload.opening_bowler_participant_id,
                require_current=True,
            )
            if payload.innings_number == 2 and capability.target_mode.value == (
                "prior_innings_plus_one"
            ):
                innings.target_runs = checked_scoring_add(
                    1,
                    current=existing[0].total_runs,
                    field_name="target total",
                )

            next_match_version = await check_and_increment_version(
                self.session,
                Match,
                match.id,
                payload.match_version_number,
            )
            match.version_number = next_match_version
            match.lifecycle_state = MatchLifecycleState.IN_PROGRESS
            self.session.add(innings)
            await self.session.flush()
            state = self._replay_orm(match, innings)
            await persist_innings_projection(
                self.session,
                innings,
                state,
                over_length_legal_balls=capability.over_length_legal_balls,
            )
            await record_innings_started(
                BusinessAuditService(self.session),
                actor=context.user,
                match=match,
                innings=innings,
                request_id=request_id,
            )
            await self.session.commit()
            reloaded_match = await self._load_match(match.id)
            reloaded_innings = await self._load_innings(match.id, innings.id)
            return _innings_response(reloaded_innings, reloaded_match)
        except Exception:
            await self.session.rollback()
            raise

    async def append_delivery(
        self,
        match_id: UUID,
        innings_id: UUID,
        payload: AppendDeliveryRequest,
        authenticated_user: User | UUID,
        *,
        request_id: str | None = None,
    ) -> DeliveryResponse:
        """Append one immutable first revision and rebuild projections atomically."""

        try:
            context = await ScoringAuthorizationAdapter(self.session).load_context(
                authenticated_user
            )
            match = await self._load_match(match_id, for_update=True)
            innings = await self._load_innings(match_id, innings_id)
            require_scoring_mutation_scope(context, match)
            if MatchLifecycleState(match.lifecycle_state) is not (
                MatchLifecycleState.IN_PROGRESS
            ) or InningsLifecycleState(innings.lifecycle_state) is not (
                InningsLifecycleState.IN_PROGRESS
            ):
                raise ScoringLifecycleError(
                    "Deliveries require an in-progress Match and Innings."
                )
            if innings.reconciliation_reason is not None:
                raise ScoringReconciliationError(
                    "Reconciliation must finish before another delivery."
                )
            validate_innings_selections(
                innings,
                match.scoring_participants,
                striker_participant_id=payload.striker_participant_id,
                non_striker_participant_id=payload.non_striker_participant_id,
                bowler_participant_id=payload.bowler_participant_id,
                require_current=True,
            )
            expected_sequence = (
                max(
                    (delivery.attempted_sequence for delivery in innings.deliveries),
                    default=0,
                )
                + 1
            )
            if payload.attempted_sequence != expected_sequence:
                raise ScoringSequenceError(
                    f"attempted_sequence must be {expected_sequence}."
                )
            if match.scoring_policy is None:
                raise ScoringAuthorityError("Match scoring policy is not locked.")
            capability = capability_from_locked_policy(match.scoring_policy)
            fielding_ids = frozenset(
                participant.id
                for participant in match.scoring_participants
                if participant.side_id == innings.fielding_side_id
            )
            classification = classify_delivery(
                payload,
                legal_balls_before=innings.legal_balls,
                over_length_legal_balls=capability.over_length_legal_balls,
                innings_total_before=innings.total_runs,
                match_total_before=sum(
                    value.total_runs for value in match.scoring_innings
                ),
                fielding_participant_ids=fielding_ids,
                allowed_dismissal_types=frozenset(capability.allowed_dismissal_types),
            )
            previous_over = next(
                (
                    over
                    for over in innings.overs
                    if over.over_number == classification.over_number - 1
                ),
                None,
            )
            usage = next(
                (
                    summary.bowling_legal_balls
                    for summary in innings.participant_summaries
                    if summary.participant_id == payload.bowler_participant_id
                ),
                0,
            )
            decision = bowler_eligibility(
                capability,
                payload.bowler_participant_id,
                fielding_participant_ids=fielding_ids,
                legal_balls_bowled=usage,
                previous_over_bowler_id=(
                    previous_over.bowler_participant_id if previous_over else None
                ),
            )
            if not decision.is_eligible:
                raise ScoringConflictError(
                    f"Delivery bowler is ineligible: {decision.reason_code}."
                )
            next_version = await self._claim_innings_version(
                match, innings, payload.innings_version_number
            )
            innings.version_number = next_version
            delivery = Delivery(
                innings=innings,
                attempted_sequence=payload.attempted_sequence,
            )
            revision = DeliveryRevision(
                revision_number=1,
                revision_state=DeliveryRevisionState.ACTIVE,
                striker_participant_id=payload.striker_participant_id,
                non_striker_participant_id=payload.non_striker_participant_id,
                bowler_participant_id=payload.bowler_participant_id,
                runs_off_bat=payload.runs_off_bat,
                wide_runs=payload.extras.wide_runs,
                no_ball_penalty_runs=payload.extras.no_ball_penalty_runs,
                bye_runs=payload.extras.bye_runs,
                leg_bye_runs=payload.extras.leg_bye_runs,
                penalty_runs=payload.extras.penalty_runs,
                total_runs=classification.total_runs,
                is_legal=classification.is_legal,
                completed_runs=classification.completed_runs,
                balls_faced=classification.balls_faced,
                bowler_conceded_runs=classification.bowler_conceded_runs,
                over_number=classification.over_number,
                ball_in_over=classification.ball_in_over,
                recorded_by_user_id=context.user.id,
                wicket_event=None,
                fielders=[],
            )
            delivery.revisions.append(revision)
            self.session.add(delivery)
            await self.session.flush()
            if payload.wicket is not None and classification.wicket is not None:
                wicket = classification.wicket
                revision.wicket_event = WicketEvent(
                    dismissed_participant_id=wicket.dismissed_participant_id,
                    dismissal_type=wicket.dismissal_type,
                    dismissed_end=wicket.dismissed_end,
                    counts_as_team_wicket=wicket.counts_as_team_wicket,
                    credited_to_bowler=wicket.credited_to_bowler,
                    primary_fielder_participant_id=(
                        wicket.primary_fielder_participant_id
                    ),
                    notes=payload.wicket.notes,
                )
                revision.fielders = [
                    DeliveryFielder(
                        participant_id=item.participant_id,
                        ordinal=ordinal,
                        role=item.role,
                    )
                    for ordinal, item in enumerate(payload.wicket.fielders, start=1)
                ]
                entry = next(
                    value
                    for value in innings.batting_entries
                    if value.participant_id == wicket.dismissed_participant_id
                )
                entry.dismissal_delivery_id = delivery.id
            await self.session.flush()
            state = self._replay_orm(match, innings)
            await persist_innings_projection(
                self.session,
                innings,
                state,
                over_length_legal_balls=capability.over_length_legal_balls,
            )
            await self.session.commit()
            logger.info(
                "Scoring delivery appended",
                extra={
                    "request_id": request_id,
                    "match_id": str(match_id),
                    "innings_id": str(innings_id),
                    "attempted_sequence": payload.attempted_sequence,
                    "expected_version": payload.innings_version_number,
                    "resulting_version": next_version,
                    "outcome": "committed",
                },
            )
            reloaded_match = await self._load_match(match_id)
            reloaded = await self._load_innings(match_id, innings_id)
            persisted = next(
                value for value in reloaded.deliveries if value.id == delivery.id
            )
            return _delivery_response(
                persisted,
                reloaded,
                reloaded_match,
            )
        except Exception as exc:
            await self.session.rollback()
            logger.info(
                "Scoring delivery rejected",
                extra={
                    "request_id": request_id,
                    "match_id": str(match_id),
                    "innings_id": str(innings_id),
                    "attempted_sequence": payload.attempted_sequence,
                    "expected_version": payload.innings_version_number,
                    "outcome": type(exc).__name__,
                },
            )
            raise

    async def correct_delivery(
        self,
        match_id: UUID,
        innings_id: UUID,
        delivery_id: UUID,
        payload: DeliveryCorrectionRequest,
        authenticated_user: User | UUID,
        *,
        request_id: str | None = None,
    ) -> DeliveryCorrectionResponse:
        """Append one revision and atomically rebuild the Match under its OCC lock."""
        try:
            context = await ScoringAuthorizationAdapter(self.session).load_context(
                authenticated_user
            )
            match = await self._load_match(match_id, for_update=True)
            require_scoring_mutation_scope(context, match)
            prior_lifecycle = MatchLifecycleState(match.lifecycle_state)
            if prior_lifecycle not in {
                MatchLifecycleState.IN_PROGRESS,
                MatchLifecycleState.COMPLETED,
            }:
                raise ScoringLifecycleError(
                    "Only an in-progress or completed Match may be corrected."
                )
            if (
                match.scoring_policy is None
                or match.scoring_authority != ScoringAuthority.DELIVERY_HISTORY
            ):
                raise ScoringAuthorityError(
                    "Correction requires locked delivery-history scoring."
                )
            try:
                capability = capability_from_locked_policy(match.scoring_policy)
            except ValueError as exc:
                raise ScoringReconciliationError(
                    "The locked capability cannot be replayed."
                ) from exc
            all_innings = [
                await self._load_innings(match.id, item.id)
                for item in sorted(
                    match.scoring_innings, key=lambda item: item.innings_number
                )
            ]
            innings = next(
                (item for item in all_innings if item.id == innings_id), None
            )
            if innings is None:
                raise ScoringVisibilityError("Innings not found.")
            delivery = next(
                (item for item in innings.deliveries if item.id == delivery_id), None
            )
            if delivery is None:
                raise ScoringVisibilityError("Delivery not found.")
            side_ids = {side.id for side in match.scoring_sides}
            if len(side_ids) != 2 or any(
                {item.batting_side_id, item.fielding_side_id} != side_ids
                for item in all_innings
            ):
                raise ScoringReconciliationError(
                    "Innings sides differ from the locked Match sides."
                )
            for item in all_innings:
                for attempt in item.deliveries:
                    self._validate_revision_chain(attempt)
            active = self._active_revision(delivery)
            if active.revision_number != payload.expected_revision_number:
                raise ScoringRevisionError("The active revision has changed.")
            match.version_number = await check_and_increment_version(
                self.session, Match, match.id, payload.match_version_number
            )
            # Always acquire roots in innings order after the Match lock.
            for item in all_innings:
                item.version_number = await check_and_increment_version(
                    self.session,
                    Innings,
                    item.id,
                    payload.innings_version_number
                    if item.id == innings.id
                    else item.version_number,
                )
            if prior_lifecycle is MatchLifecycleState.COMPLETED:
                match.lifecycle_state = MatchLifecycleState.CORRECTION_REPROCESSING
            try:
                sources = [self._replay_input(match, item) for item in all_innings]
            except (ValueError, KeyError, IndexError) as exc:
                raise ScoringReconciliationError(
                    "Stored history cannot be safely replayed."
                ) from exc
            index = innings.innings_number - 1
            source = sources[index]
            replacement_facts = DeliveryFactsRequest.model_validate(
                payload.replacement.model_dump()
            )
            sources[index] = replace(
                source,
                deliveries=tuple(
                    ReplayDelivery(attempt.attempted_sequence, replacement_facts)
                    if attempt.attempted_sequence == delivery.attempted_sequence
                    else attempt
                    for attempt in source.deliveries
                ),
            )
            # Validate all observed run totals, including history beyond a conflict.
            checked_scoring_add(
                *(
                    classify_delivery(
                        attempt.facts,
                        legal_balls_before=0,
                        over_length_legal_balls=capability.over_length_legal_balls,
                        fielding_participant_ids=item.seed.fielding_participant_ids,
                        allowed_dismissal_types=frozenset(
                            capability.allowed_dismissal_types
                        ),
                    ).total_runs
                    for item in sources
                    for attempt in item.deliveries
                ),
                field_name="Match total",
            )
            replay = replay_match(
                capability,
                sources,
                correction_innings_number=innings.innings_number,
                correction_sequence=delivery.attempted_sequence,
                prior_lifecycle_state=prior_lifecycle,
                prior_result_code=MatchResultCode(match.result_code),
                prior_result_details=match.result_details,
            )
            state = replay.innings_states[index]
            if len(state.classifications) < delivery.attempted_sequence:
                raise ScoringReconciliationError(
                    "The correction cannot be applied before the unresolved boundary."
                )
            classification = state.classifications[delivery.attempted_sequence - 1]
            material = self._revision_facts(active).model_dump(
                exclude={"wicket": {"notes"}}
            ) != replacement_facts.model_dump(exclude={"wicket": {"notes"}})
            active.revision_state = DeliveryRevisionState.SUPERSEDED
            # Free the partial unique index before inserting the replacement.
            await self.session.flush()
            revision = DeliveryRevision(
                id=uuid4(),
                delivery_id=delivery.id,
                revision_number=active.revision_number + 1,
                revision_state=DeliveryRevisionState.ACTIVE,
                striker_participant_id=replacement_facts.striker_participant_id,
                non_striker_participant_id=replacement_facts.non_striker_participant_id,
                bowler_participant_id=replacement_facts.bowler_participant_id,
                runs_off_bat=replacement_facts.runs_off_bat,
                **replacement_facts.extras.model_dump(),
                total_runs=classification.total_runs,
                is_legal=classification.is_legal,
                completed_runs=classification.completed_runs,
                balls_faced=classification.balls_faced,
                bowler_conceded_runs=classification.bowler_conceded_runs,
                over_number=classification.over_number,
                ball_in_over=classification.ball_in_over,
                supersedes_revision_id=active.id,
                replacement_reason=payload.reason,
                recorded_by_user_id=context.user.id,
                recorded_at=datetime.now(UTC),
                wicket_event=None,
                fielders=[],
            )
            if (
                classification.wicket is not None
                and replacement_facts.wicket is not None
            ):
                wicket = classification.wicket
                revision.wicket_event = WicketEvent(
                    dismissed_participant_id=wicket.dismissed_participant_id,
                    dismissal_type=wicket.dismissal_type,
                    dismissed_end=wicket.dismissed_end,
                    counts_as_team_wicket=wicket.counts_as_team_wicket,
                    credited_to_bowler=wicket.credited_to_bowler,
                    primary_fielder_participant_id=wicket.primary_fielder_participant_id,
                    notes=replacement_facts.wicket.notes,
                )
                revision.fielders = [
                    DeliveryFielder(
                        participant_id=item.participant_id,
                        ordinal=ordinal,
                        role=item.role,
                    )
                    for ordinal, item in enumerate(replacement_facts.wicket.fielders, 1)
                ]
            delivery.revisions.append(revision)
            self.session.add(revision)
            match.lifecycle_state = replay.lifecycle_state
            match.result_code, match.result_details, match.result = (
                replay.result_code,
                replay.result_details,
                replay.result,
            )
            for item, rebuilt in zip(all_innings, replay.innings_states, strict=True):
                await persist_innings_projection(
                    self.session,
                    item,
                    rebuilt,
                    over_length_legal_balls=capability.over_length_legal_balls,
                )
                # Rebuild dismissal links solely from the compatible active stream.
                dismissal_ids = {
                    classification.wicket.dismissed_participant_id: attempt.id
                    for attempt, classification in zip(
                        sorted(
                            item.deliveries, key=lambda value: value.attempted_sequence
                        ),
                        rebuilt.classifications,
                        strict=False,
                    )
                    if classification.wicket is not None
                }
                for entry in item.batting_entries:
                    entry.dismissal_delivery_id = dismissal_ids.get(
                        entry.participant_id
                    )
            await self.session.flush()
            await record_delivery_corrected(
                BusinessAuditService(self.session),
                actor=context.user,
                match=match,
                innings=innings,
                delivery_id=delivery.id,
                prior_revision_id=active.id,
                revision=revision,
                prior_lifecycle=prior_lifecycle,
                request_id=request_id,
            )
            if material:
                await stage_scoring_refresh(
                    self.session,
                    match_id=match.id,
                    innings_id=innings.id,
                    projection_revision=innings.projection_revision,
                    reason="correction",
                )
            # Serialize before committing so response failure also rolls back.
            response = DeliveryCorrectionResponse(
                **_delivery_response(delivery, innings, match).model_dump(),
                match_id=match.id,
                match_version_number=match.version_number,
                match_lifecycle_state=(
                    MatchLifecycleState.COMPLETED
                    if replay.lifecycle_state is MatchLifecycleState.COMPLETED
                    else MatchLifecycleState.IN_PROGRESS
                ),
                innings_lifecycle_state=state.lifecycle_state,
                reconciliation_reason=(
                    "incompatible_replay"
                    if state.reconciliation_sequence is not None
                    else None
                ),
                reconciliation_sequence=state.reconciliation_sequence,
                unreplayed_attempts=state.unreplayed_attempts,
                result_code=replay.result_code,
                result_details=replay.result_details,
                match_blocking_state=BlockingStateResponse.model_validate(
                    replay.blocking_state.as_dict()
                ),
            )
            await self.session.commit()
            logger.info(
                "Scoring delivery corrected",
                extra={
                    "request_id": request_id,
                    "match_id": str(match_id),
                    "innings_id": str(innings_id),
                    "delivery_id": str(delivery_id),
                    "expected_version": payload.innings_version_number,
                    "resulting_version": innings.version_number,
                    "outcome": "committed",
                },
            )
            return response
        except Exception as exc:
            await self.session.rollback()
            logger.info(
                "Scoring correction rejected",
                extra={
                    "request_id": request_id,
                    "match_id": str(match_id),
                    "innings_id": str(innings_id),
                    "delivery_id": str(delivery_id),
                    "outcome": type(exc).__name__,
                },
            )
            raise

    @classmethod
    def _validate_revision_chain(cls, delivery: Delivery) -> None:
        revisions = sorted(delivery.revisions, key=lambda item: item.revision_number)
        active = cls._active_revision(delivery)
        if [item.revision_number for item in revisions] != list(
            range(1, len(revisions) + 1)
        ) or active is not revisions[-1]:
            raise ScoringRevisionError(
                "Delivery revision history is not a single active chain."
            )
        for index, revision in enumerate(revisions):
            expected = revisions[index - 1].id if index else None
            if revision.supersedes_revision_id != expected:
                raise ScoringRevisionError("Delivery revision predecessor is invalid.")

    async def get_innings(
        self,
        match_id: UUID,
        innings_id: UUID,
        authenticated_user: User | UUID,
    ) -> InningsResponse:
        context = await ScoringAuthorizationAdapter(self.session).load_context(
            authenticated_user
        )
        match = await self._load_match(match_id)
        require_scoring_read_scope(context, match)
        return _innings_response(
            await self._load_innings(match_id, innings_id, include_history=False), match
        )

    async def get_next_bowler(
        self,
        match_id: UUID,
        innings_id: UUID,
        authenticated_user: User | UUID,
    ) -> NextBowlerResponse:
        """Read deterministic bowler options from persisted projections."""
        context = await ScoringAuthorizationAdapter(self.session).load_context(
            authenticated_user
        )
        match = await self._load_match(match_id)
        require_scoring_read_scope(context, match)
        innings = await self._load_innings(match_id, innings_id, include_history=False)
        return _next_bowler_response(innings, match)

    async def select_next_bowler(
        self,
        match_id: UUID,
        innings_id: UUID,
        payload: SelectNextBowlerRequest,
        authenticated_user: User | UUID,
        *,
        request_id: str | None = None,
    ) -> InningsResponse:
        """Commit one eligible, explicitly chosen over-boundary transition with OCC."""
        try:
            context = await ScoringAuthorizationAdapter(self.session).load_context(
                authenticated_user
            )
            match = await self._load_match(match_id, for_update=True)
            require_scoring_mutation_scope(context, match)
            innings = await self._load_innings(match_id, innings_id)
            if (
                MatchLifecycleState(match.lifecycle_state)
                is not MatchLifecycleState.IN_PROGRESS
                or InningsLifecycleState(innings.lifecycle_state)
                is not InningsLifecycleState.IN_PROGRESS
                or innings.reconciliation_reason is not None
            ):
                raise ScoringLifecycleError(
                    "Next bowler requires an in-progress Match and Innings "
                    "without reconciliation."
                )
            options = _next_bowler_response(innings, match)
            if (
                innings.current_bowler_participant_id is not None
                or innings.legal_balls == 0
                or options.over_progress.balls_in_partial_over != 0
            ):
                raise ScoringLifecycleError(
                    "Next bowler requires a completed over and an empty selection."
                )
            candidate = next(
                (
                    c
                    for c in options.candidates
                    if c.participant_id == payload.bowler_participant_id
                ),
                None,
            )
            if candidate is None:
                raise ScoringConflictError(
                    "Bowler is not a fixed fielding-side participant."
                )
            if not candidate.is_eligible:
                raise ScoringConflictError(
                    f"Bowler is ineligible: {candidate.reason_code}."
                )
            if (
                payload.bowler_participant_id != options.suggested_bowler_participant_id
                and payload.override_reason is None
            ):
                raise ScoringValidationError(
                    "An alternative to the suggestion requires override_reason."
                )
            next_version = await self._claim_innings_version(
                match, innings, payload.innings_version_number
            )
            innings.version_number = next_version
            anchor_sequence, anchor_revision_id = self._last_replay_anchor(innings)
            innings.transition_events.append(
                InningsTransitionEvent(
                    event_kind=InningsTransitionType.NEXT_BOWLER,
                    participant_id=payload.bowler_participant_id,
                    anchored_attempted_sequence=anchor_sequence,
                    anchored_revision_id=anchor_revision_id,
                    over_number=options.over_progress.overs_completed,
                    reason=payload.override_reason,
                    created_by_user_id=context.user.id,
                    created_at=datetime.now(UTC),
                )
            )
            state = self._replay_orm(match, innings)
            await persist_innings_projection(
                self.session,
                innings,
                state,
                over_length_legal_balls=options.over_progress.over_length_legal_balls,
            )
            await self.session.commit()
            logger.info(
                "Scoring next bowler selected",
                extra={
                    "request_id": request_id,
                    "match_id": str(match_id),
                    "innings_id": str(innings_id),
                    "expected_version": payload.innings_version_number,
                    "resulting_version": next_version,
                    "outcome": "committed",
                },
            )
            reloaded_match = await self._load_match(match_id)
            reloaded_innings = await self._load_innings(
                match_id, innings_id, include_history=False
            )
            return _innings_response(reloaded_innings, reloaded_match)
        except Exception as exc:
            await self.session.rollback()
            logger.info(
                "Scoring next bowler rejected",
                extra={
                    "request_id": request_id,
                    "match_id": str(match_id),
                    "innings_id": str(innings_id),
                    "expected_version": payload.innings_version_number,
                    "outcome": type(exc).__name__,
                },
            )
            raise

    async def list_delivery_history(
        self,
        match_id: UUID,
        innings_id: UUID,
        authenticated_user: User | UUID,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> DeliveryHistoryResponse:
        context = await ScoringAuthorizationAdapter(self.session).load_context(
            authenticated_user
        )
        match = await self._load_match(match_id)
        require_scoring_read_scope(context, match)
        innings = await self._load_innings(match_id, innings_id)
        deliveries = [
            delivery
            for delivery in sorted(
                innings.deliveries, key=lambda value: value.attempted_sequence
            )
            if delivery.attempted_sequence > after_sequence
        ][:limit]
        return DeliveryHistoryResponse(
            innings_id=innings.id,
            after_sequence=after_sequence,
            limit=limit,
            deliveries=[
                _delivery_response(delivery, innings, match) for delivery in deliveries
            ],
            next_after_sequence=(
                deliveries[-1].attempted_sequence
                if deliveries
                and any(
                    item.attempted_sequence > deliveries[-1].attempted_sequence
                    for item in innings.deliveries
                )
                else None
            ),
        )

    async def select_next_batter(
        self,
        match_id: UUID,
        innings_id: UUID,
        payload: SelectNextBatterRequest,
        authenticated_user: User | UUID,
    ) -> InningsResponse:
        """Fill one dismissal/retirement vacancy with an eligible unused batter."""

        try:
            context = await ScoringAuthorizationAdapter(self.session).load_context(
                authenticated_user
            )
            match = await self._load_match(match_id, for_update=True)
            innings = await self._load_innings(match_id, innings_id)
            require_scoring_mutation_scope(context, match)
            if InningsLifecycleState(innings.lifecycle_state) is not (
                InningsLifecycleState.IN_PROGRESS
            ):
                raise ScoringLifecycleError("Next batter requires an active Innings.")
            active_ids = {
                value
                for value in (
                    innings.striker_participant_id,
                    innings.non_striker_participant_id,
                )
                if value is not None
            }
            if len(active_ids) != 1 or payload.replacing_participant_id in active_ids:
                raise ScoringValidationError(
                    "Next-batter selection requires one resolved batting vacancy."
                )
            entry_by_id = {
                entry.participant_id: entry for entry in innings.batting_entries
            }
            replacement = entry_by_id.get(payload.replacing_participant_id)
            candidate = entry_by_id.get(payload.batter_participant_id)
            if replacement is None or candidate is None:
                raise ScoringValidationError(
                    "Both batter identities must belong to this Innings."
                )
            if replacement.participation_state not in {
                ParticipationState.DISMISSED,
                ParticipationState.RETIRED_HURT,
                ParticipationState.RETIRED_OUT,
            }:
                raise ScoringValidationError("The replaced participant has no vacancy.")
            if ParticipationState(candidate.participation_state) is not (
                ParticipationState.NOT_BATTED
            ):
                raise ScoringValidationError(
                    "The selected next batter is no longer eligible."
                )
            next_version = await self._claim_innings_version(
                match, innings, payload.innings_version_number
            )
            innings.version_number = next_version
            anchor_sequence, anchor_revision_id = self._last_replay_anchor(innings)
            innings.transition_events.append(
                InningsTransitionEvent(
                    event_kind=InningsTransitionType.NEXT_BATTER,
                    participant_id=candidate.participant_id,
                    anchored_attempted_sequence=anchor_sequence,
                    anchored_revision_id=anchor_revision_id,
                    reason=payload.reason,
                    created_by_user_id=context.user.id,
                    created_at=datetime.now(UTC),
                )
            )
            state = self._replay_orm(match, innings)
            capability = capability_from_locked_policy(match.scoring_policy)  # type: ignore[arg-type]
            await persist_innings_projection(
                self.session,
                innings,
                state,
                over_length_legal_balls=capability.over_length_legal_balls,
            )
            await self.session.commit()
            reloaded_match = await self._load_match(match_id)
            reloaded_innings = await self._load_innings(match_id, innings_id)
            return _innings_response(reloaded_innings, reloaded_match)
        except Exception:
            await self.session.rollback()
            raise

    async def _retirement_transition(
        self,
        match_id: UUID,
        innings_id: UUID,
        payload: RetireHurtRequest | RetiredHurtReturnRequest,
        authenticated_user: User | UUID,
        *,
        event_kind: InningsTransitionType,
    ) -> InningsResponse:
        try:
            context = await ScoringAuthorizationAdapter(self.session).load_context(
                authenticated_user
            )
            match = await self._load_match(match_id, for_update=True)
            innings = await self._load_innings(match_id, innings_id)
            require_scoring_mutation_scope(context, match)
            if InningsLifecycleState(innings.lifecycle_state) is not (
                InningsLifecycleState.IN_PROGRESS
            ):
                raise ScoringLifecycleError("Retirement requires an active Innings.")
            if match.scoring_policy is None:
                raise ScoringAuthorityError("Match scoring policy is not locked.")
            capability = capability_from_locked_policy(match.scoring_policy)
            if event_kind not in capability.allowed_transition_types:
                raise ScoringValidationError(
                    "Retirement transition is not enabled by the locked capability."
                )
            entry = next(
                (
                    value
                    for value in innings.batting_entries
                    if value.participant_id == payload.participant_id
                ),
                None,
            )
            if entry is None:
                raise ScoringValidationError("Participant is outside this Innings.")
            if event_kind is InningsTransitionType.RETIRED_HURT:
                if payload.participant_id not in {
                    innings.striker_participant_id,
                    innings.non_striker_participant_id,
                }:
                    raise ScoringValidationError(
                        "Only an active batter can retire hurt."
                    )
            elif ParticipationState(entry.participation_state) is not (
                ParticipationState.RETIRED_HURT
            ) or (
                innings.striker_participant_id is not None
                and innings.non_striker_participant_id is not None
            ):
                raise ScoringValidationError(
                    "A retired-hurt return requires that participant and a vacancy."
                )
            next_version = await self._claim_innings_version(
                match, innings, payload.innings_version_number
            )
            innings.version_number = next_version
            anchor_sequence, anchor_revision_id = self._last_replay_anchor(innings)
            innings.transition_events.append(
                InningsTransitionEvent(
                    event_kind=event_kind,
                    participant_id=payload.participant_id,
                    anchored_attempted_sequence=anchor_sequence,
                    anchored_revision_id=anchor_revision_id,
                    reason=payload.reason,
                    created_by_user_id=context.user.id,
                    created_at=datetime.now(UTC),
                )
            )
            state = self._replay_orm(match, innings)
            await persist_innings_projection(
                self.session,
                innings,
                state,
                over_length_legal_balls=capability.over_length_legal_balls,
            )
            await self.session.commit()
            reloaded_match = await self._load_match(match_id)
            reloaded_innings = await self._load_innings(match_id, innings_id)
            return _innings_response(reloaded_innings, reloaded_match)
        except Exception:
            await self.session.rollback()
            raise

    async def retire_hurt(
        self,
        match_id: UUID,
        innings_id: UUID,
        payload: RetireHurtRequest,
        authenticated_user: User | UUID,
    ) -> InningsResponse:
        return await self._retirement_transition(
            match_id,
            innings_id,
            payload,
            authenticated_user,
            event_kind=InningsTransitionType.RETIRED_HURT,
        )

    async def retired_hurt_return(
        self,
        match_id: UUID,
        innings_id: UUID,
        payload: RetiredHurtReturnRequest,
        authenticated_user: User | UUID,
    ) -> InningsResponse:
        return await self._retirement_transition(
            match_id,
            innings_id,
            payload,
            authenticated_user,
            event_kind=InningsTransitionType.RETIRED_HURT_RETURN,
        )

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


async def start_innings(
    session: AsyncSession,
    match_id: UUID,
    payload: StartInningsRequest,
    authenticated_user: User | UUID,
    *,
    request_id: str | None = None,
) -> InningsResponse:
    return await ScoringService(session).start_innings(
        match_id,
        payload,
        authenticated_user,
        request_id=request_id,
    )


async def append_delivery(
    session: AsyncSession,
    match_id: UUID,
    innings_id: UUID,
    payload: AppendDeliveryRequest,
    authenticated_user: User | UUID,
    *,
    request_id: str | None = None,
) -> DeliveryResponse:
    return await ScoringService(session).append_delivery(
        match_id,
        innings_id,
        payload,
        authenticated_user,
        request_id=request_id,
    )


async def select_next_batter(
    session: AsyncSession,
    match_id: UUID,
    innings_id: UUID,
    payload: SelectNextBatterRequest,
    authenticated_user: User | UUID,
) -> InningsResponse:
    return await ScoringService(session).select_next_batter(
        match_id,
        innings_id,
        payload,
        authenticated_user,
    )


async def retire_hurt(
    session: AsyncSession,
    match_id: UUID,
    innings_id: UUID,
    payload: RetireHurtRequest,
    authenticated_user: User | UUID,
) -> InningsResponse:
    return await ScoringService(session).retire_hurt(
        match_id,
        innings_id,
        payload,
        authenticated_user,
    )


async def retired_hurt_return(
    session: AsyncSession,
    match_id: UUID,
    innings_id: UUID,
    payload: RetiredHurtReturnRequest,
    authenticated_user: User | UUID,
) -> InningsResponse:
    return await ScoringService(session).retired_hurt_return(
        match_id,
        innings_id,
        payload,
        authenticated_user,
    )
