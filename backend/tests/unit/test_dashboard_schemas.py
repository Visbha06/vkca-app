"""Contract tests for the bounded role-aware dashboard response."""

from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.schemas.dashboard import DashboardResponse


def dashboard_payload() -> dict[str, object]:
    """Return one complete Head Coach response payload."""

    team_id = uuid4()
    return {
        "user": {
            "id": str(uuid4()),
            "display_name": "Asha Coach",
            "role": "head coach",
        },
        "dashboard_state": "ready",
        "summary": {
            "training": {
                "status": "ready",
                "data": {
                    "occurrence_id": "practice-1",
                    "event_date": "2026-08-12",
                    "start_time": "17:00:00",
                    "end_time": "18:30:00",
                    "name": "Batting fundamentals",
                    "event_type": "practice",
                    "age_groups": ["U15"],
                },
            },
            "next_match": {
                "status": "ready",
                "data": {
                    "id": str(uuid4()),
                    "match_date": "2026-08-15",
                    "format": "T20",
                    "participants": {
                        "kind": "external",
                        "academy_team": {
                            "id": str(team_id),
                            "name": "U15 Falcons",
                        },
                        "opponent_name": "Northside CC",
                        "academy_side": "home",
                    },
                },
            },
            "player_slot": {
                "status": "ready",
                "data": {
                    "kind": "active_player_count",
                    "count": 42,
                    "team_count": 4,
                },
            },
        },
        "upcoming_events": {"status": "ready", "data": []},
        "context": {
            "status": "ready",
            "data": {
                "kind": "recent_activity",
                "events": [],
                "view_all_path": "/audit-log",
            },
        },
    }


def test_response_accepts_discriminated_role_specific_slots_and_participants() -> None:
    payload = dashboard_payload()
    payload["user"]["role"] = "player"  # type: ignore[index]
    payload["summary"]["next_match"]["data"]["participants"] = {  # type: ignore[index]
        "kind": "internal",
        "home_team": {"id": str(uuid4()), "name": "U13 Falcons"},
        "away_team": {"id": str(uuid4()), "name": "U15 Falcons"},
    }
    payload["summary"]["player_slot"]["data"] = {  # type: ignore[index]
        "kind": "player_teams",
        "team_count": 2,
        "team_names": ["U13 Falcons", "U15 Falcons"],
    }
    payload["context"] = {
        "status": "ready",
        "data": {
            "kind": "my_teams",
            "teams": [],
            "view_all_path": "/teams",
        },
    }

    response = DashboardResponse.model_validate(payload)

    assert response.summary.next_match.status == "ready"
    assert response.summary.next_match.data.participants.kind == "internal"
    assert response.summary.player_slot.data.kind == "player_teams"


@pytest.mark.parametrize("status", ["empty", "unavailable"])
def test_response_represents_explicit_non_ready_section_states(status: str) -> None:
    payload = dashboard_payload()
    section: dict[str, object] = {
        "status": status,
        "message": "Contact your Head Coach for help.",
    }
    if status == "unavailable":
        section["retryable"] = True
    payload["upcoming_events"] = section

    response = DashboardResponse.model_validate(payload)

    assert response.upcoming_events.status == status
    assert "data" not in response.upcoming_events.model_dump()


def test_response_represents_a_fully_limited_unlinked_player() -> None:
    payload = dashboard_payload()
    payload["user"]["role"] = "player"  # type: ignore[index]
    payload["dashboard_state"] = "unlinked"
    unlinked = {
        "status": "unlinked",
        "message": "Contact your Head Coach for help.",
    }
    payload["summary"] = {
        "training": unlinked,
        "next_match": unlinked,
        "player_slot": unlinked,
    }
    payload["upcoming_events"] = unlinked
    payload["context"] = unlinked

    response = DashboardResponse.model_validate(payload)

    assert response.dashboard_state == "unlinked"
    assert response.context.status == "unlinked"


def test_response_rejects_client_scope_fields_and_ambiguous_sections() -> None:
    payload = dashboard_payload()
    payload["team_ids"] = [str(uuid4())]
    with pytest.raises(ValidationError):
        DashboardResponse.model_validate(payload)

    payload = dashboard_payload()
    payload["upcoming_events"] = {"status": "empty", "message": "None", "data": []}
    with pytest.raises(ValidationError):
        DashboardResponse.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "items"),
    [
        ("upcoming_events", 6),
        ("context_teams", 13),
        ("context_activity", 5),
    ],
)
def test_response_enforces_presentation_bounds(path: str, items: int) -> None:
    payload = deepcopy(dashboard_payload())
    if path == "upcoming_events":
        event = payload["summary"]["training"]["data"]  # type: ignore[index]
        payload["upcoming_events"] = {
            "status": "ready",
            "data": [deepcopy(event) for _ in range(items)],
        }
    elif path == "context_teams":
        payload["context"] = {
            "status": "ready",
            "data": {
                "kind": "my_teams",
                "teams": [
                    {
                        "id": str(uuid4()),
                        "name": f"Team {index}",
                        "age_group": "U15",
                        "active_player_count": 0,
                        "coaches": [],
                        "next_event": None,
                    }
                    for index in range(items)
                ],
                "view_all_path": "/teams",
            },
        }
    else:
        payload["context"] = {
            "status": "ready",
            "data": {
                "kind": "recent_activity",
                "events": [
                    {
                        "id": str(uuid4()),
                        "actor_display_name": "Asha Coach",
                        "action_type": "player.created",
                        "action_category": "player",
                        "target_label": f"Player {index}",
                        "summary": f"Added Player {index}",
                        "created_at": "2026-08-10T12:00:00Z",
                    }
                    for index in range(items)
                ],
                "view_all_path": "/audit-log",
            },
        }

    with pytest.raises(ValidationError):
        DashboardResponse.model_validate(payload)
