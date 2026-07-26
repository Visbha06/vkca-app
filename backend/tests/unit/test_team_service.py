"""Unit tests for team list and roster service behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import AgeGroup
from src.services.team_service import TeamNotFoundError, TeamService


def make_team():
    class TeamEntity:
        id = uuid4()
        name = "Falcons"
        age_group = AgeGroup.U13
        created_at = datetime.now(UTC)
        updated_at = datetime.now(UTC)
        version_number = 1

    return TeamEntity()


@pytest.mark.asyncio
async def test_list_teams_uses_stable_pagination_and_counts() -> None:
    team = make_team()
    session = Mock()
    session.scalar = AsyncMock(return_value=13)
    execute_result = Mock()
    execute_result.all.return_value = [(team, 8)]
    session.execute = AsyncMock(return_value=execute_result)

    result = await TeamService(session).list_teams(page=2, page_size=12)

    assert result.total_teams == 13
    assert result.total_pages == 2
    assert result.teams[0].player_count == 8
    statement = session.execute.await_args.args[0]
    assert "ORDER BY teams.name, teams.age_group, teams.id" in str(statement)
    assert "LIMIT" in str(statement)


@pytest.mark.asyncio
@pytest.mark.parametrize("page,page_size", [(0, 12), (1, 0), (1, 101)])
async def test_list_teams_rejects_invalid_page_bounds(
    page: int, page_size: int
) -> None:
    with pytest.raises(ValueError):
        await TeamService(Mock()).list_teams(page=page, page_size=page_size)


@pytest.mark.asyncio
async def test_get_team_roster_orders_and_includes_inactive_players() -> None:
    team_id = uuid4()
    player_id = uuid4()
    session = Mock()
    session.get = AsyncMock(return_value=Mock())
    execute_result = Mock()
    execute_result.all.return_value = [(player_id, "Asha", "Singh", False, 2)]
    session.execute = AsyncMock(return_value=execute_result)

    roster = await TeamService(session).get_team_roster(team_id)

    assert roster.players[0].is_active is False
    assert roster.players[0].roster_order == 2
    assert "ORDER BY team_players.roster_order ASC" in str(
        session.execute.await_args.args[0]
    )


@pytest.mark.asyncio
async def test_get_team_roster_rejects_unknown_team() -> None:
    session = Mock()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(TeamNotFoundError):
        await TeamService(session).get_team_roster(uuid4())
