"""Unit tests for player request and response schemas."""

import json
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import BattingStyle, BowlingStyle, PlayerType, UserRole
from src.schemas.player import (
    PLAYER_BIO_MAX_LENGTH,
    PLAYER_METADATA_MAX_ARRAY_ITEMS,
    PLAYER_METADATA_MAX_BYTES,
    PLAYER_METADATA_MAX_DEPTH,
    PLAYER_METADATA_MAX_KEY_LENGTH,
    PLAYER_METADATA_MAX_KEYS,
    PLAYER_METADATA_MAX_STRING_LENGTH,
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


def player_create_payload(**overrides: object) -> dict[str, object]:
    """Return the smallest complete create payload with optional overrides."""

    payload: dict[str, object] = {
        "first_name": "Sachin",
        "last_name": "Tendulkar",
        "date_of_birth": "1973-04-24",
        "batting_style": "right",
        "bowling_style": "right-arm leg-break",
        "player_type": "batter",
    }
    payload.update(overrides)
    return payload


def metadata_at_serialized_size(target_bytes: int) -> dict[str, str]:
    """Build metadata whose compact UTF-8 JSON representation is exact."""

    metadata = {
        f"part_{index}": "x" * PLAYER_METADATA_MAX_STRING_LENGTH for index in range(4)
    }
    metadata["remainder"] = ""
    current_size = len(json.dumps(metadata, separators=(",", ":")).encode("utf-8"))
    remainder = target_bytes - current_size
    assert 0 <= remainder <= PLAYER_METADATA_MAX_STRING_LENGTH
    metadata["remainder"] = "x" * remainder
    assert (
        len(json.dumps(metadata, separators=(",", ":")).encode("utf-8")) == target_bytes
    )
    return metadata


@pytest.mark.parametrize("bio", [None, "", "Normal biography"])
def test_player_bio_accepts_existing_normal_values(bio: str | None) -> None:
    assert PlayerCreate.model_validate(player_create_payload(bio=bio)).bio == bio
    assert PlayerUpdate(bio=bio, version_number=1).bio == bio


def test_player_bio_accepts_exact_limit_for_create_and_update() -> None:
    bio = "x" * PLAYER_BIO_MAX_LENGTH

    assert PlayerCreate.model_validate(player_create_payload(bio=bio)).bio == bio
    assert PlayerUpdate(bio=bio, version_number=1).bio == bio


def test_player_bio_rejects_limit_plus_one_for_create_and_update() -> None:
    bio = "x" * (PLAYER_BIO_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        PlayerCreate.model_validate(player_create_payload(bio=bio))
    with pytest.raises(ValidationError):
        PlayerUpdate(bio=bio, version_number=1)


def test_player_metadata_accepts_normal_json_for_create_and_update() -> None:
    metadata = {
        "shirt_number": 10,
        "available": True,
        "nickname": None,
        "preferences": ["opening", {"format": "T20"}],
    }

    assert (
        PlayerCreate.model_validate(
            player_create_payload(player_metadata=metadata)
        ).player_metadata
        == metadata
    )
    assert (
        PlayerUpdate(player_metadata=metadata, version_number=1).player_metadata
        == metadata
    )


def test_player_metadata_accepts_exact_serialized_byte_limit() -> None:
    metadata = metadata_at_serialized_size(PLAYER_METADATA_MAX_BYTES)

    assert (
        PlayerCreate.model_validate(
            player_create_payload(player_metadata=metadata)
        ).player_metadata
        == metadata
    )


def test_player_metadata_rejects_serialized_byte_limit_plus_one() -> None:
    metadata = metadata_at_serialized_size(PLAYER_METADATA_MAX_BYTES + 1)

    with pytest.raises(ValidationError, match="serialized UTF-8 bytes"):
        PlayerCreate.model_validate(player_create_payload(player_metadata=metadata))
    with pytest.raises(ValidationError, match="serialized UTF-8 bytes"):
        PlayerUpdate(player_metadata=metadata, version_number=1)


def test_player_metadata_accepts_structural_boundaries() -> None:
    metadata = {
        "keys": {str(index): index for index in range(PLAYER_METADATA_MAX_KEYS)},
        "array": list(range(PLAYER_METADATA_MAX_ARRAY_ITEMS)),
        "key_depth": [{"leaf": ["value"]}],
        "k" * PLAYER_METADATA_MAX_KEY_LENGTH: "x" * PLAYER_METADATA_MAX_STRING_LENGTH,
    }

    assert (
        PlayerUpdate(player_metadata=metadata, version_number=1).player_metadata
        == metadata
    )


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (
            {"nested": [{"level_three": [{"level_five": "too deep"}]}]},
            "nesting",
        ),
        (
            {str(index): index for index in range(PLAYER_METADATA_MAX_KEYS + 1)},
            "keys",
        ),
        ({"k" * (PLAYER_METADATA_MAX_KEY_LENGTH + 1): True}, "keys"),
        ({"items": list(range(PLAYER_METADATA_MAX_ARRAY_ITEMS + 1))}, "arrays"),
        ({"value": "x" * (PLAYER_METADATA_MAX_STRING_LENGTH + 1)}, "strings"),
        (
            {"nested": [{"items": list(range(PLAYER_METADATA_MAX_ARRAY_ITEMS + 1))}]},
            "arrays",
        ),
        ({"arbitrary": object()}, "JSON-compatible"),
    ],
)
def test_player_metadata_rejects_resource_limit_bypasses(
    metadata: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        PlayerCreate.model_validate(player_create_payload(player_metadata=metadata))
    with pytest.raises(ValidationError, match=message):
        PlayerUpdate(player_metadata=metadata, version_number=1)


def test_player_metadata_depth_constant_matches_boundary_fixture() -> None:
    assert PLAYER_METADATA_MAX_DEPTH == 4


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
        PlayerAccountLinkRequest(user_id=user_id, version_number=3).user_id == user_id
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
