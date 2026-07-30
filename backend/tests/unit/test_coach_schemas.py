"""Unit tests for Coaches Portal response and request schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import UserRole
from src.schemas.coach import (
    CoachCreate,
    CoachResponse,
    CoachTeamUpdate,
    PaginatedCoachResponse,
)


def make_coach() -> CoachResponse:
    now = datetime.now(UTC)
    return CoachResponse(
        id=uuid4(),
        first_name="Vikram",
        last_name="Kumar",
        email="vikram@vkca.test",
        role=UserRole.HEAD_COACH,
        is_active=True,
        version_number=1,
        created_at=now,
        updated_at=now,
        teams=[],
    )


def test_coach_response_and_paginated_response_preserve_contract_fields() -> None:
    coach = make_coach()
    page = PaginatedCoachResponse(
        coaches=[coach],
        page=1,
        page_size=12,
        total_coaches=1,
        total_pages=1,
        has_previous=False,
        has_next=False,
    )

    assert page.coaches[0].email == "vikram@vkca.test"
    assert page.total_coaches == 1
    assert page.has_next is False


@pytest.mark.parametrize("email", ["invalid", "coach@", "coach @vkca.test"])
def test_coach_create_rejects_invalid_email(email: str) -> None:
    with pytest.raises(ValidationError, match="valid email"):
        CoachCreate(first_name="Asha", last_name="Patel", email=email)


def test_coach_create_normalizes_email_and_rejects_duplicate_team_ids() -> None:
    team_id = uuid4()
    coach = CoachCreate(
        first_name="Asha",
        last_name="Patel",
        email="  ASHA@VKCA.TEST ",
    )
    assert coach.email == "asha@vkca.test"

    with pytest.raises(ValidationError, match="duplicates"):
        CoachCreate(
            first_name="Asha",
            last_name="Patel",
            email="asha@vkca.test",
            team_ids=[team_id, team_id],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("first_name", ""),
        ("first_name", "   "),
        ("last_name", ""),
        ("email", ""),
        ("first_name", "A" * 101),
        ("last_name", "P" * 101),
        ("email", f"{'a' * 246}@vkca.test"),
    ],
)
def test_coach_create_validates_required_field_lengths(
    field: str,
    value: str,
) -> None:
    payload = {
        "first_name": "Asha",
        "last_name": "Patel",
        "email": "asha@vkca.test",
        field: value,
    }

    with pytest.raises(ValidationError):
        CoachCreate.model_validate(payload)


def test_coach_team_update_accepts_complete_unique_assignment_set() -> None:
    team_ids = [uuid4(), uuid4()]

    payload = CoachTeamUpdate(team_ids=team_ids, version_number=3)

    assert payload.team_ids == team_ids
    assert payload.version_number == 3


def test_coach_team_update_allows_clearing_assignments() -> None:
    payload = CoachTeamUpdate(team_ids=[], version_number=1)

    assert payload.team_ids == []


def test_coach_team_update_rejects_duplicates_and_invalid_versions() -> None:
    team_id = uuid4()

    with pytest.raises(ValidationError, match="duplicates"):
        CoachTeamUpdate(
            team_ids=[team_id, team_id],
            version_number=1,
        )

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        CoachTeamUpdate(team_ids=[], version_number=0)
