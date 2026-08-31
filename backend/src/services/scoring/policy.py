"""Deterministic version-one Match-format capability resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.enums import (
    CORE_SCORING_DISMISSAL_TYPES,
    CORE_SCORING_TRANSITION_TYPES,
    FORMAT_CAPABILITY_VERSION,
    ONE_DAY_BOWLER_QUOTA_DIVISOR,
    STANDARD_OVER_LENGTH_LEGAL_BALLS,
    STANDARD_WICKET_LIMIT,
    T20_BOWLER_QUOTA_LEGAL_BALLS,
    T20_LEGAL_BALL_LIMIT,
    ExplicitMatchCompletionBoundary,
    FormatCapabilityProfile,
    InningsCompletionMode,
    InningsTransitionType,
    MatchCompletionMode,
    MatchFormat,
    MatchResultCode,
    MatchSideCode,
    ScoringDismissalType,
    TargetMode,
)
from src.models.scoring.scoring_policy import ScoringPolicy
from src.schemas.scoring import ScoringPolicyConfigurationRequest
from src.services.scoring.errors import ScoringValidationError


@dataclass(frozen=True, slots=True)
class FormatCapability:
    """Fully resolved immutable policy values locked before scoring starts."""

    policy_code: MatchFormat
    capability_profile: FormatCapabilityProfile
    innings_sequence: tuple[MatchSideCode, ...]
    innings_per_side: int
    legal_ball_limit: int | None
    over_length_legal_balls: int
    bowler_quota_legal_balls: int | None
    wicket_limit: int
    consecutive_overs_prohibited: bool
    target_mode: TargetMode
    allowed_dismissal_types: tuple[ScoringDismissalType, ...]
    allowed_transition_types: tuple[InningsTransitionType, ...]
    allowed_innings_completion_modes: tuple[InningsCompletionMode, ...]
    allowed_match_completion_modes: tuple[MatchCompletionMode, ...]
    allowed_result_codes: tuple[MatchResultCode, ...]
    allow_declaration: bool
    allow_draw: bool
    allow_manual_completion: bool
    explicit_match_completion_boundary: ExplicitMatchCompletionBoundary
    policy_version: int = 1
    capability_version: int = FORMAT_CAPABILITY_VERSION

    def policy_columns(self) -> dict[str, object]:
        """Return storage-ready values without leaking mutable enum lists."""

        return {
            "policy_code": self.policy_code,
            "policy_version": self.policy_version,
            "capability_profile": self.capability_profile,
            "capability_version": self.capability_version,
            "innings_sequence": [value.value for value in self.innings_sequence],
            "innings_per_side": self.innings_per_side,
            "legal_ball_limit": self.legal_ball_limit,
            "over_length_legal_balls": self.over_length_legal_balls,
            "bowler_quota_legal_balls": self.bowler_quota_legal_balls,
            "wicket_limit": self.wicket_limit,
            "consecutive_overs_prohibited": self.consecutive_overs_prohibited,
            "target_mode": self.target_mode,
            "allowed_dismissal_types": [
                value.value for value in self.allowed_dismissal_types
            ],
            "allowed_transition_types": [
                value.value for value in self.allowed_transition_types
            ],
            "allowed_innings_completion_modes": [
                value.value for value in self.allowed_innings_completion_modes
            ],
            "allowed_match_completion_modes": [
                value.value for value in self.allowed_match_completion_modes
            ],
            "allowed_result_codes": [
                value.value for value in self.allowed_result_codes
            ],
            "allow_declaration": self.allow_declaration,
            "allow_draw": self.allow_draw,
            "allow_manual_completion": self.allow_manual_completion,
            "explicit_match_completion_boundary": (
                self.explicit_match_completion_boundary
            ),
        }

    def to_model(self, match_id: UUID) -> ScoringPolicy:
        """Create the one locked ORM policy for ``match_id``."""

        return ScoringPolicy(match_id=match_id, **self.policy_columns())


_CORE_DISMISSALS = tuple(
    sorted(CORE_SCORING_DISMISSAL_TYPES, key=lambda value: value.value)
)
_CORE_TRANSITIONS = tuple(
    sorted(CORE_SCORING_TRANSITION_TYPES, key=lambda value: value.value)
)
_FIXED_INNINGS_MODES = (
    InningsCompletionMode.ALL_OUT,
    InningsCompletionMode.LEGAL_BALL_LIMIT,
    InningsCompletionMode.TARGET_REACHED,
)
_FIXED_MATCH_MODES = (
    MatchCompletionMode.DERIVED_RESULT,
    MatchCompletionMode.ABANDONMENT,
)
_FIXED_RESULTS = (
    MatchResultCode.PENDING,
    MatchResultCode.WIN_BY_RUNS,
    MatchResultCode.WIN_BY_WICKETS,
    MatchResultCode.TIE,
    MatchResultCode.NO_RESULT,
)


def _require_unique(values: tuple[object, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ScoringValidationError(f"{field_name} must not contain duplicates.")


def resolve_format_capability(
    request: ScoringPolicyConfigurationRequest | dict[str, Any],
) -> FormatCapability:
    """Resolve one strict request into the only policy later commands may use."""

    if not isinstance(request, ScoringPolicyConfigurationRequest):
        request = ScoringPolicyConfigurationRequest.model_validate(request)

    profile = request.capability_profile
    if profile is FormatCapabilityProfile.T20:
        return FormatCapability(
            policy_code=request.policy_code,
            capability_profile=profile,
            innings_sequence=tuple(request.innings_sequence),
            innings_per_side=1,
            legal_ball_limit=T20_LEGAL_BALL_LIMIT,
            over_length_legal_balls=STANDARD_OVER_LENGTH_LEGAL_BALLS,
            bowler_quota_legal_balls=T20_BOWLER_QUOTA_LEGAL_BALLS,
            wicket_limit=STANDARD_WICKET_LIMIT,
            consecutive_overs_prohibited=True,
            target_mode=TargetMode.PRIOR_INNINGS_PLUS_ONE,
            allowed_dismissal_types=_CORE_DISMISSALS,
            allowed_transition_types=_CORE_TRANSITIONS,
            allowed_innings_completion_modes=_FIXED_INNINGS_MODES,
            allowed_match_completion_modes=_FIXED_MATCH_MODES,
            allowed_result_codes=_FIXED_RESULTS,
            allow_declaration=False,
            allow_draw=False,
            allow_manual_completion=False,
            explicit_match_completion_boundary=ExplicitMatchCompletionBoundary.NONE,
        )
    if profile is FormatCapabilityProfile.ONE_DAY:
        if request.legal_ball_limit is None:
            raise ScoringValidationError(
                "one-day legal_ball_limit is required before scoring."
            )
        return FormatCapability(
            policy_code=request.policy_code,
            capability_profile=profile,
            innings_sequence=tuple(request.innings_sequence),
            innings_per_side=1,
            legal_ball_limit=request.legal_ball_limit,
            over_length_legal_balls=STANDARD_OVER_LENGTH_LEGAL_BALLS,
            bowler_quota_legal_balls=(
                request.legal_ball_limit // ONE_DAY_BOWLER_QUOTA_DIVISOR
            ),
            wicket_limit=STANDARD_WICKET_LIMIT,
            consecutive_overs_prohibited=True,
            target_mode=TargetMode.PRIOR_INNINGS_PLUS_ONE,
            allowed_dismissal_types=_CORE_DISMISSALS,
            allowed_transition_types=_CORE_TRANSITIONS,
            allowed_innings_completion_modes=_FIXED_INNINGS_MODES,
            allowed_match_completion_modes=_FIXED_MATCH_MODES,
            allowed_result_codes=_FIXED_RESULTS,
            allow_declaration=False,
            allow_draw=False,
            allow_manual_completion=False,
            explicit_match_completion_boundary=ExplicitMatchCompletionBoundary.NONE,
        )
    if profile is FormatCapabilityProfile.TEST:
        return FormatCapability(
            policy_code=request.policy_code,
            capability_profile=profile,
            innings_sequence=tuple(request.innings_sequence),
            innings_per_side=2,
            legal_ball_limit=None,
            over_length_legal_balls=STANDARD_OVER_LENGTH_LEGAL_BALLS,
            bowler_quota_legal_balls=None,
            wicket_limit=STANDARD_WICKET_LIMIT,
            consecutive_overs_prohibited=True,
            target_mode=TargetMode.NONE,
            allowed_dismissal_types=_CORE_DISMISSALS,
            allowed_transition_types=_CORE_TRANSITIONS,
            allowed_innings_completion_modes=(
                InningsCompletionMode.ALL_OUT,
                InningsCompletionMode.DECLARATION,
            ),
            allowed_match_completion_modes=(
                MatchCompletionMode.DERIVED_RESULT,
                MatchCompletionMode.DRAW,
                MatchCompletionMode.DECLARED,
                MatchCompletionMode.MANUAL,
                MatchCompletionMode.ABANDONMENT,
            ),
            allowed_result_codes=(
                MatchResultCode.PENDING,
                MatchResultCode.WIN_BY_RUNS,
                MatchResultCode.TIE,
                MatchResultCode.DRAW,
                MatchResultCode.DECLARED,
                MatchResultCode.MANUAL,
                MatchResultCode.NO_RESULT,
            ),
            allow_declaration=True,
            allow_draw=True,
            allow_manual_completion=True,
            explicit_match_completion_boundary=(
                ExplicitMatchCompletionBoundary.AFTER_COMPLETED_INNINGS
            ),
        )

    dismissals = tuple(request.allowed_dismissal_types or ())
    transitions = tuple(request.allowed_transition_types or ())
    innings_modes = tuple(request.allowed_innings_completion_modes or ())
    match_modes = tuple(request.allowed_match_completion_modes or ())
    result_codes = tuple(request.allowed_result_codes or ())
    for values, field_name in (
        (dismissals, "allowed_dismissal_types"),
        (transitions, "allowed_transition_types"),
        (innings_modes, "allowed_innings_completion_modes"),
        (match_modes, "allowed_match_completion_modes"),
        (result_codes, "allowed_result_codes"),
    ):
        _require_unique(values, field_name)
    innings_per_side = request.innings_per_side or 1
    sequence_counts = {
        side: request.innings_sequence.count(side) for side in MatchSideCode
    }
    if any(count != innings_per_side for count in sequence_counts.values()):
        raise ScoringValidationError(
            "other innings_sequence must contain each side innings_per_side times."
        )
    if set(innings_modes) != {InningsCompletionMode.MANUAL}:
        raise ScoringValidationError(
            "other allows only manual Innings completion in capability version 1."
        )
    if set(match_modes) != {
        MatchCompletionMode.MANUAL,
        MatchCompletionMode.ABANDONMENT,
    }:
        raise ScoringValidationError(
            "other Match completion modes must be manual and abandonment."
        )
    if set(result_codes) != {
        MatchResultCode.PENDING,
        MatchResultCode.MANUAL,
        MatchResultCode.NO_RESULT,
    }:
        raise ScoringValidationError(
            "other result codes must be pending, manual, and no_result."
        )
    return FormatCapability(
        policy_code=request.policy_code,
        capability_profile=profile,
        innings_sequence=tuple(request.innings_sequence),
        innings_per_side=innings_per_side,
        legal_ball_limit=request.legal_ball_limit,
        over_length_legal_balls=request.over_length_legal_balls or 1,
        bowler_quota_legal_balls=request.bowler_quota_legal_balls,
        wicket_limit=request.wicket_limit or 1,
        consecutive_overs_prohibited=bool(request.consecutive_overs_prohibited),
        target_mode=TargetMode.NONE,
        allowed_dismissal_types=dismissals,
        allowed_transition_types=transitions,
        allowed_innings_completion_modes=innings_modes,
        allowed_match_completion_modes=match_modes,
        allowed_result_codes=result_codes,
        allow_declaration=False,
        allow_draw=False,
        allow_manual_completion=True,
        explicit_match_completion_boundary=(
            request.explicit_match_completion_boundary
            or ExplicitMatchCompletionBoundary.ANY_NONTERMINAL_STATE
        ),
    )


resolve_capability_profile = resolve_format_capability
