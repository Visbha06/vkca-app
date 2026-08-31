"""Deterministic builders for isolated Match-scoring tests.

The builders intentionally return existing ORM objects for academy users and
Teams, and small immutable value objects for scoring records that are not
implemented yet. This keeps unit tests independent of database state while
allowing integration tests to use the same identifiers and observed facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from src.enums import MatchFormat, UserRole
from src.models.team import Team
from src.models.user import User

SCORING_REFERENCE_DATE = date(2026, 8, 1)


@dataclass(frozen=True, slots=True)
class ScoringParticipantFixture:
    """A fixed Match participant identity used by scoring tests."""

    id: UUID
    match_id: UUID
    side_code: str
    display_name: str
    batting_order_position: int
    player_id: UUID | None = None
    is_external: bool = False


@dataclass(frozen=True, slots=True)
class ScoringPolicyFixture:
    """Locked-policy inputs shared by policy and command tests."""

    format: MatchFormat
    innings_sequence: tuple[str, ...]
    legal_ball_limit: int | None = 120
    over_length: int = 6
    bowler_quota: int | None = 24
    wicket_limit: int = 10
    consecutive_over_prohibited: bool = False


@dataclass(frozen=True, slots=True)
class ScoringInningsFixture:
    """Minimal innings identity and locked sequence position."""

    id: UUID
    match_id: UUID
    innings_number: int = 1
    batting_side_code: str = "A"
    fielding_side_code: str = "B"


@dataclass(frozen=True, slots=True)
class ScoringWicketFixture:
    """One optional wicket fact, including canonical ordered fielders."""

    dismissal_type: str = "bowled"
    dismissed_participant_id: UUID | None = None
    dismissed_end: str | None = "striker_end"
    fielders: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoringDeliveryFixture:
    """Observed delivery components; derived values stay out of the input."""

    innings_id: UUID
    attempted_sequence: int = 1
    striker_participant_id: UUID | None = None
    non_striker_participant_id: UUID | None = None
    bowler_participant_id: UUID | None = None
    runs_off_bat: int = 0
    wide_runs: int = 0
    no_ball_penalty_runs: int = 0
    bye_runs: int = 0
    leg_bye_runs: int = 0
    penalty_runs: int = 0
    wicket: ScoringWicketFixture | None = None


@dataclass(frozen=True, slots=True)
class ScoringRevisionFixture:
    """Immutable revision metadata for correction and replay tests."""

    delivery_id: UUID
    revision_id: UUID
    revision_number: int = 1
    revision_state: str = "active"
    replacement_reason: str | None = None
    supersedes_revision_id: UUID | None = None


def build_scoring_user(
    *,
    user_id: UUID | None = None,
    first_name: str = "Scoring",
    last_name: str | None = None,
    role: UserRole = UserRole.HEAD_COACH,
    is_active: bool = True,
) -> User:
    """Build an academy account without persisting it."""

    resolved_id = user_id or uuid4()
    return User(
        id=resolved_id,
        first_name=first_name,
        last_name=last_name or f"User-{resolved_id.hex[:8]}",
        email=f"scoring-{resolved_id.hex}@example.com",
        hashed_password="$argon2id$scoring-test-placeholder",
        role=role,
        is_active=is_active,
        version_number=1,
    )


def build_scoring_team(
    *,
    team_id: UUID | None = None,
    name: str | None = None,
    age_group: str = "U13",
) -> Team:
    """Build an academy Team without roster or coach side effects."""

    resolved_id = team_id or uuid4()
    return Team(
        id=resolved_id,
        name=name or f"Scoring Team {resolved_id.hex[:8]}",
        age_group=age_group,
        version_number=1,
    )


def build_scoring_participant(
    *,
    match_id: UUID | None = None,
    participant_id: UUID | None = None,
    side_code: str = "A",
    display_name: str | None = None,
    batting_order_position: int = 1,
    player_id: UUID | None = None,
    is_external: bool = False,
) -> ScoringParticipantFixture:
    """Build one fixed internal or external Match participant."""

    resolved_id = participant_id or uuid4()
    return ScoringParticipantFixture(
        id=resolved_id,
        match_id=match_id or uuid4(),
        side_code=side_code,
        display_name=display_name or f"Participant-{resolved_id.hex[:8]}",
        batting_order_position=batting_order_position,
        player_id=player_id,
        is_external=is_external,
    )


def build_scoring_policy(
    *,
    format: MatchFormat = MatchFormat.T20,
    innings_sequence: tuple[str, ...] = ("A", "B"),
    legal_ball_limit: int | None = 120,
    over_length: int = 6,
    bowler_quota: int | None = 24,
    wicket_limit: int = 10,
    consecutive_over_prohibited: bool = False,
) -> ScoringPolicyFixture:
    """Build a policy-shaped fixture; validation belongs to the policy service."""

    return ScoringPolicyFixture(
        format=format,
        innings_sequence=innings_sequence,
        legal_ball_limit=legal_ball_limit,
        over_length=over_length,
        bowler_quota=bowler_quota,
        wicket_limit=wicket_limit,
        consecutive_over_prohibited=consecutive_over_prohibited,
    )


def build_scoring_innings_sequence(
    *side_codes: str,
) -> tuple[str, ...]:
    """Return an immutable ordered innings sequence for policy fixtures."""

    return tuple(side_codes or ("A", "B"))


def build_scoring_innings(
    *,
    match_id: UUID | None = None,
    innings_id: UUID | None = None,
    innings_number: int = 1,
    batting_side_code: str = "A",
    fielding_side_code: str = "B",
) -> ScoringInningsFixture:
    """Build one innings anchored to a Match and ordered side sequence."""

    return ScoringInningsFixture(
        id=innings_id or uuid4(),
        match_id=match_id or uuid4(),
        innings_number=innings_number,
        batting_side_code=batting_side_code,
        fielding_side_code=fielding_side_code,
    )


def build_scoring_delivery(
    *,
    innings_id: UUID | None = None,
    attempted_sequence: int = 1,
    striker_participant_id: UUID | None = None,
    non_striker_participant_id: UUID | None = None,
    bowler_participant_id: UUID | None = None,
    runs_off_bat: int = 0,
    wide_runs: int = 0,
    no_ball_penalty_runs: int = 0,
    bye_runs: int = 0,
    leg_bye_runs: int = 0,
    penalty_runs: int = 0,
    wicket: ScoringWicketFixture | None = None,
) -> ScoringDeliveryFixture:
    """Build observed delivery facts without client-derived scoring fields."""

    return ScoringDeliveryFixture(
        innings_id=innings_id or uuid4(),
        attempted_sequence=attempted_sequence,
        striker_participant_id=striker_participant_id,
        non_striker_participant_id=non_striker_participant_id,
        bowler_participant_id=bowler_participant_id,
        runs_off_bat=runs_off_bat,
        wide_runs=wide_runs,
        no_ball_penalty_runs=no_ball_penalty_runs,
        bye_runs=bye_runs,
        leg_bye_runs=leg_bye_runs,
        penalty_runs=penalty_runs,
        wicket=wicket,
    )


def build_scoring_wicket(
    *,
    dismissal_type: str = "bowled",
    dismissed_participant_id: UUID | None = None,
    dismissed_end: str | None = "striker_end",
    fielders: tuple[UUID, ...] = (),
) -> ScoringWicketFixture:
    """Build one wicket fact with fielders in API order."""

    return ScoringWicketFixture(
        dismissal_type=dismissal_type,
        dismissed_participant_id=dismissed_participant_id,
        dismissed_end=dismissed_end,
        fielders=fielders,
    )


def build_scoring_revision(
    *,
    delivery_id: UUID | None = None,
    revision_id: UUID | None = None,
    revision_number: int = 1,
    revision_state: str = "active",
    replacement_reason: str | None = None,
    supersedes_revision_id: UUID | None = None,
) -> ScoringRevisionFixture:
    """Build immutable revision provenance for append-only correction tests."""

    return ScoringRevisionFixture(
        delivery_id=delivery_id or uuid4(),
        revision_id=revision_id or uuid4(),
        revision_number=revision_number,
        revision_state=revision_state,
        replacement_reason=replacement_reason,
        supersedes_revision_id=supersedes_revision_id,
    )


__all__ = [
    "SCORING_REFERENCE_DATE",
    "ScoringDeliveryFixture",
    "ScoringInningsFixture",
    "ScoringParticipantFixture",
    "ScoringPolicyFixture",
    "ScoringRevisionFixture",
    "ScoringWicketFixture",
    "build_scoring_delivery",
    "build_scoring_innings",
    "build_scoring_innings_sequence",
    "build_scoring_participant",
    "build_scoring_policy",
    "build_scoring_revision",
    "build_scoring_team",
    "build_scoring_user",
    "build_scoring_wicket",
]
