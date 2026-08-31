"""Locked scoring-policy persistence for one configured Match."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import (
    ExplicitMatchCompletionBoundary,
    FormatCapabilityProfile,
    MatchFormat,
    TargetMode,
)
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.match import Match


class ScoringPolicy(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """Immutable resolved FormatCapability values locked to a Match."""

    __tablename__ = "match_scoring_policies"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            name="uq_match_scoring_policies_match_id",
        ),
        CheckConstraint(
            "policy_code IN ('T20', 'one-day', 'test', 'other')",
            name="ck_match_scoring_policies_policy_code",
        ),
        CheckConstraint(
            "capability_profile IN ('T20', 'one-day', 'test', 'other')",
            name="ck_match_scoring_policies_capability_profile",
        ),
        CheckConstraint(
            "policy_code = capability_profile",
            name="ck_match_scoring_policies_canonical_profile",
        ),
        CheckConstraint(
            "policy_version >= 1 AND capability_version >= 1 "
            "AND innings_per_side >= 1 AND over_length_legal_balls >= 1 "
            "AND wicket_limit >= 1 AND version_number >= 1",
            name="ck_match_scoring_policies_positive_values",
        ),
        CheckConstraint(
            "legal_ball_limit IS NULL OR legal_ball_limit >= 1",
            name="ck_match_scoring_policies_legal_ball_limit_positive",
        ),
        CheckConstraint(
            "bowler_quota_legal_balls IS NULL OR bowler_quota_legal_balls >= 1",
            name="ck_match_scoring_policies_bowler_quota_positive",
        ),
        CheckConstraint(
            "target_mode IN ('prior_innings_plus_one', 'none')",
            name="ck_match_scoring_policies_target_mode",
        ),
        CheckConstraint(
            "explicit_match_completion_boundary IN "
            "('none', 'after_completed_innings', 'any_nonterminal_state')",
            name="ck_match_scoring_policies_completion_boundary",
        ),
        CheckConstraint(
            "jsonb_typeof(innings_sequence) = 'array' "
            "AND jsonb_array_length(innings_sequence) >= 2",
            name="ck_match_scoring_policies_innings_sequence",
        ),
        CheckConstraint(
            "jsonb_typeof(allowed_dismissal_types) = 'array' "
            "AND jsonb_array_length(allowed_dismissal_types) >= 1 "
            "AND jsonb_typeof(allowed_transition_types) = 'array' "
            "AND jsonb_typeof(allowed_innings_completion_modes) = 'array' "
            "AND jsonb_array_length(allowed_innings_completion_modes) >= 1 "
            "AND jsonb_typeof(allowed_match_completion_modes) = 'array' "
            "AND jsonb_array_length(allowed_match_completion_modes) >= 1 "
            "AND jsonb_typeof(allowed_result_codes) = 'array' "
            "AND jsonb_array_length(allowed_result_codes) >= 1",
            name="ck_match_scoring_policies_capability_sets",
        ),
        CheckConstraint(
            "capability_profile <> 'one-day' OR "
            "(legal_ball_limit > 0 AND legal_ball_limit % 30 = 0 "
            "AND over_length_legal_balls = 6 "
            "AND bowler_quota_legal_balls = legal_ball_limit / 5 "
            "AND wicket_limit = 10)",
            name="ck_match_scoring_policies_one_day_policy",
        ),
        CheckConstraint(
            "capability_profile <> 'T20' OR "
            "(innings_per_side = 1 AND legal_ball_limit = 120 "
            "AND over_length_legal_balls = 6 "
            "AND bowler_quota_legal_balls = 24 AND wicket_limit = 10 "
            "AND consecutive_overs_prohibited "
            "AND target_mode = 'prior_innings_plus_one' "
            "AND explicit_match_completion_boundary = 'none')",
            name="ck_match_scoring_policies_t20_policy",
        ),
        CheckConstraint(
            "capability_profile <> 'test' OR "
            "(innings_per_side = 2 AND legal_ball_limit IS NULL "
            "AND over_length_legal_balls = 6 "
            "AND bowler_quota_legal_balls IS NULL AND wicket_limit = 10 "
            "AND consecutive_overs_prohibited AND target_mode = 'none' "
            "AND explicit_match_completion_boundary = 'after_completed_innings')",
            name="ck_match_scoring_policies_test_policy",
        ),
    )

    match_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "matches.id",
            ondelete="CASCADE",
            name="fk_match_scoring_policies_match_id_matches",
        ),
        nullable=False,
    )
    policy_code: Mapped[MatchFormat] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    capability_profile: Mapped[FormatCapabilityProfile] = mapped_column(
        String(20),
        nullable=False,
    )
    capability_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    innings_sequence: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    innings_per_side: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_ball_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    over_length_legal_balls: Mapped[int] = mapped_column(Integer, nullable=False)
    bowler_quota_legal_balls: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    wicket_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    consecutive_overs_prohibited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    target_mode: Mapped[TargetMode] = mapped_column(String(32), nullable=False)
    allowed_dismissal_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    allowed_transition_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    allowed_innings_completion_modes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
    )
    allowed_match_completion_modes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
    )
    allowed_result_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    allow_declaration: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    allow_draw: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    explicit_match_completion_boundary: Mapped[ExplicitMatchCompletionBoundary] = (
        mapped_column(String(32), nullable=False)
    )
    allow_manual_completion: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    match: Mapped[Match] = relationship(back_populates="scoring_policy")

    @property
    def derived_one_day_bowler_quota(self) -> int | None:
        """Return the canonical quota implied by a locked one-day limit."""

        if (
            self.capability_profile != FormatCapabilityProfile.ONE_DAY
            or self.legal_ball_limit is None
        ):
            return None
        return self.legal_ball_limit // 5


ScoringPolicyJson = dict[str, Any]
