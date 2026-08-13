"""Unit tests for player request and response schemas."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import BattingStyle, BowlingStyle, PlayerType, UserRole
from src.schemas.player import (
    PaginatedPlayerResponse,
    PlayerCreate,
    PlayerResponse,
    PlayerUpdate,
    TeamSummary,
)
from src.schemas.player_account import (
    PaginatedPlayerAccountResponse,
    PlayerAccountAssociationResponse,
    PlayerAccountLinkRequest,
    PlayerAccountLookupQuery,
    PlayerAccountReassignRequest,
    PlayerAccountSnapshot,
    PlayerAccountUnlinkRequest,
)


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
    assert response.teams == []
    assert response.model_dump(mode="json")["date_of_birth"] == "1973-04-24"


def test_paginated_player_response_validates_complete_metadata() -> None:
    now = datetime.now(UTC)
    team = TeamSummary(id=uuid4(), name="Senior XI")
    player = PlayerResponse.model_validate(
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
            "teams": [team],
        }
    )

    response = PaginatedPlayerResponse(
        players=[player],
        page=2,
        page_size=1,
        total_players=3,
        total_pages=3,
        has_previous=True,
        has_next=True,
    )

    assert response.players[0].teams == [team]
    assert response.model_dump(mode="json")["total_pages"] == 3


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"page": 0}, "greater than or equal to 1"),
        ({"page_size": 101}, "less than or equal to 100"),
        ({"total_players": -1}, "greater than or equal to 0"),
        ({"total_pages": 1}, "total_pages must equal 2"),
        ({"has_previous": True}, "has_previous must equal False"),
        ({"has_next": False}, "has_next must equal True"),
    ],
)
def test_paginated_player_response_rejects_invalid_metadata(
    overrides: dict[str, int | bool],
    message: str,
) -> None:
    payload = {
        "players": [],
        "page": 1,
        "page_size": 20,
        "total_players": 21,
        "total_pages": 2,
        "has_previous": False,
        "has_next": True,
    }
    payload.update(overrides)

    with pytest.raises(ValidationError, match=message):
        PaginatedPlayerResponse.model_validate(payload)


def test_player_account_lookup_normalizes_search_and_enforces_bounds() -> None:
    query = PlayerAccountLookupQuery(search="  Rohan Patel  ", page=2, page_size=25)

    assert query.search == "Rohan Patel"
    assert PlayerAccountLookupQuery(search="   ").search is None

    for invalid in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        with pytest.raises(ValidationError):
            PlayerAccountLookupQuery.model_validate(invalid)


def test_player_account_requests_are_strict_and_reassignment_is_not_a_noop() -> None:
    user_id = uuid4()

    assert (
        PlayerAccountLinkRequest(user_id=user_id, version_number=3).user_id
        == user_id
    )
    assert PlayerAccountUnlinkRequest(version_number=4).version_number == 4

    with pytest.raises(ValidationError):
        PlayerAccountLinkRequest.model_validate(
            {"user_id": user_id, "version_number": 3, "password": "secret"}
        )
    with pytest.raises(ValidationError, match="different"):
        PlayerAccountReassignRequest(
            expected_user_id=user_id,
            new_user_id=user_id,
            version_number=4,
        )


def test_player_account_responses_expose_only_allowlisted_account_fields() -> None:
    user_id = uuid4()
    player_id = uuid4()
    snapshot = PlayerAccountSnapshot.model_validate(
        {
            "id": user_id,
            "display_name": "Rohan Patel",
            "email": "rohan@example.com",
            "role": UserRole.PLAYER,
            "is_active": True,
            "hashed_password": "must-not-leak",
            "sessions": ["must-not-leak"],
        }
    )
    page = PaginatedPlayerAccountResponse(
        users=[snapshot],
        page=1,
        page_size=20,
        total_users=1,
        total_pages=1,
    )
    association = PlayerAccountAssociationResponse(
        player_id=player_id,
        account=snapshot,
        player_version_number=2,
    )

    serialized = page.model_dump(mode="json")["users"][0]
    assert serialized == {
        "id": str(user_id),
        "display_name": "Rohan Patel",
        "email": "rohan@example.com",
        "role": "player",
        "is_active": True,
    }
    assert association.account == snapshot


def test_normal_player_response_omits_account_and_session_fields() -> None:
    now = datetime.now(UTC)
    response = PlayerResponse.model_validate(
        {
            "id": uuid4(),
            "first_name": "Safe",
            "last_name": "Player",
            "date_of_birth": date(2010, 1, 1),
            "bio": None,
            "batting_style": BattingStyle.RIGHT,
            "bowling_style": BowlingStyle.RIGHT_ARM_MEDIUM,
            "player_type": PlayerType.ALL_ROUNDER,
            "player_metadata": {},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "version_number": 1,
            "user_id": uuid4(),
            "account": {"email": "hidden@example.com"},
            "hashed_password": "hidden",
            "sessions": ["hidden"],
        }
    )

    serialized = response.model_dump(mode="json")
    assert "user_id" not in serialized
    assert "account" not in serialized
    assert "hashed_password" not in serialized
    assert "sessions" not in serialized
