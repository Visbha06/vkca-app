"""Pydantic boundaries for external and internal cricket Matches."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.enums import (
    MatchFormat,
    MatchLifecycleState,
    MatchParticipantType,
    MatchResultCode,
    ScoringAuthority,
)
from src.schemas.base import BaseRequestSchema

if TYPE_CHECKING:
    from src.models.match import Match


class _MatchParticipantRequestBase(BaseModel):
    """Strict base for one participant request variant."""

    model_config = ConfigDict(extra="forbid")


class ExternalMatchParticipantRequest(_MatchParticipantRequestBase):
    """One academy Team playing a named external opponent."""

    participant_type: Literal[MatchParticipantType.EXTERNAL]
    academy_team_id: UUID
    external_opponent_name: str = Field(min_length=1, max_length=200)
    academy_side: Literal["home", "away"]

    @field_validator("external_opponent_name")
    @classmethod
    def validate_external_opponent_name(cls, value: str) -> str:
        """Reject whitespace-only names and normalize accepted opponent labels."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("external_opponent_name must not be blank")
        return normalized


class InternalMatchParticipantRequest(_MatchParticipantRequestBase):
    """Two academy Teams with explicit home and away sides."""

    participant_type: Literal[MatchParticipantType.INTERNAL]
    home_team_id: UUID
    away_team_id: UUID

    @model_validator(mode="after")
    def validate_distinct_teams(self) -> "InternalMatchParticipantRequest":
        """An academy Team cannot occupy both sides of an internal Match."""

        if self.home_team_id == self.away_team_id:
            raise ValueError("home_team_id and away_team_id must be different")
        return self


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
    lifecycle_state: MatchLifecycleState = MatchLifecycleState.SCHEDULED
    scoring_authority: ScoringAuthority = ScoringAuthority.LEGACY_AGGREGATE
    result_code: MatchResultCode = MatchResultCode.PENDING
    result_details: dict[str, Any] = Field(default_factory=dict)
    configured_at: datetime | None = None
    participants: MatchParticipantResponse
    created_at: datetime
    updated_at: datetime
    version_number: int = Field(ge=1)

    @classmethod
    def from_match(cls, match: "Match") -> "MatchResponse":
        """Expand persisted participant columns into the public union shape.

        ``MatchService`` loads both Team relationships before this adapter is
        called, keeping serialization explicit and avoiding lazy-load queries in
        the HTTP response boundary.
        """

        if match.participant_type == MatchParticipantType.EXTERNAL:
            academy_team = match.home_team or match.away_team
            if academy_team is None or match.external_opponent_name is None:
                raise ValueError(
                    "External Match is missing a participant Team or opponent"
                )
            participants: MatchParticipantResponse = ExternalMatchParticipantResponse(
                kind=MatchParticipantType.EXTERNAL,
                academy_team=MatchTeamReference.model_validate(academy_team),
                opponent_name=match.external_opponent_name,
                academy_side="home" if match.home_team is not None else "away",
            )
        elif match.participant_type == MatchParticipantType.INTERNAL:
            if match.home_team is None or match.away_team is None:
                raise ValueError("Internal Match is missing a participant Team")
            participants = InternalMatchParticipantResponse(
                kind=MatchParticipantType.INTERNAL,
                home_team=MatchTeamReference.model_validate(match.home_team),
                away_team=MatchTeamReference.model_validate(match.away_team),
            )
        else:
            raise ValueError("Match has an unsupported participant type")

        return cls(
            id=match.id,
            match_date=match.match_date,
            format=match.format,
            venue=match.venue,
            result=match.result,
            lifecycle_state=(
                match.lifecycle_state
                if match.lifecycle_state is not None
                else MatchLifecycleState.SCHEDULED
            ),
            scoring_authority=(
                match.scoring_authority
                if match.scoring_authority is not None
                else ScoringAuthority.LEGACY_AGGREGATE
            ),
            result_code=(
                match.result_code
                if match.result_code is not None
                else MatchResultCode.PENDING
            ),
            result_details=match.result_details or {},
            configured_at=match.configured_at,
            participants=participants,
            created_at=match.created_at,
            updated_at=match.updated_at,
            version_number=match.version_number,
        )


MatchParticipantsRequest = MatchParticipantRequest
MatchParticipantsResponse = MatchParticipantResponse
