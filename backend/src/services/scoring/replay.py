"""Deterministic replay of active delivery revisions and explicit transitions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID

from src.enums import (
    BlockingReasonCode,
    BlockingStateKind,
    DismissedEnd,
    ExplicitMatchCompletionBoundary,
    FormatCapabilityProfile,
    InningsCompletionMode,
    InningsLifecycleState,
    InningsTransitionType,
    MatchLifecycleState,
    MatchResultCode,
    MatchSideCode,
    ParticipationState,
    ScoringDismissalType,
)
from src.schemas.scoring import DeliveryFactsRequest
from src.services.scoring.errors import ScoringReconciliationError
from src.services.scoring.policy import FormatCapability, bowler_eligibility
from src.services.scoring.rules import (
    DeliveryClassification,
    checked_scoring_add,
    classify_delivery,
)


@dataclass(frozen=True, slots=True)
class BlockingState:
    kind: BlockingStateKind
    is_blocked: bool
    reason_code: BlockingReasonCode | None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {
            "kind": self.kind.value,
            "is_blocked": self.is_blocked,
            "reason_code": self.reason_code.value if self.reason_code else None,
        }


@dataclass(frozen=True, slots=True)
class ReplayParticipant:
    id: UUID
    batting_order_position: int


@dataclass(frozen=True, slots=True)
class ReplayDelivery:
    attempted_sequence: int
    facts: DeliveryFactsRequest


@dataclass(frozen=True, slots=True)
class ReplayTransition:
    event_kind: InningsTransitionType
    participant_id: UUID | None = None
    anchored_attempted_sequence: int | None = None
    completion_kind: InningsCompletionMode | None = None


@dataclass(frozen=True, slots=True)
class ReplaySeed:
    capability: FormatCapability
    batting_participants: tuple[ReplayParticipant, ...]
    fielding_participant_ids: frozenset[UUID]
    opening_striker_participant_id: UUID
    opening_non_striker_participant_id: UUID
    opening_bowler_participant_id: UUID
    lifecycle_state: InningsLifecycleState = InningsLifecycleState.IN_PROGRESS
    match_lifecycle_state: MatchLifecycleState = MatchLifecycleState.IN_PROGRESS
    target_runs: int | None = None


@dataclass(slots=True)
class ParticipantReplaySummary:
    participation_state: ParticipationState = ParticipationState.NOT_BATTED
    dismissal_type: ScoringDismissalType | None = None
    batting_runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    bowling_legal_balls: int = 0
    runs_conceded: int = 0
    bowling_wickets: int = 0
    wides: int = 0
    no_balls: int = 0
    fielding_dismissals: int = 0


@dataclass(slots=True)
class OverReplay:
    over_number: int
    bowler_participant_id: UUID
    legal_ball_count: int = 0
    total_runs: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    is_complete: bool = False


@dataclass(slots=True)
class ReplayState:
    lifecycle_state: InningsLifecycleState
    opening_striker_participant_id: UUID
    opening_non_striker_participant_id: UUID
    opening_bowler_participant_id: UUID
    striker_participant_id: UUID | None
    non_striker_participant_id: UUID | None
    current_bowler_participant_id: UUID | None
    completion_reason: InningsCompletionMode | None = None
    reconciliation_sequence: int | None = None
    unreplayed_attempts: int = 0
    legal_balls: int = 0
    total_runs: int = 0
    wickets_lost: int = 0
    target_runs: int | None = None
    extras: dict[str, int] = field(
        default_factory=lambda: {
            "wides": 0,
            "no_balls": 0,
            "byes": 0,
            "leg_byes": 0,
            "penalty_runs": 0,
        }
    )
    participants: dict[UUID, ParticipantReplaySummary] = field(default_factory=dict)
    overs: dict[int, OverReplay] = field(default_factory=dict)
    fall_of_wickets: list[dict[str, object]] = field(default_factory=list)
    classifications: list[DeliveryClassification] = field(default_factory=list)
    blocking_state: BlockingState = field(
        default_factory=lambda: BlockingState(BlockingStateKind.NONE, False, None)
    )


def derive_innings_blocking_state(
    *,
    match_lifecycle_state: MatchLifecycleState,
    innings_lifecycle_state: InningsLifecycleState,
    striker_participant_id: UUID | None,
    non_striker_participant_id: UUID | None,
    current_bowler_participant_id: UUID | None,
    has_eligible_bowler: bool = True,
) -> BlockingState:
    """Derive the sole serialized Innings progression state in fixed precedence."""

    if match_lifecycle_state is MatchLifecycleState.ABANDONED:
        return BlockingState(
            BlockingStateKind.MATCH_ABANDONED,
            True,
            BlockingReasonCode.MATCH_ABANDONED,
        )
    if match_lifecycle_state is MatchLifecycleState.COMPLETED:
        return BlockingState(
            BlockingStateKind.MATCH_COMPLETED,
            True,
            BlockingReasonCode.MATCH_COMPLETED,
        )
    if innings_lifecycle_state is InningsLifecycleState.RECONCILIATION_REQUIRED:
        return BlockingState(
            BlockingStateKind.RECONCILIATION_REQUIRED,
            True,
            BlockingReasonCode.INCOMPATIBLE_REPLAY,
        )
    if innings_lifecycle_state is InningsLifecycleState.PENDING:
        return BlockingState(
            BlockingStateKind.INNINGS_NOT_STARTED,
            True,
            BlockingReasonCode.INNINGS_NOT_STARTED,
        )
    if innings_lifecycle_state is InningsLifecycleState.COMPLETED:
        return BlockingState(
            BlockingStateKind.INNINGS_COMPLETED,
            True,
            BlockingReasonCode.INNINGS_COMPLETED,
        )
    if striker_participant_id is None or non_striker_participant_id is None:
        return BlockingState(
            BlockingStateKind.AWAITING_NEXT_BATTER,
            True,
            BlockingReasonCode.NEXT_BATTER_REQUIRED,
        )
    if current_bowler_participant_id is None:
        return BlockingState(
            BlockingStateKind.AWAITING_NEXT_BOWLER,
            True,
            (
                BlockingReasonCode.NEXT_BOWLER_REQUIRED
                if has_eligible_bowler
                else BlockingReasonCode.NO_ELIGIBLE_BOWLER
            ),
        )
    return BlockingState(BlockingStateKind.NONE, False, None)


def derive_match_blocking_state(
    match_lifecycle_state: MatchLifecycleState,
    innings_states: list[ReplayState],
    *,
    required_innings_count: int,
) -> BlockingState:
    """Derive Match progression without persisting a second mutable state."""

    if match_lifecycle_state is MatchLifecycleState.ABANDONED:
        return derive_innings_blocking_state(
            match_lifecycle_state=match_lifecycle_state,
            innings_lifecycle_state=InningsLifecycleState.PENDING,
            striker_participant_id=None,
            non_striker_participant_id=None,
            current_bowler_participant_id=None,
        )
    if match_lifecycle_state is MatchLifecycleState.COMPLETED:
        return derive_innings_blocking_state(
            match_lifecycle_state=match_lifecycle_state,
            innings_lifecycle_state=InningsLifecycleState.COMPLETED,
            striker_participant_id=None,
            non_striker_participant_id=None,
            current_bowler_participant_id=None,
        )
    for state in innings_states:
        if state.lifecycle_state is InningsLifecycleState.RECONCILIATION_REQUIRED:
            return state.blocking_state
    active = next(
        (
            state
            for state in reversed(innings_states)
            if state.lifecycle_state is InningsLifecycleState.IN_PROGRESS
        ),
        None,
    )
    if active is not None:
        return active.blocking_state
    if len(innings_states) < required_innings_count or any(
        state.lifecycle_state is InningsLifecycleState.PENDING
        for state in innings_states
    ):
        return BlockingState(
            BlockingStateKind.INNINGS_NOT_STARTED,
            True,
            BlockingReasonCode.INNINGS_NOT_STARTED,
        )
    return BlockingState(BlockingStateKind.NONE, False, None)


def _apply_transition(
    state: ReplayState, transition: ReplayTransition, seed: ReplaySeed
) -> None:
    participant_id = transition.participant_id
    if transition.event_kind is InningsTransitionType.INNINGS_STARTED:
        return
    if state.lifecycle_state is InningsLifecycleState.COMPLETED:
        if transition.event_kind is InningsTransitionType.INNINGS_COMPLETED:
            return
        raise ScoringReconciliationError("A transition follows innings completion.")
    if (
        transition.event_kind
        in {
            InningsTransitionType.RETIRED_HURT,
            InningsTransitionType.RETIRED_HURT_RETURN,
        }
        and transition.event_kind not in seed.capability.allowed_transition_types
    ):
        raise ScoringReconciliationError("Transition is outside the locked capability.")
    if transition.event_kind is InningsTransitionType.NEXT_BOWLER:
        if (
            participant_id is None
            or state.current_bowler_participant_id is not None
            or state.legal_balls == 0
            or state.legal_balls % seed.capability.over_length_legal_balls
        ):
            raise ScoringReconciliationError(
                "Next-bowler transition requires a completed over "
                "and an empty selection."
            )
        previous = state.overs[
            state.legal_balls // seed.capability.over_length_legal_balls - 1
        ]
        summary = state.participants.get(participant_id)
        decision = bowler_eligibility(
            seed.capability,
            participant_id,
            fielding_participant_ids=seed.fielding_participant_ids,
            legal_balls_bowled=summary.bowling_legal_balls if summary else 0,
            previous_over_bowler_id=previous.bowler_participant_id,
        )
        if not decision.is_eligible:
            raise ScoringReconciliationError(
                f"Next bowler is ineligible: {decision.reason_code}."
            )
        state.current_bowler_participant_id = participant_id
        return
    if transition.event_kind is InningsTransitionType.NEXT_BATTER:
        if participant_id is None or participant_id not in {
            p.id for p in seed.batting_participants
        }:
            raise ScoringReconciliationError("Next-batter transition is invalid.")
        if state.participants[participant_id].participation_state not in {
            ParticipationState.NOT_BATTED,
        }:
            raise ScoringReconciliationError("Next batter is no longer eligible.")
        if state.striker_participant_id is None:
            state.striker_participant_id = participant_id
        elif state.non_striker_participant_id is None:
            state.non_striker_participant_id = participant_id
        else:
            raise ScoringReconciliationError("Next-batter transition has no vacancy.")
        state.participants[
            participant_id
        ].participation_state = ParticipationState.ACTIVE
        return
    if transition.event_kind is InningsTransitionType.RETIRED_HURT:
        if participant_id is None or participant_id not in state.participants:
            raise ScoringReconciliationError("Retired-hurt transition is invalid.")
        if participant_id not in {
            state.striker_participant_id,
            state.non_striker_participant_id,
        }:
            raise ScoringReconciliationError(
                "Only an active batter can transition to retired hurt."
            )
        state.participants[
            participant_id
        ].participation_state = ParticipationState.RETIRED_HURT
        if state.striker_participant_id == participant_id:
            state.striker_participant_id = None
        if state.non_striker_participant_id == participant_id:
            state.non_striker_participant_id = None
        return
    if transition.event_kind is InningsTransitionType.RETIRED_HURT_RETURN:
        if (
            participant_id is None
            or participant_id not in state.participants
            or state.participants[participant_id].participation_state
            is not ParticipationState.RETIRED_HURT
        ):
            raise ScoringReconciliationError("Retired-hurt return is invalid.")
        if state.striker_participant_id is None:
            state.striker_participant_id = participant_id
        elif state.non_striker_participant_id is None:
            state.non_striker_participant_id = participant_id
        else:
            raise ScoringReconciliationError("No batting vacancy exists for return.")
        state.participants[
            participant_id
        ].participation_state = ParticipationState.ACTIVE
        return
    if transition.event_kind is InningsTransitionType.INNINGS_COMPLETED:
        automatic_modes = {
            InningsCompletionMode.ALL_OUT,
            InningsCompletionMode.LEGAL_BALL_LIMIT,
            InningsCompletionMode.TARGET_REACHED,
        }
        if transition.completion_kind in automatic_modes or (
            transition.completion_kind is None
            and set(seed.capability.allowed_innings_completion_modes).issubset(
                automatic_modes
            )
        ):
            # An automatic completion records an outcome, not a scorer choice.
            # Recompute it after correction so a compatible innings can reopen.
            state.completion_reason = _automatic_completion(state, seed.capability)
            if state.completion_reason is not None:
                state.lifecycle_state = InningsLifecycleState.COMPLETED
            return
        if (
            transition.completion_kind
            not in {
                InningsCompletionMode.DECLARATION,
                InningsCompletionMode.MANUAL,
            }
            or transition.completion_kind
            not in seed.capability.allowed_innings_completion_modes
        ):
            raise ScoringReconciliationError(
                "Completion no longer follows from history."
            )
        state.lifecycle_state = InningsLifecycleState.COMPLETED
        state.completion_reason = transition.completion_kind


def _automatic_completion(
    state: ReplayState, capability: FormatCapability
) -> InningsCompletionMode | None:
    modes = capability.allowed_innings_completion_modes
    if (
        InningsCompletionMode.TARGET_REACHED in modes
        and state.target_runs is not None
        and state.total_runs >= state.target_runs
    ):
        return InningsCompletionMode.TARGET_REACHED
    if (
        InningsCompletionMode.ALL_OUT in modes
        and state.wickets_lost >= capability.wicket_limit
    ):
        return InningsCompletionMode.ALL_OUT
    if (
        InningsCompletionMode.LEGAL_BALL_LIMIT in modes
        and capability.legal_ball_limit is not None
        and state.legal_balls >= capability.legal_ball_limit
    ):
        return InningsCompletionMode.LEGAL_BALL_LIMIT
    return None


def _apply_delivery(
    state: ReplayState, delivery: ReplayDelivery, seed: ReplaySeed
) -> None:
    if state.lifecycle_state is InningsLifecycleState.COMPLETED:
        raise ScoringReconciliationError("A delivery follows innings completion.")
    facts = delivery.facts
    if (
        facts.striker_participant_id != state.striker_participant_id
        or facts.non_striker_participant_id != state.non_striker_participant_id
        or facts.bowler_participant_id != state.current_bowler_participant_id
    ):
        raise ScoringReconciliationError(
            "A delivery conflicts with the replayed active selections."
        )
    classification = classify_delivery(
        facts,
        legal_balls_before=state.legal_balls,
        over_length_legal_balls=seed.capability.over_length_legal_balls,
        innings_total_before=state.total_runs,
        fielding_participant_ids=seed.fielding_participant_ids,
        allowed_dismissal_types=frozenset(seed.capability.allowed_dismissal_types),
    )
    previous_over = state.overs.get(classification.over_number - 1)
    decision = bowler_eligibility(
        seed.capability,
        facts.bowler_participant_id,
        fielding_participant_ids=seed.fielding_participant_ids,
        legal_balls_bowled=state.participants[
            facts.bowler_participant_id
        ].bowling_legal_balls,
        previous_over_bowler_id=(
            previous_over.bowler_participant_id if previous_over else None
        ),
    )
    if not decision.is_eligible:
        raise ScoringReconciliationError(
            f"Delivery bowler is ineligible: {decision.reason_code}."
        )
    existing_over = state.overs.get(classification.over_number)
    if (
        existing_over is not None
        and existing_over.bowler_participant_id != facts.bowler_participant_id
    ):
        raise ScoringReconciliationError("One over contains multiple bowlers.")
    state.classifications.append(classification)
    state.total_runs += classification.total_runs
    state.legal_balls += int(classification.is_legal)
    extras = facts.extras
    state.extras["wides"] += extras.wide_runs
    state.extras["no_balls"] += extras.no_ball_penalty_runs
    state.extras["byes"] += extras.bye_runs
    state.extras["leg_byes"] += extras.leg_bye_runs
    state.extras["penalty_runs"] += extras.penalty_runs

    batter = state.participants[facts.striker_participant_id]
    batter.batting_runs += facts.runs_off_bat
    batter.balls_faced += int(classification.balls_faced)
    batter.fours += int(classification.is_four)
    batter.sixes += int(classification.is_six)
    bowler = state.participants[facts.bowler_participant_id]
    bowler.bowling_legal_balls += int(classification.is_legal)
    bowler.runs_conceded += classification.bowler_conceded_runs
    bowler.wides += extras.wide_runs
    bowler.no_balls += extras.no_ball_penalty_runs

    over = state.overs.setdefault(
        classification.over_number,
        OverReplay(classification.over_number, facts.bowler_participant_id),
    )
    over.legal_ball_count += int(classification.is_legal)
    over.total_runs += classification.total_runs
    over.runs_conceded += classification.bowler_conceded_runs

    if classification.completed_runs % 2:
        state.striker_participant_id, state.non_striker_participant_id = (
            state.non_striker_participant_id,
            state.striker_participant_id,
        )
    wicket = classification.wicket
    if wicket is not None:
        state.wickets_lost += int(wicket.counts_as_team_wicket)
        over.wickets += int(wicket.counts_as_team_wicket)
        dismissed = state.participants[wicket.dismissed_participant_id]
        dismissed.participation_state = (
            ParticipationState.RETIRED_OUT
            if wicket.dismissal_type is ScoringDismissalType.RETIRED_OUT
            else ParticipationState.DISMISSED
        )
        dismissed.dismissal_type = wicket.dismissal_type
        if wicket.credited_to_bowler:
            bowler.bowling_wickets += 1
        if facts.wicket is not None:
            for fielder in facts.wicket.fielders:
                state.participants[fielder.participant_id].fielding_dismissals += 1
        if state.striker_participant_id == wicket.dismissed_participant_id:
            state.striker_participant_id = None
        if state.non_striker_participant_id == wicket.dismissed_participant_id:
            state.non_striker_participant_id = None
        if wicket.dismissal_type is ScoringDismissalType.RUN_OUT:
            survivor = (
                facts.non_striker_participant_id
                if wicket.dismissed_participant_id == facts.striker_participant_id
                else facts.striker_participant_id
            )
            if wicket.dismissed_end is DismissedEnd.STRIKER_END:
                state.striker_participant_id = None
                state.non_striker_participant_id = survivor
            else:
                state.striker_participant_id = survivor
                state.non_striker_participant_id = None
        state.fall_of_wickets.append(
            {
                "attempted_sequence": delivery.attempted_sequence,
                "score": state.total_runs,
                "wicket_number": state.wickets_lost,
                "participant_id": str(wicket.dismissed_participant_id),
                "dismissal_type": wicket.dismissal_type.value,
            }
        )

    if (
        classification.is_legal
        and state.legal_balls % seed.capability.over_length_legal_balls == 0
    ):
        over.is_complete = True
        state.striker_participant_id, state.non_striker_participant_id = (
            state.non_striker_participant_id,
            state.striker_participant_id,
        )
        state.current_bowler_participant_id = None


def replay_innings(
    seed: ReplaySeed,
    deliveries: list[ReplayDelivery] | tuple[ReplayDelivery, ...],
    transitions: list[ReplayTransition] | tuple[ReplayTransition, ...] = (),
    *,
    correction_from_sequence: int | None = None,
    derive_completion: bool = False,
) -> ReplayState:
    """Fold active facts into a deterministic current Innings state."""

    participant_ids = {participant.id for participant in seed.batting_participants}
    if {
        seed.opening_striker_participant_id,
        seed.opening_non_striker_participant_id,
    }.difference(participant_ids):
        raise ScoringReconciliationError(
            "Opening batters are outside the batting side."
        )
    if seed.opening_striker_participant_id == seed.opening_non_striker_participant_id:
        raise ScoringReconciliationError("Opening batters must be distinct.")
    if participant_ids.intersection(seed.fielding_participant_ids):
        raise ScoringReconciliationError("Batting and fielding sides overlap.")
    if seed.opening_bowler_participant_id not in seed.fielding_participant_ids:
        raise ScoringReconciliationError("Opening bowler is outside the fielding side.")

    summaries = {
        participant.id: ParticipantReplaySummary()
        for participant in seed.batting_participants
    }
    summaries.update(
        {
            participant_id: ParticipantReplaySummary()
            for participant_id in seed.fielding_participant_ids
        }
    )
    summaries[
        seed.opening_striker_participant_id
    ].participation_state = ParticipationState.ACTIVE
    summaries[
        seed.opening_non_striker_participant_id
    ].participation_state = ParticipationState.ACTIVE
    state = ReplayState(
        lifecycle_state=seed.lifecycle_state,
        opening_striker_participant_id=seed.opening_striker_participant_id,
        opening_non_striker_participant_id=seed.opening_non_striker_participant_id,
        opening_bowler_participant_id=seed.opening_bowler_participant_id,
        striker_participant_id=seed.opening_striker_participant_id,
        non_striker_participant_id=seed.opening_non_striker_participant_id,
        current_bowler_participant_id=seed.opening_bowler_participant_id,
        target_runs=seed.target_runs,
        participants=summaries,
    )
    transitions_by_anchor: dict[int, list[ReplayTransition]] = {}
    sequences = [
        delivery.attempted_sequence
        for delivery in sorted(deliveries, key=lambda item: item.attempted_sequence)
    ]
    if sequences != list(range(1, len(deliveries) + 1)):
        raise ScoringReconciliationError(
            "Delivery attempts must be unique and contiguous."
        )
    for transition in transitions:
        if (transition.anchored_attempted_sequence or 0) > len(deliveries):
            raise ScoringReconciliationError(
                "A transition references a missing delivery."
            )
        transitions_by_anchor.setdefault(
            transition.anchored_attempted_sequence or 0, []
        ).append(transition)
    for transition in transitions_by_anchor.get(0, []):
        _apply_transition(state, transition, seed)

    for delivery in sorted(deliveries, key=lambda item: item.attempted_sequence):
        try:
            _apply_delivery(state, delivery, seed)
        except ScoringReconciliationError:
            if (
                correction_from_sequence is None
                or delivery.attempted_sequence <= correction_from_sequence
            ):
                raise
            state.lifecycle_state = InningsLifecycleState.RECONCILIATION_REQUIRED
            state.reconciliation_sequence = delivery.attempted_sequence
            state.unreplayed_attempts = len(deliveries) - len(state.classifications)
            break
        if derive_completion:
            state.completion_reason = _automatic_completion(state, seed.capability)
            if state.completion_reason is not None:
                state.lifecycle_state = InningsLifecycleState.COMPLETED
        try:
            for transition in transitions_by_anchor.get(
                delivery.attempted_sequence, []
            ):
                _apply_transition(state, transition, seed)
        except ScoringReconciliationError:
            if (
                correction_from_sequence is None
                or delivery.attempted_sequence < correction_from_sequence
            ):
                raise
            state.lifecycle_state = InningsLifecycleState.RECONCILIATION_REQUIRED
            state.reconciliation_sequence = delivery.attempted_sequence
            state.unreplayed_attempts = len(deliveries) - len(state.classifications)
            break

    current_over_number = state.legal_balls // seed.capability.over_length_legal_balls
    previous_over = state.overs.get(current_over_number - 1)
    has_eligible_bowler = any(
        bowler_eligibility(
            seed.capability,
            participant_id,
            fielding_participant_ids=seed.fielding_participant_ids,
            legal_balls_bowled=state.participants[participant_id].bowling_legal_balls,
            previous_over_bowler_id=(
                previous_over.bowler_participant_id if previous_over else None
            ),
        ).is_eligible
        for participant_id in seed.fielding_participant_ids
    )
    state.blocking_state = derive_innings_blocking_state(
        match_lifecycle_state=seed.match_lifecycle_state,
        innings_lifecycle_state=state.lifecycle_state,
        striker_participant_id=state.striker_participant_id,
        non_striker_participant_id=state.non_striker_participant_id,
        current_bowler_participant_id=state.current_bowler_participant_id,
        has_eligible_bowler=has_eligible_bowler,
    )
    return state


replay_active_innings = replay_innings


@dataclass(frozen=True, slots=True)
class ReplayInnings:
    """One authoritative innings stream in the locked Match sequence."""

    innings_number: int
    batting_side_code: MatchSideCode | str
    seed: ReplaySeed
    deliveries: tuple[ReplayDelivery, ...] = ()
    transitions: tuple[ReplayTransition, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchReplayState:
    innings_states: tuple[ReplayState, ...]
    lifecycle_state: MatchLifecycleState
    result_code: MatchResultCode
    result_details: dict[str, object]
    result: str
    blocking_state: BlockingState


def _match_result(
    capability: FormatCapability,
    states: list[ReplayState],
    prior_lifecycle_state: MatchLifecycleState,
    prior_result_code: MatchResultCode,
    prior_result_details: dict[str, object],
) -> tuple[MatchResultCode, dict[str, object], str]:
    if any(
        s.lifecycle_state is InningsLifecycleState.RECONCILIATION_REQUIRED
        for s in states
    ):
        return MatchResultCode.PENDING, {}, "Pending"
    complete = bool(states) and all(
        s.lifecycle_state is InningsLifecycleState.COMPLETED for s in states
    )
    if (
        complete
        and len(states) == len(capability.innings_sequence)
        and capability.capability_profile is not FormatCapabilityProfile.OTHER
    ):
        totals: dict[str, int] = {}
        for code, state in zip(capability.innings_sequence, states, strict=True):
            totals[code.value] = checked_scoring_add(
                state.total_runs, current=totals.get(code.value, 0)
            )
        first_code, second_code = capability.innings_sequence[:2]
        first_total, second_total = totals[first_code.value], totals[second_code.value]
        if first_total == second_total:
            return MatchResultCode.TIE, {"side_totals": totals}, "Match tied"
        winner = first_code if first_total > second_total else second_code
        if states[-1].completion_reason is InningsCompletionMode.TARGET_REACHED:
            margin = max(0, capability.wicket_limit - states[-1].wickets_lost)
            return (
                MatchResultCode.WIN_BY_WICKETS,
                {
                    "winning_side_code": winner.value,
                    "wickets_remaining": margin,
                    "side_totals": totals,
                },
                f"{winner.value} won by {margin} wickets",
            )
        margin = abs(first_total - second_total)
        return (
            MatchResultCode.WIN_BY_RUNS,
            {
                "winning_side_code": winner.value,
                "runs_margin": margin,
                "side_totals": totals,
            },
            f"{winner.value} won by {margin} runs",
        )
    if (
        prior_lifecycle_state is MatchLifecycleState.COMPLETED
        and prior_result_code
        in {
            MatchResultCode.DRAW,
            MatchResultCode.DECLARED,
            MatchResultCode.MANUAL,
        }
        and prior_result_code in capability.allowed_result_codes
    ):
        boundary = capability.explicit_match_completion_boundary
        if boundary is ExplicitMatchCompletionBoundary.ANY_NONTERMINAL_STATE or (
            boundary is ExplicitMatchCompletionBoundary.AFTER_COMPLETED_INNINGS
            and complete
        ):
            return (
                prior_result_code,
                dict(prior_result_details),
                prior_result_code.value.capitalize(),
            )
    return MatchResultCode.PENDING, {}, "Pending"


def replay_match(
    capability: FormatCapability,
    innings: list[ReplayInnings] | tuple[ReplayInnings, ...],
    *,
    correction_innings_number: int,
    correction_sequence: int,
    prior_lifecycle_state: MatchLifecycleState = MatchLifecycleState.IN_PROGRESS,
    prior_result_code: MatchResultCode = MatchResultCode.PENDING,
    prior_result_details: dict[str, object] | None = None,
) -> MatchReplayState:
    """Rebuild correction outcomes from history, preserving incompatible choices.

    A conflict after the correction retains the last compatible projection and
    its exact boundary. The remaining immutable attempts are explicitly counted
    as unreplayed; ordinary scoring cannot use this partial state.
    """

    if prior_lifecycle_state not in {
        MatchLifecycleState.IN_PROGRESS,
        MatchLifecycleState.COMPLETED,
    }:
        raise ScoringReconciliationError("Match lifecycle does not permit correction.")
    ordered = sorted(innings, key=lambda item: item.innings_number)
    if [item.innings_number for item in ordered] != list(
        range(1, len(ordered) + 1)
    ) or len(ordered) > len(capability.innings_sequence):
        raise ScoringReconciliationError("Innings do not follow the locked sequence.")
    corrected = next(
        (item for item in ordered if item.innings_number == correction_innings_number),
        None,
    )
    if corrected is None or not 1 <= correction_sequence <= len(corrected.deliveries):
        raise ScoringReconciliationError(
            "Correction boundary is not in the active history."
        )
    states: list[ReplayState] = []
    for item in ordered:
        if (
            MatchSideCode(item.batting_side_code)
            != capability.innings_sequence[item.innings_number - 1]
            or item.seed.capability != capability
        ):
            raise ScoringReconciliationError(
                "Innings capability or sides differ from the locked policy."
            )
        prior_complete = all(
            state.lifecycle_state is InningsLifecycleState.COMPLETED for state in states
        )
        target = None
        if (
            item.innings_number == 2
            and capability.target_mode.value == "prior_innings_plus_one"
            and prior_complete
        ):
            target = checked_scoring_add(
                1, current=states[0].total_runs, field_name="target total"
            )
        seed = replace(
            item.seed,
            lifecycle_state=InningsLifecycleState.IN_PROGRESS,
            match_lifecycle_state=MatchLifecycleState.IN_PROGRESS,
            target_runs=target,
        )
        boundary = (
            correction_sequence
            if item.innings_number == correction_innings_number
            else 0
            if item.innings_number > correction_innings_number
            else None
        )
        state = replay_innings(
            seed,
            item.deliveries if prior_complete else (),
            item.transitions if prior_complete else (),
            correction_from_sequence=boundary,
            derive_completion=True,
        )
        if not prior_complete:
            state.lifecycle_state = InningsLifecycleState.RECONCILIATION_REQUIRED
            state.reconciliation_sequence = 0
            state.unreplayed_attempts = len(item.deliveries)
            state.blocking_state = derive_innings_blocking_state(
                match_lifecycle_state=MatchLifecycleState.IN_PROGRESS,
                innings_lifecycle_state=state.lifecycle_state,
                striker_participant_id=state.striker_participant_id,
                non_striker_participant_id=state.non_striker_participant_id,
                current_bowler_participant_id=state.current_bowler_participant_id,
            )
        states.append(state)
    checked_scoring_add(
        *(state.total_runs for state in states), field_name="Match total"
    )
    code, details, text = _match_result(
        capability,
        states,
        prior_lifecycle_state,
        prior_result_code,
        prior_result_details or {},
    )
    lifecycle = (
        MatchLifecycleState.IN_PROGRESS
        if code is MatchResultCode.PENDING
        else MatchLifecycleState.COMPLETED
    )
    for state in states:
        if lifecycle is MatchLifecycleState.COMPLETED:
            state.blocking_state = derive_innings_blocking_state(
                match_lifecycle_state=lifecycle,
                innings_lifecycle_state=state.lifecycle_state,
                striker_participant_id=state.striker_participant_id,
                non_striker_participant_id=state.non_striker_participant_id,
                current_bowler_participant_id=state.current_bowler_participant_id,
            )
    return MatchReplayState(
        tuple(states),
        lifecycle,
        code,
        details,
        text,
        derive_match_blocking_state(
            lifecycle, states, required_innings_count=len(capability.innings_sequence)
        ),
    )


__all__ = [
    "BlockingState",
    "MatchReplayState",
    "ReplayInnings",
    "replay_match",
    "OverReplay",
    "ParticipantReplaySummary",
    "ReplayDelivery",
    "ReplayParticipant",
    "ReplaySeed",
    "ReplayState",
    "ReplayTransition",
    "derive_innings_blocking_state",
    "derive_match_blocking_state",
    "replay_active_innings",
    "replay_innings",
]
