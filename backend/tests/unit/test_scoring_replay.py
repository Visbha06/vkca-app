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


def test_correction_replay_matches_clean_stream_and_replaces_fielders():
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    corrected = _facts(
        batters[0],
        batters[1],
        bowlers[0],
        wicket={
            "dismissal_type": "run_out",
            "dismissed_participant_id": batters[0],
            "dismissed_end": "striker_end",
            "fielders": [
                {"participant_id": bowlers[1], "role": "thrower"},
                {"participant_id": bowlers[0], "role": "keeper"},
            ],
        },
    )
    stream = (ReplayDelivery(1, corrected),)
    result = replay_match(
        seed.capability,
        [ReplayInnings(1, "home", seed, stream)],
        correction_innings_number=1,
        correction_sequence=1,
    )
    clean = replay_innings(seed, stream)
    assert result.innings_states[0].participants == clean.participants
    assert result.innings_states[0].total_runs == clean.total_runs
    assert (
        result.innings_states[0]
        .classifications[0]
        .wicket.primary_fielder_participant_id
        == bowlers[1]
    )


def test_correction_marks_and_clears_incompatible_batter_transition():
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    facts = _facts(batters[0], batters[1], bowlers[0])
    transition = ReplayTransition(InningsTransitionType.NEXT_BATTER, batters[2], 1)
    result = replay_match(
        seed.capability,
        [ReplayInnings(1, "home", seed, (ReplayDelivery(1, facts),), (transition,))],
        correction_innings_number=1,
        correction_sequence=1,
    )
    state = result.innings_states[0]
    assert state.lifecycle_state is InningsLifecycleState.RECONCILIATION_REQUIRED
    assert state.reconciliation_sequence == 1
    assert result.blocking_state.kind is BlockingStateKind.RECONCILIATION_REQUIRED
    assert state.striker_participant_id == batters[0]
    wicket = facts.model_copy(
        update={
            "wicket": _facts(
                batters[0],
                batters[1],
                bowlers[0],
                wicket={
                    "dismissal_type": "bowled",
                    "dismissed_participant_id": batters[0],
                },
            ).wicket
        }
    )
    restored = replay_match(
        seed.capability,
        [ReplayInnings(1, "home", seed, (ReplayDelivery(1, wicket),), (transition,))],
        correction_innings_number=1,
        correction_sequence=1,
    )
    assert (
        restored.innings_states[0].lifecycle_state is InningsLifecycleState.IN_PROGRESS
    )
    assert restored.innings_states[0].reconciliation_sequence is None
    assert restored.blocking_state.kind is BlockingStateKind.NONE


def test_correction_preserves_safe_boundary_when_later_actors_conflict():
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    stream = (
        ReplayDelivery(1, _facts(batters[0], batters[1], bowlers[0], runs_off_bat=1)),
        ReplayDelivery(2, _facts(batters[0], batters[1], bowlers[0], runs_off_bat=4)),
    )
    result = replay_match(
        seed.capability,
        [ReplayInnings(1, "home", seed, stream)],
        correction_innings_number=1,
        correction_sequence=1,
    )
    state = result.innings_states[0]
    assert state.lifecycle_state is InningsLifecycleState.RECONCILIATION_REQUIRED
    assert state.reconciliation_sequence == 2
    assert state.total_runs == 1
    assert state.striker_participant_id == batters[1]
    assert stream[1].facts.striker_participant_id == batters[0]


def test_correction_cannot_replace_actors_at_an_invalid_boundary():
    import pytest

    from src.services.scoring.errors import ScoringReconciliationError
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    stream = (ReplayDelivery(1, _facts(batters[1], batters[0], bowlers[0])),)
    with pytest.raises(ScoringReconciliationError):
        replay_match(
            seed.capability,
            [ReplayInnings(1, "home", seed, stream)],
            correction_innings_number=1,
            correction_sequence=1,
        )


def test_correction_reprocesses_completed_target_and_reopens_when_needed():
    from dataclasses import replace

    from src.enums import InningsCompletionMode, MatchResultCode
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    # A short explicit fixture exercises replay without a 120-ball setup.
    capability = replace(seed.capability, legal_ball_limit=1)
    seed = replace(seed, capability=capability)
    second = replace(
        seed,
        batting_participants=tuple(
            ReplayParticipant(p, i) for i, p in enumerate(bowlers, 1)
        ),
        fielding_participant_ids=frozenset(batters),
        opening_striker_participant_id=bowlers[0],
        opening_non_striker_participant_id=bowlers[1],
        opening_bowler_participant_id=batters[0],
    )
    first_stream = (
        ReplayDelivery(1, _facts(batters[0], batters[1], bowlers[0], runs_off_bat=4)),
    )
    for chase_runs, expected_state, expected_result in [
        (6, MatchLifecycleState.COMPLETED, MatchResultCode.WIN_BY_WICKETS),
        (0, MatchLifecycleState.IN_PROGRESS, MatchResultCode.PENDING),
    ]:
        chase = (
            ReplayDelivery(
                1,
                _facts(
                    bowlers[0],
                    bowlers[1],
                    batters[0],
                    runs_off_bat=chase_runs,
                    extras={"no_ball_penalty_runs": 1},
                ),
            ),
        )
        result = replay_match(
            capability,
            [
                ReplayInnings(1, "home", seed, first_stream),
                ReplayInnings(2, "away", second, chase),
            ],
            correction_innings_number=2,
            correction_sequence=1,
            prior_lifecycle_state=MatchLifecycleState.COMPLETED,
        )
        assert result.lifecycle_state is expected_state
        assert result.result_code is expected_result
        assert result.innings_states[1].target_runs == 5
        assert result.innings_states[1].completion_reason is (
            InningsCompletionMode.TARGET_REACHED if chase_runs else None
        )
        assert result.lifecycle_state is not MatchLifecycleState.CORRECTION_REPROCESSING


def test_upstream_correction_invalidates_downstream_innings_start():
    from dataclasses import replace

    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    capability = replace(seed.capability, legal_ball_limit=1)
    seed = replace(seed, capability=capability)
    result = replay_match(
        capability,
        [
            ReplayInnings(
                1,
                "home",
                seed,
                (
                    ReplayDelivery(
                        1,
                        _facts(
                            batters[0], batters[1], bowlers[0], extras={"wide_runs": 1}
                        ),
                    ),
                ),
            ),
            ReplayInnings(
                2,
                "away",
                replace(
                    seed,
                    batting_participants=tuple(
                        ReplayParticipant(p, i) for i, p in enumerate(bowlers, 1)
                    ),
                    fielding_participant_ids=frozenset(batters),
                    opening_striker_participant_id=bowlers[0],
                    opening_non_striker_participant_id=bowlers[1],
                    opening_bowler_participant_id=batters[0],
                ),
            ),
        ],
        correction_innings_number=1,
        correction_sequence=1,
        prior_lifecycle_state=MatchLifecycleState.COMPLETED,
    )
    assert result.innings_states[0].lifecycle_state is InningsLifecycleState.IN_PROGRESS
    assert (
        result.innings_states[1].lifecycle_state
        is InningsLifecycleState.RECONCILIATION_REQUIRED
    )
    assert result.lifecycle_state is MatchLifecycleState.IN_PROGRESS
    assert result.blocking_state.kind is BlockingStateKind.RECONCILIATION_REQUIRED


def test_correction_revalidates_and_restores_next_bowler_boundary():
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    dots = tuple(
        ReplayDelivery(i, _facts(batters[0], batters[1], bowlers[0]))
        for i in range(1, 7)
    )
    transition = ReplayTransition(InningsTransitionType.NEXT_BOWLER, bowlers[1], 6)
    corrected = (
        ReplayDelivery(
            1, _facts(batters[0], batters[1], bowlers[0], extras={"wide_runs": 1})
        ),
        *dots[1:],
    )
    result = replay_match(
        seed.capability,
        [ReplayInnings(1, "home", seed, corrected, (transition,))],
        correction_innings_number=1,
        correction_sequence=1,
    )
    assert result.innings_states[0].reconciliation_sequence == 6
    assert result.innings_states[0].legal_balls == 5
    assert result.blocking_state.kind is BlockingStateKind.RECONCILIATION_REQUIRED
    restored = replay_match(
        seed.capability,
        [ReplayInnings(1, "home", seed, dots, (transition,))],
        correction_innings_number=1,
        correction_sequence=1,
    )
    assert restored.innings_states[0].current_bowler_participant_id == bowlers[1]
    assert restored.innings_states[0].reconciliation_sequence is None
    assert restored.blocking_state.kind is BlockingStateKind.NONE


def test_correction_rebuilds_test_aggregate_across_four_declared_innings():
    from dataclasses import replace

    from src.enums import InningsCompletionMode, MatchResultCode
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    capability = resolve_format_capability(
        {
            "policy_code": "test",
            "capability_profile": "test",
            "innings_sequence": ["home", "away", "home", "away"],
        }
    )
    first = replace(
        seed,
        capability=capability,
        lifecycle_state=InningsLifecycleState.RECONCILIATION_REQUIRED,
    )
    second = replace(
        first,
        batting_participants=tuple(
            ReplayParticipant(p, i) for i, p in enumerate(bowlers, 1)
        ),
        fielding_participant_ids=frozenset(batters),
        opening_striker_participant_id=bowlers[0],
        opening_non_striker_participant_id=bowlers[1],
        opening_bowler_participant_id=batters[0],
    )
    innings = []
    for number, runs in enumerate([2, 2, 6, 2], 1):
        current = first if number % 2 else second
        innings.append(
            ReplayInnings(
                number,
                "home" if number % 2 else "away",
                current,
                (
                    ReplayDelivery(
                        1,
                        _facts(
                            current.opening_striker_participant_id,
                            current.opening_non_striker_participant_id,
                            current.opening_bowler_participant_id,
                            runs_off_bat=runs,
                        ),
                    ),
                ),
                (
                    ReplayTransition(
                        InningsTransitionType.INNINGS_COMPLETED,
                        anchored_attempted_sequence=1,
                        completion_kind=InningsCompletionMode.DECLARATION,
                    ),
                ),
            )
        )
    result = replay_match(
        capability,
        innings,
        correction_innings_number=3,
        correction_sequence=1,
        prior_lifecycle_state=MatchLifecycleState.COMPLETED,
    )
    assert result.lifecycle_state is MatchLifecycleState.COMPLETED
    assert result.result_code is MatchResultCode.WIN_BY_RUNS
    assert result.result_details == {
        "winning_side_code": "home",
        "runs_margin": 4,
        "side_totals": {"home": 8, "away": 4},
    }
    assert [s.total_runs for s in result.innings_states] == [2, 2, 6, 2]
    assert all(
        s.target_runs is None and s.reconciliation_sequence is None
        for s in result.innings_states
    )


def test_pending_match_blocker_is_derived_even_when_all_innings_rows_exist():
    from dataclasses import replace

    from src.services.scoring.replay import derive_match_blocking_state

    seed, _, _ = _seed()
    states = [
        replay_innings(replace(seed, lifecycle_state=lifecycle), [])
        for lifecycle in [
            InningsLifecycleState.COMPLETED,
            InningsLifecycleState.PENDING,
        ]
    ]
    blocker = derive_match_blocking_state(
        MatchLifecycleState.IN_PROGRESS, states, required_innings_count=2
    )
    assert blocker.kind is BlockingStateKind.INNINGS_NOT_STARTED


def test_automatic_completion_event_is_rederived_when_correction_reopens_innings():
    from dataclasses import replace

    from src.enums import InningsCompletionMode
    from src.services.scoring.replay import ReplayInnings, replay_match

    seed, batters, bowlers = _seed()
    capability = replace(seed.capability, legal_ball_limit=1)
    seed = replace(seed, capability=capability)
    facts = _facts(batters[0], batters[1], bowlers[0], extras={"wide_runs": 1})
    result = replay_match(
        capability,
        [
            ReplayInnings(
                1,
                "home",
                seed,
                (ReplayDelivery(1, facts),),
                (
                    ReplayTransition(
                        InningsTransitionType.INNINGS_COMPLETED,
                        anchored_attempted_sequence=1,
                        completion_kind=InningsCompletionMode.LEGAL_BALL_LIMIT,
                    ),
                ),
            )
        ],
        correction_innings_number=1,
        correction_sequence=1,
    )
    assert result.innings_states[0].lifecycle_state is InningsLifecycleState.IN_PROGRESS
    assert result.innings_states[0].completion_reason is None
    assert result.innings_states[0].reconciliation_sequence is None
