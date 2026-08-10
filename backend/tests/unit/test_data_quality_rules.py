"""Unit coverage for the deterministic Data Quality rule catalogue."""

from datetime import date
from uuid import uuid4

from src.enums import QualityDomain, QualityRuleId, QualitySeverity, UserRole
from src.services.data_quality_rules import (
    RULE_REGISTRY,
    CalendarSeriesProjection,
    CoachAssignmentProjection,
    CoachProjection,
    EvaluationContext,
    PlayerProjection,
    RosterMembershipProjection,
    TeamProjection,
    evaluate_registered_rules,
    normalize_player_name,
)


def test_rule_registry_covers_the_complete_initial_allowlist() -> None:
    """Every documented rule has stable metadata and an evaluator."""

    assert set(RULE_REGISTRY) == set(QualityRuleId)
    assert {rule.domain for rule in RULE_REGISTRY.values()} == set(QualityDomain)
    assert (
        RULE_REGISTRY[QualityRuleId.COACH_SOLE_HEAD_COACH_INTEGRITY].severity
        == QualitySeverity.CRITICAL
    )


def test_normalized_player_name_collapses_case_unicode_and_whitespace() -> None:
    assert normalize_player_name("  A\u0301sha   PATEL ") == "ásha patel"


def test_healthy_context_has_no_findings() -> None:
    team_id, coach_id = uuid4(), uuid4()
    players = tuple(
        PlayerProjection(uuid4(), "Player", str(index), date(2013, 1, index + 1), True)
        for index in range(7)
    )
    context = EvaluationContext(
        players=players,
        teams=(TeamProjection(team_id, "U13 Falcons", "U13", 1),),
        roster_memberships=tuple(
            RosterMembershipProjection(team_id, player.player_id, index + 1)
            for index, player in enumerate(players)
        ),
        coaches=(
            CoachProjection(coach_id, "Alex", "Morgan", UserRole.HEAD_COACH, True, 1),
        ),
        coach_assignments=(CoachAssignmentProjection(coach_id, team_id),),
    )

    assert evaluate_registered_rules(context) == []


def test_unhealthy_context_reports_expected_rules_with_safe_assistant_action() -> None:
    team_id, duplicate_team_id = uuid4(), uuid4()
    head_id, inactive_assistant_id, player_id = uuid4(), uuid4(), uuid4()
    duplicate_date = date(2013, 1, 15)
    context = EvaluationContext(
        players=(
            PlayerProjection(player_id, "Asha", "Patel", duplicate_date, False),
            PlayerProjection(uuid4(), "  asha", "PATEL ", duplicate_date, True),
        ),
        teams=(
            TeamProjection(team_id, "Falcons", "U13", 3),
            TeamProjection(duplicate_team_id, " falcons ", "U13", 1),
        ),
        roster_memberships=(RosterMembershipProjection(team_id, player_id, 0),),
        coaches=(
            CoachProjection(head_id, "Head", "Coach", UserRole.HEAD_COACH, False, 1),
            CoachProjection(
                inactive_assistant_id,
                "Assistant",
                "Coach",
                UserRole.ASSISTANT_COACH,
                False,
                4,
            ),
        ),
        coach_assignments=(CoachAssignmentProjection(inactive_assistant_id, team_id),),
        calendar_series=(
            CalendarSeriesProjection(
                uuid4(),
                "Practice",
                date(2026, 8, 2),
                uuid4(),
                "weekly",
                "end_date",
                date(2026, 8, 1),
                None,
            ),
        ),
    )

    findings = evaluate_registered_rules(context)
    rule_ids = {finding.rule_id for finding in findings}

    assert {
        QualityRuleId.PLAYER_INACTIVE_ROSTERED,
        QualityRuleId.PLAYER_NORMALIZED_IDENTITY_DUPLICATE,
        QualityRuleId.TEAM_ROSTER_BELOW_MINIMUM,
        QualityRuleId.ROSTER_ORDER_NON_POSITIVE,
        QualityRuleId.TEAM_NORMALIZED_NAME_CONFLICT,
        QualityRuleId.COACH_SOLE_HEAD_COACH_INTEGRITY,
        QualityRuleId.COACH_INACTIVE_ASSIGNED,
        QualityRuleId.CALENDAR_RECURRENCE_END_BEFORE_START,
    } <= rule_ids
    integrity = next(
        item
        for item in findings
        if item.rule_id == QualityRuleId.COACH_SOLE_HEAD_COACH_INTEGRITY
    )
    assistant = next(
        item
        for item in findings
        if item.rule_id == QualityRuleId.COACH_INACTIVE_ASSIGNED
    )
    assert integrity.direct_remediation is None
    assert assistant.direct_remediation is not None
    assert (
        assistant.direct_remediation.action.value
        == "remove_inactive_assistant_assignment"
    )
