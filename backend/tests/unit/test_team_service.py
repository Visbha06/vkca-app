"""Unit tests for team list and atomic roster mutation behavior."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import AgeGroup, AuditActionType, UserRole
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.schemas.team import TeamCreate, TeamUpdate
from src.services.business_audit_service import AuditActorContext
from src.services.occ import StaleVersionError
from src.services.team_service import (
    PlayerNotFoundError,
    TeamNameConflictError,
    TeamNotFoundError,
    TeamRemediationConflictError,
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
    missing_session.execute = AsyncMock(return_value=roster_result(player_ids[:-1]))
    missing_session.rollback = AsyncMock()
    with pytest.raises(PlayerNotFoundError):
        await TeamService(missing_session).create_team(make_create_payload(player_ids))
    missing_session.rollback.assert_awaited_once()

    inactive_session = Mock()
    inactive_session.execute = AsyncMock(
        return_value=roster_result(player_ids, active=False)
    )
    inactive_session.rollback = AsyncMock()
    with pytest.raises(TeamValidationError, match="active"):
        await TeamService(inactive_session).create_team(make_create_payload(player_ids))
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
    session.execute = AsyncMock(side_effect=[roster_result(player_ids), Mock()])
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
    session.execute = AsyncMock(side_effect=[roster_result(player_ids), Mock()])
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


def remediation_actor() -> AuditActorContext:
    return AuditActorContext(
        user_id=uuid4(),
        display_name="Asha Head Coach",
        role=UserRole.HEAD_COACH,
    )


@pytest.mark.asyncio
async def test_normalize_roster_order_preserves_membership_and_reuses_audit_action(
    mocker,
) -> None:
    team = make_team()
    team.version_number = 3
    positions = (1, 2, 4, 5, 6, 7, 8)
    memberships = [
        SimpleNamespace(player_id=uuid4(), roster_order=position)
        for position in positions
    ]
    membership_result = Mock()
    membership_result.all.return_value = memberships
    session = Mock()
    session.get = AsyncMock(return_value=team)
    session.scalars = AsyncMock(return_value=membership_result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = TeamService(session)
    service._validate_roster_players = AsyncMock()
    version_check = mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(return_value=4),
    )
    audit_service = Mock()
    audit_service.record = AsyncMock()
    mocker.patch(
        "src.services.team_service.BusinessAuditService",
        return_value=audit_service,
    )
    original_player_ids = [membership.player_id for membership in memberships]

    await service.normalize_roster_order(
        team.id,
        expected_team_version=3,
        actor=remediation_actor(),
    )

    service._validate_roster_players.assert_awaited_once_with(original_player_ids)
    version_check.assert_awaited_once_with(session, Team, team.id, 3)
    assert [membership.player_id for membership in memberships] == original_player_ids
    assert [membership.roster_order for membership in memberships] == list(range(1, 8))
    assert team.version_number == 4
    audit_call = audit_service.record.await_args.kwargs
    assert audit_call["action_type"] is AuditActionType.ROSTER_REORDERED
    assert audit_call["metadata"]["affected_count"] == 5
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_inactive_player_deletes_only_the_selected_membership(
    mocker,
) -> None:
    team = make_team()
    team.version_number = 2
    selected_player = SimpleNamespace(id=uuid4(), is_active=False)
    membership = SimpleNamespace(roster_order=6)
    remaining_player_ids = make_player_ids(7)
    remaining_result = Mock()
    remaining_result.all.return_value = remaining_player_ids
    session = Mock()

    async def get_entity(model, key):
        if model is Team:
            return team
        if model is Player:
            return selected_player
        if model is TeamPlayer:
            return membership
        raise AssertionError(f"unexpected model {model}")

    session.get = AsyncMock(side_effect=get_entity)
    session.scalars = AsyncMock(return_value=remaining_result)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = TeamService(session)
    service._validate_roster_players = AsyncMock()
    version_check = mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(return_value=3),
    )
    audit_service = Mock()
    audit_service.record = AsyncMock()
    mocker.patch(
        "src.services.team_service.BusinessAuditService",
        return_value=audit_service,
    )

    await service.remove_inactive_player(
        team.id,
        selected_player.id,
        expected_team_version=2,
        actor=remediation_actor(),
    )

    service._validate_roster_players.assert_awaited_once_with(remaining_player_ids)
    version_check.assert_awaited_once_with(session, Team, team.id, 2)
    delete_sql = str(session.execute.await_args.args[0])
    assert "DELETE FROM team_players" in delete_sql
    assert "team_players.team_id" in delete_sql
    assert "team_players.player_id" in delete_sql
    audit_call = audit_service.record.await_args.kwargs
    assert audit_call["action_type"] is AuditActionType.ROSTER_REMOVED
    assert audit_call["metadata"] == {
        "player_id": selected_player.id,
        "prior_roster_position": 6,
    }
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_roster_remediation_enforces_valid_active_roster_preconditions(
    mocker,
) -> None:
    team = make_team()
    selected_player = SimpleNamespace(id=uuid4(), is_active=False)
    membership = SimpleNamespace(roster_order=1)
    remaining_result = Mock()
    remaining_result.all.return_value = make_player_ids(6)
    session = Mock()

    async def get_entity(model, key):
        return {
            Team: team,
            Player: selected_player,
            TeamPlayer: membership,
        }[model]

    session.get = AsyncMock(side_effect=get_entity)
    session.scalars = AsyncMock(return_value=remaining_result)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = TeamService(session)
    service._validate_roster_players = AsyncMock(
        side_effect=TeamValidationError("A team roster must contain 7 to 15 players.")
    )
    version_check = mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(),
    )

    with pytest.raises(TeamValidationError, match="7 to 15"):
        await service.remove_inactive_player(
            team.id,
            selected_player.id,
            expected_team_version=1,
            actor=remediation_actor(),
        )

    version_check.assert_not_awaited()
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_roster_remediation_rejects_changed_target_and_occ_conflict(
    mocker,
) -> None:
    team = make_team()
    active_player = SimpleNamespace(id=uuid4(), is_active=True)
    membership = SimpleNamespace(roster_order=1)
    session = Mock()

    async def get_entity(model, key):
        return {
            Team: team,
            Player: active_player,
            TeamPlayer: membership,
        }[model]

    session.get = AsyncMock(side_effect=get_entity)
    session.rollback = AsyncMock()

    with pytest.raises(TeamRemediationConflictError, match="inactive"):
        await TeamService(session).remove_inactive_player(
            team.id,
            active_player.id,
            expected_team_version=1,
        )
    session.rollback.assert_awaited_once()

    memberships = [
        SimpleNamespace(player_id=uuid4(), roster_order=position)
        for position in (1, 2, 4, 5, 6, 7, 8)
    ]
    membership_result = Mock()
    membership_result.all.return_value = memberships
    stale_session = Mock()
    stale_session.get = AsyncMock(return_value=team)
    stale_session.scalars = AsyncMock(return_value=membership_result)
    stale_session.rollback = AsyncMock()
    stale_service = TeamService(stale_session)
    stale_service._validate_roster_players = AsyncMock()
    mocker.patch(
        "src.services.team_service.check_and_increment_version",
        new=AsyncMock(side_effect=StaleVersionError(Team, team.id, 1)),
    )
    audit_service = Mock()
    audit_service.record = AsyncMock()
    mocker.patch(
        "src.services.team_service.BusinessAuditService",
        return_value=audit_service,
    )

    with pytest.raises(StaleVersionError):
        await stale_service.normalize_roster_order(
            team.id,
            expected_team_version=1,
            actor=remediation_actor(),
        )

    stale_session.rollback.assert_awaited_once()
    audit_service.record.assert_not_awaited()
