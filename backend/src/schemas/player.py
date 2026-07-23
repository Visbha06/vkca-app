"""Pydantic schemas for player profile requests and responses."""

from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class TeamSummary(BaseModel):
    """Lightweight team identity embedded in player responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


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
    teams: list[TeamSummary] = Field(default_factory=list)


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
