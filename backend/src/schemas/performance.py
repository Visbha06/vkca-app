"""Pydantic schemas for atomic match performance submissions."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.enums import DismissalType
from src.schemas.base import BaseRequestSchema


class BattingPerformance(BaseRequestSchema):
    """Optional batting metrics for one player in one match."""

    runs_scored: int = Field(default=0, ge=0)
    balls_faced: int = Field(default=0, ge=0)
    dismissal: DismissalType = DismissalType.NOT_OUT
    fours: int = Field(default=0, ge=0)
    sixes: int = Field(default=0, ge=0)
    notes: str | None = None


class BowlingPerformance(BaseRequestSchema):
    """Optional bowling metrics for one player in one match."""

    overs_bowled: Decimal = Field(
        default=Decimal("0.0"), ge=0, max_digits=5, decimal_places=1
    )
    maidens: int = Field(default=0, ge=0)
    runs_conceded: int = Field(default=0, ge=0)
    wickets_taken: int = Field(default=0, ge=0)
    wides: int = Field(default=0, ge=0)
    notes: str | None = None


class FieldingPerformance(BaseRequestSchema):
    """Optional fielding metrics for one player in one match."""

    catches: int = Field(default=0, ge=0)
    stumpings: int = Field(default=0, ge=0)
    run_outs: int = Field(default=0, ge=0)
    dropped_catches: int = Field(default=0, ge=0)
    notes: str | None = None


class PlayerPerformance(BaseRequestSchema):
    """All supplied performance groups for one player."""

    player_id: UUID
    batting: BattingPerformance | None = None
    bowling: BowlingPerformance | None = None
    fielding: FieldingPerformance | None = None

    @model_validator(mode="after")
    def require_at_least_one_performance(self) -> "PlayerPerformance":
        """Reject player entries that contain no metrics."""

        if self.batting is None and self.bowling is None and self.fielding is None:
            raise ValueError("Each player must include at least one performance group.")
        return self


class BatchPerformanceRequest(BaseRequestSchema):
    """Non-empty atomic batch of player performances."""

    performances: list[PlayerPerformance] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_players(self) -> "BatchPerformanceRequest":
        """Prevent duplicate unique-key writes within one match batch."""

        player_ids = [performance.player_id for performance in self.performances]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("Batch contains a duplicate player_id.")
        return self


class BatchPerformanceResponse(BaseModel):
    """Counts produced by a successful atomic batch submission."""

    match_id: UUID
    performances_created: int = Field(ge=0)
    batting_records: int = Field(ge=0)
    bowling_records: int = Field(ge=0)
    fielding_records: int = Field(ge=0)
    players_stats_updated: int = Field(ge=0)
