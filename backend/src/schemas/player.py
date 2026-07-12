"""Pydantic schemas for player profile requests and responses."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.schemas.base import BaseRequestSchema


class PlayerFields(BaseRequestSchema):
    """Shared validated player profile fields."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    bio: str | None = None
    batting_style: BattingStyle
    bowling_style: BowlingStyle
    player_type: PlayerType
    player_metadata: dict[str, Any] = Field(default_factory=dict)


class PlayerCreate(PlayerFields):
    """Payload for creating a player profile."""


class PlayerUpdate(BaseRequestSchema):
    """Partial player update carrying the required OCC version."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    date_of_birth: date | None = None
    bio: str | None = None
    batting_style: BattingStyle | None = None
    bowling_style: BowlingStyle | None = None
    player_type: PlayerType | None = None
    player_metadata: dict[str, Any] | None = None
    is_active: bool | None = None
    version_number: int = Field(ge=1)


class PlayerResponse(BaseModel):
    """Complete server-managed player representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    bio: str | None
    batting_style: BattingStyle
    bowling_style: BowlingStyle
    player_type: PlayerType
    player_metadata: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version_number: int
