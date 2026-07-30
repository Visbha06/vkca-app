"""Pydantic contracts for the Coaches Portal."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.enums import UserRole
from src.schemas.base import BaseRequestSchema

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class CoachTeamResponse(BaseModel):
    """A compact team representation nested in coach responses."""

    id: UUID
    name: str


class CoachResponse(BaseModel):
    """Public coach account information, including current team assignments."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    role: UserRole
    is_active: bool
    version_number: int
    created_at: datetime
    updated_at: datetime
    teams: list[CoachTeamResponse] = Field(default_factory=list)


class CoachCreateResponse(CoachResponse):
    """Creation response containing the one-time plaintext password."""

    temporary_password: str


class PaginatedCoachResponse(BaseModel):
    """Server-paginated coach collection metadata."""

    coaches: list[CoachResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_coaches: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_previous: bool
    has_next: bool


class CoachCreate(BaseRequestSchema):
    """Payload for creating an assistant coach account."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    team_ids: list[UUID] = Field(default_factory=list)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Trim names and reject whitespace-only values."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Require a conventional email address and normalize its case."""

        normalized = value.strip().lower()
        if EMAIL_PATTERN.fullmatch(normalized) is None:
            raise ValueError("email must be a valid email address")
        return normalized

    @model_validator(mode="after")
    def validate_unique_team_ids(self) -> "CoachCreate":
        """Reject duplicate initial assignments before any write begins."""

        if len(set(self.team_ids)) != len(self.team_ids):
            raise ValueError("team_ids must not contain duplicates")
        return self


class CoachTeamUpdate(BaseRequestSchema):
    """Complete desired team-assignment set with an OCC version."""

    team_ids: list[UUID] = Field(default_factory=list)
    version_number: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_unique_team_ids(self) -> "CoachTeamUpdate":
        """Reject duplicates instead of allowing ambiguous replacement sets."""

        if len(set(self.team_ids)) != len(self.team_ids):
            raise ValueError("team_ids must not contain duplicates")
        return self


class CoachStatusUpdate(BaseRequestSchema):
    """OCC version supplied for a coach account status mutation."""

    version_number: int = Field(ge=1)
