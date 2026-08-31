"""Strict request and typed response boundaries for Match scoring."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.enums import (
    SCORING_RUN_COMPONENT_MAX,
    SCORING_RUN_TOTAL_MAX,
    BlockingReasonCode,
    BlockingStateKind,
    DeliveryRevisionState,
    DismissedEnd,
    ExplicitMatchCompletionBoundary,
    FielderRole,
    FormatCapabilityProfile,
    InningsCompletionMode,
    InningsLifecycleState,
    InningsTransitionType,
    MatchCompletionMode,
    MatchFormat,
    MatchLifecycleState,
    MatchParticipantKind,
    MatchResultCode,
    MatchSideCode,
    MatchSideKind,
    ParticipationState,
    PerformanceProvenance,
    ScoringAuthority,
    ScoringDismissalType,
    TargetMode,
)

MAX_SCORING_HISTORY_LIMIT = 200
MAX_SCORING_REASON_LENGTH = 500


class StrictScoringRequest(BaseModel):
    """Forbid unknown and server-derived fields at every scoring input seam."""

    model_config = ConfigDict(extra="forbid")


class ScoringResponse(BaseModel):
    """Shared attribute-aware response configuration."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class BlockingStateResponse(ScoringResponse):
    """Canonical read-only progression blocker."""

    kind: BlockingStateKind
    is_blocked: bool
    reason_code: BlockingReasonCode | None

    @model_validator(mode="after")
    def validate_reason(self) -> Self:
        """Keep kind, blocked state, and bounded reason deterministic."""

        valid_reasons: dict[BlockingStateKind, set[BlockingReasonCode]] = {
            BlockingStateKind.INNINGS_NOT_STARTED: {
                BlockingReasonCode.INNINGS_NOT_STARTED
            },
            BlockingStateKind.AWAITING_NEXT_BATTER: {
                BlockingReasonCode.NEXT_BATTER_REQUIRED
            },
            BlockingStateKind.AWAITING_NEXT_BOWLER: {
                BlockingReasonCode.NEXT_BOWLER_REQUIRED,
                BlockingReasonCode.NO_ELIGIBLE_BOWLER,
            },
            BlockingStateKind.RECONCILIATION_REQUIRED: {
                BlockingReasonCode.INCOMPATIBLE_REPLAY
            },
            BlockingStateKind.INNINGS_COMPLETED: {BlockingReasonCode.INNINGS_COMPLETED},
            BlockingStateKind.MATCH_COMPLETED: {BlockingReasonCode.MATCH_COMPLETED},
            BlockingStateKind.MATCH_ABANDONED: {BlockingReasonCode.MATCH_ABANDONED},
        }
        if self.kind is BlockingStateKind.NONE:
            if self.is_blocked or self.reason_code is not None:
                raise ValueError(
                    "none blocking state must be unblocked without a reason"
                )
            return self
        if not self.is_blocked:
            raise ValueError("every non-none blocking state must be blocked")
        if self.reason_code not in valid_reasons[self.kind]:
            raise ValueError("reason_code does not match blocking-state kind")
        return self


class ScoringPolicyConfigurationRequest(StrictScoringRequest):
    """Capability selection plus only the policy values a profile permits."""

    policy_code: MatchFormat
    capability_profile: FormatCapabilityProfile
    capability_version: int = Field(default=1, ge=1)
    innings_sequence: list[MatchSideCode] = Field(min_length=2, max_length=32)
    innings_per_side: int | None = Field(default=None, ge=1)
    legal_ball_limit: int | None = Field(default=None, ge=1)
    over_length_legal_balls: int | None = Field(default=None, ge=1)
    bowler_quota_legal_balls: int | None = Field(default=None, ge=1)
    wicket_limit: int | None = Field(default=None, ge=1)
    consecutive_overs_prohibited: bool | None = None
    target_mode: TargetMode | None = None
    allow_declaration: bool | None = None
    allow_draw: bool | None = None
    allow_manual_completion: bool | None = None
    explicit_match_completion_boundary: ExplicitMatchCompletionBoundary | None = None
    allowed_dismissal_types: list[ScoringDismissalType] | None = None
    allowed_transition_types: list[InningsTransitionType] | None = None
    allowed_innings_completion_modes: list[InningsCompletionMode] | None = None
    allowed_match_completion_modes: list[MatchCompletionMode] | None = None
    allowed_result_codes: list[MatchResultCode] | None = None

    @model_validator(mode="after")
    def validate_capability_contract(self) -> Self:
        """Reject aliases, derived inputs, and profile contradictions early."""

        if self.policy_code.value != self.capability_profile.value:
            raise ValueError("policy_code must equal capability_profile")
        if self.capability_version != 1:
            raise ValueError("unsupported capability_version")

        sequence = self.innings_sequence
        first, second = sequence[0], sequence[1]
        if first is second:
            raise ValueError("innings_sequence must contain both configured sides")

        derived_set_fields = {
            "allowed_dismissal_types",
            "allowed_transition_types",
            "allowed_innings_completion_modes",
            "allowed_match_completion_modes",
            "allowed_result_codes",
        }
        if self.capability_profile is not FormatCapabilityProfile.OTHER:
            supplied_derived = derived_set_fields.intersection(self.model_fields_set)
            if supplied_derived:
                raise ValueError(
                    "capability sets are server-derived for canonical profiles"
                )

        expected_common: dict[str, object] = {
            "over_length_legal_balls": 6,
            "wicket_limit": 10,
            "consecutive_overs_prohibited": True,
        }
        for field_name, expected in expected_common.items():
            supplied = getattr(self, field_name)
            if (
                self.capability_profile is not FormatCapabilityProfile.OTHER
                and supplied is not None
                and supplied != expected
            ):
                raise ValueError(f"{field_name} contradicts the capability")

        if self.capability_profile is FormatCapabilityProfile.T20:
            self._validate_two_innings_sequence()
            self._require_if_supplied("innings_per_side", 1)
            self._require_if_supplied("legal_ball_limit", 120)
            self._require_if_supplied("bowler_quota_legal_balls", 24)
            self._require_if_supplied("target_mode", TargetMode.PRIOR_INNINGS_PLUS_ONE)
            self._require_if_supplied("allow_declaration", False)
            self._require_if_supplied("allow_draw", False)
            self._require_if_supplied("allow_manual_completion", False)
            self._require_if_supplied(
                "explicit_match_completion_boundary",
                ExplicitMatchCompletionBoundary.NONE,
            )
        elif self.capability_profile is FormatCapabilityProfile.ONE_DAY:
            self._validate_two_innings_sequence()
            self._require_if_supplied("innings_per_side", 1)
            if self.legal_ball_limit is None or self.legal_ball_limit % 30 != 0:
                raise ValueError(
                    "one-day legal_ball_limit must be a positive multiple of 30"
                )
            if "bowler_quota_legal_balls" in self.model_fields_set:
                raise ValueError("one-day bowler quota is server-derived")
            self._require_if_supplied("target_mode", TargetMode.PRIOR_INNINGS_PLUS_ONE)
            self._require_if_supplied("allow_declaration", False)
            self._require_if_supplied("allow_draw", False)
            self._require_if_supplied("allow_manual_completion", False)
            self._require_if_supplied(
                "explicit_match_completion_boundary",
                ExplicitMatchCompletionBoundary.NONE,
            )
        elif self.capability_profile is FormatCapabilityProfile.TEST:
            if len(sequence) != 4 or sequence != [first, second, first, second]:
                raise ValueError("test innings_sequence must alternate A, B, A, B")
            self._require_if_supplied("innings_per_side", 2)
            if self.legal_ball_limit is not None:
                raise ValueError("test legal_ball_limit must be null")
            if self.bowler_quota_legal_balls is not None:
                raise ValueError("test bowler quota must be null")
            self._require_if_supplied("target_mode", TargetMode.NONE)
            self._require_if_supplied("allow_declaration", True)
            self._require_if_supplied("allow_draw", True)
            self._require_if_supplied("allow_manual_completion", True)
            self._require_if_supplied(
                "explicit_match_completion_boundary",
                ExplicitMatchCompletionBoundary.AFTER_COMPLETED_INNINGS,
            )
        else:
            required_fields = {
                "innings_per_side",
                "legal_ball_limit",
                "over_length_legal_balls",
                "bowler_quota_legal_balls",
                "wicket_limit",
                "consecutive_overs_prohibited",
                "target_mode",
                "allow_declaration",
                "allow_draw",
                "allow_manual_completion",
                "explicit_match_completion_boundary",
                *derived_set_fields,
            }
            missing = required_fields.difference(self.model_fields_set)
            if missing:
                raise ValueError(
                    "other capability requires every explicit policy field: "
                    + ", ".join(sorted(missing))
                )
            if self.target_mode is not TargetMode.NONE:
                raise ValueError("other target_mode must be none")
            if self.allow_declaration or self.allow_draw:
                raise ValueError("other does not enable declaration or draw")
            if self.allow_manual_completion is not True:
                raise ValueError("other must enable manual completion")
            if self.explicit_match_completion_boundary not in {
                ExplicitMatchCompletionBoundary.AFTER_COMPLETED_INNINGS,
                ExplicitMatchCompletionBoundary.ANY_NONTERMINAL_STATE,
            }:
                raise ValueError("other requires an explicit completion boundary")
            if not self.allowed_dismissal_types:
                raise ValueError("other requires at least one dismissal type")
            if not self.allowed_innings_completion_modes:
                raise ValueError("other requires an innings completion mode")
            if (
                InningsCompletionMode.MANUAL
                not in self.allowed_innings_completion_modes
            ):
                raise ValueError("other must permit manual Innings completion")
            if not self.allowed_match_completion_modes or not self.allowed_result_codes:
                raise ValueError("other requires Match completion and result codes")

        return self

    def _validate_two_innings_sequence(self) -> None:
        if len(self.innings_sequence) != 2:
            raise ValueError("fixed-over innings_sequence must contain two sides")

    def _require_if_supplied(self, field_name: str, expected: object) -> None:
        if (
            field_name in self.model_fields_set
            and getattr(self, field_name) != expected
        ):
            raise ValueError(f"{field_name} contradicts the capability")

    @property
    def derived_bowler_quota_legal_balls(self) -> int | None:
        """Expose the one-day derived quota without accepting it from clients."""

        if (
            self.capability_profile is FormatCapabilityProfile.ONE_DAY
            and self.legal_ball_limit is not None
        ):
            return self.legal_ball_limit // 5
        return self.bowler_quota_legal_balls


class MatchSideConfigurationRequest(StrictScoringRequest):
    """One academy or external side supplied during atomic configuration."""

    side_code: MatchSideCode
    side_kind: MatchSideKind
    team_id: UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.side_kind is MatchSideKind.ACADEMY:
            if self.team_id is None:
                raise ValueError("academy side requires team_id")
            if self.display_name is not None:
                raise ValueError("academy display name is server-derived")
        else:
            if self.team_id is not None:
                raise ValueError("external side cannot reference team_id")
            if self.display_name is None or not self.display_name.strip():
                raise ValueError("external side requires display_name")
            self.display_name = self.display_name.strip()
        return self


class MatchParticipantConfigurationRequest(StrictScoringRequest):
    """Minimal fixed participant identity; account fields are not accepted."""

    side_code: MatchSideCode
    participant_kind: MatchParticipantKind
    player_id: UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    batting_order_position: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.participant_kind is MatchParticipantKind.INTERNAL:
            if self.player_id is None:
                raise ValueError("internal participant requires player_id")
            if self.display_name is not None:
                raise ValueError("internal display name is server-derived")
        else:
            if self.player_id is not None:
                raise ValueError("external participant cannot reference player_id")
            if self.display_name is None or not self.display_name.strip():
                raise ValueError("external participant requires display_name")
            self.display_name = self.display_name.strip()
        return self


class MatchConfigurationRequest(StrictScoringRequest):
    """Atomic fixed-side, participant, and capability configuration command."""

    match_version_number: int = Field(ge=1)
    format: MatchFormat
    policy: ScoringPolicyConfigurationRequest
    sides: list[MatchSideConfigurationRequest] = Field(min_length=2, max_length=2)
    participants: list[MatchParticipantConfigurationRequest] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if self.format is not self.policy.policy_code:
            raise ValueError("format must equal policy_code")
        side_by_code = {side.side_code: side for side in self.sides}
        if set(side_by_code) != {MatchSideCode.HOME, MatchSideCode.AWAY}:
            raise ValueError("configuration requires one home and one away side")
        if len(side_by_code) != len(self.sides):
            raise ValueError("side_code values must be unique")
        team_ids = [side.team_id for side in self.sides if side.team_id is not None]
        if len(team_ids) != len(set(team_ids)):
            raise ValueError("academy teams must be distinct")

        seen_positions: set[tuple[MatchSideCode, int]] = set()
        seen_players: set[UUID] = set()
        participant_counts = {code: 0 for code in side_by_code}
        for participant in self.participants:
            side = side_by_code.get(participant.side_code)
            if side is None:
                raise ValueError("participant references an unconfigured side")
            if (
                side.side_kind is MatchSideKind.ACADEMY
                and participant.participant_kind is not MatchParticipantKind.INTERNAL
            ) or (
                side.side_kind is MatchSideKind.EXTERNAL
                and participant.participant_kind is not MatchParticipantKind.EXTERNAL
            ):
                raise ValueError("participant identity kind contradicts its side")
            order_key = (
                participant.side_code,
                participant.batting_order_position,
            )
            if order_key in seen_positions:
                raise ValueError("batting-order positions must be unique within a side")
            seen_positions.add(order_key)
            if participant.player_id is not None:
                if participant.player_id in seen_players:
                    raise ValueError("one academy Player cannot represent both sides")
                seen_players.add(participant.player_id)
            participant_counts[participant.side_code] += 1
        if any(count == 0 for count in participant_counts.values()):
            raise ValueError("each side requires at least one participant")
        if any(code not in side_by_code for code in self.policy.innings_sequence):
            raise ValueError("innings_sequence references an unconfigured side")
        return self


class DeliveryExtrasRequest(StrictScoringRequest):
    """Observed extras quantities with exact persistence bounds."""

    wide_runs: int = Field(default=0, ge=0, le=SCORING_RUN_COMPONENT_MAX)
    no_ball_penalty_runs: int = Field(default=0, ge=0, le=1)
    bye_runs: int = Field(default=0, ge=0, le=SCORING_RUN_COMPONENT_MAX)
    leg_bye_runs: int = Field(default=0, ge=0, le=SCORING_RUN_COMPONENT_MAX)
    penalty_runs: int = Field(default=0, ge=0, le=SCORING_RUN_COMPONENT_MAX)

    @model_validator(mode="after")
    def validate_combinations(self) -> Self:
        if self.wide_runs and self.no_ball_penalty_runs:
            raise ValueError("wide and no-ball extras cannot coexist")
        if self.bye_runs and self.leg_bye_runs:
            raise ValueError("bye and leg-bye extras cannot coexist")
        return self


class DeliveryFielderRequest(StrictScoringRequest):
    """One canonical ordered fielder item."""

    participant_id: UUID
    role: FielderRole


class WicketRequest(StrictScoringRequest):
    """The single optional wicket shape accepted for one delivery."""

    dismissal_type: ScoringDismissalType
    dismissed_participant_id: UUID
    dismissed_end: DismissedEnd | None = None
    fielders: list[DeliveryFielderRequest] = Field(default_factory=list, max_length=12)
    notes: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_fielder_cardinality(self) -> Self:
        roles = [fielder.role for fielder in self.fielders]
        if len(
            {(fielder.participant_id, fielder.role) for fielder in self.fielders}
        ) != len(self.fielders):
            raise ValueError("duplicate fielder associations are not allowed")

        no_fielder = {
            ScoringDismissalType.BOWLED,
            ScoringDismissalType.LBW,
            ScoringDismissalType.HIT_WICKET,
            ScoringDismissalType.RETIRED_OUT,
        }
        required_single = {
            ScoringDismissalType.CAUGHT: FielderRole.CATCHER,
            ScoringDismissalType.CAUGHT_AND_BOWLED: FielderRole.BOWLER,
            ScoringDismissalType.STUMPED: FielderRole.KEEPER,
        }
        if self.dismissal_type in no_fielder and self.fielders:
            raise ValueError("dismissal type does not permit fielders")
        if self.dismissal_type in required_single and roles != [
            required_single[self.dismissal_type]
        ]:
            raise ValueError("dismissal type requires one fielder with its exact role")
        if self.dismissal_type is ScoringDismissalType.RUN_OUT:
            if self.dismissed_end is None:
                raise ValueError("run_out requires dismissed_end")
            allowed = {
                FielderRole.THROWER,
                FielderRole.KEEPER,
                FielderRole.ASSISTER,
                FielderRole.OTHER,
            }
            if not roles or any(role not in allowed for role in roles):
                raise ValueError("run_out requires one or more valid ordered fielders")
        elif self.dismissed_end is not None:
            raise ValueError("dismissed_end is accepted only for run_out")
        return self


class DeliveryFactsRequest(StrictScoringRequest):
    """Observed facts shared by append and immutable correction commands."""

    striker_participant_id: UUID
    non_striker_participant_id: UUID
    bowler_participant_id: UUID
    runs_off_bat: int = Field(default=0, ge=0, le=SCORING_RUN_COMPONENT_MAX)
    extras: DeliveryExtrasRequest = Field(default_factory=DeliveryExtrasRequest)
    wicket: WicketRequest | None = None

    @model_validator(mode="after")
    def validate_observed_facts(self) -> Self:
        if self.striker_participant_id == self.non_striker_participant_id:
            raise ValueError("striker and non-striker must be different")
        if self.extras.wide_runs and self.runs_off_bat:
            raise ValueError("wide deliveries cannot include runs_off_bat")
        total = self.runs_off_bat + sum(
            (
                self.extras.wide_runs,
                self.extras.no_ball_penalty_runs,
                self.extras.bye_runs,
                self.extras.leg_bye_runs,
                self.extras.penalty_runs,
            )
        )
        if total > SCORING_RUN_TOTAL_MAX:
            raise ValueError("delivery total exceeds SCORING_RUN_TOTAL_MAX")
        if (
            self.wicket is not None
            and self.wicket.dismissal_type is ScoringDismissalType.CAUGHT_AND_BOWLED
            and self.wicket.fielders[0].participant_id != self.bowler_participant_id
        ):
            raise ValueError("caught_and_bowled fielder must be the current bowler")
        return self


class AppendDeliveryRequest(DeliveryFactsRequest):
    """Versioned append of one stable attempted delivery."""

    innings_version_number: int = Field(ge=1)
    attempted_sequence: int = Field(ge=1)


class StartInningsRequest(StrictScoringRequest):
    """Versioned explicit opening selections for a new Innings."""

    match_version_number: int = Field(ge=1)
    innings_number: int = Field(ge=1)
    opening_striker_participant_id: UUID
    opening_non_striker_participant_id: UUID
    opening_bowler_participant_id: UUID

    @model_validator(mode="after")
    def validate_openers(self) -> Self:
        if (
            self.opening_striker_participant_id
            == self.opening_non_striker_participant_id
        ):
            raise ValueError("opening batters must be different")
        return self


class SelectNextBatterRequest(StrictScoringRequest):
    innings_version_number: int = Field(ge=1)
    batter_participant_id: UUID
    replacing_participant_id: UUID
    reason: str = Field(min_length=1, max_length=MAX_SCORING_REASON_LENGTH)


class SelectNextBowlerRequest(StrictScoringRequest):
    innings_version_number: int = Field(ge=1)
    bowler_participant_id: UUID
    override_reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_SCORING_REASON_LENGTH,
    )


class RetireHurtRequest(StrictScoringRequest):
    innings_version_number: int = Field(ge=1)
    participant_id: UUID
    reason: str = Field(min_length=1, max_length=MAX_SCORING_REASON_LENGTH)


class RetiredHurtReturnRequest(RetireHurtRequest):
    """Explicitly restore one retired-hurt participant."""


class DeliveryReplacementRequest(DeliveryFactsRequest):
    """Replacement observed facts for an immutable correction revision."""


class DeliveryCorrectionRequest(StrictScoringRequest):
    innings_version_number: int = Field(ge=1)
    match_version_number: int = Field(ge=1)
    expected_revision_number: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=MAX_SCORING_REASON_LENGTH)
    replacement: DeliveryReplacementRequest


class InningsCompletionRequest(StrictScoringRequest):
    innings_version_number: int = Field(ge=1)
    completion_kind: InningsCompletionMode
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_SCORING_REASON_LENGTH,
    )

    @model_validator(mode="after")
    def validate_reason(self) -> Self:
        explicit = {
            InningsCompletionMode.DECLARATION,
            InningsCompletionMode.MANUAL,
        }
        if (self.completion_kind in explicit) != (self.reason is not None):
            raise ValueError("explicit completion requires a reason")
        return self


class MatchCompletionRequest(StrictScoringRequest):
    match_version_number: int = Field(ge=1)
    completion_kind: MatchCompletionMode
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_SCORING_REASON_LENGTH,
    )

    @model_validator(mode="after")
    def validate_reason(self) -> Self:
        if self.completion_kind is MatchCompletionMode.DERIVED_RESULT:
            if self.reason is not None:
                raise ValueError("derived completion does not accept a reason")
        elif self.reason is None:
            raise ValueError("explicit Match completion requires a reason")
        return self


class DeliveryHistoryQuery(StrictScoringRequest):
    after_sequence: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=MAX_SCORING_HISTORY_LIMIT)


class ScoringPolicyResponse(ScoringResponse):
    id: UUID
    policy_code: MatchFormat
    policy_version: int = Field(ge=1)
    capability_profile: FormatCapabilityProfile
    capability_version: int = Field(ge=1)
    innings_sequence: list[MatchSideCode]
    innings_per_side: int = Field(ge=1)
    legal_ball_limit: int | None = Field(default=None, ge=1)
    over_length_legal_balls: int = Field(ge=1)
    bowler_quota_legal_balls: int | None = Field(default=None, ge=1)
    wicket_limit: int = Field(ge=1)
    consecutive_overs_prohibited: bool
    target_mode: TargetMode
    allowed_dismissal_types: list[ScoringDismissalType]
    allowed_transition_types: list[InningsTransitionType]
    allowed_innings_completion_modes: list[InningsCompletionMode]
    allowed_match_completion_modes: list[MatchCompletionMode]
    allowed_result_codes: list[MatchResultCode]
    allow_declaration: bool
    allow_draw: bool
    allow_manual_completion: bool
    explicit_match_completion_boundary: ExplicitMatchCompletionBoundary
    version_number: int = Field(ge=1)


class MatchSideResponse(ScoringResponse):
    id: UUID
    side_code: MatchSideCode
    side_kind: MatchSideKind
    team_id: UUID | None
    display_name_snapshot: str


class MatchParticipantResponse(ScoringResponse):
    id: UUID
    side_id: UUID
    participant_kind: MatchParticipantKind
    player_id: UUID | None
    display_name_snapshot: str
    batting_order_position: int = Field(ge=1)


class MatchConfigurationResponse(ScoringResponse):
    match_id: UUID
    match_version_number: int = Field(ge=1)
    lifecycle_state: MatchLifecycleState
    scoring_authority: ScoringAuthority
    configured_at: datetime
    policy: ScoringPolicyResponse
    sides: list[MatchSideResponse] = Field(min_length=2, max_length=2)
    participants: list[MatchParticipantResponse]
    blocking_state: BlockingStateResponse


class DeliveryFielderResponse(ScoringResponse):
    participant_id: UUID
    ordinal: int = Field(ge=1)
    role: FielderRole


class WicketResponse(ScoringResponse):
    dismissal_type: ScoringDismissalType
    dismissed_participant_id: UUID
    dismissed_end: DismissedEnd | None
    counts_as_team_wicket: bool
    credited_to_bowler: bool
    fielders: list[DeliveryFielderResponse]
    primary_fielder_participant_id: UUID | None
    notes: str | None


class DeliveryExtrasResponse(ScoringResponse):
    wide_runs: int = Field(ge=0, le=SCORING_RUN_COMPONENT_MAX)
    no_ball_penalty_runs: int = Field(ge=0, le=1)
    bye_runs: int = Field(ge=0, le=SCORING_RUN_COMPONENT_MAX)
    leg_bye_runs: int = Field(ge=0, le=SCORING_RUN_COMPONENT_MAX)
    penalty_runs: int = Field(ge=0, le=SCORING_RUN_COMPONENT_MAX)


class DeliveryRevisionResponse(ScoringResponse):
    id: UUID
    revision_number: int = Field(ge=1)
    revision_state: DeliveryRevisionState
    striker_participant_id: UUID
    non_striker_participant_id: UUID
    bowler_participant_id: UUID
    runs_off_bat: int = Field(ge=0, le=SCORING_RUN_COMPONENT_MAX)
    extras: DeliveryExtrasResponse
    total_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    is_legal: bool
    completed_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    balls_faced: bool
    bowler_conceded_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    over_number: int = Field(ge=0)
    ball_in_over: int = Field(ge=1)
    wicket: WicketResponse | None
    replacement_reason: str | None
    supersedes_revision_id: UUID | None
    recorded_by_user_id: UUID
    recorded_at: datetime


class DeliveryResponse(ScoringResponse):
    id: UUID
    innings_id: UUID
    attempted_sequence: int = Field(ge=1)
    active_revision: DeliveryRevisionResponse


class InningsOverResponse(ScoringResponse):
    over_number: int = Field(ge=0)
    bowler_participant_id: UUID
    legal_ball_count: int = Field(ge=0)
    total_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    runs_conceded: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    wickets: int = Field(ge=0)
    is_complete: bool
    projection_revision: int = Field(ge=0)


class ParticipantSummaryResponse(ScoringResponse):
    participant_id: UUID
    participation_state: ParticipationState
    dismissal_type: ScoringDismissalType | None
    batting_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    balls_faced: int = Field(ge=0)
    fours: int = Field(ge=0)
    sixes: int = Field(ge=0)
    bowling_legal_balls: int = Field(ge=0)
    bowling_overs_completed: int = Field(ge=0)
    bowling_balls_in_partial_over: int = Field(ge=0)
    runs_conceded: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    bowling_wickets: int = Field(ge=0)
    wides: int = Field(ge=0)
    no_balls: int = Field(ge=0)
    fielding_dismissals: int = Field(ge=0)
    projection_revision: int = Field(ge=0)


class InningsResponse(ScoringResponse):
    id: UUID
    match_id: UUID
    innings_number: int = Field(ge=1)
    batting_side_id: UUID
    fielding_side_id: UUID
    lifecycle_state: InningsLifecycleState
    reconciliation_reason: str | None
    striker_participant_id: UUID | None
    non_striker_participant_id: UUID | None
    current_bowler_participant_id: UUID | None
    legal_balls: int = Field(ge=0)
    total_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    wickets_lost: int = Field(ge=0)
    target_runs: int | None = Field(default=None, ge=1, le=SCORING_RUN_TOTAL_MAX)
    completion_reason: InningsCompletionMode | None
    completed_at: datetime | None
    projection_revision: int = Field(ge=0)
    version_number: int = Field(ge=1)
    blocking_state: BlockingStateResponse
    overs: list[InningsOverResponse] = Field(default_factory=list)
    participant_summaries: list[ParticipantSummaryResponse] = Field(
        default_factory=list
    )


class DeliveryHistoryResponse(ScoringResponse):
    innings_id: UUID
    after_sequence: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_SCORING_HISTORY_LIMIT)
    deliveries: list[DeliveryResponse]
    next_after_sequence: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_bound(self) -> Self:
        if len(self.deliveries) > self.limit:
            raise ValueError("delivery history exceeds requested limit")
        return self


class MatchParticipantPerformanceResponse(ScoringResponse):
    participant_id: UUID
    innings_id: UUID
    batting_runs: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    balls_faced: int = Field(ge=0)
    fours: int = Field(ge=0)
    sixes: int = Field(ge=0)
    dismissal_type: ScoringDismissalType | None
    bowling_legal_balls: int = Field(ge=0)
    runs_conceded: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    bowling_wickets: int = Field(ge=0)
    wides: int = Field(ge=0)
    no_balls: int = Field(ge=0)
    extras_conceded: int = Field(ge=0, le=SCORING_RUN_TOTAL_MAX)
    catches: int = Field(ge=0)
    stumpings: int = Field(ge=0)
    run_out_involvements: int = Field(ge=0)
    projection_revision: int = Field(ge=0)
    provenance: PerformanceProvenance


class ScorecardResponse(ScoringResponse):
    match_id: UUID
    lifecycle_state: MatchLifecycleState
    scoring_authority: ScoringAuthority
    result_code: MatchResultCode
    result_details: dict[str, Any]
    compatibility_result: str
    policy: ScoringPolicyResponse | None
    sides: list[MatchSideResponse]
    participants: list[MatchParticipantResponse]
    innings: list[InningsResponse]
    participant_performances: list[MatchParticipantPerformanceResponse]
    blocking_state: BlockingStateResponse
    match_version_number: int = Field(ge=1)
    projection_revision: int = Field(ge=0)


type ScoringErrorCode = Literal[
    "scoring_authentication_required",
    "scoring_forbidden",
    "scoring_not_found",
    "scoring_validation_failed",
    "scoring_lifecycle_conflict",
    "scoring_revision_conflict",
    "scoring_reconciliation_conflict",
    "scoring_authority_conflict",
    "scoring_version_conflict",
    "scoring_sequence_conflict",
    "scoring_conflict",
]


class ScoringFieldError(ScoringResponse):
    field: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=500)


class ScoringErrorResponse(ScoringResponse):
    """Stable non-sensitive scoring error envelope."""

    detail: str = Field(min_length=1, max_length=500)
    code: ScoringErrorCode
    request_id: str | None = Field(default=None, max_length=128)
    field_errors: list[ScoringFieldError] = Field(default_factory=list, max_length=50)


# Short aliases keep service and route code readable without weakening schemas.
ScoringPolicyRequest = ScoringPolicyConfigurationRequest
MatchScoringConfigurationRequest = MatchConfigurationRequest
AppendScoringDeliveryRequest = AppendDeliveryRequest
