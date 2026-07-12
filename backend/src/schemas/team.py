"""Pydantic schemas for team and roster membership operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.base import BaseRequestSchema


class TeamCreate(BaseRequestSchema):
    """Payload for creating a cricket team."""

    name: str = Field(min_length=1, max_length=200)
    age_group: str = Field(min_length=1, max_length=50)


class TeamResponse(BaseModel):
    """Complete server-managed team representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    age_group: str
    created_at: datetime
    updated_at: datetime
    version_number: int


class TeamPlayerResponse(BaseModel):
    """Public representation of a player's team membership."""

    model_config = ConfigDict(from_attributes=True)

    team_id: UUID
    player_id: UUID
    joined_at: datetime
