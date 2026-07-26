"""Unit tests for team list and atomic roster mutation behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import AgeGroup
from src.models.team import Team
from src.schemas.team import TeamCreate, TeamUpdate
from src.services.occ import StaleVersionError
from src.services.team_service import (
    PlayerNotFoundError,
    TeamNameConflictError,
    TeamNotFoundError,
    TeamService,
    TeamValidationError,
)


def make_team():
    class TeamEntity:
        id = uuid4()
        name = "Falcons"
        age_group = AgeGroup.U13
        created_at = datetime.now(UTC)
        updated_at = datetime.now(UTC)
        version_number = 1

    return TeamEntity()


def make_player_ids(count: int = 7):
    return [uuid4() for _ in range(count)]


def make_create_payload(player_ids=None):
    return TeamCreate(
        name="  Falcons  ",
        age_group=AgeGroup.U13,
        player_ids=player_ids or make_player_ids(),
    )


def roster_result(player_ids, *, active: bool = True):
    result = Mock()
    result.all.return_value = [(player_id, active) for player_id in player_ids]
    return result


async def populate_team_defaults(team: Team) -> None:
    now = datetime.now(UTC)
    team.id = team.id or uuid4()
    team.created_at = now
    team.updated_at = now
    team.version_number = team.version_number or 1


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


@pytest.mark.asyncio
async def test_create_team_persists_the_complete_roster_atomically() -> None:
    player_ids = make_player_ids(8)
    session = Mock()
    session.execute = AsyncMock(return_value=roster_result(player_ids))
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock(side_effect=populate_team_defaults)

    result = await TeamService(session).create_team(make_create_payload(player_ids))

    assert result.name == "Falcons"
    assert result.player_count == 8
    assert session.flush.await_count == 2
    session.commit.assert_awaited_once()
    memberships = session.add_all.call_args.args[0]
    assert [membership.player_id for membership in memberships] == player_ids
    assert [membership.roster_order for membership in memberships] == list(range(1, 9))


@pytest.mark.asyncio
async def test_create_team_rejects_duplicate_missing_and_inactive_players() -> None:
    duplicate_id = uuid4()
    duplicate_payload = TeamCreate.model_construct(
        name="Falcons",
        age_group=AgeGroup.U13,
        player_ids=[duplicate_id] * 7,
    )
    duplicate_session = Mock()
    duplicate_session.rollback = AsyncMock()

    with pytest.raises(TeamValidationError, match="duplicate"):
        await TeamService(duplicate_session).create_team(duplicate_payload)
    duplicate_session.rollback.assert_awaited_once()

    player_ids = make_player_ids()
    missing_session = Mock()
    missing_session.execute = AsyncMock(
        return_value=roster_result(player_ids[:-1])
    )
    missing_session.rollback = AsyncMock()
    with pytest.raises(PlayerNotFoundError):
        await TeamService(missing_session).create_team(
            make_create_payload(player_ids)
        )
    missing_session.rollback.assert_awaited_once()

    inactive_session = Mock()
    inactive_session.execute = AsyncMock(
        return_value=roster_result(player_ids, active=False)
    )
    inactive_session.rollback = AsyncMock()
    with pytest.raises(TeamValidationError, match="active"):
        await TeamService(inactive_session).create_team(
            make_create_payload(player_ids)
        )
    inactive_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_team_rejects_normalized_name_conflicts() -> None:
    player_ids = make_player_ids()
    session = Mock()
    session.execute = AsyncMock(return_value=roster_result(player_ids))
    session.scalar = AsyncMock(return_value=uuid4())
    session.rollback = AsyncMock()

    with pytest.raises(TeamNameConflictError):
        await TeamService(session).create_team(make_create_payload(player_ids))

    uniqueness_statement = session.scalar.await_args.args[0]
    uniqueness_sql = str(uniqueness_statement).lower()
    assert "lower(trim(teams.name)) = lower(trim(" in uniqueness_sql
    assert "teams.age_group" in uniqueness_sql
    session.rollback.assert_awaited_once()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_team_rolls_back_when_persistence_fails() -> None:
    player_ids = make_player_ids()
    session = Mock()
    session.execute = AsyncMock(return_value=roster_result(player_ids))
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.refresh = AsyncMock(side_effect=populate_team_defaults)
    session.commit = AsyncMock(side_effect=RuntimeError("database unavailable"))
    session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="database unavailable"):
        await TeamService(session).create_team(make_create_payload(player_ids))

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_team_replaces_the_roster_and_increments_version(mocker) -> None:
    team_id = uuid4()
    player_ids = make_player_ids(8)
    team = Team(name="Falcons", age_group=AgeGroup.U13)
    team.id = team_id
    await populate_team_defaults(team)
    session = Mock()
    session.get = AsyncMock(return_value=team)
    session.execute = AsyncMock(
        side_effect=[roster_result(player_ids), Mock()]
    )
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock(side_effect=populate_team_defaults)
    version_check = mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(return_value=2),
    )
    payload = TeamUpdate(
        name="Eagles",
        age_group=AgeGroup.U15,
        player_ids=player_ids,
        version_number=1,
    )

    result = await TeamService(session).update_team(team_id, payload)

    version_check.assert_awaited_once_with(session, Team, team_id, 1)
    assert result.name == "Eagles"
    assert result.age_group is AgeGroup.U15
    assert result.version_number == 2
    assert result.player_count == 8
    delete_statement = session.execute.await_args_list[1].args[0]
    assert "DELETE FROM team_players" in str(delete_statement)
    uniqueness_statement = session.scalar.await_args.args[0]
    assert "teams.id !=" in str(uniqueness_statement)
    memberships = session.add_all.call_args.args[0]
    assert [membership.player_id for membership in memberships] == player_ids
    assert [membership.roster_order for membership in memberships] == list(range(1, 9))


@pytest.mark.asyncio
async def test_update_team_rolls_back_when_roster_replacement_fails(mocker) -> None:
    team_id = uuid4()
    player_ids = make_player_ids()
    team = Team(name="Falcons", age_group=AgeGroup.U13)
    team.id = team_id
    await populate_team_defaults(team)
    session = Mock()
    session.get = AsyncMock(return_value=team)
    session.execute = AsyncMock(
        side_effect=[roster_result(player_ids), Mock()]
    )
    session.scalar = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    session.refresh = AsyncMock(side_effect=populate_team_defaults)
    session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    session.rollback = AsyncMock()
    mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(return_value=2),
    )
    payload = TeamUpdate(
        name="Eagles",
        age_group=AgeGroup.U15,
        player_ids=player_ids,
        version_number=1,
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await TeamService(session).update_team(team_id, payload)

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_team_rolls_back_stale_versions(mocker) -> None:
    team_id = uuid4()
    team = Team(name="Falcons", age_group=AgeGroup.U13)
    team.id = team_id
    session = Mock()
    session.get = AsyncMock(return_value=team)
    session.rollback = AsyncMock()
    mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(side_effect=StaleVersionError(Team, team_id, 1)),
    )
    payload = TeamUpdate(
        name="Falcons",
        age_group=AgeGroup.U13,
        player_ids=make_player_ids(),
        version_number=1,
    )

    with pytest.raises(StaleVersionError):
        await TeamService(session).update_team(team_id, payload)

    session.rollback.assert_awaited_once()
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_team_rejects_unknown_teams() -> None:
    session = Mock()
    session.get = AsyncMock(return_value=None)
    session.rollback = AsyncMock()
    payload = TeamUpdate(
        name="Falcons",
        age_group=AgeGroup.U13,
        player_ids=make_player_ids(),
        version_number=1,
    )

    with pytest.raises(TeamNotFoundError):
        await TeamService(session).update_team(uuid4(), payload)

    session.rollback.assert_awaited_once()
