"""Integration coverage for safe one-at-a-time Data Quality remediation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import AuditActionType, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    """Exercise writes as a persisted Head Coach audit actor."""

    actor = User(
        id=uuid4(),
        first_name="Integration",
        last_name="Head Coach",
        email=f"quality-remediation-{uuid4().hex}@example.test",
        hashed_password="unused-dependency-override",
        role=UserRole.HEAD_COACH,
        is_active=True,
        version_number=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    async with AsyncSessionFactory() as session:
        session.add(actor)
        await session.commit()

    async def override_current_user():
        return actor, Mock(spec=AuthSession)

    app.dependency_overrides[get_current_user] = override_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def _seed_inactive_assistant_assignment(quality_data_builder):
    team = await quality_data_builder.team(name="U13 Remediation Falcons")
    coach = await quality_data_builder.coach(
        first_name="Alex",
        last_name="Morgan",
        role=UserRole.ASSISTANT_COACH,
        is_active=False,
        version_number=4,
    )
    await quality_data_builder.coach_assignment(team=team, coach=coach)
    await quality_data_builder.commit()
    return team, coach


async def _inactive_assistant_finding(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.get(
        "/api/v1/data-quality",
        params={"rule_id": "coach.inactive_assigned"},
    )
    assert response.status_code == 200, response.text
    findings = response.json()["findings"]
    assert len(findings) == 1
    return findings[0]


def _assistant_command(finding: dict[str, object]) -> dict[str, object]:
    remediation = finding["direct_remediation"]
    assert isinstance(remediation, dict)
    return {
        "finding_id": finding["finding_id"],
        "action": remediation["action"],
        "coach_id": remediation["coach_id"],
        "team_id": remediation["team_id"],
        "expected_coach_version": remediation["expected_coach_version"],
        "confirmed": True,
    }


@pytest.mark.asyncio
async def test_success_removes_one_assignment_refreshes_and_records_one_event(
    client: httpx.AsyncClient,
    quality_data_builder,
) -> None:
    team, coach = await _seed_inactive_assistant_assignment(quality_data_builder)
    finding = await _inactive_assistant_finding(client)

    response = await client.post(
        "/api/v1/data-quality/remediations",
        json=_assistant_command(finding),
        headers={"X-Request-ID": "integration-remediation-success"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "applied",
        "action": "remove_inactive_assistant_assignment",
        "message": "The inactive Assistant Coach assignment was removed.",
        "affected_entity_id": str(coach.id),
        "audit_action": AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED.value,
    }
    refreshed = await client.get(
        "/api/v1/data-quality",
        params={"rule_id": "coach.inactive_assigned"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["findings"] == []

    async with AsyncSessionFactory() as session:
        assert await session.get(
            TeamCoach,
            {"team_id": team.id, "user_id": coach.id},
        ) is None
        persisted_coach = await session.get(User, coach.id)
        assert persisted_coach is not None
        assert persisted_coach.version_number == 5
        events = list(
            (
                await session.scalars(
                    select(BusinessAuditEvent).where(
                        BusinessAuditEvent.action_type
                        == AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED.value
                    )
                )
            ).all()
        )
    assert len(events) == 1
    assert events[0].target_entity_id == coach.id
    assert events[0].event_metadata["removed_team_ids"] == [str(team.id)]


@pytest.mark.asyncio
async def test_confirmation_and_stale_versions_reject_without_mutation_or_audit(
    client: httpx.AsyncClient,
    quality_data_builder,
) -> None:
    team, coach = await _seed_inactive_assistant_assignment(quality_data_builder)
    finding = await _inactive_assistant_finding(client)
    command = _assistant_command(finding)
    command["confirmed"] = False

    unconfirmed = await client.post(
        "/api/v1/data-quality/remediations",
        json=command,
    )
    assert unconfirmed.status_code == 400

    async with AsyncSessionFactory() as session:
        persisted_coach = await session.get(User, coach.id)
        assert persisted_coach is not None
        persisted_coach.version_number += 1
        await session.commit()

    command["confirmed"] = True
    stale = await client.post(
        "/api/v1/data-quality/remediations",
        json=command,
    )
    assert stale.status_code == 409

    async with AsyncSessionFactory() as session:
        assert await session.get(
            TeamCoach,
            {"team_id": team.id, "user_id": coach.id},
        ) is not None
        audit_count = await session.scalar(select(func.count(BusinessAuditEvent.id)))
    assert audit_count == 0


@pytest.mark.asyncio
async def test_changed_roster_precondition_preserves_the_selected_membership(
    client: httpx.AsyncClient,
    quality_data_builder,
) -> None:
    team = await quality_data_builder.team(
        name="U13 Roster Validation",
        version_number=3,
    )
    active_players = []
    for index in range(8):
        player = await quality_data_builder.player(
            first_name=f"Active {index}",
            last_name="Roster",
        )
        active_players.append(player)
        await quality_data_builder.roster_membership(
            team=team,
            player=player,
            roster_order=index + 1,
        )
    inactive_player = await quality_data_builder.player(
        first_name="Inactive",
        last_name="Roster",
        is_active=False,
    )
    await quality_data_builder.roster_membership(
        team=team,
        player=inactive_player,
        roster_order=9,
    )
    await quality_data_builder.commit()

    read = await client.get(
        "/api/v1/data-quality",
        params={"rule_id": "player.inactive_rostered"},
    )
    assert read.status_code == 200, read.text
    finding = read.json()["findings"][0]
    remediation = finding["direct_remediation"]
    assert remediation["action"] == "remove_inactive_player"

    async with AsyncSessionFactory() as session:
        changed_player = await session.get(Player, active_players[0].id)
        assert changed_player is not None
        changed_player.is_active = False
        await session.commit()

    rejected = await client.post(
        "/api/v1/data-quality/remediations",
        json={
            "finding_id": finding["finding_id"],
            "action": remediation["action"],
            "team_id": remediation["team_id"],
            "player_id": remediation["player_id"],
            "expected_team_version": remediation["expected_team_version"],
            "confirmed": True,
        },
    )
    assert rejected.status_code == 409

    async with AsyncSessionFactory() as session:
        assert await session.get(
            TeamPlayer,
            {"team_id": team.id, "player_id": inactive_player.id},
        ) is not None
        audit_count = await session.scalar(select(func.count(BusinessAuditEvent.id)))
    assert audit_count == 0


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_assignment_and_version(
    client: httpx.AsyncClient,
    quality_data_builder,
    mocker,
) -> None:
    team, coach = await _seed_inactive_assistant_assignment(quality_data_builder)
    finding = await _inactive_assistant_finding(client)
    mocker.patch(
        "src.services.coach_service.BusinessAuditService.record",
        new=AsyncMock(side_effect=RuntimeError("simulated audit persistence failure")),
    )

    response = await client.post(
        "/api/v1/data-quality/remediations",
        json=_assistant_command(finding),
    )

    assert response.status_code == 500
    async with AsyncSessionFactory() as session:
        assert await session.get(
            TeamCoach,
            {"team_id": team.id, "user_id": coach.id},
        ) is not None
        persisted_coach = await session.get(User, coach.id)
        assert persisted_coach is not None
        assert persisted_coach.version_number == 4
        audit_count = await session.scalar(select(func.count(BusinessAuditEvent.id)))
    assert audit_count == 0
