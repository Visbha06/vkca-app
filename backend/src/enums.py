"""String enums shared by database models and API schemas."""

from enum import StrEnum


class UserRole(StrEnum):
    """Supported user account roles."""

    HEAD_COACH = "head coach"
    ASSISTANT_COACH = "assistant coach"
    PLAYER = "player"


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
