"""Pure, capability-driven classification for one observed delivery."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.enums import (
    SCORING_RUN_COMPONENT_MAX,
    SCORING_RUN_TOTAL_MAX,
    DismissedEnd,
    FielderRole,
    ScoringDismissalType,
)
from src.schemas.scoring import DeliveryFactsRequest, WicketRequest
from src.services.scoring.errors import ScoringValidationError


@dataclass(frozen=True, slots=True)
class WicketClassification:
    """Validated scoring effects for the optional wicket observation."""

    dismissal_type: ScoringDismissalType
    dismissed_participant_id: UUID
    dismissed_end: DismissedEnd | None
    counts_as_team_wicket: bool
    credited_to_bowler: bool
    primary_fielder_participant_id: UUID | None


@dataclass(frozen=True, slots=True)
class DeliveryClassification:
    """All derived facts persisted with one immutable delivery revision."""

    total_runs: int
    is_legal: bool
    completed_runs: int
    balls_faced: bool
    bowler_conceded_runs: int
    over_number: int
    ball_in_over: int
    is_four: bool
    is_six: bool
    wicket: WicketClassification | None


def checked_scoring_add(
    *values: int,
    current: int = 0,
    field_name: str = "scoring total",
) -> int:
    """Add non-negative run values without exceeding the persisted integer bound."""

    if current < 0 or current > SCORING_RUN_TOTAL_MAX:
        raise ScoringValidationError(f"{field_name} is outside the scoring range.")
    total = current
    for value in values:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ScoringValidationError(f"{field_name} components must be integers.")
        if value < 0 or value > SCORING_RUN_COMPONENT_MAX:
            raise ScoringValidationError(
                f"{field_name} component is outside the scoring range."
            )
        if value > SCORING_RUN_TOTAL_MAX - total:
            raise ScoringValidationError(f"{field_name} exceeds SCORING_RUN_TOTAL_MAX.")
        total += value
    return total


def classify_wicket(
    wicket: WicketRequest | None,
    *,
    striker_participant_id: UUID,
    non_striker_participant_id: UUID,
    bowler_participant_id: UUID,
    fielding_participant_ids: frozenset[UUID] | set[UUID],
    allowed_dismissal_types: frozenset[ScoringDismissalType]
    | set[ScoringDismissalType],
) -> WicketClassification | None:
    """Validate one wicket against active identities and its locked capability."""

    if wicket is None:
        return None
    if wicket.dismissal_type not in allowed_dismissal_types:
        raise ScoringValidationError(
            "Dismissal type is not enabled by the locked scoring capability."
        )
    active_batters = {striker_participant_id, non_striker_participant_id}
    if wicket.dismissed_participant_id not in active_batters:
        raise ScoringValidationError(
            "The dismissed participant must be an active batter."
        )
    striker_only = {
        ScoringDismissalType.BOWLED,
        ScoringDismissalType.CAUGHT,
        ScoringDismissalType.CAUGHT_AND_BOWLED,
        ScoringDismissalType.LBW,
        ScoringDismissalType.STUMPED,
        ScoringDismissalType.HIT_WICKET,
    }
    if (
        wicket.dismissal_type in striker_only
        and wicket.dismissed_participant_id != striker_participant_id
    ):
        raise ScoringValidationError(
            "This dismissal type can dismiss only the active striker."
        )
    if any(
        item.participant_id not in fielding_participant_ids for item in wicket.fielders
    ):
        raise ScoringValidationError(
            "Every fielder must be a fixed participant on the fielding side."
        )
    if (
        wicket.dismissal_type is ScoringDismissalType.CAUGHT_AND_BOWLED
        and wicket.fielders[0].participant_id != bowler_participant_id
    ):
        raise ScoringValidationError(
            "The caught-and-bowled fielder must be the current bowler."
        )
    if wicket.dismissal_type is ScoringDismissalType.STUMPED and (
        wicket.fielders[0].role is not FielderRole.KEEPER
    ):
        raise ScoringValidationError("A stumping requires one keeper.")

    credited = wicket.dismissal_type not in {
        ScoringDismissalType.RUN_OUT,
        ScoringDismissalType.RETIRED_OUT,
    }
    return WicketClassification(
        dismissal_type=wicket.dismissal_type,
        dismissed_participant_id=wicket.dismissed_participant_id,
        dismissed_end=wicket.dismissed_end,
        counts_as_team_wicket=True,
        credited_to_bowler=credited,
        primary_fielder_participant_id=(
            wicket.fielders[0].participant_id if wicket.fielders else None
        ),
    )


def classify_delivery(
    facts: DeliveryFactsRequest,
    *,
    legal_balls_before: int,
    over_length_legal_balls: int,
    innings_total_before: int = 0,
    match_total_before: int = 0,
    fielding_participant_ids: frozenset[UUID] | set[UUID] = frozenset(),
    allowed_dismissal_types: frozenset[ScoringDismissalType]
    | set[ScoringDismissalType] = frozenset(ScoringDismissalType),
) -> DeliveryClassification:
    """Classify observed facts once for storage, replay, and every projection."""

    if legal_balls_before < 0:
        raise ScoringValidationError("legal_balls_before cannot be negative.")
    if over_length_legal_balls < 1:
        raise ScoringValidationError("over length must be positive.")

    extras = facts.extras
    total_runs = checked_scoring_add(
        facts.runs_off_bat,
        extras.wide_runs,
        extras.no_ball_penalty_runs,
        extras.bye_runs,
        extras.leg_bye_runs,
        extras.penalty_runs,
        field_name="delivery total",
    )
    checked_scoring_add(
        total_runs,
        current=innings_total_before,
        field_name="innings aggregate",
    )
    checked_scoring_add(
        total_runs,
        current=match_total_before,
        field_name="Match aggregate",
    )

    is_legal = extras.wide_runs == 0 and extras.no_ball_penalty_runs == 0
    legal_ball_number = legal_balls_before + (1 if is_legal else 0)
    over_number = legal_balls_before // over_length_legal_balls
    ball_in_over = (
        legal_ball_number - over_number * over_length_legal_balls
        if is_legal
        else legal_balls_before % over_length_legal_balls + 1
    )
    completed_runs = checked_scoring_add(
        facts.runs_off_bat,
        extras.bye_runs,
        extras.leg_bye_runs,
        max(0, extras.wide_runs - 1),
        field_name="completed runs",
    )
    bowler_conceded_runs = checked_scoring_add(
        facts.runs_off_bat,
        extras.wide_runs,
        extras.no_ball_penalty_runs,
        field_name="bowler-conceded runs",
    )
    wicket = classify_wicket(
        facts.wicket,
        striker_participant_id=facts.striker_participant_id,
        non_striker_participant_id=facts.non_striker_participant_id,
        bowler_participant_id=facts.bowler_participant_id,
        fielding_participant_ids=fielding_participant_ids,
        allowed_dismissal_types=allowed_dismissal_types,
    )
    boundary_eligible = not (extras.wide_runs or extras.bye_runs or extras.leg_bye_runs)
    return DeliveryClassification(
        total_runs=total_runs,
        is_legal=is_legal,
        completed_runs=completed_runs,
        balls_faced=is_legal,
        bowler_conceded_runs=bowler_conceded_runs,
        over_number=over_number,
        ball_in_over=ball_in_over,
        is_four=boundary_eligible and facts.runs_off_bat == 4,
        is_six=boundary_eligible and facts.runs_off_bat == 6,
        wicket=wicket,
    )


classify_delivery_facts = classify_delivery


__all__ = [
    "DeliveryClassification",
    "WicketClassification",
    "checked_scoring_add",
    "classify_delivery",
    "classify_delivery_facts",
    "classify_wicket",
]
