"""Pure projections, helpers, and rules for Academy Data Quality."""

from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from src.enums import (
    QualityDomain,
    QualityEntityType,
    QualityRuleId,
    QualitySeverity,
    RecurrenceFrequency,
    RecurrenceTermination,
    UserRole,
)
from src.schemas.data_quality import (
    DataQualityFinding,
    DirectQualityRemediation,
    NormalizeRosterOrderRemediation,
    RelatedQualityEntity,
    RemoveInactiveAssistantAssignmentRemediation,
    RemoveInactivePlayerRemediation,
)
from src.services.calendar_recurrence import (
    CalendarRecurrenceError,
    recurrence_occurs_on,
)

MINIMUM_ROSTER_SIZE = 7
MAXIMUM_ROSTER_SIZE = 15


@dataclass(frozen=True, slots=True)
class PlayerProjection:
    """Columns needed to evaluate player and roster quality rules."""

    player_id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    is_active: bool


@dataclass(frozen=True, slots=True)
class TeamProjection:
    """Columns needed to evaluate team-level quality rules."""

    team_id: UUID
    name: str
    age_group: str
    version_number: int


@dataclass(frozen=True, slots=True)
class RosterMembershipProjection:
    """One persisted player/team relationship and its display position."""

    team_id: UUID
    player_id: UUID
    roster_order: int


@dataclass(frozen=True, slots=True)
class CoachProjection:
    """Account columns needed for coach assignment quality rules."""

    coach_id: UUID
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    version_number: int


@dataclass(frozen=True, slots=True)
class CoachAssignmentProjection:
    """One persisted user/team coach assignment."""

    coach_id: UUID
    team_id: UUID


@dataclass(frozen=True, slots=True)
class CalendarSeriesProjection:
    """One recurrence rule joined to the owning event."""

    event_id: UUID
    event_name: str
    first_date: date
    series_id: UUID
    frequency: RecurrenceFrequency
    termination: RecurrenceTermination
    end_date: date | None
    occurrence_count: int | None


@dataclass(frozen=True, slots=True)
class CalendarExceptionProjection:
    """One occurrence exception that must remain on its parent series."""

    exception_id: UUID
    series_id: UUID
    original_date: date


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Shared request-scoped projections consumed by every registered rule."""

    players: tuple[PlayerProjection, ...] = field(default_factory=tuple)
    teams: tuple[TeamProjection, ...] = field(default_factory=tuple)
    roster_memberships: tuple[RosterMembershipProjection, ...] = field(
        default_factory=tuple
    )
    coaches: tuple[CoachProjection, ...] = field(default_factory=tuple)
    coach_assignments: tuple[CoachAssignmentProjection, ...] = field(
        default_factory=tuple
    )
    calendar_series: tuple[CalendarSeriesProjection, ...] = field(default_factory=tuple)
    calendar_exceptions: tuple[CalendarExceptionProjection, ...] = field(
        default_factory=tuple
    )


type RemediationPolicy = Literal["navigate", "direct", "manual"]
type RuleEvaluator = Callable[[EvaluationContext], list[DataQualityFinding]]


@dataclass(frozen=True, slots=True)
class QualityRule:
    """Immutable metadata and evaluator for one stable rule identifier."""

    rule_id: QualityRuleId
    domain: QualityDomain
    severity: QualitySeverity
    title: str
    recommended_action: str
    remediation_policy: RemediationPolicy
    evaluator: RuleEvaluator


def normalize_player_name(value: str) -> str:
    """Normalize one player name using the documented identity comparison."""

    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().split()).casefold()


def player_identity_key(player: PlayerProjection) -> tuple[str, str, date]:
    """Return the deterministic normalized duplicate-player grouping key."""

    return (
        normalize_player_name(player.first_name),
        normalize_player_name(player.last_name),
        player.date_of_birth,
    )


def team_name_group_key(team: TeamProjection) -> tuple[str, str]:
    """Mirror the existing lower(trim(name)) comparison within an age group."""

    return team.age_group, team.name.strip().lower()


def group_teams_by_normalized_name(
    teams: Iterable[TeamProjection],
) -> dict[tuple[str, str], tuple[TeamProjection, ...]]:
    """Group teams by the existing service-level name comparison."""

    groups: dict[tuple[str, str], list[TeamProjection]] = defaultdict(list)
    for team in teams:
        groups[team_name_group_key(team)].append(team)
    return {
        key: tuple(sorted(group, key=lambda item: str(item.team_id)))
        for key, group in groups.items()
    }


def build_finding_id(
    rule_id: QualityRuleId | str,
    *identifiers: UUID | str | Iterable[UUID | str],
) -> str:
    """Build an order-independent finding identifier from affected identities."""

    flattened: list[str] = []
    for identifier in identifiers:
        if isinstance(identifier, UUID | str):
            flattened.append(str(identifier))
        else:
            flattened.extend(str(value) for value in identifier)
    stable_identifiers = sorted(set(flattened))
    rule_value = rule_id.value if isinstance(rule_id, QualityRuleId) else str(rule_id)
    return ":".join((rule_value, *stable_identifiers))


stable_finding_id = build_finding_id


def _person_label(first_name: str, last_name: str) -> str:
    return f"{first_name} {last_name}".strip()


def _related_entity(
    entity_type: QualityEntityType,
    entity_id: UUID,
    entity_label: str,
) -> RelatedQualityEntity:
    return RelatedQualityEntity(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
    )


def _sort_related_entities(
    entities: Iterable[RelatedQualityEntity],
) -> list[RelatedQualityEntity]:
    return sorted(
        entities,
        key=lambda entity: (entity.entity_type.value, str(entity.entity_id)),
    )


def _finding(
    rule_id: QualityRuleId,
    *,
    identifiers: Iterable[UUID | str],
    entity_type: QualityEntityType,
    entity_id: UUID | None,
    entity_label: str,
    explanation: str,
    direct_remediation: DirectQualityRemediation | None = None,
    related_entities: Iterable[RelatedQualityEntity] = (),
) -> DataQualityFinding:
    rule = RULE_REGISTRY[rule_id]
    return DataQualityFinding(
        finding_id=build_finding_id(rule_id, identifiers),
        rule_id=rule.rule_id,
        severity=rule.severity,
        domain=rule.domain,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        title=rule.title,
        explanation=explanation,
        recommended_action=rule.recommended_action,
        direct_remediation=direct_remediation,
        related_entities=_sort_related_entities(related_entities),
    )


def _memberships_by_team(
    context: EvaluationContext,
) -> dict[UUID, list[RosterMembershipProjection]]:
    grouped: dict[UUID, list[RosterMembershipProjection]] = defaultdict(list)
    for membership in context.roster_memberships:
        grouped[membership.team_id].append(membership)
    for memberships in grouped.values():
        memberships.sort(
            key=lambda membership: (
                membership.roster_order,
                str(membership.player_id),
            )
        )
    return grouped


def _assignments_by_coach(
    context: EvaluationContext,
) -> dict[UUID, set[UUID]]:
    grouped: dict[UUID, set[UUID]] = defaultdict(set)
    for assignment in context.coach_assignments:
        grouped[assignment.coach_id].add(assignment.team_id)
    return grouped


def _roster_normalization_action(
    context: EvaluationContext,
    team: TeamProjection,
    memberships: list[RosterMembershipProjection],
) -> NormalizeRosterOrderRemediation | None:
    players = {player.player_id: player for player in context.players}
    if not MINIMUM_ROSTER_SIZE <= len(memberships) <= MAXIMUM_ROSTER_SIZE:
        return None
    if len({membership.player_id for membership in memberships}) != len(memberships):
        return None
    if any(
        membership.player_id not in players
        or not players[membership.player_id].is_active
        for membership in memberships
    ):
        return None
    return NormalizeRosterOrderRemediation(
        team_id=team.team_id,
        expected_team_version=team.version_number,
    )


def _inactive_player_action(
    context: EvaluationContext,
    team: TeamProjection,
    selected_player_id: UUID,
    memberships: list[RosterMembershipProjection],
) -> RemoveInactivePlayerRemediation | None:
    players = {player.player_id: player for player in context.players}
    remaining = [
        membership
        for membership in memberships
        if membership.player_id != selected_player_id
    ]
    if not MINIMUM_ROSTER_SIZE <= len(remaining) <= MAXIMUM_ROSTER_SIZE:
        return None
    if len({membership.player_id for membership in remaining}) != len(remaining):
        return None
    if any(
        membership.player_id not in players
        or not players[membership.player_id].is_active
        for membership in remaining
    ):
        return None
    return RemoveInactivePlayerRemediation(
        team_id=team.team_id,
        player_id=selected_player_id,
        expected_team_version=team.version_number,
    )


def _active_unassigned_players(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    assigned_player_ids = {
        membership.player_id for membership in context.roster_memberships
    }
    findings = []
    for player in context.players:
        if not player.is_active or player.player_id in assigned_player_ids:
            continue
        label = _person_label(player.first_name, player.last_name)
        findings.append(
            _finding(
                QualityRuleId.PLAYER_ACTIVE_UNASSIGNED,
                identifiers=(player.player_id,),
                entity_type=QualityEntityType.PLAYER,
                entity_id=player.player_id,
                entity_label=label,
                explanation=(
                    f"{label} is active but is not included in any team roster. "
                    "The player may be missed by team workflows."
                ),
            )
        )
    return findings


def _inactive_rostered_players(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    players = {player.player_id: player for player in context.players}
    teams = {team.team_id: team for team in context.teams}
    memberships_by_team = _memberships_by_team(context)
    findings = []
    for membership in context.roster_memberships:
        player = players.get(membership.player_id)
        team = teams.get(membership.team_id)
        if player is None or team is None or player.is_active:
            continue
        player_label = _person_label(player.first_name, player.last_name)
        findings.append(
            _finding(
                QualityRuleId.PLAYER_INACTIVE_ROSTERED,
                identifiers=(player.player_id, team.team_id),
                entity_type=QualityEntityType.ROSTER_MEMBERSHIP,
                entity_id=player.player_id,
                entity_label=f"{player_label} — {team.name}",
                explanation=(
                    f"{player_label} is inactive but remains on {team.name}. "
                    "The membership can make the current roster inaccurate."
                ),
                direct_remediation=_inactive_player_action(
                    context,
                    team,
                    player.player_id,
                    memberships_by_team[team.team_id],
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.TEAM,
                        team.team_id,
                        team.name,
                    ),
                ),
            )
        )
    return findings


def _normalized_player_duplicates(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    groups: dict[tuple[str, str, date], list[PlayerProjection]] = defaultdict(list)
    for player in context.players:
        groups[player_identity_key(player)].append(player)

    findings = []
    for group in groups.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda player: str(player.player_id))
        primary = ordered[0]
        label = _person_label(primary.first_name, primary.last_name)
        findings.append(
            _finding(
                QualityRuleId.PLAYER_NORMALIZED_IDENTITY_DUPLICATE,
                identifiers=(player.player_id for player in ordered),
                entity_type=QualityEntityType.PLAYER,
                entity_id=primary.player_id,
                entity_label=f"{label} ({len(ordered)} records)",
                explanation=(
                    f"{len(ordered)} player records share the same normalized "
                    "name and date of birth. They require human review before "
                    "any record is changed."
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.PLAYER,
                        player.player_id,
                        _person_label(player.first_name, player.last_name),
                    )
                    for player in ordered[1:]
                ),
            )
        )
    return findings


def _team_roster_bounds(context: EvaluationContext) -> list[DataQualityFinding]:
    memberships = _memberships_by_team(context)
    findings = []
    for team in context.teams:
        roster_count = len(memberships.get(team.team_id, ()))
        if roster_count < MINIMUM_ROSTER_SIZE:
            findings.append(
                _finding(
                    QualityRuleId.TEAM_ROSTER_BELOW_MINIMUM,
                    identifiers=(team.team_id,),
                    entity_type=QualityEntityType.TEAM,
                    entity_id=team.team_id,
                    entity_label=team.name,
                    explanation=(
                        f"{team.name} has {roster_count} roster memberships; "
                        f"a complete roster requires at least {MINIMUM_ROSTER_SIZE}."
                    ),
                )
            )
        elif roster_count > MAXIMUM_ROSTER_SIZE:
            findings.append(
                _finding(
                    QualityRuleId.TEAM_ROSTER_ABOVE_MAXIMUM,
                    identifiers=(team.team_id,),
                    entity_type=QualityEntityType.TEAM,
                    entity_id=team.team_id,
                    entity_label=team.name,
                    explanation=(
                        f"{team.name} has {roster_count} roster memberships; "
                        f"a complete roster allows at most {MAXIMUM_ROSTER_SIZE}."
                    ),
                )
            )
    return findings


def _roster_order_findings(context: EvaluationContext) -> list[DataQualityFinding]:
    players = {player.player_id: player for player in context.players}
    memberships_by_team = _memberships_by_team(context)
    findings = []
    for team in context.teams:
        memberships = memberships_by_team.get(team.team_id, [])
        if not memberships:
            continue
        positions = [membership.roster_order for membership in memberships]
        position_counts = Counter(positions)
        non_positive = [position for position in positions if position <= 0]
        duplicate_positions = sorted(
            position for position, count in position_counts.items() if count > 1
        )
        positive_positions = {position for position in positions if position > 0}
        missing_positions = (
            sorted(
                set(range(min(positive_positions), max(positive_positions) + 1))
                - positive_positions
            )
            if positive_positions
            else []
        )
        direct_action = _roster_normalization_action(
            context,
            team,
            memberships,
        )

        if non_positive:
            findings.append(
                _roster_order_finding(
                    context,
                    team,
                    memberships,
                    QualityRuleId.ROSTER_ORDER_NON_POSITIVE,
                    explanation=(
                        f"{team.name} has {len(non_positive)} roster position(s) "
                        "at zero or below, so its displayed order is invalid."
                    ),
                    direct_action=direct_action,
                    players=players,
                )
            )
        if duplicate_positions:
            duplicate_text = ", ".join(map(str, duplicate_positions))
            findings.append(
                _roster_order_finding(
                    context,
                    team,
                    memberships,
                    QualityRuleId.ROSTER_ORDER_DUPLICATE,
                    explanation=(
                        f"{team.name} has multiple roster memberships at "
                        f"position(s) {duplicate_text}."
                    ),
                    direct_action=direct_action,
                    players=players,
                )
            )
        if missing_positions:
            missing_text = ", ".join(map(str, missing_positions))
            findings.append(
                _roster_order_finding(
                    context,
                    team,
                    memberships,
                    QualityRuleId.ROSTER_ORDER_GAP,
                    explanation=(
                        f"{team.name} is missing roster position(s) "
                        f"{missing_text} between its current positions."
                    ),
                    direct_action=direct_action,
                    players=players,
                )
            )
        expected_positions = list(range(1, len(memberships) + 1))
        if (
            not non_positive
            and not duplicate_positions
            and not missing_positions
            and sorted(positions) != expected_positions
        ):
            findings.append(
                _roster_order_finding(
                    context,
                    team,
                    memberships,
                    QualityRuleId.ROSTER_ORDER_NON_CONTIGUOUS,
                    explanation=(
                        f"{team.name}'s roster positions do not form the expected "
                        f"contiguous range 1 through {len(memberships)}."
                    ),
                    direct_action=direct_action,
                    players=players,
                )
            )
    return findings


def _roster_order_finding(
    context: EvaluationContext,
    team: TeamProjection,
    memberships: list[RosterMembershipProjection],
    rule_id: QualityRuleId,
    *,
    explanation: str,
    direct_action: NormalizeRosterOrderRemediation | None,
    players: Mapping[UUID, PlayerProjection],
) -> DataQualityFinding:
    del context
    return _finding(
        rule_id,
        identifiers=(team.team_id,),
        entity_type=QualityEntityType.ROSTER,
        entity_id=team.team_id,
        entity_label=f"{team.name} roster",
        explanation=explanation,
        direct_remediation=direct_action,
        related_entities=(
            _related_entity(
                QualityEntityType.PLAYER,
                membership.player_id,
                (
                    _person_label(player.first_name, player.last_name)
                    if (player := players.get(membership.player_id)) is not None
                    else str(membership.player_id)
                ),
            )
            for membership in memberships
        ),
    )


def _normalized_team_name_conflicts(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    findings = []
    for group in group_teams_by_normalized_name(context.teams).values():
        if len(group) < 2:
            continue
        primary = group[0]
        findings.append(
            _finding(
                QualityRuleId.TEAM_NORMALIZED_NAME_CONFLICT,
                identifiers=(team.team_id for team in group),
                entity_type=QualityEntityType.TEAM,
                entity_id=primary.team_id,
                entity_label=f"{primary.name} ({primary.age_group})",
                explanation=(
                    f"{len(group)} teams in {primary.age_group} use names that "
                    "match after trimming and lower-casing. A coach must decide "
                    "which names are correct."
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.TEAM,
                        team.team_id,
                        team.name,
                    )
                    for team in group[1:]
                ),
            )
        )
    return findings


def _teams_without_coaches(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    assigned_team_ids = {assignment.team_id for assignment in context.coach_assignments}
    return [
        _finding(
            QualityRuleId.TEAM_NO_ASSIGNED_COACH,
            identifiers=(team.team_id,),
            entity_type=QualityEntityType.TEAM,
            entity_id=team.team_id,
            entity_label=team.name,
            explanation=(
                f"{team.name} has no coach assignment. Current team responsibility "
                "is therefore unclear."
            ),
        )
        for team in context.teams
        if team.team_id not in assigned_team_ids
    ]


def _sole_head_coach_integrity(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    head_coaches = [
        coach for coach in context.coaches if coach.role == UserRole.HEAD_COACH
    ]
    assignments = _assignments_by_coach(context)
    all_team_ids = {team.team_id for team in context.teams}
    healthy = (
        len(head_coaches) == 1
        and head_coaches[0].is_active
        and assignments.get(head_coaches[0].coach_id, set()) == all_team_ids
    )
    if healthy:
        return []

    unique_head = head_coaches[0] if len(head_coaches) == 1 else None
    missing_team_ids = (
        all_team_ids - assignments.get(unique_head.coach_id, set())
        if unique_head is not None
        else all_team_ids
    )
    teams = {team.team_id: team for team in context.teams}
    related = [
        _related_entity(
            QualityEntityType.COACH,
            coach.coach_id,
            _person_label(coach.first_name, coach.last_name),
        )
        for coach in head_coaches
    ]
    related.extend(
        _related_entity(
            QualityEntityType.TEAM,
            team_id,
            teams[team_id].name,
        )
        for team_id in missing_team_ids
    )
    label = (
        _person_label(unique_head.first_name, unique_head.last_name)
        if unique_head is not None
        else "Academy Head Coach coverage"
    )
    return [
        _finding(
            QualityRuleId.COACH_SOLE_HEAD_COACH_INTEGRITY,
            identifiers=("academy",),
            entity_type=QualityEntityType.ACADEMY,
            entity_id=unique_head.coach_id if unique_head is not None else None,
            entity_label=label,
            explanation=(
                "The academy cannot confirm exactly one active Head Coach assigned "
                "to every current team. This invariant requires manual review; no "
                "Head Coach assignment will be removed automatically."
            ),
            related_entities=related,
        )
    ]


def _inactive_assistant_assignments(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    coaches = {coach.coach_id: coach for coach in context.coaches}
    teams = {team.team_id: team for team in context.teams}
    findings = []
    for assignment in context.coach_assignments:
        coach = coaches.get(assignment.coach_id)
        team = teams.get(assignment.team_id)
        if (
            coach is None
            or team is None
            or coach.role != UserRole.ASSISTANT_COACH
            or coach.is_active
        ):
            continue
        coach_label = _person_label(coach.first_name, coach.last_name)
        findings.append(
            _finding(
                QualityRuleId.COACH_INACTIVE_ASSIGNED,
                identifiers=(coach.coach_id, team.team_id),
                entity_type=QualityEntityType.COACH_ASSIGNMENT,
                entity_id=coach.coach_id,
                entity_label=f"{coach_label} — {team.name}",
                explanation=(
                    f"{coach_label} is inactive but remains assigned to "
                    f"{team.name}. The assignment can confuse responsibility."
                ),
                direct_remediation=(
                    RemoveInactiveAssistantAssignmentRemediation(
                        coach_id=coach.coach_id,
                        team_id=team.team_id,
                        expected_coach_version=coach.version_number,
                    )
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.TEAM,
                        team.team_id,
                        team.name,
                    ),
                ),
            )
        )
    return findings


def _active_unassigned_assistants(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    assigned_coach_ids = {
        assignment.coach_id for assignment in context.coach_assignments
    }
    findings = []
    for coach in context.coaches:
        if (
            coach.role != UserRole.ASSISTANT_COACH
            or not coach.is_active
            or coach.coach_id in assigned_coach_ids
        ):
            continue
        label = _person_label(coach.first_name, coach.last_name)
        findings.append(
            _finding(
                QualityRuleId.COACH_ACTIVE_ASSISTANT_UNASSIGNED,
                identifiers=(coach.coach_id,),
                entity_type=QualityEntityType.COACH,
                entity_id=coach.coach_id,
                entity_label=label,
                explanation=(
                    f"{label} is an active Assistant Coach without a team "
                    "assignment. This may be intentional but should be reviewed."
                ),
            )
        )
    return findings


def _invalid_role_assignments(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    coaches = {coach.coach_id: coach for coach in context.coaches}
    teams = {team.team_id: team for team in context.teams}
    valid_roles = {UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH}
    findings = []
    for assignment in context.coach_assignments:
        coach = coaches.get(assignment.coach_id)
        team = teams.get(assignment.team_id)
        if coach is None or team is None or coach.role in valid_roles:
            continue
        coach_label = _person_label(coach.first_name, coach.last_name)
        findings.append(
            _finding(
                QualityRuleId.COACH_ASSIGNMENT_INVALID_ROLE,
                identifiers=(coach.coach_id, team.team_id),
                entity_type=QualityEntityType.COACH_ASSIGNMENT,
                entity_id=coach.coach_id,
                entity_label=f"{coach_label} — {team.name}",
                explanation=(
                    f"{coach_label} is assigned to {team.name} with role "
                    f"'{coach.role}', which is not a coach role. The record "
                    "requires manual review."
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.TEAM,
                        team.team_id,
                        team.name,
                    ),
                ),
            )
        )
    return findings


def _recurrence_end_before_start(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    findings = []
    for series in context.calendar_series:
        if series.end_date is None or series.end_date >= series.first_date:
            continue
        findings.append(
            _finding(
                QualityRuleId.CALENDAR_RECURRENCE_END_BEFORE_START,
                identifiers=(series.series_id,),
                entity_type=QualityEntityType.RECURRENCE_SERIES,
                entity_id=series.series_id,
                entity_label=series.event_name,
                explanation=(
                    f"{series.event_name} ends on {series.end_date.isoformat()}, "
                    f"before its first date {series.first_date.isoformat()}. "
                    "Its recurrence cannot be projected reliably."
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.CALENDAR_EVENT,
                        series.event_id,
                        series.event_name,
                    ),
                ),
            )
        )
    return findings


def _stale_occurrence_exceptions(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    series_by_id = {series.series_id: series for series in context.calendar_series}
    findings = []
    for exception in context.calendar_exceptions:
        series = series_by_id.get(exception.series_id)
        if series is None or (
            series.end_date is not None and series.end_date < series.first_date
        ):
            continue
        try:
            is_current_occurrence = recurrence_occurs_on(
                exception.original_date,
                first_date=series.first_date,
                frequency=series.frequency,
                termination=series.termination,
                end_date=series.end_date,
                occurrence_count=series.occurrence_count,
            )
        except CalendarRecurrenceError:
            continue
        if is_current_occurrence:
            continue
        findings.append(
            _finding(
                QualityRuleId.CALENDAR_STALE_OCCURRENCE_EXCEPTION,
                identifiers=(exception.exception_id,),
                entity_type=QualityEntityType.OCCURRENCE_EXCEPTION,
                entity_id=exception.exception_id,
                entity_label=(
                    f"{series.event_name} — {exception.original_date.isoformat()}"
                ),
                explanation=(
                    f"The saved exception for {series.event_name} on "
                    f"{exception.original_date.isoformat()} no longer matches an "
                    "occurrence generated by the current recurrence rule."
                ),
                related_entities=(
                    _related_entity(
                        QualityEntityType.RECURRENCE_SERIES,
                        series.series_id,
                        series.event_name,
                    ),
                ),
            )
        )
    return findings


def _rule(
    rule_id: QualityRuleId,
    domain: QualityDomain,
    severity: QualitySeverity,
    title: str,
    recommended_action: str,
    policy: RemediationPolicy,
    evaluator: RuleEvaluator,
) -> QualityRule:
    return QualityRule(
        rule_id=rule_id,
        domain=domain,
        severity=severity,
        title=title,
        recommended_action=recommended_action,
        remediation_policy=policy,
        evaluator=evaluator,
    )


def _select_rule(
    evaluator: RuleEvaluator,
    rule_id: QualityRuleId,
) -> RuleEvaluator:
    """Keep a shared family evaluator independently scoped to one rule."""

    def selected(context: EvaluationContext) -> list[DataQualityFinding]:
        return [finding for finding in evaluator(context) if finding.rule_id == rule_id]

    return selected


_RULES = (
    _rule(
        QualityRuleId.PLAYER_ACTIVE_UNASSIGNED,
        QualityDomain.PLAYERS,
        QualitySeverity.WARNING,
        "Active player is not assigned to a team",
        "Review the player in Teams and choose an appropriate roster.",
        "navigate",
        _active_unassigned_players,
    ),
    _rule(
        QualityRuleId.PLAYER_INACTIVE_ROSTERED,
        QualityDomain.PLAYERS,
        QualitySeverity.WARNING,
        "Inactive player remains on a roster",
        "Remove this one membership when eligible, or review it in Teams.",
        "direct",
        _inactive_rostered_players,
    ),
    _rule(
        QualityRuleId.PLAYER_NORMALIZED_IDENTITY_DUPLICATE,
        QualityDomain.PLAYERS,
        QualitySeverity.WARNING,
        "Player records may represent the same person",
        "Review the records in Players; do not merge them automatically.",
        "navigate",
        _normalized_player_duplicates,
    ),
    _rule(
        QualityRuleId.TEAM_ROSTER_BELOW_MINIMUM,
        QualityDomain.TEAMS,
        QualitySeverity.WARNING,
        "Team roster is below the minimum",
        "Review the team in Teams and select the correct active players.",
        "navigate",
        _select_rule(
            _team_roster_bounds,
            QualityRuleId.TEAM_ROSTER_BELOW_MINIMUM,
        ),
    ),
    _rule(
        QualityRuleId.TEAM_ROSTER_ABOVE_MAXIMUM,
        QualityDomain.TEAMS,
        QualitySeverity.WARNING,
        "Team roster is above the maximum",
        "Review the team in Teams and decide which players belong.",
        "navigate",
        _select_rule(
            _team_roster_bounds,
            QualityRuleId.TEAM_ROSTER_ABOVE_MAXIMUM,
        ),
    ),
    _rule(
        QualityRuleId.ROSTER_ORDER_NON_POSITIVE,
        QualityDomain.ROSTERS,
        QualitySeverity.WARNING,
        "Roster contains a non-positive position",
        "Normalize the roster order when eligible, or review it in Teams.",
        "direct",
        _select_rule(
            _roster_order_findings,
            QualityRuleId.ROSTER_ORDER_NON_POSITIVE,
        ),
    ),
    _rule(
        QualityRuleId.ROSTER_ORDER_DUPLICATE,
        QualityDomain.ROSTERS,
        QualitySeverity.WARNING,
        "Roster contains duplicate positions",
        "Normalize the roster order when eligible, or review it in Teams.",
        "direct",
        _select_rule(
            _roster_order_findings,
            QualityRuleId.ROSTER_ORDER_DUPLICATE,
        ),
    ),
    _rule(
        QualityRuleId.ROSTER_ORDER_GAP,
        QualityDomain.ROSTERS,
        QualitySeverity.WARNING,
        "Roster order contains a gap",
        "Normalize the roster order when eligible, or review it in Teams.",
        "direct",
        _select_rule(
            _roster_order_findings,
            QualityRuleId.ROSTER_ORDER_GAP,
        ),
    ),
    _rule(
        QualityRuleId.ROSTER_ORDER_NON_CONTIGUOUS,
        QualityDomain.ROSTERS,
        QualitySeverity.WARNING,
        "Roster order is not contiguous",
        "Normalize the roster order when eligible, or review it in Teams.",
        "direct",
        _select_rule(
            _roster_order_findings,
            QualityRuleId.ROSTER_ORDER_NON_CONTIGUOUS,
        ),
    ),
    _rule(
        QualityRuleId.TEAM_NORMALIZED_NAME_CONFLICT,
        QualityDomain.TEAMS,
        QualitySeverity.WARNING,
        "Team names conflict within an age group",
        "Review the teams in Teams and choose distinct correct names.",
        "navigate",
        _normalized_team_name_conflicts,
    ),
    _rule(
        QualityRuleId.TEAM_NO_ASSIGNED_COACH,
        QualityDomain.TEAMS,
        QualitySeverity.WARNING,
        "Team has no assigned coach",
        "Open Coaches and review the team's assignment.",
        "navigate",
        _teams_without_coaches,
    ),
    _rule(
        QualityRuleId.COACH_SOLE_HEAD_COACH_INTEGRITY,
        QualityDomain.COACHES,
        QualitySeverity.CRITICAL,
        "Sole Head Coach coverage is incomplete",
        "Review the Head Coach and team assignments manually in Coaches.",
        "manual",
        _sole_head_coach_integrity,
    ),
    _rule(
        QualityRuleId.COACH_INACTIVE_ASSIGNED,
        QualityDomain.COACHES,
        QualitySeverity.WARNING,
        "Inactive Assistant Coach remains assigned",
        "Remove this one Assistant assignment, or review it in Coaches.",
        "direct",
        _inactive_assistant_assignments,
    ),
    _rule(
        QualityRuleId.COACH_ACTIVE_ASSISTANT_UNASSIGNED,
        QualityDomain.COACHES,
        QualitySeverity.INFO,
        "Active Assistant Coach has no team",
        "Review the Assistant Coach in Coaches and decide whether to assign a team.",
        "navigate",
        _active_unassigned_assistants,
    ),
    _rule(
        QualityRuleId.COACH_ASSIGNMENT_INVALID_ROLE,
        QualityDomain.COACHES,
        QualitySeverity.CRITICAL,
        "Coach assignment references a non-coach role",
        "Review the account and team assignment manually in Coaches.",
        "manual",
        _invalid_role_assignments,
    ),
    _rule(
        QualityRuleId.CALENDAR_RECURRENCE_END_BEFORE_START,
        QualityDomain.CALENDAR,
        QualitySeverity.CRITICAL,
        "Recurrence ends before its first event date",
        "Open Calendar and choose a valid recurrence termination.",
        "navigate",
        _recurrence_end_before_start,
    ),
    _rule(
        QualityRuleId.CALENDAR_STALE_OCCURRENCE_EXCEPTION,
        QualityDomain.CALENDAR,
        QualitySeverity.WARNING,
        "Occurrence exception no longer belongs to its series",
        "Open Calendar and use the confirmation-aware series workflow.",
        "navigate",
        _stale_occurrence_exceptions,
    ),
)

RULE_REGISTRY: Mapping[QualityRuleId, QualityRule] = MappingProxyType(
    {rule.rule_id: rule for rule in _RULES}
)
DATA_QUALITY_RULES = RULE_REGISTRY


def evaluate_registered_rules(
    context: EvaluationContext,
) -> list[DataQualityFinding]:
    """Evaluate every rule once and remove shared-family duplicate output."""

    findings_by_id: dict[str, DataQualityFinding] = {}
    evaluated: set[RuleEvaluator] = set()
    for rule in RULE_REGISTRY.values():
        if rule.evaluator in evaluated:
            continue
        evaluated.add(rule.evaluator)
        for finding in rule.evaluator(context):
            findings_by_id[finding.finding_id] = finding
    return list(findings_by_id.values())
