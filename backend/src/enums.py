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
    REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT = (
        "remove_inactive_assistant_assignment"
    )


class QualityRuleId(StrEnum):
    """Stable identifiers for the initial Data Quality rule catalogue."""

    PLAYER_ACTIVE_UNASSIGNED = "player.active_unassigned"
    PLAYER_INACTIVE_ROSTERED = "player.inactive_rostered"
    PLAYER_NORMALIZED_IDENTITY_DUPLICATE = (
        "player.normalized_identity_duplicate"
    )
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
    CALENDAR_RECURRENCE_END_BEFORE_START = (
        "calendar.recurrence_end_before_start"
    )
    CALENDAR_STALE_OCCURRENCE_EXCEPTION = (
        "calendar.stale_occurrence_exception"
    )


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


class DismissalType(StrEnum):
    """Supported batting dismissal outcomes."""

    NOT_OUT = "not out"
    CAUGHT = "caught"
    BOWLED = "bowled"
    LBW = "lbw"
    RUN_OUT = "run out"
    STUMPED = "stumped"
    OTHER = "other"
