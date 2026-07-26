"""Unit tests for team summary, mutation, and roster schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import AgeGroup
from src.schemas.team import (
    PaginatedTeamResponse,
    TeamCreate,
    TeamResponse,
    TeamRosterPlayerResponse,
    TeamRosterResponse,
    TeamUpdate,
)


def valid_player_ids() -> list[str]:
    return [str(uuid4()) for _ in range(7)]


def test_team_create_validates_complete_roster_payload() -> None:
    team = TeamCreate.model_validate(
        {"name": "U13 Lions", "age_group": "U13", "player_ids": valid_player_ids()}
    )

    assert team.age_group is AgeGroup.U13
    assert len(team.player_ids) == 7


@pytest.mark.parametrize("player_count", [0, 6, 16])
def test_team_create_rejects_rosters_outside_supported_size(player_count: int) -> None:
    with pytest.raises(ValidationError):
        TeamCreate.model_validate(
            {
                "name": "U13 Lions",
                "age_group": "U13",
                "player_ids": [str(uuid4()) for _ in range(player_count)],
            }
        )


def test_team_update_requires_a_positive_version_number() -> None:
    payload = {
        "name": "U13 Lions",
        "age_group": "U13",
        "player_ids": valid_player_ids(),
    }
    with pytest.raises(ValidationError):
        TeamUpdate.model_validate({**payload, "version_number": 0})


def test_team_response_and_pagination_include_player_count() -> None:
    now = datetime.now(UTC)
    team = TeamResponse(
        id=uuid4(),
        name="U13 Lions",
        age_group=AgeGroup.U13,
        player_count=8,
        created_at=now,
        updated_at=now,
        version_number=1,
    )
    page = PaginatedTeamResponse(
        teams=[team], page=1, page_size=12, total_teams=1, total_pages=1
    )

    assert page.model_dump(mode="json")["teams"][0]["player_count"] == 8


def test_roster_schema_serializes_player_identity_and_order() -> None:
    player = TeamRosterPlayerResponse(
        player_id=uuid4(),
        first_name="Asha",
        last_name="Singh",
        is_active=False,
        roster_order=2,
    )
    roster = TeamRosterResponse(team_id=uuid4(), players=[player])

    assert roster.players[0].is_active is False
    assert roster.players[0].roster_order == 2
