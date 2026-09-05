"""Phase 4 pure replay state-machine coverage."""

from uuid import UUID, uuid4

from src.enums import (
    BlockingStateKind,
    InningsLifecycleState,
    InningsTransitionType,
    MatchLifecycleState,
    ParticipationState,
)
from src.schemas.scoring import DeliveryFactsRequest
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.replay import (
    ReplayDelivery,
    ReplayParticipant,
    ReplaySeed,
    ReplayTransition,
    derive_innings_blocking_state,
    replay_innings,
)


def _capability():
    return resolve_format_capability(
        {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        }
    )


def _facts(
    striker: UUID,
    non_striker: UUID,
    bowler: UUID,
    **overrides: object,
) -> DeliveryFactsRequest:
    payload: dict[str, object] = {
        "striker_participant_id": striker,
        "non_striker_participant_id": non_striker,
        "bowler_participant_id": bowler,
        "runs_off_bat": 0,
        "extras": {},
    }
    payload.update(overrides)
    return DeliveryFactsRequest.model_validate(payload)


def _seed(*, target_runs: int | None = None):
    batters = [uuid4(), uuid4(), uuid4()]
    bowlers = [uuid4(), uuid4()]
    return (
        ReplaySeed(
            capability=_capability(),
            batting_participants=tuple(
                ReplayParticipant(identifier, position)
                for position, identifier in enumerate(batters, start=1)
            ),
            fielding_participant_ids=frozenset(bowlers),
            opening_striker_participant_id=batters[0],
            opening_non_striker_participant_id=batters[1],
            opening_bowler_participant_id=bowlers[0],
            target_runs=target_runs,
        ),
        batters,
        bowlers,
    )


def test_replay_folds_runs_extras_strike_overs_and_summaries() -> None:
    seed, batters, bowlers = _seed()
    deliveries = [
        ReplayDelivery(1, _facts(batters[0], batters[1], bowlers[0], runs_off_bat=1)),
        ReplayDelivery(
            2,
            _facts(
                batters[1],
                batters[0],
                bowlers[0],
                extras={"wide_runs": 3},
            ),
        ),
        ReplayDelivery(
            3,
            _facts(
                batters[1],
                batters[0],
                bowlers[0],
                runs_off_bat=4,
                extras={"no_ball_penalty_runs": 1},
            ),
        ),
        ReplayDelivery(
            4,
            _facts(
                batters[1],
                batters[0],
                bowlers[0],
                extras={"bye_runs": 2},
            ),
        ),
    ]

    state = replay_innings(seed, deliveries)

    assert state.total_runs == 11
    assert state.legal_balls == 2
    assert state.extras == {
        "wides": 3,
        "no_balls": 1,
        "byes": 2,
        "leg_byes": 0,
        "penalty_runs": 0,
    }
    assert state.participants[batters[0]].batting_runs == 1
    assert state.participants[batters[1]].batting_runs == 4
    assert state.participants[bowlers[0]].runs_conceded == 9
    assert state.striker_participant_id == batters[1]
    assert state.blocking_state.kind is BlockingStateKind.NONE


def test_one_wicket_blocks_until_explicit_next_batter_transition() -> None:
    seed, batters, bowlers = _seed()
    wicket = {
        "dismissal_type": "caught",
        "dismissed_participant_id": batters[0],
        "fielders": [{"participant_id": bowlers[1], "role": "catcher"}],
    }
    delivery = ReplayDelivery(
        1,
        _facts(batters[0], batters[1], bowlers[0], wicket=wicket),
    )
    blocked = replay_innings(seed, [delivery])
    restored = replay_innings(
        seed,
        [delivery],
        [
            ReplayTransition(
                event_kind=InningsTransitionType.NEXT_BATTER,
                participant_id=batters[2],
                anchored_attempted_sequence=1,
            )
        ],
    )

    assert blocked.wickets_lost == 1
    assert blocked.blocking_state.kind is BlockingStateKind.AWAITING_NEXT_BATTER
    assert blocked.participants[batters[0]].participation_state is (
        ParticipationState.DISMISSED
    )
    assert restored.blocking_state.kind is BlockingStateKind.NONE
    assert restored.striker_participant_id == batters[2]


def test_retired_hurt_is_a_transition_not_a_team_wicket_and_can_return() -> None:
    seed, batters, _bowlers = _seed()
    retired = replay_innings(
        seed,
        [],
        [
            ReplayTransition(
                event_kind=InningsTransitionType.RETIRED_HURT,
                participant_id=batters[0],
            )
        ],
    )
    returned = replay_innings(
        seed,
        [],
        [
            ReplayTransition(
                event_kind=InningsTransitionType.RETIRED_HURT,
                participant_id=batters[0],
            ),
            ReplayTransition(
                event_kind=InningsTransitionType.RETIRED_HURT_RETURN,
                participant_id=batters[0],
            ),
        ],
    )

    assert retired.wickets_lost == 0
    assert retired.blocking_state.kind is BlockingStateKind.AWAITING_NEXT_BATTER
    assert retired.participants[batters[0]].participation_state is (
        ParticipationState.RETIRED_HURT
    )
    assert returned.wickets_lost == 0
    assert returned.blocking_state.kind is BlockingStateKind.NONE


def test_blocking_state_precedence_has_no_innings_abandonment_state() -> None:
    completed = derive_innings_blocking_state(
        match_lifecycle_state=MatchLifecycleState.IN_PROGRESS,
        innings_lifecycle_state=InningsLifecycleState.COMPLETED,
        striker_participant_id=None,
        non_striker_participant_id=None,
        current_bowler_participant_id=None,
    )
    abandoned = derive_innings_blocking_state(
        match_lifecycle_state=MatchLifecycleState.ABANDONED,
        innings_lifecycle_state=InningsLifecycleState.IN_PROGRESS,
        striker_participant_id=uuid4(),
        non_striker_participant_id=uuid4(),
        current_bowler_participant_id=uuid4(),
    )
    batter_first = derive_innings_blocking_state(
        match_lifecycle_state=MatchLifecycleState.IN_PROGRESS,
        innings_lifecycle_state=InningsLifecycleState.IN_PROGRESS,
        striker_participant_id=None,
        non_striker_participant_id=uuid4(),
        current_bowler_participant_id=None,
    )

    assert completed.kind is BlockingStateKind.INNINGS_COMPLETED
    assert abandoned.kind is BlockingStateKind.MATCH_ABANDONED
    assert batter_first.kind is BlockingStateKind.AWAITING_NEXT_BATTER
