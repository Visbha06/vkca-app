"""Unit tests for match request and response schemas."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import MatchFormat
from src.schemas.match import MatchCreate, MatchResponse


def test_match_create_validates_and_ignores_server_managed_fields() -> None:
    match = MatchCreate.model_validate(
        {
            "match_date": "2026-07-01",
            "format": "T20",
            "opponent_name": "Challengers CC",
            "venue": "Main Ground",
            "result": "Won by 7 wickets",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "version_number": 99,
        }
    )

    assert match.match_date == date(2026, 7, 1)
    assert match.format is MatchFormat.T20
    assert match.opponent_name == "Challengers CC"
    assert "created_at" not in match.model_fields_set
    assert "updated_at" not in match.model_fields_set
    assert "version_number" not in match.model_fields_set


@pytest.mark.parametrize("field", ["opponent_name", "venue", "result"])
def test_match_create_rejects_blank_text_fields(field: str) -> None:
    payload = {
        "match_date": "2026-07-01",
        "format": "T20",
        "opponent_name": "Challengers CC",
        "venue": "Main Ground",
        "result": "Won by 7 wickets",
    }
    payload[field] = ""

    with pytest.raises(ValidationError):
        MatchCreate.model_validate(payload)


def test_match_create_rejects_unknown_format() -> None:
    with pytest.raises(ValidationError):
        MatchCreate.model_validate(
            {
                "match_date": "2026-07-01",
                "format": "hundred",
                "opponent_name": "Challengers CC",
                "venue": "Main Ground",
                "result": "Won by 7 wickets",
            }
        )


def test_match_response_serializes_complete_match() -> None:
    now = datetime.now(UTC)
    response = MatchResponse.model_validate(
        {
            "id": uuid4(),
            "match_date": date(2026, 7, 1),
            "format": MatchFormat.T20,
            "opponent_name": "Challengers CC",
            "venue": "Main Ground",
            "result": "Won by 7 wickets",
            "created_at": now,
            "updated_at": now,
            "version_number": 1,
        }
    )

    serialized = response.model_dump(mode="json")
    assert serialized["match_date"] == "2026-07-01"
    assert serialized["format"] == "T20"
    assert serialized["version_number"] == 1
