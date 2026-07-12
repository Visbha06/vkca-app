"""Unit tests for player request and response schemas."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.schemas.player import PlayerCreate, PlayerResponse, PlayerUpdate


def test_player_create_validates_and_ignores_server_managed_fields() -> None:
    payload = {
        "first_name": "Sachin",
        "last_name": "Tendulkar",
        "date_of_birth": "1973-04-24",
        "bio": "Right-handed batter",
        "batting_style": "right",
        "bowling_style": "right-arm leg-break",
        "player_type": "batter",
        "player_metadata": {"shirt_number": 10},
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "version_number": 99,
    }

    player = PlayerCreate.model_validate(payload)

    assert player.first_name == "Sachin"
    assert player.date_of_birth == date(1973, 4, 24)
    assert player.batting_style is BattingStyle.RIGHT
    assert player.bowling_style is BowlingStyle.RIGHT_ARM_LEG_BREAK
    assert player.player_type is PlayerType.BATTER
    assert player.player_metadata == {"shirt_number": 10}
    assert "created_at" not in player.model_fields_set
    assert "updated_at" not in player.model_fields_set
    assert "version_number" not in player.model_fields_set


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_player_create_rejects_blank_names(field: str) -> None:
    payload = {
        "first_name": "Sachin",
        "last_name": "Tendulkar",
        "date_of_birth": "1973-04-24",
        "batting_style": "right",
        "bowling_style": "right-arm leg-break",
        "player_type": "batter",
    }
    payload[field] = ""

    with pytest.raises(ValidationError):
        PlayerCreate.model_validate(payload)


def test_player_update_requires_version_and_only_emits_supplied_changes() -> None:
    update = PlayerUpdate.model_validate(
        {"bio": "Updated bio", "is_active": False, "version_number": 3}
    )

    assert update.version_number == 3
    assert update.model_dump(exclude_unset=True) == {
        "bio": "Updated bio",
        "is_active": False,
        "version_number": 3,
    }

    with pytest.raises(ValidationError):
        PlayerUpdate.model_validate({"bio": "Missing version"})


def test_player_response_serializes_complete_profile() -> None:
    now = datetime.now(UTC)
    response = PlayerResponse.model_validate(
        {
            "id": uuid4(),
            "first_name": "Sachin",
            "last_name": "Tendulkar",
            "date_of_birth": date(1973, 4, 24),
            "bio": None,
            "batting_style": BattingStyle.RIGHT,
            "bowling_style": BowlingStyle.RIGHT_ARM_LEG_BREAK,
            "player_type": PlayerType.BATTER,
            "player_metadata": {},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "version_number": 1,
        }
    )

    assert response.version_number == 1
    assert response.is_active is True
    assert response.model_dump(mode="json")["date_of_birth"] == "1973-04-24"
