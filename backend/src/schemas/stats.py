"""Pydantic response schemas for aggregate career statistics."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from src.enums import MatchFormat


class BattingStatsResponse(BaseModel):
    """Lifetime batting totals for one match format."""

    model_config = ConfigDict(from_attributes=True)

    format: MatchFormat
    matches: int = Field(ge=0)
    innings: int = Field(ge=0)
    not_outs: int = Field(ge=0)
    runs: int = Field(ge=0)
    balls_faced: int = Field(ge=0)
    high_score: int = Field(ge=0)
    hundreds: int = Field(ge=0)
    fifties: int = Field(ge=0)
    ducks: int = Field(ge=0)
    fours: int = Field(ge=0)
    sixes: int = Field(ge=0)


class BowlingStatsResponse(BaseModel):
    """Lifetime bowling totals for one match format."""

    model_config = ConfigDict(from_attributes=True)

    format: MatchFormat
    matches: int = Field(ge=0)
    innings: int = Field(ge=0)
    overs_bowled: Decimal = Field(ge=0)
    runs_conceded: int = Field(ge=0)
    wickets: int = Field(ge=0)
    best_bowled: str | None
    maidens: int = Field(ge=0)
    four_wicket_hauls: int = Field(ge=0)
    five_wicket_hauls: int = Field(ge=0)
    wides: int = Field(ge=0)
    catches: int = Field(ge=0)

    @field_serializer("overs_bowled", when_used="json")
    def serialize_overs_bowled(self, value: Decimal) -> float:
        """Emit numeric JSON that matches the public API contract."""

        return float(value)
