"""Transactional Match-scoring application commands."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import (
    BlockingReasonCode,
    BlockingStateKind,
    DeliveryRevisionState,
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
    ParticipantSummaryResponse,
    RetiredHurtReturnRequest,
    RetireHurtRequest,
    ScoringPolicyResponse,
    SelectNextBatterRequest,
    StartInningsRequest,
    WicketRequest,
    WicketResponse,
)
from src.services.business_audit_service import BusinessAuditService
from src.services.occ import check_and_increment_version
from src.services.scoring.audit import (
    record_innings_started,
    record_scoring_initialization,
)
from src.services.scoring.authorization import (
    ScoringAuthorizationAdapter,
    require_configuration_scope,
    require_scoring_mutation_scope,
    require_scoring_read_scope,
    validate_innings_selections,
)
from src.services.scoring.errors import (
    ScoringAuthorityError,
    ScoringLifecycleError,
    ScoringReconciliationError,
    ScoringSequenceError,
    ScoringValidationError,
    ScoringVisibilityError,
)
from src.services.scoring.policy import (
    capability_from_locked_policy,
    resolve_format_capability,
)
from src.services.scoring.projections import persist_innings_projection
from src.services.scoring.replay import (
    ReplayDelivery,
    ReplayParticipant,
    ReplaySeed,
    ReplayTransition,
    derive_innings_blocking_state,
    replay_innings,
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
        over_number=active.over_number,
        ball_in_over=active.ball_in_over,
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

    async def _load_innings(self, match_id: UUID, innings_id: UUID) -> Innings:
        statement = (
            select(Innings)
            .options(
                selectinload(Innings.batting_entries),
                selectinload(Innings.deliveries)
                .selectinload(Delivery.revisions)
                .selectinload(DeliveryRevision.wicket_event),
                selectinload(Innings.deliveries)
                .selectinload(Delivery.revisions)
                .selectinload(DeliveryRevision.fielders),
                selectinload(Innings.transition_events),
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
    def _replay_orm(cls, match: Match, innings: Innings):
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
        if deliveries:
            opening = cls._active_revision(deliveries[0])
            opening_striker_id = opening.striker_participant_id
            opening_non_striker_id = opening.non_striker_participant_id
            opening_bowler_id = opening.bowler_participant_id
        else:
            stored_opening = innings.state_snapshot.get("opening_selections")
            if isinstance(stored_opening, dict):
                try:
                    opening_striker_id = UUID(
                        str(stored_opening["striker_participant_id"])
                    )
                    opening_non_striker_id = UUID(
                        str(stored_opening["non_striker_participant_id"])
                    )
                    opening_bowler_id = UUID(
                        str(stored_opening["bowler_participant_id"])
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ScoringReconciliationError(
                        "The stored opening selections are invalid."
                    ) from exc
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
        return replay_innings(seed, replay_deliveries, replay_transitions)

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
            match = await self._load_match(match_id)
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
            match = await self._load_match(match_id)
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
            next_version = await check_and_increment_version(
                self.session,
                Innings,
                innings.id,
                payload.innings_version_number,
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
            reloaded = await self._load_innings(match_id, innings_id)
            persisted = next(
                value for value in reloaded.deliveries if value.id == delivery.id
            )
            return _delivery_response(
                persisted,
                reloaded,
                await self._load_match(match_id),
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
        return _innings_response(await self._load_innings(match_id, innings_id), match)

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
            match = await self._load_match(match_id)
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
            next_version = await check_and_increment_version(
                self.session,
                Innings,
                innings.id,
                payload.innings_version_number,
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
            match = await self._load_match(match_id)
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
            next_version = await check_and_increment_version(
                self.session,
                Innings,
                innings.id,
                payload.innings_version_number,
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
