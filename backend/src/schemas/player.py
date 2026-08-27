"""Pydantic schemas for player profile requests and responses."""

import json
import math
from datetime import date, datetime
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.schemas.base import BaseRequestSchema

# Player profile bounds prevent authenticated resource exhaustion and keep
# directory responses safe when a page contains many profiles.
PLAYER_BIO_MAX_LENGTH = 2_000
PLAYER_METADATA_MAX_BYTES = 8 * 1_024
PLAYER_METADATA_MAX_DEPTH = 4
PLAYER_METADATA_MAX_KEYS = 50
PLAYER_METADATA_MAX_KEY_LENGTH = 100
PLAYER_METADATA_MAX_ARRAY_ITEMS = 50
PLAYER_METADATA_MAX_STRING_LENGTH = 2_000


def _validate_metadata_value(value: object, *, depth: int) -> None:
    """Validate one JSON value without descending beyond the configured depth."""

    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str) and len(value) > PLAYER_METADATA_MAX_STRING_LENGTH:
            raise ValueError(
                "player_metadata strings must not exceed "
                f"{PLAYER_METADATA_MAX_STRING_LENGTH} characters"
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("player_metadata numbers must be finite")
        return
    if isinstance(value, dict):
        if depth > PLAYER_METADATA_MAX_DEPTH:
            raise ValueError(
                "player_metadata nesting must not exceed "
                f"{PLAYER_METADATA_MAX_DEPTH} levels"
            )
        if len(value) > PLAYER_METADATA_MAX_KEYS:
            raise ValueError(
                "player_metadata objects must not exceed "
                f"{PLAYER_METADATA_MAX_KEYS} keys"
            )
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("player_metadata object keys must be strings")
            if len(key) > PLAYER_METADATA_MAX_KEY_LENGTH:
                raise ValueError(
                    "player_metadata keys must not exceed "
                    f"{PLAYER_METADATA_MAX_KEY_LENGTH} characters"
                )
            _validate_metadata_value(item, depth=depth + 1)
        return
    if isinstance(value, list):
        if depth > PLAYER_METADATA_MAX_DEPTH:
            raise ValueError(
                "player_metadata nesting must not exceed "
                f"{PLAYER_METADATA_MAX_DEPTH} levels"
            )
        if len(value) > PLAYER_METADATA_MAX_ARRAY_ITEMS:
            raise ValueError(
                "player_metadata arrays must not exceed "
                f"{PLAYER_METADATA_MAX_ARRAY_ITEMS} items"
            )
        for item in value:
            _validate_metadata_value(item, depth=depth + 1)
        return
    raise ValueError("player_metadata values must be JSON-compatible")


def validate_player_metadata(value: object) -> dict[str, Any]:
    """Return a bounded JSON object suitable for persistence."""

    if not isinstance(value, dict):
        raise ValueError("player_metadata must be a JSON object")
    _validate_metadata_value(value, depth=1)
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("player_metadata must be valid UTF-8 JSON") from exc
    if len(encoded) > PLAYER_METADATA_MAX_BYTES:
        raise ValueError(
            "player_metadata must not exceed "
            f"{PLAYER_METADATA_MAX_BYTES} serialized UTF-8 bytes"
        )
    return value


PlayerBio = Annotated[str, Field(max_length=PLAYER_BIO_MAX_LENGTH)]
PlayerMetadata = Annotated[
    dict[str, Any],
    BeforeValidator(validate_player_metadata),
]


class PlayerFields(BaseRequestSchema):
    """Shared validated player profile fields."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    bio: PlayerBio | None = None
    batting_style: BattingStyle
    bowling_style: BowlingStyle
    player_type: PlayerType
    player_metadata: PlayerMetadata = Field(default_factory=dict)


class PlayerCreate(PlayerFields):
    """Payload for creating a player profile."""


class PlayerUpdate(BaseRequestSchema):
    """Partial player update carrying the required OCC version."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    bio: PlayerBio | None = None
    batting_style: BattingStyle | None = None
    bowling_style: BowlingStyle | None = None
    player_type: PlayerType | None = None
    player_metadata: PlayerMetadata | None = None
    is_active: bool | None = None
    version_number: int = Field(ge=1)


class TeamSummary(BaseModel):
    """Lightweight team identity embedded in player responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class PlayerResponse(BaseModel):
    """Complete player projection with bounds for legacy oversized rows.

    Valid stored values are returned unchanged. Legacy biographies are projected
    to their first 2,000 characters, while legacy metadata that violates current
    write bounds is represented as an empty object. Reads never mutate storage.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    bio: str | None = Field(max_length=PLAYER_BIO_MAX_LENGTH)
    batting_style: BattingStyle
    bowling_style: BowlingStyle
    player_type: PlayerType
    player_metadata: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version_number: int
    teams: list[TeamSummary] = Field(default_factory=list)

    @field_validator("bio", mode="before")
    @classmethod
    def bound_legacy_bio(cls, value: object) -> object:
        """Project legacy biographies to the current response maximum."""

        if isinstance(value, str) and len(value) > PLAYER_BIO_MAX_LENGTH:
            return value[:PLAYER_BIO_MAX_LENGTH]
        return value

    @field_validator("player_metadata", mode="before")
    @classmethod
    def bound_legacy_metadata(cls, value: object) -> dict[str, Any]:
        """Omit legacy metadata that cannot satisfy current response bounds."""

        try:
            return validate_player_metadata(value)
        except ValueError:
            return {}


class PaginatedPlayerResponse(BaseModel):
    """One page of active players with navigation metadata."""

    players: list[PlayerResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_players: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_previous: bool
    has_next: bool

    @model_validator(mode="after")
    def validate_pagination_metadata(self) -> Self:
        """Reject metadata that disagrees with the page and total counts."""

        expected_total_pages = (
            self.total_players + self.page_size - 1
        ) // self.page_size
        if self.total_pages != expected_total_pages:
            raise ValueError(f"total_pages must equal {expected_total_pages}")

        expected_has_previous = self.page > 1
        if self.has_previous != expected_has_previous:
            raise ValueError(f"has_previous must equal {expected_has_previous}")

        expected_has_next = self.page < self.total_pages
        if self.has_next != expected_has_next:
            raise ValueError(f"has_next must equal {expected_has_next}")

        return self
