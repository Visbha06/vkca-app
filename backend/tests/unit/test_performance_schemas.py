"""Unit tests for match performance request and response schemas."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import DismissalType
from src.schemas.performance import (
    MAX_PERFORMANCE_BATCH_SIZE,
    MAX_PERFORMANCE_NOTES_LENGTH,
    BatchPerformanceRequest,
    BatchPerformanceResponse,
    BattingPerformance,
    BowlingPerformance,
    FieldingPerformance,
    PlayerPerformance,
)


def test_performance_subobjects_supply_zero_value_defaults() -> None:
    batting = BattingPerformance()
    bowling = BowlingPerformance()
    fielding = FieldingPerformance()

    assert batting.runs_scored == 0
    assert batting.balls_faced == 0
    assert batting.dismissal is DismissalType.NOT_OUT
    assert batting.fours == 0
    assert batting.sixes == 0
    assert batting.notes is None
    assert bowling.overs_bowled == Decimal("0.0")
    assert bowling.maidens == 0
    assert bowling.runs_conceded == 0
    assert bowling.wickets_taken == 0
    assert bowling.wides == 0
    assert bowling.notes is None
    assert fielding.catches == 0
    assert fielding.stumpings == 0
    assert fielding.run_outs == 0
    assert fielding.dropped_catches == 0
    assert fielding.notes is None


def test_player_performance_accepts_each_optional_subobject_independently() -> None:
    player_id = uuid4()

    batting_only = PlayerPerformance(
        player_id=player_id,
        batting={"runs_scored": 75, "dismissal": "caught"},
    )
    bowling_only = PlayerPerformance(
        player_id=player_id,
        bowling={"overs_bowled": "4.2", "wickets_taken": 3},
    )
    fielding_only = PlayerPerformance(
        player_id=player_id,
        fielding={"catches": 2},
    )

    assert batting_only.batting is not None
    assert batting_only.bowling is None
    assert batting_only.fielding is None
    assert bowling_only.batting is None
    assert bowling_only.bowling is not None
    assert fielding_only.fielding is not None


def test_player_performance_rejects_entry_without_metrics() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        PlayerPerformance(player_id=uuid4())


def test_batch_performance_request_requires_at_least_one_entry() -> None:
    with pytest.raises(ValidationError):
        BatchPerformanceRequest(performances=[])


def test_batch_performance_request_accepts_the_maximum_supported_batch() -> None:
    request = BatchPerformanceRequest(
        performances=[
            {"player_id": uuid4(), "batting": {}}
            for _ in range(MAX_PERFORMANCE_BATCH_SIZE)
        ]
    )

    assert len(request.performances) == MAX_PERFORMANCE_BATCH_SIZE


def test_batch_performance_request_rejects_batches_above_maximum() -> None:
    with pytest.raises(ValidationError):
        BatchPerformanceRequest(
            performances=[
                {"player_id": uuid4(), "batting": {}}
                for _ in range(MAX_PERFORMANCE_BATCH_SIZE + 1)
            ]
        )


def test_batch_performance_request_rejects_duplicate_players() -> None:
    player_id = uuid4()

    with pytest.raises(ValidationError, match="duplicate player_id"):
        BatchPerformanceRequest(
            performances=[
                {"player_id": player_id, "batting": {}},
                {"player_id": player_id, "fielding": {}},
            ]
        )


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (BattingPerformance, {"runs_scored": -1}),
        (BowlingPerformance, {"wickets_taken": -1}),
        (FieldingPerformance, {"catches": -1}),
    ],
)
def test_performance_metrics_reject_negative_values(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.parametrize(
    "schema", [BattingPerformance, BowlingPerformance, FieldingPerformance]
)
def test_performance_notes_have_a_bounded_length(schema) -> None:
    schema.model_validate({"notes": "n" * MAX_PERFORMANCE_NOTES_LENGTH})

    with pytest.raises(ValidationError):
        schema.model_validate({"notes": "n" * (MAX_PERFORMANCE_NOTES_LENGTH + 1)})


def test_batch_performance_response_serializes_counts() -> None:
    match_id = uuid4()
    response = BatchPerformanceResponse(
        match_id=match_id,
        performances_created=2,
        batting_records=2,
        bowling_records=1,
        fielding_records=1,
        players_stats_updated=2,
    )

    assert response.model_dump(mode="json") == {
        "match_id": str(match_id),
        "performances_created": 2,
        "batting_records": 2,
        "bowling_records": 1,
        "fielding_records": 1,
        "players_stats_updated": 2,
    }
