"""Phase 4 replay-to-projection coverage."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.schemas.scoring import DeliveryFactsRequest
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.projections import build_innings_projection
from src.services.scoring.replay import (
    ReplayDelivery,
    ReplayParticipant,
    ReplaySeed,
    ReplayTransition,
    replay_innings,
)


@pytest.mark.parametrize(
    ("profile", "overs", "length", "exhausted"),
    [
        ("T20", 8, 6, True),
        ("one-day", 2, 6, True),
        ("test", 10, 6, False),
        ("other", 5, 8, False),
    ],
)
def test_replay_quota_usage_ignores_illegal_attempts_and_persists_progress(
    profile,
    overs,
    length,
    exhausted,
):
    from src.enums import InningsTransitionType
    from src.services.scoring.errors import ScoringReconciliationError

    policy = {
        "policy_code": profile,
        "capability_profile": profile,
        "innings_sequence": ["home", "away"] * (2 if profile == "test" else 1),
    }
    if profile == "one-day":
        policy["legal_ball_limit"] = 30
    if profile == "other":
        policy.update(
            {
                "innings_per_side": 1,
                "legal_ball_limit": None,
                "over_length_legal_balls": length,
                "bowler_quota_legal_balls": None,
                "wicket_limit": 8,
                "consecutive_overs_prohibited": False,
                "target_mode": "none",
                "allow_declaration": False,
                "allow_draw": False,
                "allow_manual_completion": True,
                "explicit_match_completion_boundary": "any_nonterminal_state",
                "allowed_dismissal_types": ["bowled"],
                "allowed_transition_types": [],
                "allowed_innings_completion_modes": ["manual"],
                "allowed_match_completion_modes": ["manual", "abandonment"],
                "allowed_result_codes": ["pending", "manual", "no_result"],
            }
        )
    capability = resolve_format_capability(policy)
    striker, non_striker, first, second = uuid4(), uuid4(), uuid4(), uuid4()
    seed = ReplaySeed(
        capability,
        (ReplayParticipant(striker, 1), ReplayParticipant(non_striker, 2)),
        frozenset({first, second}),
        striker,
        non_striker,
        first,
    )
    deliveries, transitions = [], []
    for over in range(overs):
        bowler = first if profile == "other" or over % 2 == 0 else second
        if over:
            transitions.append(
                ReplayTransition(
                    InningsTransitionType.NEXT_BOWLER, bowler, len(deliveries)
                )
            )
        for _ in range(length):
            for extras in ({"wide_runs": 1}, {"no_ball_penalty_runs": 1}, {}):
                deliveries.append(
                    ReplayDelivery(
                        len(deliveries) + 1,
                        DeliveryFactsRequest.model_validate(
                            {
                                "striker_participant_id": striker,
                                "non_striker_participant_id": non_striker,
                                "bowler_participant_id": bowler,
                                "runs_off_bat": 0,
                                "extras": extras,
                            }
                        ),
                    )
                )
        striker, non_striker = non_striker, striker
    state = replay_innings(seed, deliveries, transitions)
    projection = build_innings_projection(state, over_length_legal_balls=length)
    assert state.legal_balls == overs * length
    assert state.total_runs == overs * length * 2
    assert state.current_bowler_participant_id is None
    assert state.blocking_state.reason_code == (
        "no_eligible_bowler" if exhausted else "next_bowler_required"
    )
    assert projection.state_snapshot["over_progress"] == {
        "over_length_legal_balls": length,
        "overs_completed": overs,
        "balls_in_partial_over": 0,
        "next_ball_in_over": 1,
    }
    assert projection.state_snapshot["completed_bowler_participant_ids"] == [
        str(first if profile == "other" or i % 2 == 0 else second) for i in range(overs)
    ]
    assert all(o.is_complete and o.legal_ball_count == length for o in projection.overs)
    if exhausted:
        with pytest.raises(ScoringReconciliationError, match="ineligible"):
            replay_innings(
                seed,
                deliveries,
                [
                    *transitions,
                    ReplayTransition(
                        InningsTransitionType.NEXT_BOWLER, first, len(deliveries)
                    ),
                ],
            )
    elif profile == "test":
        with pytest.raises(
            ScoringReconciliationError, match="consecutive_over_prohibited"
        ):
            replay_innings(
                seed,
                deliveries,
                [
                    *transitions,
                    ReplayTransition(
                        InningsTransitionType.NEXT_BOWLER, second, len(deliveries)
                    ),
                ],
            )


def test_replay_rejects_bowler_transitions_before_over_end_and_outside_side():
    from src.enums import InningsTransitionType
    from src.services.scoring.errors import ScoringReconciliationError

    striker, non_striker, bowler = uuid4(), uuid4(), uuid4()
    capability = resolve_format_capability(
        {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        }
    )
    seed = ReplaySeed(
        capability,
        (ReplayParticipant(striker, 1), ReplayParticipant(non_striker, 2)),
        frozenset({bowler}),
        striker,
        non_striker,
        bowler,
    )
    deliveries = [
        ReplayDelivery(
            i + 1,
            DeliveryFactsRequest(
                striker_participant_id=striker,
                non_striker_participant_id=non_striker,
                bowler_participant_id=bowler,
                runs_off_bat=0,
            ),
        )
        for i in range(6)
    ]
    with pytest.raises(ScoringReconciliationError, match="completed over"):
        replay_innings(
            seed,
            deliveries,
            [ReplayTransition(InningsTransitionType.NEXT_BOWLER, uuid4(), 3)],
        )
    with pytest.raises(ScoringReconciliationError, match="not_fielding_participant"):
        replay_innings(
            seed,
            deliveries,
            [ReplayTransition(InningsTransitionType.NEXT_BOWLER, uuid4(), 6)],
        )


@pytest.mark.parametrize(
    ("profile", "limit", "quota"),
    [
        ("T20", None, 24),
        ("one-day", 240, 48),
        ("test", None, None),
    ],
)
def test_bowler_decisions_use_locked_quota_and_previous_over(profile, limit, quota):
    from src.services.scoring.policy import bowler_eligibility

    policy = {
        "policy_code": profile,
        "capability_profile": profile,
        "innings_sequence": ["home", "away"] * (2 if profile == "test" else 1),
    }
    if limit:
        policy["legal_ball_limit"] = limit
    capability = resolve_format_capability(policy)
    bowler, previous = uuid4(), uuid4()
    ids = frozenset({bowler, previous})
    decision = bowler_eligibility(
        capability,
        bowler,
        fielding_participant_ids=ids,
        legal_balls_bowled=quota or 600,
        previous_over_bowler_id=previous,
    )
    assert decision.is_eligible is (quota is None)
    assert decision.quota_legal_balls == quota
    assert decision.reason_code == (None if quota is None else "quota_exhausted")
    previous_decision = bowler_eligibility(
        capability,
        previous,
        fielding_participant_ids=ids,
        legal_balls_bowled=6,
        previous_over_bowler_id=previous,
    )
    assert previous_decision.reason_code == "consecutive_over_prohibited"
    assert not previous_decision.is_eligible


def test_bowler_suggestion_normalizes_names_breaks_ties_and_prefers_alternate():
    from src.models.scoring.participant import MatchParticipant
    from src.services.scoring.authorization import next_bowler_options

    capability = resolve_format_capability(
        {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        }
    )
    match_id, side_id = uuid4(), uuid4()
    participants = [
        MatchParticipant(
            id=UUID(int=i),
            match_id=match_id,
            side_id=side_id,
            display_name_snapshot=name,
        )
        for i, name in [(3, "Zulu"), (2, " ＡLPHA  Jones "), (1, "alpha jones")]
    ]

    def options(history=(), usage=None):
        return next_bowler_options(
            capability,
            participants,
            match_id=match_id,
            fielding_side_id=side_id,
            legal_balls_by_bowler=usage or {},
            completed_bowler_ids=history,
        )

    assert options().suggested_bowler_participant_id == UUID(int=1)
    assert options((UUID(int=3), UUID(int=2))).suggested_bowler_participant_id == UUID(
        int=3
    )
    assert options(
        (UUID(int=3), UUID(int=2)), {UUID(int=3): 24}
    ).suggested_bowler_participant_id == UUID(int=1)
    exhausted = options((UUID(int=2),), {UUID(int=1): 24, UUID(int=3): 24})
    assert exhausted.suggested_bowler_participant_id is None
    assert exhausted.reason_code == "no_eligible_bowler"


def test_projection_reconciles_totals_overs_participants_target_and_blocker() -> None:
    striker, non_striker, bowler = uuid4(), uuid4(), uuid4()
    capability = resolve_format_capability(
        {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        }
    )
    state = replay_innings(
        ReplaySeed(
            capability=capability,
            batting_participants=(
                ReplayParticipant(striker, 1),
                ReplayParticipant(non_striker, 2),
            ),
            fielding_participant_ids=frozenset({bowler}),
            opening_striker_participant_id=striker,
            opening_non_striker_participant_id=non_striker,
            opening_bowler_participant_id=bowler,
            target_runs=10,
        ),
        [
            ReplayDelivery(
                1,
                DeliveryFactsRequest(
                    striker_participant_id=striker,
                    non_striker_participant_id=non_striker,
                    bowler_participant_id=bowler,
                    runs_off_bat=4,
                ),
            )
        ],
    )

    projection = build_innings_projection(
        state, over_length_legal_balls=capability.over_length_legal_balls
    )

    assert projection.total_runs == 4
    assert projection.legal_balls == 1
    assert projection.overs[0].total_runs == 4
    assert projection.overs[0].legal_ball_count == 1
    batter = next(
        item
        for item in projection.participant_summaries
        if item.participant_id == striker
    )
    assert (batter.batting_runs, batter.balls_faced, batter.fours) == (4, 1, 1)
    assert projection.state_snapshot["target"] == {
        "target_runs": 10,
        "runs_required": 6,
        "wickets_remaining": 10,
        "legal_balls_remaining": 119,
    }
    assert projection.state_snapshot["opening_selections"] == {
        "striker_participant_id": str(striker),
        "non_striker_participant_id": str(non_striker),
        "bowler_participant_id": str(bowler),
    }
    assert projection.state_snapshot["blocking_state"] == {
        "kind": "none",
        "is_blocked": False,
        "reason_code": None,
    }


def _completion_policy(profile="T20", boundary="after_completed_innings"):
    policy = {
        "policy_code": profile,
        "capability_profile": profile,
        "innings_sequence": ["home", "away"] * (2 if profile == "test" else 1),
    }
    if profile == "other":
        policy.update(
            {
                "innings_per_side": 1,
                "legal_ball_limit": None,
                "over_length_legal_balls": 6,
                "bowler_quota_legal_balls": None,
                "wicket_limit": 10,
                "consecutive_overs_prohibited": True,
                "target_mode": "none",
                "allow_declaration": False,
                "allow_draw": False,
                "allow_manual_completion": True,
                "explicit_match_completion_boundary": boundary,
                "allowed_dismissal_types": ["bowled"],
                "allowed_transition_types": [],
                "allowed_innings_completion_modes": ["manual"],
                "allowed_match_completion_modes": ["manual", "abandonment"],
                "allowed_result_codes": ["pending", "manual", "no_result"],
            }
        )
    return resolve_format_capability(policy)


def _result_state(runs=0, lifecycle="completed", reason="all_out", wickets=10):
    from types import SimpleNamespace

    from src.enums import InningsCompletionMode, InningsLifecycleState

    return SimpleNamespace(
        total_runs=runs,
        lifecycle_state=InningsLifecycleState(lifecycle),
        completion_reason=InningsCompletionMode(reason) if reason else None,
        wickets_lost=wickets,
    )


@pytest.mark.parametrize(
    "profile,totals,reason,expected,margin",
    [
        ("T20", [20, 12], "all_out", "win_by_runs", 8),
        ("T20", [20, 21], "target_reached", "win_by_wickets", 7),
        ("T20", [20, 20], "all_out", "tie", None),
        ("test", [20, 30, 40, 50], "declaration", "win_by_runs", 20),
        ("test", [20, 30, 40, 30], "all_out", "tie", None),
    ],
)
def test_completion_result_projection(profile, totals, reason, expected, margin):
    from src.services.scoring.rules import derive_match_result

    states = [_result_state(total) for total in totals]
    states[-1] = _result_state(totals[-1], reason=reason, wickets=3)
    code, details, text = derive_match_result(_completion_policy(profile), states)
    assert code == expected
    if margin is not None:
        assert details.get("runs_margin", details.get("wickets_remaining")) == margin
    assert details["side_totals"] == {
        "home": sum(totals[::2]),
        "away": sum(totals[1::2]),
    }
    assert text


@pytest.mark.parametrize(
    "profile,kind",
    [("test", "draw"), ("test", "declared"), ("test", "manual"), ("other", "manual")],
)
@pytest.mark.parametrize(
    "boundary", ["after_completed_innings", "any_nonterminal_state"]
)
@pytest.mark.parametrize(
    "lifecycle",
    [None, "pending", "in_progress", "completed", "reconciliation_required"],
)
def test_explicit_result_boundaries(profile, kind, boundary, lifecycle):
    from src.enums import MatchLifecycleState, MatchResultCode
    from src.services.scoring.rules import derive_match_result

    states = [] if lifecycle is None else [_result_state(lifecycle=lifecycle)]
    code, _, _ = derive_match_result(
        _completion_policy(profile, boundary),
        states,
        MatchLifecycleState.COMPLETED,
        MatchResultCode(kind),
        {"reason": "Agreed close"},
    )
    allowed = lifecycle == "completed" or (
        profile == "other"
        and boundary == "any_nonterminal_state"
        and lifecycle != "reconciliation_required"
    )
    assert code == (kind if allowed else "pending")


@pytest.mark.parametrize(
    "lifecycle",
    [None, "pending", "in_progress", "completed", "reconciliation_required"],
)
def test_abandonment_result_and_reconciliation_precedence(lifecycle):
    from src.enums import MatchLifecycleState
    from src.services.scoring.rules import derive_match_result

    states = [] if lifecycle is None else [_result_state(lifecycle=lifecycle)]
    code, _, _ = derive_match_result(
        _completion_policy(), states, MatchLifecycleState.ABANDONED
    )
    assert code == (
        "pending" if lifecycle == "reconciliation_required" else "no_result"
    )
    if states:
        assert states[0].lifecycle_state == lifecycle


def test_result_overflow_and_disallowed_codes_fail_closed():
    from dataclasses import replace

    from src.enums import SCORING_RUN_TOTAL_MAX, MatchResultCode
    from src.services.scoring.errors import ScoringValidationError
    from src.services.scoring.rules import derive_match_result

    with pytest.raises(ScoringValidationError, match="Match total"):
        derive_match_result(
            _completion_policy(),
            [_result_state(SCORING_RUN_TOTAL_MAX), _result_state(1)],
        )
    capability = replace(
        _completion_policy(), allowed_result_codes=(MatchResultCode.PENDING,)
    )
    with pytest.raises(ScoringValidationError, match="Result"):
        derive_match_result(capability, [_result_state(1), _result_state(0)])


@pytest.mark.parametrize("profile,limit", [("T20", 120), ("one-day", 240)])
def test_replay_completes_at_exact_locked_ball_limit(profile, limit):
    from src.enums import InningsTransitionType

    policy = {
        "policy_code": profile,
        "capability_profile": profile,
        "innings_sequence": ["home", "away"],
    }
    if profile == "one-day":
        policy["legal_ball_limit"] = limit
    capability = resolve_format_capability(policy)
    batters, bowlers = [uuid4(), uuid4()], [uuid4() for _ in range(5)]
    seed = ReplaySeed(
        capability,
        tuple(ReplayParticipant(p, i) for i, p in enumerate(batters, 1)),
        frozenset(bowlers),
        *batters,
        bowlers[0],
    )
    deliveries, transitions = [], []
    for i in range(limit):
        bowler = bowlers[(i // 6) % 5]
        if i and i % 6 == 0:
            batters.reverse()
            transitions.append(
                ReplayTransition(InningsTransitionType.NEXT_BOWLER, bowler, i)
            )
        deliveries.append(
            ReplayDelivery(
                i + 1,
                DeliveryFactsRequest(
                    striker_participant_id=batters[0],
                    non_striker_participant_id=batters[1],
                    bowler_participant_id=bowler,
                    runs_off_bat=0,
                ),
            )
        )
    penultimate = replay_innings(
        seed, deliveries[:-1], transitions, derive_completion=True
    )
    assert penultimate.lifecycle_state == "in_progress"
    final = replay_innings(seed, deliveries, transitions, derive_completion=True)
    assert final.lifecycle_state == "completed"
    assert final.completion_reason == "legal_ball_limit"
    projection = build_innings_projection(final, over_length_legal_balls=6)
    assert projection.state_snapshot["target"]["legal_balls_remaining"] == 0
    assert max(p.bowling_legal_balls for p in final.participants.values()) == limit // 5


def test_result_projection_accepts_persisted_string_values():
    from types import SimpleNamespace

    from src.services.scoring.rules import derive_match_result

    states = [
        SimpleNamespace(
            total_runs=runs,
            lifecycle_state="completed",
            completion_reason=reason,
            wickets_lost=0,
        )
        for runs, reason in [(4, "all_out"), (6, "target_reached")]
    ]
    assert derive_match_result(_completion_policy(), states)[0] == "win_by_wickets"


def _scorecard_match(*, lifecycle: str = "in_progress"):
    from src.models.match import Match
    from src.models.scoring.innings import Innings
    from src.models.scoring.match_participant_performance import (
        MatchParticipantPerformance,
    )
    from src.models.scoring.match_side import MatchSide
    from src.models.scoring.over import InningsOver
    from src.models.scoring.participant import MatchParticipant
    from src.models.scoring.participant_summary import InningsParticipantSummary

    match_id, academy_side_id, external_side_id = uuid4(), uuid4(), uuid4()
    internal_player_id = uuid4()
    internal_id, external_id, bowler_id = uuid4(), uuid4(), uuid4()
    policy = _completion_policy().to_model(match_id)
    policy.id = uuid4()
    policy.version_number = 1
    sides = [
        MatchSide(
            id=academy_side_id,
            match_id=match_id,
            side_code="home",
            side_kind="academy",
            team_id=uuid4(),
            display_name_snapshot="Academy XI",
            version_number=1,
        ),
        MatchSide(
            id=external_side_id,
            match_id=match_id,
            side_code="away",
            side_kind="external",
            team_id=None,
            display_name_snapshot="Visitors XI",
            version_number=1,
        ),
    ]
    participants = [
        MatchParticipant(
            id=internal_id,
            match_id=match_id,
            side_id=academy_side_id,
            participant_kind="internal",
            player_id=internal_player_id,
            display_name_snapshot="Academy Batter",
            batting_order_position=1,
            version_number=1,
        ),
        MatchParticipant(
            id=external_id,
            match_id=match_id,
            side_id=external_side_id,
            participant_kind="external",
            player_id=None,
            display_name_snapshot="Visiting Batter",
            batting_order_position=1,
            version_number=1,
        ),
        MatchParticipant(
            id=bowler_id,
            match_id=match_id,
            side_id=external_side_id,
            participant_kind="external",
            player_id=None,
            display_name_snapshot="Visiting Bowler",
            batting_order_position=2,
            version_number=1,
        ),
    ]
    innings_id = uuid4()
    innings = Innings(
        id=innings_id,
        match_id=match_id,
        innings_number=1,
        batting_side_id=academy_side_id,
        fielding_side_id=external_side_id,
        lifecycle_state="in_progress",
        striker_participant_id=internal_id,
        non_striker_participant_id=internal_id,
        current_bowler_participant_id=bowler_id,
        legal_balls=7,
        total_runs=12,
        wickets_lost=1,
        target_runs=20,
        projection_revision=4,
        version_number=3,
        state_snapshot={
            "extras": {
                "wides": 2,
                "no_balls": 1,
                "byes": 1,
                "leg_byes": 2,
                "penalty_runs": 0,
            },
            "fall_of_wickets": [
                {
                    "attempted_sequence": 5,
                    "score": 9,
                    "wicket_number": 1,
                    "participant_id": str(internal_id),
                    "dismissal_type": "run_out",
                }
            ],
            "blocking_state": {
                "kind": "none",
                "is_blocked": False,
                "reason_code": None,
            },
        },
        overs=[
            InningsOver(
                innings_id=innings_id,
                over_number=0,
                bowler_participant_id=bowler_id,
                legal_ball_count=6,
                total_runs=10,
                runs_conceded=7,
                wickets=1,
                is_complete=True,
                projection_revision=4,
            )
        ],
        participant_summaries=[
            InningsParticipantSummary(
                innings_id=innings_id,
                participant_id=internal_id,
                participation_state="dismissed",
                dismissal_type="run_out",
                batting_runs=6,
                balls_faced=5,
                fours=1,
                sixes=0,
                bowling_legal_balls=0,
                bowling_overs_completed=0,
                bowling_balls_in_partial_over=0,
                runs_conceded=0,
                bowling_wickets=0,
                wides=0,
                no_balls=0,
                fielding_dismissals=0,
                projection_revision=4,
            )
        ],
    )
    performance = MatchParticipantPerformance(
        match_id=match_id,
        innings_id=innings_id,
        participant_id=internal_id,
        batting_runs=6,
        balls_faced=5,
        fours=1,
        sixes=0,
        bowling_legal_balls=0,
        runs_conceded=0,
        bowling_wickets=0,
        wides=0,
        no_balls=0,
        extras_conceded=0,
        catches=0,
        stumpings=0,
        run_out_involvements=0,
        projection_revision=4,
        provenance="delivery_derived",
    )
    return Match(
        id=match_id,
        match_date=date(2026, 9, 10),
        format="T20",
        participant_type="external",
        home_team_id=sides[0].team_id,
        away_team_id=None,
        external_opponent_name="Visitors XI",
        venue="Academy",
        result="In progress",
        lifecycle_state=lifecycle,
        scoring_authority="delivery_history",
        result_code="pending",
        result_details={"target_runs": 20},
        configured_at=datetime.now(UTC),
        version_number=5,
        scoring_policy=policy,
        scoring_sides=sides,
        scoring_participants=participants,
        scoring_innings=[innings],
        scoring_performances=[performance],
    )


def test_scorecard_serializes_bounded_current_projection_and_external_identity():
    from src.services.scoring.service import _scorecard_response

    response = _scorecard_response(_scorecard_match())

    assert response.scoring_authority == "delivery_history"
    assert response.policy is not None
    assert response.policy.innings_sequence == ["home", "away"]
    assert [side.side_code for side in response.sides] == ["away", "home"]
    external = next(
        item for item in response.participants if item.participant_kind == "external"
    )
    assert external.player_id is None
    assert response.innings[0].extras.model_dump() == {
        "wides": 2,
        "no_balls": 1,
        "byes": 1,
        "leg_byes": 2,
        "penalty_runs": 0,
        "total": 6,
    }
    assert response.innings[0].fall_of_wickets[0].model_dump(mode="json") == {
        "attempted_sequence": 5,
        "score": 9,
        "wicket_number": 1,
        "participant_id": str(response.innings[0].fall_of_wickets[0].participant_id),
        "dismissal_type": "run_out",
    }
    assert response.innings[0].overs[0].legal_ball_count == 6
    assert response.innings[0].participant_summaries[0].batting_runs == 6
    assert response.innings[0].runs_required == 8
    assert response.participant_performances[0].provenance == "delivery_derived"
    assert response.projection_revision == 4
    assert response.result_details == {"target_runs": 20}


def test_legacy_scorecard_keeps_aggregate_authority_label_without_history():
    from src.models.match import Match
    from src.services.scoring.service import _scorecard_response

    match = Match(
        id=uuid4(),
        match_date=date(2026, 9, 10),
        format="T20",
        participant_type="internal",
        home_team_id=uuid4(),
        away_team_id=uuid4(),
        venue="Legacy Ground",
        result="Home won",
        lifecycle_state="completed",
        scoring_authority="legacy_aggregate",
        result_code="pending",
        result_details={},
        version_number=2,
        scoring_sides=[],
        scoring_participants=[],
        scoring_innings=[],
        scoring_performances=[],
    )

    response = _scorecard_response(match)

    assert response.scoring_authority == "legacy_aggregate"
    assert response.policy is None
    assert response.innings == []
    assert response.participant_performances == []
    assert response.blocking_state.kind == "match_completed"


@pytest.mark.parametrize(
    ("lifecycle", "innings_lifecycle", "expected"),
    [
        ("completed", "reconciliation_required", "match_completed"),
        ("abandoned", "reconciliation_required", "match_abandoned"),
        ("in_progress", "reconciliation_required", "reconciliation_required"),
        ("in_progress", "pending", "innings_not_started"),
        ("in_progress", "in_progress", "none"),
    ],
)
def test_match_blocking_state_uses_canonical_terminal_reconciliation_precedence(
    lifecycle, innings_lifecycle, expected
):
    from src.services.scoring.service import _match_blocking_response

    match = _scorecard_match(lifecycle=lifecycle)
    match.scoring_innings[0].lifecycle_state = innings_lifecycle
    match.scoring_innings[0].state_snapshot["blocking_state"] = (
        {
            "kind": "reconciliation_required",
            "is_blocked": True,
            "reason_code": "incompatible_replay",
        }
        if innings_lifecycle == "reconciliation_required"
        else {
            "kind": "none",
            "is_blocked": False,
            "reason_code": None,
        }
    )
    if innings_lifecycle == "pending":
        match.scoring_innings[0].state_snapshot.pop("blocking_state")

    assert _match_blocking_response(match).kind == expected


def test_delivery_serializes_ordered_fielders_and_primary_fielder():
    from src.services.scoring.service import _delivery_response

    match = _scorecard_match()
    persisted_innings = match.scoring_innings[0]
    first, second = uuid4(), uuid4()
    active = SimpleNamespace(
        id=uuid4(),
        revision_number=1,
        revision_state="active",
        striker_participant_id=match.scoring_participants[0].id,
        non_striker_participant_id=match.scoring_participants[0].id,
        bowler_participant_id=match.scoring_participants[2].id,
        runs_off_bat=0,
        wide_runs=0,
        no_ball_penalty_runs=0,
        bye_runs=0,
        leg_bye_runs=0,
        penalty_runs=0,
        total_runs=0,
        is_legal=True,
        completed_runs=0,
        balls_faced=True,
        bowler_conceded_runs=0,
        fielders=[
            SimpleNamespace(participant_id=second, ordinal=2, role="assister"),
            SimpleNamespace(participant_id=first, ordinal=1, role="thrower"),
        ],
        wicket_event=SimpleNamespace(
            dismissal_type="run_out",
            dismissed_participant_id=match.scoring_participants[0].id,
            dismissed_end="striker_end",
            counts_as_team_wicket=True,
            credited_to_bowler=False,
            notes=None,
        ),
        replacement_reason=None,
        supersedes_revision_id=None,
        recorded_by_user_id=uuid4(),
        recorded_at=datetime.now(UTC),
    )
    delivery = SimpleNamespace(
        id=uuid4(),
        innings_id=persisted_innings.id,
        attempted_sequence=1,
        revisions=[active],
    )
    innings = SimpleNamespace(
        **{
            key: getattr(persisted_innings, key)
            for key in (
                "id",
                "version_number",
                "total_runs",
                "legal_balls",
                "wickets_lost",
                "striker_participant_id",
                "non_striker_participant_id",
                "current_bowler_participant_id",
                "lifecycle_state",
                "state_snapshot",
            )
        },
        blocking_state=persisted_innings.blocking_state,
        deliveries=[delivery],
    )

    wicket = _delivery_response(delivery, innings, match).active_revision.wicket

    assert wicket is not None
    assert [item.participant_id for item in wicket.fielders] == [first, second]
    assert wicket.primary_fielder_participant_id == first
