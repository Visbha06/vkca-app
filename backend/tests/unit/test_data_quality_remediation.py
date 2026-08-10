"""Unit coverage for allowlisted Data Quality remediation dispatch."""

from datetime import date
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import (
    AuditActionType,
    QualityAction,
    QualityRuleId,
    UserRole,
)
from src.schemas.data_quality import (
    NormalizeRosterOrderRequest,
    RemoveInactiveAssistantAssignmentRequest,
)
from src.services.business_audit_service import AuditActorContext
from src.services.data_quality_rules import (
    CoachAssignmentProjection,
    CoachProjection,
    EvaluationContext,
    PlayerProjection,
    RosterMembershipProjection,
    TeamProjection,
    build_finding_id,
)
from src.services.data_quality_service import (
    DataQualityRemediationConflictError,
    DataQualityRemediationValidationError,
    DataQualityService,
)


def _actor() -> AuditActorContext:
    return AuditActorContext(
        user_id=uuid4(),
        display_name="Asha Head Coach",
        role=UserRole.HEAD_COACH,
        request_id="quality-unit-request",
    )


def _roster_context() -> tuple[EvaluationContext, TeamProjection]:
    team = TeamProjection(uuid4(), "U13 Falcons", "U13", 3)
    players = tuple(
        PlayerProjection(
            uuid4(),
            f"Player {index}",
            "Falcon",
            date(2013, 1, index),
            True,
        )
        for index in range(1, 8)
    )
    positions = (1, 2, 4, 5, 6, 7, 8)
    memberships = tuple(
        RosterMembershipProjection(team.team_id, player.player_id, position)
        for player, position in zip(players, positions, strict=True)
    )
    return (
        EvaluationContext(
            players=players,
            teams=(team,),
            roster_memberships=memberships,
        ),
        team,
    )


def _inactive_assistant_context() -> tuple[
    EvaluationContext,
    TeamProjection,
    CoachProjection,
]:
    team = TeamProjection(uuid4(), "U13 Falcons", "U13", 2)
    coach = CoachProjection(
        uuid4(),
        "Alex",
        "Morgan",
        UserRole.ASSISTANT_COACH,
        False,
        4,
    )
    return (
        EvaluationContext(
            teams=(team,),
            coaches=(coach,),
            coach_assignments=(
                CoachAssignmentProjection(coach.coach_id, team.team_id),
            ),
        ),
        team,
        coach,
    )


@pytest.mark.asyncio
async def test_normalize_dispatch_requires_the_exact_current_finding(mocker) -> None:
    context, team = _roster_context()
    domain_service = Mock()
    domain_service.normalize_roster_order = AsyncMock()
    mocker.patch(
        "src.services.data_quality_service.TeamService",
        return_value=domain_service,
    )
    service = DataQualityService(Mock())
    service.load_context = AsyncMock(return_value=context)
    command = NormalizeRosterOrderRequest(
        finding_id=build_finding_id(
            QualityRuleId.ROSTER_ORDER_GAP,
            team.team_id,
        ),
        team_id=team.team_id,
        expected_team_version=team.version_number,
        confirmed=True,
    )

    result = await service.remediate(command, actor=_actor())

    domain_service.normalize_roster_order.assert_awaited_once_with(
        team.team_id,
        expected_team_version=team.version_number,
        actor=mocker.ANY,
    )
    assert result.action is QualityAction.NORMALIZE_ROSTER_ORDER
    assert result.affected_entity_id == team.team_id
    assert result.audit_action is AuditActionType.ROSTER_REORDERED


@pytest.mark.asyncio
async def test_remediation_rejects_changed_target_metadata_and_resolved_finding(
    mocker,
) -> None:
    context, team = _roster_context()
    domain_service = Mock()
    domain_service.normalize_roster_order = AsyncMock()
    mocker.patch(
        "src.services.data_quality_service.TeamService",
        return_value=domain_service,
    )
    service = DataQualityService(Mock())
    service.load_context = AsyncMock(return_value=context)
    finding_id = build_finding_id(QualityRuleId.ROSTER_ORDER_GAP, team.team_id)

    with pytest.raises(DataQualityRemediationConflictError, match="changed"):
        await service.remediate(
            NormalizeRosterOrderRequest(
                finding_id=finding_id,
                team_id=uuid4(),
                expected_team_version=team.version_number,
                confirmed=True,
            ),
            actor=_actor(),
        )
    domain_service.normalize_roster_order.assert_not_awaited()

    service.load_context = AsyncMock(return_value=EvaluationContext())
    with pytest.raises(DataQualityRemediationConflictError, match="current"):
        await service.remediate(
            NormalizeRosterOrderRequest(
                finding_id=finding_id,
                team_id=team.team_id,
                expected_team_version=team.version_number,
                confirmed=True,
            ),
            actor=_actor(),
        )


@pytest.mark.asyncio
async def test_confirmation_is_validated_before_current_state_is_loaded() -> None:
    context, team = _roster_context()
    service = DataQualityService(Mock())
    service.load_context = AsyncMock(return_value=context)

    with pytest.raises(DataQualityRemediationValidationError, match="confirmation"):
        await service.remediate(
            NormalizeRosterOrderRequest(
                finding_id=build_finding_id(
                    QualityRuleId.ROSTER_ORDER_GAP,
                    team.team_id,
                ),
                team_id=team.team_id,
                expected_team_version=team.version_number,
                confirmed=False,
            ),
            actor=_actor(),
        )

    service.load_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_assistant_dispatches_one_exact_assignment(mocker) -> None:
    context, team, coach = _inactive_assistant_context()
    coach_service = Mock()
    coach_service.remove_inactive_assistant_assignment = AsyncMock()
    mocker.patch(
        "src.services.data_quality_service.CoachService",
        return_value=coach_service,
    )
    service = DataQualityService(Mock())
    service.load_context = AsyncMock(return_value=context)

    result = await service.remediate(
        RemoveInactiveAssistantAssignmentRequest(
            finding_id=build_finding_id(
                QualityRuleId.COACH_INACTIVE_ASSIGNED,
                coach.coach_id,
                team.team_id,
            ),
            coach_id=coach.coach_id,
            team_id=team.team_id,
            expected_coach_version=coach.version_number,
            confirmed=True,
        ),
        actor=_actor(),
    )

    coach_service.remove_inactive_assistant_assignment.assert_awaited_once_with(
        coach.coach_id,
        team.team_id,
        expected_coach_version=coach.version_number,
        actor=mocker.ANY,
    )
    assert result.action is QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT
    assert result.audit_action is AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED


@pytest.mark.asyncio
async def test_head_coach_assignment_never_dispatches_removal(mocker) -> None:
    team = TeamProjection(uuid4(), "U13 Falcons", "U13", 1)
    head_coach = CoachProjection(
        uuid4(),
        "Asha",
        "Head Coach",
        UserRole.HEAD_COACH,
        False,
        2,
    )
    context = EvaluationContext(
        teams=(team,),
        coaches=(head_coach,),
        coach_assignments=(
            CoachAssignmentProjection(head_coach.coach_id, team.team_id),
        ),
    )
    coach_service = Mock()
    coach_service.remove_inactive_assistant_assignment = AsyncMock()
    mocker.patch(
        "src.services.data_quality_service.CoachService",
        return_value=coach_service,
    )
    service = DataQualityService(Mock())
    service.load_context = AsyncMock(return_value=context)

    with pytest.raises(DataQualityRemediationConflictError):
        await service.remediate(
            RemoveInactiveAssistantAssignmentRequest(
                finding_id=build_finding_id(
                    QualityRuleId.COACH_INACTIVE_ASSIGNED,
                    head_coach.coach_id,
                    team.team_id,
                ),
                coach_id=head_coach.coach_id,
                team_id=team.team_id,
                expected_coach_version=head_coach.version_number,
                confirmed=True,
            ),
            actor=_actor(),
        )

    coach_service.remove_inactive_assistant_assignment.assert_not_awaited()
