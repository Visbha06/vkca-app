"""Unit tests for aggregate cricket statistics schemas."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.enums import MatchFormat
from src.schemas.stats import BattingStatsResponse, BowlingStatsResponse


def test_batting_stats_response_serializes_complete_aggregate() -> None:
    response = BattingStatsResponse(
        format=MatchFormat.T20,
        matches=15,
        innings=14,
        not_outs=3,
        runs=450,
        balls_faced=320,
        high_score=89,
        hundreds=0,
        fifties=4,
        ducks=1,
        fours=48,
        sixes=12,
    )

    assert response.model_dump(mode="json") == {
        "format": "T20",
        "matches": 15,
        "innings": 14,
        "not_outs": 3,
        "runs": 450,
        "balls_faced": 320,
        "high_score": 89,
        "hundreds": 0,
        "fifties": 4,
        "ducks": 1,
        "fours": 48,
        "sixes": 12,
    }


def test_bowling_stats_response_supports_overs_and_best_figures() -> None:
    response = BowlingStatsResponse(
        format=MatchFormat.ONE_DAY,
        matches=8,
        innings=7,
        overs_bowled=Decimal("52.3"),
        runs_conceded=310,
        wickets=22,
        best_bowled="5/32",
        maidens=3,
        four_wicket_hauls=2,
        five_wicket_hauls=1,
        wides=8,
        catches=1,
    )

    serialized = response.model_dump(mode="json")
    assert serialized["format"] == "one-day"
    assert serialized["overs_bowled"] == 52.3
    assert serialized["best_bowled"] == "5/32"


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (
            BattingStatsResponse,
            {
                "format": "T20",
                "matches": -1,
                "innings": 0,
                "not_outs": 0,
                "runs": 0,
                "balls_faced": 0,
                "high_score": 0,
                "hundreds": 0,
                "fifties": 0,
                "ducks": 0,
                "fours": 0,
                "sixes": 0,
            },
        ),
        (
            BowlingStatsResponse,
            {
                "format": "T20",
                "matches": 0,
                "innings": 0,
                "overs_bowled": 0,
                "runs_conceded": 0,
                "wickets": -1,
                "best_bowled": None,
                "maidens": 0,
                "four_wicket_hauls": 0,
                "five_wicket_hauls": 0,
                "wides": 0,
                "catches": 0,
            },
        ),
    ],
)
def test_stats_responses_reject_negative_aggregates(schema, payload) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)
