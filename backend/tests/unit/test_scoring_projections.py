"""Phase 4 replay-to-projection coverage."""

from uuid import uuid4

from src.schemas.scoring import DeliveryFactsRequest
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.projections import build_innings_projection
from src.services.scoring.replay import (
    ReplayDelivery,
    ReplayParticipant,
    ReplaySeed,
    replay_innings,
)


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
