"""Pydantic boundaries for external and internal cricket Matches."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.enums import MatchFormat, MatchParticipantType
from src.schemas.base import BaseRequestSchema


class _MatchParticipantRequestBase(BaseModel):
    """Strict base for one participant request variant."""

    model_config = ConfigDict(extra="forbid")


class ExternalMatchParticipantRequest(_MatchParticipantRequestBase):
    """One academy Team playing a named external opponent."""

    participant_type: Literal[MatchParticipantType.EXTERNAL]
    academy_team_id: UUID
    external_opponent_name: str = Field(min_length=1, max_length=200)
    academy_side: Literal["home", "away"]


class InternalMatchParticipantRequest(_MatchParticipantRequestBase):
    """Two academy Teams with explicit home and away sides."""

    participant_type: Literal[MatchParticipantType.INTERNAL]
    home_team_id: UUID
    away_team_id: UUID


type MatchParticipantRequest = Annotated[
    ExternalMatchParticipantRequest | InternalMatchParticipantRequest,
    Field(discriminator="participant_type"),
]


class MatchFields(BaseRequestSchema):
    """Common Match metadata plus one typed participant request."""

    match_date: date
    format: MatchFormat
    venue: str = Field(min_length=1, max_length=200)
    result: str = Field(min_length=1, max_length=200)
    participants: MatchParticipantRequest


class MatchCreate(MatchFields):
    """Payload for recording a cricket Match."""


class MatchUpdate(MatchFields):
    """Complete Match replacement carrying its OCC version."""

    version_number: int = Field(ge=1)


class MatchTeamReference(BaseModel):
    """Safe Team identity embedded in participant responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(min_length=1, max_length=200)


class ExternalMatchParticipantResponse(BaseModel):
    """Expanded external participant response."""

    kind: Literal[MatchParticipantType.EXTERNAL]
    academy_team: MatchTeamReference
    opponent_name: str = Field(min_length=1, max_length=200)
    academy_side: Literal["home", "away"]


class InternalMatchParticipantResponse(BaseModel):
    """Expanded internal participant response."""

    kind: Literal[MatchParticipantType.INTERNAL]
    home_team: MatchTeamReference
    away_team: MatchTeamReference


type MatchParticipantResponse = Annotated[
    ExternalMatchParticipantResponse | InternalMatchParticipantResponse,
    Field(discriminator="kind"),
]


class MatchResponse(BaseModel):
    """Complete server-managed Match representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_date: date
    format: MatchFormat
    venue: str
    result: str
    participants: MatchParticipantResponse
    created_at: datetime
    updated_at: datetime
    version_number: int = Field(ge=1)


MatchParticipantsRequest = MatchParticipantRequest
MatchParticipantsResponse = MatchParticipantResponse
