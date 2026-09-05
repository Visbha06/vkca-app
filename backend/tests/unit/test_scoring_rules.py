"""Phase 4 canonical delivery-rule coverage."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import SCORING_RUN_COMPONENT_MAX, ScoringDismissalType
from src.schemas.scoring import AppendDeliveryRequest, DeliveryFactsRequest
from src.services.scoring.errors import ScoringValidationError
from src.services.scoring.rules import checked_scoring_add, classify_delivery


@pytest.mark.parametrize("before", [0, 1, 5, 6, 11, 12])
@pytest.mark.parametrize("extras", [{}, {"wide_runs": 1}, {"no_ball_penalty_runs": 1}])
def test_legal_indexes_and_attempt_positions(before, extras) -> None:
    result = classify_delivery(
        _facts(extras=extras), legal_balls_before=before, over_length_legal_balls=6
    )
    assert result.legal_ball_index == before + int(not extras)
    assert (result.over_number, result.ball_in_over) == (before // 6, before % 6 + 1)


@pytest.mark.parametrize(
    ("runs", "extras", "completed"),
    [
        (1, {}, 1),
        (2, {}, 2),
        (5, {}, 5),
        (0, {"wide_runs": 1}, 0),
        (0, {"wide_runs": 2}, 1),
        (0, {"wide_runs": 3}, 2),
        (0, {"no_ball_penalty_runs": 1}, 0),
        (1, {"no_ball_penalty_runs": 1}, 1),
        (0, {"no_ball_penalty_runs": 1, "bye_runs": 3}, 3),
        (0, {"penalty_runs": 5}, 0),
        (0, {"leg_bye_runs": 1}, 1),
    ],
)
@pytest.mark.parametrize("over_end", [False, True])
def test_strike_parity_and_over_exchange(runs, extras, completed, over_end) -> None:
    from src.services.scoring.policy import resolve_format_capability
    from src.services.scoring.replay import (
        ReplayDelivery,
        ReplayParticipant,
        ReplaySeed,
        replay_innings,
    )

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
    prefix = 5 if over_end else 0
    deliveries = [
        ReplayDelivery(
            i + 1,
            _facts(
                striker_participant_id=striker,
                non_striker_participant_id=non_striker,
                bowler_participant_id=bowler,
            ),
        )
        for i in range(prefix)
    ]
    deliveries.append(
        ReplayDelivery(
            prefix + 1,
            _facts(
                striker_participant_id=striker,
                non_striker_participant_id=non_striker,
                bowler_participant_id=bowler,
                runs_off_bat=runs,
                extras=extras,
            ),
        )
    )
    state = replay_innings(seed, deliveries)
    legal = not (extras.get("wide_runs") or extras.get("no_ball_penalty_runs"))
    swapped = bool(completed % 2) != (over_end and legal)
    assert (state.striker_participant_id, state.non_striker_participant_id) == (
        (non_striker, striker) if swapped else (striker, non_striker)
    )
    assert state.legal_balls == prefix + int(legal)
    assert state.current_bowler_participant_id == (
        None if over_end and legal else bowler
    )


def _facts(**overrides: object) -> DeliveryFactsRequest:
    payload: dict[str, object] = {
        "striker_participant_id": uuid4(),
        "non_striker_participant_id": uuid4(),
        "bowler_participant_id": uuid4(),
        "runs_off_bat": 0,
        "extras": {},
    }
    payload.update(overrides)
    return DeliveryFactsRequest.model_validate(payload)


@pytest.mark.parametrize("end", ["striker_end", "non_striker_end"])
def test_run_out_uses_explicit_dismissed_end_before_over_exchange(end):
    from src.services.scoring.policy import resolve_format_capability
    from src.services.scoring.replay import (
        ReplayDelivery,
        ReplayParticipant,
        ReplaySeed,
        replay_innings,
    )

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
    facts = _facts(
        striker_participant_id=striker,
        non_striker_participant_id=non_striker,
        bowler_participant_id=bowler,
    )
    deliveries = [ReplayDelivery(i + 1, facts) for i in range(5)]
    deliveries.append(
        ReplayDelivery(
            6,
            _facts(
                striker_participant_id=striker,
                non_striker_participant_id=non_striker,
                bowler_participant_id=bowler,
                runs_off_bat=1,
                wicket={
                    "dismissal_type": "run_out",
                    "dismissed_participant_id": striker,
                    "dismissed_end": end,
                    "fielders": [{"participant_id": bowler, "role": "thrower"}],
                },
            ),
        )
    )
    state = replay_innings(seed, deliveries)
    assert (state.striker_participant_id, state.non_striker_participant_id) == (
        (non_striker, None) if end == "striker_end" else (None, non_striker)
    )
    assert state.current_bowler_participant_id is None
    assert state.blocking_state.kind == "awaiting_next_batter"


@pytest.mark.parametrize(
    ("facts", "total", "legal", "completed", "faced", "conceded"),
    [
        (_facts(runs_off_bat=1), 1, True, 1, True, 1),
        (_facts(runs_off_bat=4), 4, True, 4, True, 4),
        (_facts(runs_off_bat=5), 5, True, 5, True, 5),
        (_facts(extras={"wide_runs": 3}), 3, False, 2, False, 3),
        (
            _facts(runs_off_bat=2, extras={"no_ball_penalty_runs": 1}),
            3,
            False,
            2,
            False,
            3,
        ),
        (_facts(extras={"bye_runs": 2}), 2, True, 2, True, 0),
        (_facts(extras={"leg_bye_runs": 3}), 3, True, 3, True, 0),
        (_facts(extras={"penalty_runs": 5}), 5, True, 0, True, 0),
    ],
)
def test_classifier_uses_one_derivation_for_all_delivery_classes(
    facts: DeliveryFactsRequest,
    total: int,
    legal: bool,
    completed: int,
    faced: bool,
    conceded: int,
) -> None:
    result = classify_delivery(
        facts,
        legal_balls_before=5,
        over_length_legal_balls=6,
    )

    assert (
        result.total_runs,
        result.is_legal,
        result.completed_runs,
        result.balls_faced,
        result.bowler_conceded_runs,
    ) == (total, legal, completed, faced, conceded)
    assert result.over_number == 0
    assert result.ball_in_over == 6


def test_exact_numeric_boundaries_and_aggregate_overflow_fail_closed() -> None:
    maximum = _facts(runs_off_bat=SCORING_RUN_COMPONENT_MAX)
    result = classify_delivery(
        maximum,
        legal_balls_before=0,
        over_length_legal_balls=6,
    )
    assert result.total_runs == SCORING_RUN_COMPONENT_MAX

    with pytest.raises(ValidationError):
        _facts(runs_off_bat=-1)
    with pytest.raises(ValidationError):
        _facts(runs_off_bat=SCORING_RUN_COMPONENT_MAX + 1)
    with pytest.raises(ScoringValidationError, match="innings aggregate"):
        classify_delivery(
            _facts(runs_off_bat=1),
            legal_balls_before=0,
            over_length_legal_balls=6,
            innings_total_before=SCORING_RUN_COMPONENT_MAX,
        )
    with pytest.raises(ScoringValidationError, match="Match aggregate"):
        classify_delivery(
            _facts(runs_off_bat=1),
            legal_balls_before=0,
            over_length_legal_balls=6,
            match_total_before=SCORING_RUN_COMPONENT_MAX,
        )
    with pytest.raises(ScoringValidationError):
        checked_scoring_add(SCORING_RUN_COMPONENT_MAX, 1)


@pytest.mark.parametrize(
    "extras",
    [
        {"wide_runs": 1, "no_ball_penalty_runs": 1},
        {"bye_runs": 1, "leg_bye_runs": 1},
    ],
)
def test_conflicting_extras_are_rejected(extras: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        _facts(extras=extras)


@pytest.mark.parametrize(
    ("dismissal", "role", "credited"),
    [
        ("caught", "catcher", True),
        ("caught_and_bowled", "bowler", True),
        ("stumped", "keeper", True),
        ("run_out", "thrower", False),
    ],
)
def test_wicket_cardinality_order_and_credit_are_canonical(
    dismissal: str,
    role: str,
    credited: bool,
) -> None:
    striker, non_striker, bowler, fielder = uuid4(), uuid4(), uuid4(), uuid4()
    selected_fielder = bowler if dismissal == "caught_and_bowled" else fielder
    wicket: dict[str, object] = {
        "dismissal_type": dismissal,
        "dismissed_participant_id": striker,
        "fielders": [{"participant_id": selected_fielder, "role": role}],
    }
    if dismissal == "run_out":
        wicket["dismissed_end"] = "striker_end"
    result = classify_delivery(
        _facts(
            striker_participant_id=striker,
            non_striker_participant_id=non_striker,
            bowler_participant_id=bowler,
            wicket=wicket,
        ),
        legal_balls_before=0,
        over_length_legal_balls=6,
        fielding_participant_ids={bowler, fielder},
    )

    assert result.wicket is not None
    assert result.wicket.counts_as_team_wicket
    assert result.wicket.credited_to_bowler is credited
    assert result.wicket.primary_fielder_participant_id == selected_fielder


@pytest.mark.parametrize(
    "dismissal",
    ["bowled", "lbw", "hit_wicket", "retired_out"],
)
def test_zero_fielder_dismissals_apply_one_wicket(dismissal: str) -> None:
    striker, non_striker, bowler = uuid4(), uuid4(), uuid4()
    result = classify_delivery(
        _facts(
            striker_participant_id=striker,
            non_striker_participant_id=non_striker,
            bowler_participant_id=bowler,
            wicket={
                "dismissal_type": dismissal,
                "dismissed_participant_id": striker,
                "fielders": [],
            },
        ),
        legal_balls_before=0,
        over_length_legal_balls=6,
        fielding_participant_ids={bowler},
        allowed_dismissal_types=set(ScoringDismissalType),
    )
    assert result.wicket is not None
    assert result.wicket.counts_as_team_wicket is True


def test_duplicate_conflicting_and_reserved_wickets_are_rejected() -> None:
    payload = {
        "innings_version_number": 1,
        "attempted_sequence": 1,
        **_facts().model_dump(mode="json"),
    }
    payload["wicket"] = [
        {
            "dismissal_type": "bowled",
            "dismissed_participant_id": payload["striker_participant_id"],
            "fielders": [],
        }
    ]
    with pytest.raises(ValidationError):
        AppendDeliveryRequest.model_validate(payload)
    payload["wicket"] = {
        "dismissal_type": "timed_out",
        "dismissed_participant_id": payload["striker_participant_id"],
        "fielders": [],
    }
    with pytest.raises(ValidationError):
        AppendDeliveryRequest.model_validate(payload)
