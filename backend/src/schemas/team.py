"""Pydantic schemas for team and roster operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.enums import AgeGroup
from src.schemas.base import BaseRequestSchema


class TeamCreate(BaseRequestSchema):
    """Validated payload for creating a complete team roster."""

    name: str = Field(min_length=1, max_length=200)
    age_group: AgeGroup
    player_ids: list[UUID] = Field(min_length=7, max_length=15)


class TeamUpdate(TeamCreate):
    """Complete replacement payload carrying the OCC version."""

    version_number: int = Field(ge=1)


class TeamResponse(BaseModel):
    """Team summary used in lists and mutation responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    age_group: AgeGroup
    player_count: int = Field(ge=0, default=0)
    created_at: datetime
    updated_at: datetime
    version_number: int


class PaginatedTeamResponse(BaseModel):
    """A stable, server-paginated page of team summaries."""

    teams: list[TeamResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_teams: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class TeamRosterPlayerResponse(BaseModel):
    """A roster entry, including inactive historical members."""

    player_id: UUID
    first_name: str
    last_name: str
    is_active: bool
    roster_order: int = Field(ge=0)


class TeamRosterResponse(BaseModel):
    """Ordered players belonging to one team."""

    team_id: UUID
    players: list[TeamRosterPlayerResponse]


class TeamPlayerResponse(BaseModel):
    """Legacy public representation of a single team membership."""

    model_config = ConfigDict(from_attributes=True)

    team_id: UUID
    player_id: UUID
    joined_at: datetime
