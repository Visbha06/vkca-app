"""Focused coverage for the role-specific dashboard context projection."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import AgeGroup, UserRole
from src.models.team import Team
from src.schemas.dashboard import DashboardRecentActivity, DashboardResponse
from src.services.dashboard_service import (
    DashboardCalendarProjection,
    DashboardScope,
    DashboardService,
)

from .test_dashboard_service import NOW, make_event, scalar_result


def make_team(name: str, age_group: AgeGroup) -> Team:
    return Team(id=uuid4(), name=name, age_group=age_group, version_number=1)


@pytest.mark.asyncio
async def test_head_coach_context_is_bounded_recent_activity_in_stable_order(
    mocker,
) -> None:
    service = DashboardService(Mock(), now=NOW)
    recent = Mock(
        events=[
            Mock(
                id=uuid4(),
                actor_display_name="Asha Coach",
                action_type="player.created",
                action_category="player",
                target_label="Rohan Player",
                summary="Asha Coach added Rohan Player",
                created_at=datetime(2026, 8, 10, 18, tzinfo=UTC),
            )
        ]
    )
    audit = Mock(list_recent=AsyncMock(return_value=recent))
    mocker.patch(
        "src.services.dashboard_service.BusinessAuditService", return_value=audit
    )

    context = await service._load_context(
        DashboardScope(UserRole.HEAD_COACH, (), None),
        DashboardCalendarProjection(instances=()),
    )

    assert isinstance(context, DashboardRecentActivity)
    assert context.events[0].summary == "Asha Coach added Rohan Player"
    audit.list_recent.assert_awaited_once_with(limit=4)


@pytest.mark.asyncio
async def test_my_teams_context_has_distinct_active_counts_coaches_and_next_event() -> (
    None
):
    u13 = make_team("U13 Falcons", AgeGroup.U13)
    u15 = make_team("U15 Falcons", AgeGroup.U15)
    session = Mock()
    session.execute = AsyncMock(
        side_effect=[
            scalar_result((u13.id, 8), (u15.id, 12)),
            scalar_result(
                (u13.id, uuid4(), "Asha", "Coach"),
                (u13.id, uuid4(), "Bea", "Coach"),
            ),
        ]
    )
    service = DashboardService(session, now=NOW)
    projection = DashboardCalendarProjection(
        instances=(
            make_event("u13-next", date(2026, 8, 12), age_groups=[AgeGroup.U13]),
            make_event("u15-next", date(2026, 8, 13), age_groups=[AgeGroup.U15]),
        )
    )

    context = await service._load_context(
        DashboardScope(UserRole.PLAYER, (u13, u15), uuid4()),
        projection,
    )

    assert [team.name for team in context.teams] == ["U13 Falcons", "U15 Falcons"]
    assert [team.active_player_count for team in context.teams] == [8, 12]
    assert [coach.display_name for coach in context.teams[0].coaches] == [
        "Asha Coach",
        "Bea Coach",
    ]
    assert context.teams[1].coaches == []
    assert context.teams[0].next_event is not None
    assert context.teams[0].next_event.occurrence_id == "u13-next"


@pytest.mark.asyncio
async def test_assistant_context_does_not_load_or_expose_audit_activity(mocker) -> None:
    team = make_team("U15 Falcons", AgeGroup.U15)
    session = Mock()
    session.execute = AsyncMock(return_value=scalar_result((team.id, 4)))
    audit = Mock(list_recent=AsyncMock())
    mocker.patch(
        "src.services.dashboard_service.BusinessAuditService", return_value=audit
    )

    context = await DashboardService(session, now=NOW)._load_context(
        DashboardScope(UserRole.ASSISTANT_COACH, (team,), None),
        DashboardCalendarProjection(instances=()),
    )

    assert context.kind == "my_teams"
    assert context.teams[0].coaches == []
    audit.list_recent.assert_not_awaited()


def test_role_specific_context_rejects_recent_activity_for_non_head_coach() -> None:
    payload = {
        "user": {
            "id": str(uuid4()),
            "display_name": "Anya Coach",
            "role": "assistant coach",
        },
        "dashboard_state": "ready",
        "summary": {
            "training": {"status": "empty", "message": "No training."},
            "next_match": {"status": "empty", "message": "No matches."},
            "player_slot": {"status": "empty", "message": "No players."},
        },
        "upcoming_events": {"status": "empty", "message": "No events."},
        "context": {
            "status": "ready",
            "data": {
                "kind": "recent_activity",
                "events": [],
                "view_all_path": "/audit-log",
            },
        },
    }

    with pytest.raises(ValueError, match="Dashboard context is incompatible"):
        DashboardResponse.model_validate(payload)
