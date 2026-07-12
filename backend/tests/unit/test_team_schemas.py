"""Unit tests for team and roster membership schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas.team import TeamCreate, TeamPlayerResponse, TeamResponse


def test_team_create_validates_and_ignores_server_managed_fields() -> None:
    team = TeamCreate.model_validate(
        {
            "name": "U14 Lions",
            "age_group": "U14",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
            "version_number": 99,
        }
    )

    assert team.name == "U14 Lions"
    assert team.age_group == "U14"
    assert "created_at" not in team.model_fields_set
    assert "updated_at" not in team.model_fields_set
    assert "version_number" not in team.model_fields_set


@pytest.mark.parametrize("field", ["name", "age_group"])
def test_team_create_rejects_blank_fields(field: str) -> None:
    payload = {"name": "U14 Lions", "age_group": "U14"}
    payload[field] = ""

    with pytest.raises(ValidationError):
        TeamCreate.model_validate(payload)


def test_team_response_serializes_complete_team() -> None:
    now = datetime.now(UTC)
    response = TeamResponse.model_validate(
        {
            "id": uuid4(),
            "name": "U14 Lions",
            "age_group": "U14",
            "created_at": now,
            "updated_at": now,
            "version_number": 1,
        }
    )

    serialized = response.model_dump(mode="json")
    assert serialized["name"] == "U14 Lions"
    assert serialized["age_group"] == "U14"
    assert serialized["version_number"] == 1


def test_team_player_response_serializes_membership() -> None:
    team_id = uuid4()
    player_id = uuid4()
    joined_at = datetime.now(UTC)

    response = TeamPlayerResponse.model_validate(
        {
            "team_id": team_id,
            "player_id": player_id,
            "joined_at": joined_at,
        }
    )

    assert response.model_dump(mode="json") == {
        "team_id": str(team_id),
        "player_id": str(player_id),
        "joined_at": joined_at.isoformat().replace("+00:00", "Z"),
    }
