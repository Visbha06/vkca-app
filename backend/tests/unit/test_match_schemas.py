"""Unit tests for the discriminated Match participant schemas."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import MatchFormat, MatchParticipantType
from src.schemas.match import MatchCreate, MatchResponse


def external_payload(*, academy_side: str = "home") -> dict[str, object]:
    """Return a valid external Match request payload."""

    return {
        "match_date": "2026-07-01",
        "format": "T20",
        "venue": "Main Ground",
        "result": "Scheduled",
        "participants": {
            "participant_type": "external",
            "academy_team_id": str(uuid4()),
            "external_opponent_name": "Challengers CC",
            "academy_side": academy_side,
        },
    }


def internal_payload() -> dict[str, object]:
    """Return a valid internal Match request payload."""

    return {
        "match_date": "2026-07-01",
        "format": "T20",
        "venue": "Main Ground",
        "result": "Scheduled",
        "participants": {
            "participant_type": "internal",
            "home_team_id": str(uuid4()),
            "away_team_id": str(uuid4()),
        },
    }


@pytest.mark.parametrize("academy_side", ["home", "away"])
def test_match_create_accepts_external_participants(academy_side: str) -> None:
    match = MatchCreate.model_validate(external_payload(academy_side=academy_side))

    assert match.format is MatchFormat.T20
    assert match.participants.participant_type is MatchParticipantType.EXTERNAL
    assert match.participants.academy_side == academy_side


def test_match_create_accepts_internal_participants() -> None:
    match = MatchCreate.model_validate(internal_payload())

    assert match.participants.participant_type is MatchParticipantType.INTERNAL
    assert match.participants.home_team_id != match.participants.away_team_id


@pytest.mark.parametrize(
    "participants",
    [
        {
            "participant_type": "external",
            "academy_team_id": str(uuid4()),
            "external_opponent_name": "Northside CC",
            "academy_side": "home",
            "home_team_id": str(uuid4()),
        },
        {
            "participant_type": "external",
            "academy_team_id": str(uuid4()),
            "external_opponent_name": "Northside CC",
        },
        {
            "participant_type": "external",
            "academy_team_id": str(uuid4()),
            "external_opponent_name": "   ",
            "academy_side": "home",
        },
        {
            "participant_type": "internal",
            "home_team_id": str(uuid4()),
        },
        {
            "participant_type": "unknown",
            "academy_team_id": str(uuid4()),
            "external_opponent_name": "Northside CC",
            "academy_side": "home",
        },
    ],
)
def test_match_create_rejects_invalid_participant_shapes(
    participants: dict[str, object],
) -> None:
    payload = external_payload()
    payload["participants"] = participants

    with pytest.raises(ValidationError):
        MatchCreate.model_validate(payload)


def test_match_create_rejects_same_internal_team_and_legacy_opponent_shape() -> None:
    team_id = uuid4()
    same_team = internal_payload()
    same_team["participants"] = {
        "participant_type": "internal",
        "home_team_id": str(team_id),
        "away_team_id": str(team_id),
    }

    with pytest.raises(ValidationError):
        MatchCreate.model_validate(same_team)
    with pytest.raises(ValidationError):
        MatchCreate.model_validate(
            {
                "match_date": "2026-07-01",
                "format": "T20",
                "opponent_name": "Legacy CC",
                "venue": "Main Ground",
                "result": "Scheduled",
            }
        )


def test_match_response_serializes_external_participant() -> None:
    now = datetime.now(UTC)
    team_id = uuid4()
    response = MatchResponse.model_validate(
        {
            "id": uuid4(),
            "match_date": date(2026, 7, 1),
            "format": MatchFormat.T20,
            "venue": "Main Ground",
            "result": "Scheduled",
            "participants": {
                "kind": "external",
                "academy_team": {"id": team_id, "name": "U15 Falcons"},
                "opponent_name": "Challengers CC",
                "academy_side": "home",
            },
            "created_at": now,
            "updated_at": now,
            "version_number": 1,
        }
    )

    assert response.model_dump(mode="json")["participants"] == {
        "kind": "external",
        "academy_team": {"id": str(team_id), "name": "U15 Falcons"},
        "opponent_name": "Challengers CC",
        "academy_side": "home",
    }
