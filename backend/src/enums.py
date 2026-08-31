"""String enums shared by database models and API schemas."""

from enum import StrEnum


class UserRole(StrEnum):
    """Supported user account roles."""

    HEAD_COACH = "head coach"
    ASSISTANT_COACH = "assistant coach"
    PLAYER = "player"


class QualitySeverity(StrEnum):
    """Operational impact levels exposed by Data Quality findings."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class QualityDomain(StrEnum):
    """Allowlisted academy domains evaluated by Data Quality."""

    PLAYERS = "players"
    TEAMS = "teams"
    ROSTERS = "rosters"
    COACHES = "coaches"
    CALENDAR = "calendar"


class QualityAction(StrEnum):
    """Direct corrections supported by the initial quality contract."""

    NORMALIZE_ROSTER_ORDER = "normalize_roster_order"
    REMOVE_INACTIVE_PLAYER = "remove_inactive_player"
    REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT = "remove_inactive_assistant_assignment"


class QualityRuleId(StrEnum):
    """Stable identifiers for the initial Data Quality rule catalogue."""

    PLAYER_ACTIVE_UNASSIGNED = "player.active_unassigned"
    PLAYER_INACTIVE_ROSTERED = "player.inactive_rostered"
    PLAYER_NORMALIZED_IDENTITY_DUPLICATE = "player.normalized_identity_duplicate"
    TEAM_ROSTER_BELOW_MINIMUM = "team.roster_below_minimum"
    TEAM_ROSTER_ABOVE_MAXIMUM = "team.roster_above_maximum"
    ROSTER_ORDER_NON_POSITIVE = "roster.order_non_positive"
    ROSTER_ORDER_DUPLICATE = "roster.order_duplicate"
    ROSTER_ORDER_GAP = "roster.order_gap"
    ROSTER_ORDER_NON_CONTIGUOUS = "roster.order_non_contiguous"
    TEAM_NORMALIZED_NAME_CONFLICT = "team.normalized_name_conflict"
    TEAM_NO_ASSIGNED_COACH = "team.no_assigned_coach"
    COACH_SOLE_HEAD_COACH_INTEGRITY = "coach.sole_head_coach_integrity"
    COACH_INACTIVE_ASSIGNED = "coach.inactive_assigned"
    COACH_ACTIVE_ASSISTANT_UNASSIGNED = "coach.active_assistant_unassigned"
    COACH_ASSIGNMENT_INVALID_ROLE = "coach.assignment_invalid_role"
    CALENDAR_RECURRENCE_END_BEFORE_START = "calendar.recurrence_end_before_start"
    CALENDAR_STALE_OCCURRENCE_EXCEPTION = "calendar.stale_occurrence_exception"


class QualityEntityType(StrEnum):
    """Entity labels permitted in current-state quality findings."""

    PLAYER = "player"
    TEAM = "team"
    ROSTER = "roster"
    ROSTER_MEMBERSHIP = "roster_membership"
    COACH = "coach"
    COACH_ASSIGNMENT = "coach_assignment"
    CALENDAR_EVENT = "calendar_event"
    RECURRENCE_SERIES = "recurrence_series"
    OCCURRENCE_EXCEPTION = "occurrence_exception"
    ACADEMY = "academy"


class AuditActionCategory(StrEnum):
    """Business domains represented in the academy activity history."""

    COACH = "coach"
    PLAYER = "player"
    TEAM = "team"
    ROSTER = "roster"
    CALENDAR = "calendar"


class AuditEntityType(StrEnum):
    """Historical target kinds supported by the business-audit feed."""

    COACH = "coach"
    PLAYER = "player"
    TEAM = "team"
    ROSTER = "roster"
    CALENDAR_EVENT = "calendar_event"
    RECURRENCE_SERIES = "recurrence_series"


class AuditActionType(StrEnum):
    """Stable identifiers for the initial business-audit action catalogue."""

    COACH_CREATED = "coach.created"
    COACH_ACTIVATED = "coach.activated"
    COACH_DEACTIVATED = "coach.deactivated"
    COACH_TEAM_ASSIGNMENTS_UPDATED = "coach.team_assignments_updated"
    PLAYER_CREATED = "player.created"
    PLAYER_UPDATED = "player.updated"
    PLAYER_ACCOUNT_LINKED = "player.account_linked"
    PLAYER_ACCOUNT_UNLINKED = "player.account_unlinked"
    PLAYER_ACCOUNT_REASSIGNED = "player.account_reassigned"
    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    ROSTER_ADDED = "roster.added"
    ROSTER_REMOVED = "roster.removed"
    ROSTER_REORDERED = "roster.reordered"
    CALENDAR_STANDALONE_CREATED = "calendar.standalone_created"
    CALENDAR_STANDALONE_UPDATED = "calendar.standalone_updated"
    CALENDAR_STANDALONE_DELETED = "calendar.standalone_deleted"
    CALENDAR_SERIES_CREATED = "calendar.series_created"
    CALENDAR_SERIES_UPDATED = "calendar.series_updated"
    CALENDAR_SERIES_DELETED = "calendar.series_deleted"
    CALENDAR_OCCURRENCE_UPDATED = "calendar.occurrence_updated"
    CALENDAR_OCCURRENCE_MOVED = "calendar.occurrence_moved"
    CALENDAR_OCCURRENCE_DELETED = "calendar.occurrence_deleted"


class BattingStyle(StrEnum):
    """Supported batting orientations."""

    RIGHT = "right"
    LEFT = "left"


class BowlingStyle(StrEnum):
    """Supported bowling styles."""

    RIGHT_ARM_FAST = "right-arm fast"
    RIGHT_ARM_MEDIUM = "right-arm medium"
    RIGHT_ARM_OFF_BREAK = "right-arm off-break"
    RIGHT_ARM_LEG_BREAK = "right-arm leg-break"
    LEFT_ARM_FAST = "left-arm fast"
    LEFT_ARM_MEDIUM = "left-arm medium"
    LEFT_ARM_ORTHODOX = "left-arm orthodox"
    LEFT_ARM_UNORTHODOX = "left-arm unorthodox"


class PlayerType(StrEnum):
    """Supported player roles."""

    BATTER = "batter"
    BOWLER = "bowler"
    ALL_ROUNDER = "all-rounder"
    WICKET_KEEPER = "wicket-keeper"


class AgeGroup(StrEnum):
    """Supported cricket team age groups."""

    J = "J"
    U11 = "U11"
    U13 = "U13"
    U15 = "U15"


class EventType(StrEnum):
    """Supported academy calendar event classifications."""

    PRACTICE = "practice"
    GAME = "game"
    MISCELLANEOUS = "miscellaneous"


class ScopeKind(StrEnum):
    """Supported audience scope representations for calendar events."""

    AGE_GROUP = "age_group"
    ALL_ACADEMY = "all_academy"


class RecurrenceFrequency(StrEnum):
    """Supported fixed-interval calendar recurrence frequencies."""

    WEEKLY = "weekly"
    YEARLY = "yearly"


class RecurrenceTermination(StrEnum):
    """Supported ways to terminate a recurring calendar series."""

    NEVER = "never"
    END_DATE = "end_date"
    OCCURRENCE_COUNT = "occurrence_count"


class MatchFormat(StrEnum):
    """Supported cricket match formats."""

    T20 = "T20"
    ONE_DAY = "one-day"
    TEST = "test"
    OTHER = "other"


class FormatCapabilityProfile(StrEnum):
    """Canonical immutable scoring-capability profile identifiers."""

    T20 = "T20"
    ONE_DAY = "one-day"
    TEST = "test"
    OTHER = "other"


# Scoring limits are persistence/API invariants, not configurable policy values.
SCORING_RUN_COMPONENT_MAX = 2_147_483_647
SCORING_RUN_TOTAL_MAX = 2_147_483_647

# Version-one capability constants shared by schemas, persistence, and policy code.
FORMAT_CAPABILITY_VERSION = 1
STANDARD_OVER_LENGTH_LEGAL_BALLS = 6
STANDARD_WICKET_LIMIT = 10
T20_LEGAL_BALL_LIMIT = 120
T20_BOWLER_QUOTA_LEGAL_BALLS = 24
ONE_DAY_LEGAL_BALL_LIMIT_MULTIPLE = 30
ONE_DAY_BOWLER_QUOTA_DIVISOR = 5
TEST_CONSECUTIVE_OVERS_PROHIBITED = True


class MatchLifecycleState(StrEnum):
    """Lifecycle values owned by the Match aggregate."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    CORRECTION_REPROCESSING = "correction_reprocessing"


class ScoringAuthority(StrEnum):
    """Authoritative source used for a Match's scoring figures."""

    LEGACY_AGGREGATE = "legacy_aggregate"
    DELIVERY_HISTORY = "delivery_history"


class MatchResultCode(StrEnum):
    """Canonical non-terminal and terminal Match result codes."""

    PENDING = "pending"
    WIN_BY_RUNS = "win_by_runs"
    WIN_BY_WICKETS = "win_by_wickets"
    TIE = "tie"
    DRAW = "draw"
    NO_RESULT = "no_result"
    DECLARED = "declared"
    MANUAL = "manual"


class MatchSideCode(StrEnum):
    """Stable side positions retained from the existing Match boundary."""

    HOME = "home"
    AWAY = "away"


class MatchSideKind(StrEnum):
    """Identity source for one configured Match side."""

    ACADEMY = "academy"
    EXTERNAL = "external"


class MatchParticipantKind(StrEnum):
    """Identity source for one fixed Match participant."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class InningsLifecycleState(StrEnum):
    """Authoritative Innings lifecycle, including reconciliation state."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class InningsReconciliationReason(StrEnum):
    """Bounded reasons for entering Innings reconciliation."""

    INCOMPATIBLE_REPLAY = "incompatible_replay"


class BlockingStateKind(StrEnum):
    """Canonical read-only scoring progression states."""

    NONE = "none"
    INNINGS_NOT_STARTED = "innings_not_started"
    AWAITING_NEXT_BATTER = "awaiting_next_batter"
    AWAITING_NEXT_BOWLER = "awaiting_next_bowler"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    INNINGS_COMPLETED = "innings_completed"
    MATCH_COMPLETED = "match_completed"
    MATCH_ABANDONED = "match_abandoned"


class BlockingReasonCode(StrEnum):
    """Bounded reason codes paired with non-``none`` blocking states."""

    INNINGS_NOT_STARTED = "innings_not_started"
    NEXT_BATTER_REQUIRED = "next_batter_required"
    NEXT_BOWLER_REQUIRED = "next_bowler_required"
    NO_ELIGIBLE_BOWLER = "no_eligible_bowler"
    INCOMPATIBLE_REPLAY = "incompatible_replay"
    INNINGS_COMPLETED = "innings_completed"
    MATCH_COMPLETED = "match_completed"
    MATCH_ABANDONED = "match_abandoned"


class TargetMode(StrEnum):
    """Capability-defined target derivation behavior."""

    PRIOR_INNINGS_PLUS_ONE = "prior_innings_plus_one"
    NONE = "none"


class ExplicitMatchCompletionBoundary(StrEnum):
    """Points where a capability may accept explicit Match completion."""

    NONE = "none"
    AFTER_COMPLETED_INNINGS = "after_completed_innings"
    ANY_NONTERMINAL_STATE = "any_nonterminal_state"


class InningsCompletionMode(StrEnum):
    """Capability-listed ways an Innings may complete."""

    ALL_OUT = "all_out"
    LEGAL_BALL_LIMIT = "legal_ball_limit"
    TARGET_REACHED = "target_reached"
    DECLARATION = "declaration"
    MANUAL = "manual"


class MatchCompletionMode(StrEnum):
    """Supported Match-level completion commands."""

    DERIVED_RESULT = "derived_result"
    DRAW = "draw"
    DECLARED = "declared"
    MANUAL = "manual"
    ABANDONMENT = "abandonment"


class ParticipationState(StrEnum):
    """One participant's state within a specific Innings."""

    NOT_BATTED = "not_batted"
    ACTIVE = "active"
    DISMISSED = "dismissed"
    RETIRED_HURT = "retired_hurt"
    RETIRED_OUT = "retired_out"
    COMPLETED = "completed"


class InningsTransitionType(StrEnum):
    """Append-only scorer selections anchored in Innings history."""

    INNINGS_STARTED = "innings_started"
    NEXT_BATTER = "next_batter"
    NEXT_BOWLER = "next_bowler"
    RETIRED_HURT = "retired_hurt"
    RETIRED_HURT_RETURN = "retired_hurt_return"
    INNINGS_COMPLETED = "innings_completed"


class DeliveryRevisionState(StrEnum):
    """Lifecycle of one immutable delivery revision."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"


class ScoringDismissalType(StrEnum):
    """Current public scoring dismissal vocabulary.

    Reserved future dismissals are deliberately absent so schema parsing fails
    closed until a later capability version introduces them.
    """

    BOWLED = "bowled"
    CAUGHT = "caught"
    CAUGHT_AND_BOWLED = "caught_and_bowled"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"
    RETIRED_OUT = "retired_out"


RESERVED_SCORING_DISMISSAL_IDENTIFIERS = frozenset(
    {"obstructing_the_field", "hit_the_ball_twice", "timed_out"}
)
CORE_SCORING_DISMISSAL_TYPES = frozenset(ScoringDismissalType)
CORE_SCORING_TRANSITION_TYPES = frozenset(
    {InningsTransitionType.RETIRED_HURT, InningsTransitionType.RETIRED_HURT_RETURN}
)


class DismissedEnd(StrEnum):
    """Crease occupied by the participant dismissed on a run-out."""

    STRIKER_END = "striker_end"
    NON_STRIKER_END = "non_striker_end"


class FielderRole(StrEnum):
    """Ordered role played by a fielder in one wicket event."""

    BOWLER = "bowler"
    CATCHER = "catcher"
    THROWER = "thrower"
    KEEPER = "keeper"
    ASSISTER = "assister"
    OTHER = "other"


class PerformanceProvenance(StrEnum):
    """Source marker for rebuildable Match participant projections."""

    DELIVERY_DERIVED = "delivery_derived"


class MatchParticipantType(StrEnum):
    """Persisted Match participant structures."""

    EXTERNAL = "external"
    INTERNAL = "internal"


class DismissalType(StrEnum):
    """Supported batting dismissal outcomes."""

    NOT_OUT = "not out"
    CAUGHT = "caught"
    BOWLED = "bowled"
    LBW = "lbw"
    RUN_OUT = "run out"
    STUMPED = "stumped"
    OTHER = "other"
