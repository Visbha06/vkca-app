"""Deterministic replay of active delivery revisions and explicit transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from src.enums import (
    BlockingReasonCode,
    BlockingStateKind,
    InningsLifecycleState,
    InningsTransitionType,
    MatchLifecycleState,
    ParticipationState,
    ScoringDismissalType,
)
from src.schemas.scoring import DeliveryFactsRequest
from src.services.scoring.errors import ScoringReconciliationError
from src.services.scoring.policy import FormatCapability
from src.services.scoring.rules import DeliveryClassification, classify_delivery


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
    if len(innings_states) < required_innings_count:
        return BlockingState(
            BlockingStateKind.INNINGS_NOT_STARTED,
            True,
            BlockingReasonCode.INNINGS_NOT_STARTED,
        )
    return BlockingState(BlockingStateKind.NONE, False, None)


def _apply_transition(state: ReplayState, transition: ReplayTransition) -> None:
    participant_id = transition.participant_id
    if transition.event_kind is InningsTransitionType.INNINGS_STARTED:
        return
    if transition.event_kind is InningsTransitionType.NEXT_BOWLER:
        if participant_id is None:
            raise ScoringReconciliationError(
                "Next-bowler transition has no participant."
            )
        state.current_bowler_participant_id = participant_id
        return
    if transition.event_kind is InningsTransitionType.NEXT_BATTER:
        if participant_id is None or participant_id not in state.participants:
            raise ScoringReconciliationError("Next-batter transition is invalid.")
        if state.participants[participant_id].participation_state not in {
            ParticipationState.NOT_BATTED,
            ParticipationState.RETIRED_HURT,
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
        state.lifecycle_state = InningsLifecycleState.COMPLETED


def replay_innings(
    seed: ReplaySeed,
    deliveries: list[ReplayDelivery] | tuple[ReplayDelivery, ...],
    transitions: list[ReplayTransition] | tuple[ReplayTransition, ...] = (),
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
    for transition in transitions:
        transitions_by_anchor.setdefault(
            transition.anchored_attempted_sequence or 0, []
        ).append(transition)
    for transition in transitions_by_anchor.get(0, []):
        _apply_transition(state, transition)

    expected_sequence = 1
    for delivery in sorted(deliveries, key=lambda item: item.attempted_sequence):
        if delivery.attempted_sequence != expected_sequence:
            raise ScoringReconciliationError(
                "Active delivery attempts are not contiguous from sequence one."
            )
        expected_sequence += 1
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
        if over.bowler_participant_id != facts.bowler_participant_id:
            raise ScoringReconciliationError("One over contains multiple bowlers.")
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
        for transition in transitions_by_anchor.get(delivery.attempted_sequence, []):
            _apply_transition(state, transition)

    state.blocking_state = derive_innings_blocking_state(
        match_lifecycle_state=seed.match_lifecycle_state,
        innings_lifecycle_state=state.lifecycle_state,
        striker_participant_id=state.striker_participant_id,
        non_striker_participant_id=state.non_striker_participant_id,
        current_bowler_participant_id=state.current_bowler_participant_id,
        has_eligible_bowler=bool(seed.fielding_participant_ids),
    )
    return state


replay_active_innings = replay_innings


__all__ = [
    "BlockingState",
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
