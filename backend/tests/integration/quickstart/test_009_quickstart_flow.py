"""Executable quickstart coverage for business audit capture and retrieval."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select

from src.database import AsyncSessionFactory
from src.enums import AuditActionType, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.models.user import User


def player_payload(run_id: str, index: int) -> dict[str, str]:
    """Build one valid, uniquely identifiable player request."""

    return {
        "first_name": f"Quickstart-{index}-{run_id}",
        "last_name": "Player",
        "date_of_birth": f"2009-02-{index + 1:02d}",
        "batting_style": "right",
        "bowling_style": "right-arm medium",
        "player_type": "all-rounder",
    }


def actor(role: UserRole, run_id: str) -> User:
    """Build an authenticated actor snapshot without requiring a live FK."""

    return User(
        id=uuid4(),
        first_name=(
            f"Aaa-{run_id}" if role is UserRole.HEAD_COACH else role.value.title()
        ),
        last_name=(
            "Head Coach" if role is UserRole.HEAD_COACH else f"Quickstart-{run_id}"
        ),
        email=f"{role.value.replace(' ', '-')}-{run_id}@example.test",
        hashed_password="unused-dependency-override",
        role=role,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_business_audit_quickstart_flow() -> None:
    """Run the documented capture, rollback, history, bounds, and role flow."""

    run_id = uuid4().hex[:8]
    head_coach = actor(UserRole.HEAD_COACH, run_id)
    assistant_coach = actor(UserRole.ASSISTANT_COACH, run_id)
    player_actor = actor(UserRole.PLAYER, run_id)
    current_actor = {"user": head_coach}
    player_ids: list[UUID] = []
    team_id: UUID | None = None

    async def override_current_user():
        return current_actor["user"], Mock(spec=AuthSession)

    app.dependency_overrides[get_current_user] = override_current_user
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            for index in range(8):
                response = await client.post(
                    "/api/v1/players",
                    json=player_payload(run_id, index),
                )
                assert response.status_code == 201, response.text
                player_ids.append(UUID(response.json()["id"]))

            created_team = await client.post(
                "/api/v1/teams",
                json={
                    "name": f"Quickstart Falcons {run_id}",
                    "age_group": "U15",
                    "player_ids": [str(player_id) for player_id in player_ids[:7]],
                },
            )
            assert created_team.status_code == 201, created_team.text
            team_id = UUID(created_team.json()["id"])

            async with AsyncSessionFactory() as session:
                before_composite = int(
                    await session.scalar(
                        select(func.count(BusinessAuditEvent.id)).where(
                            BusinessAuditEvent.actor_user_id == head_coach.id
                        )
                    )
                    or 0
                )

            composite = await client.put(
                f"/api/v1/teams/{team_id}",
                json={
                    "name": f"Quickstart Hawks {run_id}",
                    "age_group": "U15",
                    "player_ids": [
                        str(player_id)
                        for player_id in [*player_ids[1:7], player_ids[7]]
                    ],
                    "version_number": 1,
                },
            )
            assert composite.status_code == 200, composite.text

            async with AsyncSessionFactory() as session:
                composite_events = list(
                    (
                        await session.scalars(
                            select(BusinessAuditEvent)
                            .where(BusinessAuditEvent.actor_user_id == head_coach.id)
                            .order_by(
                                BusinessAuditEvent.created_at, BusinessAuditEvent.id
                            )
                        )
                    ).all()
                )
            assert len(composite_events) == before_composite + 1
            composite_event = composite_events[-1]
            assert composite_event.action_type == AuditActionType.TEAM_UPDATED.value
            assert composite_event.event_metadata["roster_replaced"] is True
            assert "password" not in str(composite_event.event_metadata).lower()

            failed_payload = player_payload(run_id, 8)
            with patch(
                "src.services.player_service.BusinessAuditService.record",
                new=AsyncMock(side_effect=RuntimeError("simulated audit failure")),
            ):
                failed = await client.post("/api/v1/players", json=failed_payload)
            assert failed.status_code == 500
            failed_target_label = (
                f"{failed_payload['first_name']} {failed_payload['last_name']}"
            )
            async with AsyncSessionFactory() as session:
                failed_player = await session.scalar(
                    select(Player).where(
                        Player.first_name == failed_payload["first_name"],
                        Player.last_name == failed_payload["last_name"],
                    )
                )
                failed_event = await session.scalar(
                    select(BusinessAuditEvent).where(
                        BusinessAuditEvent.actor_user_id == head_coach.id,
                        BusinessAuditEvent.target_label == failed_target_label,
                    )
                )
            assert failed_player is None
            assert failed_event is None

            full_log = await client.get(
                "/api/v1/audit-log",
                params={
                    "actor_user_id": str(head_coach.id),
                    "page": 1,
                    "page_size": 20,
                },
            )
            assert full_log.status_code == 200, full_log.text
            full_json = full_log.json()
            assert full_json["total_events"] == before_composite + 1
            ordering = [
                (item["created_at"], item["id"]) for item in full_json["events"]
            ]
            assert ordering == sorted(ordering, reverse=True)

            filtered = await client.get(
                "/api/v1/audit-log",
                params={
                    "actor_user_id": str(head_coach.id),
                    "action_category": "team",
                    "action_type": "team.updated",
                    "entity_type": "team",
                    "target_entity_id": str(team_id),
                    "start_date": datetime.now(UTC).date().isoformat(),
                    "end_date": datetime.now(UTC).date().isoformat(),
                },
            )
            assert filtered.status_code == 200, filtered.text
            assert filtered.json()["total_events"] == 1

            actors = await client.get("/api/v1/audit-log/actors")
            assert actors.status_code == 200, actors.text
            actor_options = actors.json()["actors"]
            assert len(actor_options) <= 100
            assert len({item["actor_user_id"] for item in actor_options}) == len(
                actor_options
            )
            assert [
                item["actor_display_name"].lower() for item in actor_options
            ] == sorted(item["actor_display_name"].lower() for item in actor_options)
            assert {
                "actor_user_id": str(head_coach.id),
                "actor_display_name": f"Aaa-{run_id} Head Coach",
                "actor_role": "head coach",
            } in actor_options

            recent = await client.get("/api/v1/audit-log/recent", params={"limit": 4})
            assert recent.status_code == 200, recent.text
            assert 1 <= len(recent.json()["events"]) <= 4
            excessive_recent = await client.get(
                "/api/v1/audit-log/recent", params={"limit": 5}
            )
            assert excessive_recent.status_code == 422
            excessive_dates = await client.get(
                "/api/v1/audit-log",
                params={"start_date": "2025-01-01", "end_date": "2026-01-02"},
            )
            assert excessive_dates.status_code == 422

            empty = await client.get(
                "/api/v1/audit-log",
                params={"actor_user_id": str(uuid4())},
            )
            assert empty.status_code == 200
            assert empty.json() == {
                "events": [],
                "page": 1,
                "page_size": 20,
                "total_events": 0,
                "total_pages": 0,
                "has_previous": False,
                "has_next": False,
            }

            with patch(
                "src.middleware.auth.AuditService.log_event",
                new=AsyncMock(),
            ):
                for unauthorized_actor in (assistant_coach, player_actor):
                    current_actor["user"] = unauthorized_actor
                    for path in (
                        "/api/v1/audit-log",
                        "/api/v1/audit-log/actors",
                        "/api/v1/audit-log/recent?limit=4",
                    ):
                        denied = await client.get(path)
                        assert denied.status_code == 403
                        assert denied.json() == {"detail": "Not authorized"}

            current_actor["user"] = head_coach
            head_coach.first_name = "Renamed"
            assert team_id is not None
            async with AsyncSessionFactory() as session:
                await session.execute(
                    delete(TeamPlayer).where(TeamPlayer.team_id == team_id)
                )
                await session.execute(delete(Team).where(Team.id == team_id))
                await session.commit()

            historical = await client.get(
                "/api/v1/audit-log",
                params={"target_entity_id": str(team_id)},
            )
            assert historical.status_code == 200, historical.text
            historical_items = historical.json()["events"]
            assert len(historical_items) == 2
            assert {item["target_label"] for item in historical_items} == {
                f"Quickstart Falcons {run_id}",
                f"Quickstart Hawks {run_id}",
            }
            assert {item["actor_display_name"] for item in historical_items} == {
                f"Aaa-{run_id} Head Coach"
            }
    finally:
        app.dependency_overrides.clear()
        async with AsyncSessionFactory() as session:
            await session.execute(
                delete(BusinessAuditEvent).where(
                    BusinessAuditEvent.actor_user_id == head_coach.id
                )
            )
            if team_id is not None:
                await session.execute(
                    delete(TeamPlayer).where(TeamPlayer.team_id == team_id)
                )
                await session.execute(delete(Team).where(Team.id == team_id))
            if player_ids:
                await session.execute(
                    delete(TeamPlayer).where(TeamPlayer.player_id.in_(player_ids))
                )
                await session.execute(delete(Player).where(Player.id.in_(player_ids)))
            await session.commit()
