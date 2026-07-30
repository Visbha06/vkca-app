"""Unit tests for paginated coach directory queries."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import UserRole
from src.services.coach_service import CoachService


class CoachEntity:
    def __init__(self, *, role: UserRole = UserRole.HEAD_COACH) -> None:
        now = datetime.now(UTC)
        self.id = uuid4()
        self.first_name = "Vikram"
        self.last_name = "Kumar"
        self.email = "vikram@vkca.test"
        self.role = role
        self.is_active = True
        self.version_number = 1
        self.created_at = now
        self.updated_at = now


@pytest.mark.asyncio
async def test_list_coaches_filters_active_accounts_and_calculates_pages() -> None:
    coach = CoachEntity()
    session = Mock()
    session.scalar = AsyncMock(return_value=13)
    rows = Mock()
    rows.all.return_value = [(coach, None, None)]
    session.execute = AsyncMock(return_value=rows)

    result = await CoachService(session).list_coaches(
        status="active", page=2, page_size=12
    )

    assert result.total_coaches == 13
    assert result.total_pages == 2
    assert result.has_previous is True
    assert result.has_next is False
    statement = session.execute.await_args.args[0]
    sql = str(statement)
    assert "users.is_active IS true" in sql
    assert "ORDER BY CASE" in sql
    assert "LIMIT" in sql and "OFFSET" in sql


@pytest.mark.asyncio
async def test_list_coaches_supports_inactive_and_all_statuses() -> None:
    expectations = (
        ("inactive", "users.is_active IS false"),
        ("all", "WHERE users.role"),
    )
    for status, fragment in expectations:
        session = Mock()
        session.scalar = AsyncMock(return_value=0)
        rows = Mock()
        rows.all.return_value = []
        session.execute = AsyncMock(return_value=rows)

        result = await CoachService(session).list_coaches(status=status)

        assert result.coaches == []
        assert fragment in str(session.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_list_coaches_rejects_invalid_pagination_and_status() -> None:
    service = CoachService(Mock())
    with pytest.raises(ValueError):
        await service.list_coaches(status="unknown")
    with pytest.raises(ValueError):
        await service.list_coaches(page=0)
    with pytest.raises(ValueError):
        await service.list_coaches(page_size=101)


@pytest.mark.asyncio
async def test_get_coach_loads_team_assignments_and_excludes_non_coaches() -> None:
    coach = CoachEntity(role=UserRole.ASSISTANT_COACH)
    session = Mock()
    rows = Mock()
    team_id = uuid4()
    rows.all.return_value = [(coach, team_id, "U13 Lions")]
    session.execute = AsyncMock(return_value=rows)

    result = await CoachService(session).get_coach(coach.id)

    assert result.id == coach.id
    assert result.teams[0].name == "U13 Lions"
    statement = session.execute.await_args.args[0]
    assert "users.role IN" in str(statement)
    assert "team_coaches" in str(statement)
