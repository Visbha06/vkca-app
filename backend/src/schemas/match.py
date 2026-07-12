"""Pydantic schemas for match requests and responses."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.enums import MatchFormat
from src.schemas.base import BaseRequestSchema


class MatchCreate(BaseRequestSchema):
    """Payload for recording a cricket match."""

    match_date: date
    format: MatchFormat
    opponent_name: str = Field(min_length=1, max_length=200)
    venue: str = Field(min_length=1, max_length=200)
    result: str = Field(min_length=1, max_length=200)


class MatchResponse(BaseModel):
    """Complete server-managed match representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_date: date
    format: MatchFormat
    opponent_name: str
    venue: str
    result: str
    created_at: datetime
    updated_at: datetime
    version_number: int
