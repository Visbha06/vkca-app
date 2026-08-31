"""Typed vocabulary and metadata allowlists for business audit events."""

from dataclasses import dataclass

from src.enums import AuditActionCategory, AuditActionType, AuditEntityType


@dataclass(frozen=True, slots=True)
class AuditActionDefinition:
    """Immutable classification and presentation rules for one action."""

    category: AuditActionCategory
    target_entity_type: AuditEntityType
    summary_template: str
    metadata_fields: frozenset[str] = frozenset()


ACTION_REGISTRY: dict[AuditActionType, AuditActionDefinition] = {
    AuditActionType.COACH_CREATED: AuditActionDefinition(
        AuditActionCategory.COACH,
        AuditEntityType.COACH,
        "{actor} created assistant coach {target}",
        frozenset({"assigned_team_ids", "assigned_team_count"}),
    ),
    AuditActionType.COACH_ACTIVATED: AuditActionDefinition(
        AuditActionCategory.COACH,
        AuditEntityType.COACH,
        "{actor} activated coach {target}",
        frozenset({"changed_fields"}),
    ),
    AuditActionType.COACH_DEACTIVATED: AuditActionDefinition(
        AuditActionCategory.COACH,
        AuditEntityType.COACH,
        "{actor} deactivated coach {target}",
        frozenset({"changed_fields"}),
    ),
    AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED: AuditActionDefinition(
        AuditActionCategory.COACH,
        AuditEntityType.COACH,
        "{actor} updated team assignments for {target}",
        frozenset(
            {
                "added_team_ids",
                "removed_team_ids",
                "added_count",
                "removed_count",
            }
        ),
    ),
    AuditActionType.PLAYER_CREATED: AuditActionDefinition(
        AuditActionCategory.PLAYER,
        AuditEntityType.PLAYER,
        "{actor} added player {target}",
        frozenset({"changed_fields"}),
    ),
    AuditActionType.PLAYER_UPDATED: AuditActionDefinition(
        AuditActionCategory.PLAYER,
        AuditEntityType.PLAYER,
        "{actor} updated player {target}",
        frozenset({"changed_fields"}),
    ),
    AuditActionType.PLAYER_ACCOUNT_LINKED: AuditActionDefinition(
        AuditActionCategory.PLAYER,
        AuditEntityType.PLAYER,
        "{actor} linked an account to player {target}",
        frozenset({"account_user_id"}),
    ),
    AuditActionType.PLAYER_ACCOUNT_UNLINKED: AuditActionDefinition(
        AuditActionCategory.PLAYER,
        AuditEntityType.PLAYER,
        "{actor} unlinked the account from player {target}",
        frozenset({"previous_account_user_id"}),
    ),
    AuditActionType.PLAYER_ACCOUNT_REASSIGNED: AuditActionDefinition(
        AuditActionCategory.PLAYER,
        AuditEntityType.PLAYER,
        "{actor} reassigned the account for player {target}",
        frozenset({"previous_account_user_id", "account_user_id"}),
    ),
    AuditActionType.TEAM_CREATED: AuditActionDefinition(
        AuditActionCategory.TEAM,
        AuditEntityType.TEAM,
        "{actor} created team {target}",
        frozenset({"age_group", "roster_count"}),
    ),
    AuditActionType.TEAM_UPDATED: AuditActionDefinition(
        AuditActionCategory.TEAM,
        AuditEntityType.TEAM,
        "{actor} updated team {target}",
        frozenset(
            {
                "changed_fields",
                "roster_replaced",
                "roster_count",
                "added_player_ids",
                "removed_player_ids",
                "reordered_player_ids",
            }
        ),
    ),
    AuditActionType.ROSTER_ADDED: AuditActionDefinition(
        AuditActionCategory.ROSTER,
        AuditEntityType.TEAM,
        "{actor} added a player to {target}'s roster",
        frozenset({"player_id", "new_roster_position"}),
    ),
    AuditActionType.ROSTER_REMOVED: AuditActionDefinition(
        AuditActionCategory.ROSTER,
        AuditEntityType.TEAM,
        "{actor} removed a player from {target}'s roster",
        frozenset({"player_id", "prior_roster_position"}),
    ),
    AuditActionType.ROSTER_REORDERED: AuditActionDefinition(
        AuditActionCategory.ROSTER,
        AuditEntityType.TEAM,
        "{actor} reordered {target}'s roster",
        frozenset({"affected_player_ids", "affected_count", "changed_positions"}),
    ),
    AuditActionType.CALENDAR_STANDALONE_CREATED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.CALENDAR_EVENT,
        "{actor} scheduled {target}",
        frozenset({"event_type", "scope", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_STANDALONE_UPDATED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.CALENDAR_EVENT,
        "{actor} updated calendar event {target}",
        frozenset({"changed_fields", "scope", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_STANDALONE_DELETED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.CALENDAR_EVENT,
        "{actor} deleted calendar event {target}",
        frozenset({"event_type", "scope", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_SERIES_CREATED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.RECURRENCE_SERIES,
        "{actor} scheduled recurring series {target}",
        frozenset({"event_type", "frequency", "scope", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_SERIES_UPDATED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.RECURRENCE_SERIES,
        "{actor} updated recurring series {target}",
        frozenset({"changed_fields", "frequency", "exception_count", "scope"}),
    ),
    AuditActionType.CALENDAR_SERIES_DELETED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.RECURRENCE_SERIES,
        "{actor} deleted recurring series {target}",
        frozenset({"event_type", "frequency", "scope", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_OCCURRENCE_UPDATED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.RECURRENCE_SERIES,
        "{actor} updated an occurrence of {target}",
        frozenset({"original_date", "changed_fields", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_OCCURRENCE_MOVED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.RECURRENCE_SERIES,
        "{actor} moved an occurrence of {target}",
        frozenset({"original_date", "replacement_date", "schedule_label"}),
    ),
    AuditActionType.CALENDAR_OCCURRENCE_DELETED: AuditActionDefinition(
        AuditActionCategory.CALENDAR,
        AuditEntityType.RECURRENCE_SERIES,
        "{actor} deleted an occurrence of {target}",
        frozenset({"original_date"}),
    ),
    AuditActionType.SCORING_INITIALIZED: AuditActionDefinition(
        AuditActionCategory.SCORING,
        AuditEntityType.MATCH,
        "{actor} initialized scoring for {target}",
        frozenset(
            {
                "capability_profile",
                "capability_version",
                "innings_sequence",
                "participant_count",
            }
        ),
    ),
}


def get_action_definition(action_type: AuditActionType) -> AuditActionDefinition:
    """Return the single registered contract for an action identifier."""

    return ACTION_REGISTRY[action_type]
