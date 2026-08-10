"""Executable Academy Data Quality quickstart validation."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select, update

from src.database import AsyncSessionFactory
from src.enums import AuditActionType, UserRole
from src.main import app
from src.models.business_audit_event import BusinessAuditEvent
from src.models.team_coach import TeamCoach
from src.models.user import User
from src.services.password_service import PasswordService


async def _login(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _business_audit_count() -> int:
    async with AsyncSessionFactory() as session:
        return int(
            await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0
        )


@pytest.mark.asyncio
async def test_academy_data_quality_quickstart_flow(quality_data_builder) -> None:
    """Validate reads, roles, Head Coach integrity, OCC, remediation, and audit."""

    run_id = uuid4().hex
    password = "DataQualityQuickstart-P@ssword1"
    team = await quality_data_builder.team(name=f"Quickstart Falcons {run_id}")
    head_coach = await quality_data_builder.coach(
        first_name="Quickstart",
        last_name="Head Coach",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )
    assistant_actor = await quality_data_builder.coach(
        first_name="Quickstart",
        last_name="Assistant",
        role=UserRole.ASSISTANT_COACH,
        is_active=True,
    )
    player_actor = await quality_data_builder.coach(
        first_name="Quickstart",
        last_name="Player",
        role=UserRole.PLAYER,
        is_active=True,
    )
    inactive_assistant = await quality_data_builder.coach(
        first_name="Inactive",
        last_name="Assistant",
        role=UserRole.ASSISTANT_COACH,
        is_active=False,
        version_number=4,
    )
    for actor in (head_coach, assistant_actor, player_actor):
        actor.hashed_password = PasswordService.hash_password(password)
    await quality_data_builder.coach_assignment(team=team, coach=head_coach)
    await quality_data_builder.coach_assignment(team=team, coach=player_actor)
    await quality_data_builder.coach_assignment(
        team=team,
        coach=inactive_assistant,
    )
    await quality_data_builder.player(
        first_name="Unassigned",
        last_name=f"Player {run_id}",
        date_of_birth=date(2013, 2, 10),
    )
    await quality_data_builder.commit()

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        head_headers = await _login(
            client,
            email=head_coach.email,
            password=password,
        )
        assistant_headers = await _login(
            client,
            email=assistant_actor.email,
            password=password,
        )
        player_headers = await _login(
            client,
            email=player_actor.email,
            password=password,
        )

        mixed = await client.get("/api/v1/data-quality", headers=head_headers)
        assert mixed.status_code == 200, mixed.text
        body = mixed.json()
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert body["total_findings"] == 5
        assert body["summary"] == {
            "total_findings": 5,
            "critical_count": 1,
            "warning_count": 3,
            "info_count": 1,
            "domain_counts": {
                "players": 1,
                "teams": 1,
                "rosters": 0,
                "coaches": 3,
                "calendar": 0,
            },
        }
        ordered_rule_ids = [item["rule_id"] for item in body["findings"]]
        assert ordered_rule_ids == [
            "coach.assignment_invalid_role",
            "player.active_unassigned",
            "team.roster_below_minimum",
            "coach.inactive_assigned",
            "coach.active_assistant_unassigned",
        ]
        repeated = await client.get("/api/v1/data-quality", headers=head_headers)
        assert repeated.status_code == 200
        assert repeated.json()["findings"] == body["findings"]
        assert await _business_audit_count() == 0

        filtered = await client.get(
            "/api/v1/data-quality",
            params={"severity": "warning", "domain": "coaches", "page_size": 1},
            headers=head_headers,
        )
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total_findings"] == 1
        assert filtered.json()["summary"] == body["summary"]
        assert filtered.json()["findings"][0]["rule_id"] == "coach.inactive_assigned"

        for denied_headers in (assistant_headers, player_headers):
            denied_read = await client.get(
                "/api/v1/data-quality",
                headers=denied_headers,
            )
            denied_write = await client.post(
                "/api/v1/data-quality/remediations",
                json={
                    "finding_id": "denied",
                    "action": "remove_inactive_assistant_assignment",
                    "coach_id": str(inactive_assistant.id),
                    "team_id": str(team.id),
                    "expected_coach_version": 4,
                    "confirmed": True,
                },
                headers=denied_headers,
            )
            assert denied_read.status_code == 403
            assert denied_write.status_code == 403
        assert await _business_audit_count() == 0

        healthy_head_coach = await client.get(
            "/api/v1/data-quality",
            params={"rule_id": "coach.sole_head_coach_integrity"},
            headers=head_headers,
        )
        assert healthy_head_coach.status_code == 200
        assert healthy_head_coach.json()["findings"] == []

        async with AsyncSessionFactory() as session:
            await session.execute(
                delete(TeamCoach).where(
                    TeamCoach.team_id == team.id,
                    TeamCoach.user_id == head_coach.id,
                )
            )
            await session.commit()
        broken_head_coach = await client.get(
            "/api/v1/data-quality",
            params={"rule_id": "coach.sole_head_coach_integrity"},
            headers=head_headers,
        )
        assert broken_head_coach.status_code == 200
        integrity_finding = broken_head_coach.json()["findings"][0]
        assert integrity_finding["severity"] == "critical"
        assert integrity_finding["direct_remediation"] is None
        async with AsyncSessionFactory() as session:
            session.add(TeamCoach(team_id=team.id, user_id=head_coach.id))
            await session.commit()

        current = await client.get(
            "/api/v1/data-quality",
            params={"rule_id": "coach.inactive_assigned"},
            headers=head_headers,
        )
        finding = current.json()["findings"][0]
        remediation = finding["direct_remediation"]
        command = {
            "finding_id": finding["finding_id"],
            "action": remediation["action"],
            "coach_id": remediation["coach_id"],
            "team_id": remediation["team_id"],
            "expected_coach_version": remediation["expected_coach_version"],
            "confirmed": False,
        }
        unconfirmed = await client.post(
            "/api/v1/data-quality/remediations",
            json=command,
            headers=head_headers,
        )
        assert unconfirmed.status_code == 400

        async with AsyncSessionFactory() as session:
            await session.execute(
                update(User)
                .where(User.id == inactive_assistant.id)
                .values(version_number=5)
            )
            await session.commit()
        stale = await client.post(
            "/api/v1/data-quality/remediations",
            json={**command, "confirmed": True},
            headers=head_headers,
        )
        assert stale.status_code == 409
        async with AsyncSessionFactory() as session:
            assert await session.get(
                TeamCoach,
                {"team_id": team.id, "user_id": inactive_assistant.id},
            ) is not None
        assert await _business_audit_count() == 0

        refreshed = await client.get(
            "/api/v1/data-quality",
            params={"rule_id": "coach.inactive_assigned"},
            headers=head_headers,
        )
        refreshed_finding = refreshed.json()["findings"][0]
        refreshed_remediation = refreshed_finding["direct_remediation"]
        applied = await client.post(
            "/api/v1/data-quality/remediations",
            json={
                "finding_id": refreshed_finding["finding_id"],
                "action": refreshed_remediation["action"],
                "coach_id": refreshed_remediation["coach_id"],
                "team_id": refreshed_remediation["team_id"],
                "expected_coach_version": refreshed_remediation[
                    "expected_coach_version"
                ],
                "confirmed": True,
            },
            headers={**head_headers, "X-Request-ID": f"quickstart-{run_id}"},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["audit_action"] == (
            AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED.value
        )
        resolved = await client.get(
            "/api/v1/data-quality",
            params={"rule_id": "coach.inactive_assigned"},
            headers=head_headers,
        )
        assert resolved.status_code == 200
        assert resolved.json()["findings"] == []

    async with AsyncSessionFactory() as session:
        assert await session.get(
            TeamCoach,
            {"team_id": team.id, "user_id": inactive_assistant.id},
        ) is None
        events = list((await session.scalars(select(BusinessAuditEvent))).all())
    assert len(events) == 1
    assert events[0].action_type == (
        AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED.value
    )
    assert events[0].request_id == f"quickstart-{run_id}"
    assert events[0].event_metadata["removed_team_ids"] == [str(team.id)]
