"""Allowlisted scoring Business Audit behavior through authenticated commands."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from src.database import AsyncSessionFactory
from src.enums import AuditActionType, MatchSideCode
from src.main import app
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.scoring.innings import Innings
from src.models.user import User
from src.services.business_audit_service import BusinessAuditService
from src.services.scoring.audit import record_scoring_initialization
from tests.integration.test_match_scoring_api import _phase7_configuration


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as value:
        yield value


@pytest_asyncio.fixture(loop_scope="session")
async def audit_match_ids(authenticated_client):
    ids: list[UUID] = []
    try:
        yield ids
    finally:
        async with AsyncSessionFactory() as session:
            for match_id in ids:
                await session.execute(
                    delete(Innings).where(Innings.match_id == match_id)
                )
                await session.execute(delete(Match).where(Match.id == match_id))
            await session.commit()


async def _event_snapshot(match_id: UUID) -> list[BusinessAuditEvent]:
    async with AsyncSessionFactory() as session:
        return list(
            (
                await session.scalars(
                    select(BusinessAuditEvent)
                    .where(BusinessAuditEvent.target_entity_id == match_id)
                    .order_by(BusinessAuditEvent.created_at, BusinessAuditEvent.id)
                )
            ).all()
        )


async def _append(client, match_id: str, innings: dict, **facts):
    response = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings['id']}/deliveries",
        json={
            "innings_version_number": innings["version_number"],
            "attempted_sequence": innings["legal_balls"] + 1,
            "striker_participant_id": innings["striker_participant_id"],
            "non_striker_participant_id": innings["non_striker_participant_id"],
            "bowler_participant_id": innings["current_bowler_participant_id"],
            "runs_off_bat": 0,
            **facts,
        },
    )
    assert response.status_code == 200, response.text
    refreshed = await client.get(f"/api/v1/matches/{match_id}/innings/{innings['id']}")
    assert refreshed.status_code == 200, refreshed.text
    return refreshed.json(), response.json()


async def _take_wickets(client, match_id: str, innings: dict, batters, bowlers):
    state = innings
    previous_bowler = state["current_bowler_participant_id"]
    for wicket_number in range(10):
        if state["current_bowler_participant_id"] is None:
            next_bowler_id = bowlers[1] if previous_bowler == bowlers[0] else bowlers[0]
            chosen = await client.post(
                f"/api/v1/matches/{match_id}/innings/{state['id']}/next-bowler",
                json={
                    "innings_version_number": state["version_number"],
                    "bowler_participant_id": next_bowler_id,
                    "override_reason": "Rotate after completed over",
                },
            )
            assert chosen.status_code == 200, chosen.text
            state = chosen.json()
            previous_bowler = next_bowler_id
        else:
            previous_bowler = state["current_bowler_participant_id"]

        dismissed = state["striker_participant_id"]
        state, _ = await _append(
            client,
            match_id,
            state,
            wicket={
                "dismissal_type": "bowled",
                "dismissed_participant_id": dismissed,
                "fielders": [],
            },
        )
        if wicket_number < 9:
            next_batter = await client.post(
                f"/api/v1/matches/{match_id}/innings/{state['id']}/next-batter",
                json={
                    "innings_version_number": state["version_number"],
                    "batter_participant_id": batters[wicket_number + 2],
                    "replacing_participant_id": dismissed,
                    "reason": "Dismissed",
                },
            )
            assert next_batter.status_code == 200, next_batter.text
            state = next_batter.json()
    assert state["lifecycle_state"] == "completed"
    return state


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_scoring_audit_allowlist_and_rollback(client, audit_match_ids):
    """Record only five public scoring action kinds, with bounded snapshots."""

    config, participants = await _phase7_configuration(
        client, "T20", False, audit_match_ids
    )
    match_id = config["match_id"]
    match_uuid = UUID(match_id)
    initialized = await _event_snapshot(match_uuid)
    assert [event.action_type for event in initialized] == [
        AuditActionType.SCORING_INITIALIZED.value
    ]
    assert initialized[0].actor_user_id is not None
    assert initialized[0].actor_role == "head coach"
    assert initialized[0].target_entity_type == "match"
    assert initialized[0].event_metadata == {
        "capability_profile": "T20",
        "capability_version": 1,
        "innings_sequence": ["home", "away"],
        "participant_count": 22,
    }

    first = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": config["match_version_number"],
            "innings_number": 1,
            "opening_striker_participant_id": participants["home"][0],
            "opening_non_striker_participant_id": participants["home"][1],
            "opening_bowler_participant_id": participants["away"][0],
        },
    )
    assert first.status_code == 200, first.text
    state = first.json()
    base = f"/api/v1/matches/{match_id}/innings/{state['id']}"

    retired = await client.post(
        base + "/retired-hurt",
        json={
            "innings_version_number": state["version_number"],
            "participant_id": state["striker_participant_id"],
            "reason": "Medical check",
        },
    )
    assert retired.status_code == 200, retired.text
    returned = await client.post(
        base + "/retired-hurt-return",
        json={
            "innings_version_number": retired.json()["version_number"],
            "participant_id": state["striker_participant_id"],
            "reason": "Cleared to return",
        },
    )
    assert returned.status_code == 200, returned.text
    state, _ = await _append(client, match_id, returned.json())
    for _ in range(5):
        state, _ = await _append(client, match_id, state)
    assert state["current_bowler_participant_id"] is None
    next_bowler = await client.post(
        base + "/next-bowler",
        json={
            "innings_version_number": state["version_number"],
            "bowler_participant_id": participants["away"][1],
            "override_reason": "Change of tactics",
        },
    )
    assert next_bowler.status_code == 200, next_bowler.text
    state = next_bowler.json()
    await _take_wickets(
        client, match_id, state, participants["home"], participants["away"]
    )

    second = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": (
                await client.get(f"/api/v1/matches/{match_id}/scorecard")
            ).json()["match_version_number"],
            "innings_number": 2,
            "opening_striker_participant_id": participants["away"][0],
            "opening_non_striker_participant_id": participants["away"][1],
            "opening_bowler_participant_id": participants["home"][0],
        },
    )
    assert second.status_code == 200, second.text
    state = second.json()
    state, delivery = await _append(client, match_id, state, runs_off_bat=1)
    assert state["lifecycle_state"] == "completed"
    match_id_from_response = state["match_id"]
    history = await client.get(
        f"/api/v1/matches/{match_id_from_response}/innings/{state['id']}/deliveries"
    )
    assert history.status_code == 200, history.text
    recorded = history.json()["deliveries"][0]
    match = await client.get(f"/api/v1/matches/{match_id}/scorecard")
    correction_body = {
        "match_version_number": match.json()["match_version_number"],
        "innings_version_number": state["version_number"],
        "expected_revision_number": recorded["active_revision"]["revision_number"],
        "reason": "Correct the observed winning boundary",
        "replacement": {
            "striker_participant_id": delivery["active_revision"][
                "striker_participant_id"
            ],
            "non_striker_participant_id": delivery["active_revision"][
                "non_striker_participant_id"
            ],
            "bowler_participant_id": delivery["active_revision"][
                "bowler_participant_id"
            ],
            "runs_off_bat": 2,
            "extras": {},
        },
    }
    correction_path = (
        f"/api/v1/matches/{match_id}/innings/{state['id']}/deliveries/"
        f"{delivery['id']}/correction"
    )
    corrected = await client.post(correction_path, json=correction_body)
    assert corrected.status_code == 200, corrected.text
    stale = await client.post(correction_path, json=correction_body)
    assert stale.status_code == 409

    events = await _event_snapshot(match_uuid)
    action_types = [event.action_type for event in events]
    assert action_types.count(AuditActionType.SCORING_INITIALIZED.value) == 1
    assert action_types.count(AuditActionType.SCORING_INNINGS_STARTED.value) == 2
    assert action_types.count(AuditActionType.SCORING_INNINGS_COMPLETED.value) == 2
    assert action_types.count(AuditActionType.SCORING_MATCH_COMPLETED.value) == 1
    assert action_types.count(AuditActionType.SCORING_DELIVERY_CORRECTED.value) == 1
    assert len(events) == 7
    assert all(event.actor_user_id is not None for event in events)
    assert all(event.target_entity_type == "match" for event in events)
    assert all(len(event.summary) <= 500 for event in events)
    assert all(
        len(str(value)) <= 500
        for event in events
        for value in event.event_metadata.values()
        if isinstance(value, str)
    )
    assert all(
        not {"runs_off_bat", "wide_runs", "delivery_payload"}
        & set(event.event_metadata)
        for event in events
    )
    # The stale correction failed in the caller transaction and produced no event.
    assert len(await _event_snapshot(match_uuid)) == len(events)

    # A flushed allowlisted event remains part of its caller's transaction.
    async with AsyncSessionFactory() as session:
        actor = await session.get(User, events[0].actor_user_id)
        match_row = await session.get(Match, match_uuid)
        assert actor is not None and match_row is not None
        await record_scoring_initialization(
            BusinessAuditService(session),
            actor=actor,
            match=match_row,
            capability_profile="T20",
            capability_version=1,
            innings_sequence=(MatchSideCode.HOME, MatchSideCode.AWAY),
            participant_count=22,
        )
        staged_count = await session.scalar(
            select(func.count(BusinessAuditEvent.id)).where(
                BusinessAuditEvent.target_entity_id == match_uuid
            )
        )
        assert staged_count == len(events) + 1
        await session.rollback()
    assert len(await _event_snapshot(match_uuid)) == len(events)
