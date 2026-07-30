"""Unit tests for paginated coach directory queries."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import UserRole
from src.models.team_coach import TeamCoach
from src.models.user import User
from src.schemas.coach import CoachCreate, CoachTeamUpdate
from src.services.coach_service import (
    CoachAlreadyExistsError,
    CoachInactiveError,
    CoachService,
    CoachTeamValidationError,
)
from src.services.password_service import PasswordService


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


def test_generate_temporary_password_satisfies_policy() -> None:
    first = CoachService.generate_temporary_password()
    second = CoachService.generate_temporary_password()

    PasswordService.validate_password_policy(first)
    PasswordService.validate_password_policy(second)
    assert first != second
    assert len(first) <= 128


@pytest.mark.asyncio
async def test_create_coach_persists_account_and_assignments_atomically(
    mocker,
) -> None:
    team_id = uuid4()
    team = SimpleNamespace(id=team_id, name="U13 Lions")
    session = Mock()
    session.scalar = AsyncMock(return_value=None)
    teams = Mock()
    teams.all.return_value = [team]
    session.scalars = AsyncMock(return_value=teams)
    session.add = Mock()
    session.add_all = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    now = datetime.now(UTC)

    async def populate_server_fields(coach: User) -> None:
        coach.id = uuid4()
        coach.version_number = 1
        coach.created_at = now
        coach.updated_at = now

    session.refresh = AsyncMock(side_effect=populate_server_fields)
    service = CoachService(session)
    mocker.patch(
        "src.services.coach_service.PasswordService.hash_password",
        return_value="argon2-hash",
    )

    response, temporary_password = await service.create_coach(
        CoachCreate(
            first_name="Asha",
            last_name="Patel",
            email="ASHA@VKCA.TEST",
            team_ids=[team_id],
        )
    )

    assert response.email == "asha@vkca.test"
    assert response.teams[0].name == "U13 Lions"
    created_user = session.add.call_args.args[0]
    assert isinstance(created_user, User)
    assert created_user.email == "asha@vkca.test"
    assert created_user.role == UserRole.ASSISTANT_COACH
    assert created_user.is_active is True
    PasswordService.validate_password_policy(temporary_password)
    memberships = session.add_all.call_args.args[0]
    assert len(memberships) == 1
    assert isinstance(memberships[0], TeamCoach)
    assert memberships[0].team_id == team_id
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_coach_rejects_duplicate_email_and_unknown_teams() -> None:
    duplicate_session = Mock()
    duplicate_session.scalar = AsyncMock(return_value=uuid4())
    duplicate_session.rollback = AsyncMock()
    with pytest.raises(CoachAlreadyExistsError):
        await CoachService(duplicate_session).create_coach(
            CoachCreate(
                first_name="Asha",
                last_name="Patel",
                email="asha@vkca.test",
            )
        )

    missing_team_session = Mock()
    missing_team_session.scalar = AsyncMock(return_value=None)
    teams = Mock()
    teams.all.return_value = []
    missing_team_session.scalars = AsyncMock(return_value=teams)
    missing_team_session.rollback = AsyncMock()
    with pytest.raises(CoachTeamValidationError):
        await CoachService(missing_team_session).create_coach(
            CoachCreate(
                first_name="Asha",
                last_name="Patel",
                email="asha@vkca.test",
                team_ids=[uuid4()],
            )
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("desired_status", [False, True])
async def test_toggle_coach_status_uses_occ_and_only_revokes_on_deactivate(
    mocker,
    desired_status: bool,
) -> None:
    coach = CoachEntity(role=UserRole.ASSISTANT_COACH)
    session = Mock()
    session.get = AsyncMock(return_value=coach)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = CoachService(session)
    updated_response = Mock()
    service.get_coach = AsyncMock(return_value=updated_response)
    increment = mocker.patch(
        "src.services.coach_service.check_and_increment_version",
        new=AsyncMock(return_value=2),
    )
    auth_service = Mock()
    auth_service.revoke_user_sessions = AsyncMock(return_value=[])
    mocker.patch(
        "src.services.coach_service.AuthService",
        return_value=auth_service,
    )

    response = await service.toggle_coach_status(
        coach.id,
        is_active=desired_status,
        version_number=1,
    )

    assert response is updated_response
    increment.assert_awaited_once_with(session, User, coach.id, 1)
    assert coach.is_active is desired_status
    assert coach.version_number == 2
    session.commit.assert_awaited_once()
    if desired_status:
        auth_service.revoke_user_sessions.assert_not_awaited()
    else:
        auth_service.revoke_user_sessions.assert_awaited_once_with(
            coach.id,
            reason="user_disabled",
            target_resource=f"/api/v1/users/{coach.id}/disable",
        )


@pytest.mark.asyncio
async def test_update_team_assignments_atomically_replaces_all_and_increments_version(
    mocker,
) -> None:
    coach = CoachEntity(role=UserRole.ASSISTANT_COACH)
    team_ids = [uuid4(), uuid4()]
    teams = [
        SimpleNamespace(id=team_ids[0], name="U11 Falcons"),
        SimpleNamespace(id=team_ids[1], name="U13 Lions"),
    ]
    session = Mock()
    session.get = AsyncMock(return_value=coach)
    team_result = Mock()
    team_result.all.return_value = teams
    session.scalars = AsyncMock(return_value=team_result)
    session.execute = AsyncMock()
    session.add_all = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = CoachService(session)
    updated_response = Mock()
    service.get_coach = AsyncMock(return_value=updated_response)
    increment = mocker.patch(
        "src.services.coach_service.check_and_increment_version",
        new=AsyncMock(return_value=2),
    )

    result = await service.update_team_assignments(
        coach.id,
        CoachTeamUpdate(team_ids=team_ids, version_number=1),
    )

    assert result is updated_response
    increment.assert_awaited_once_with(session, User, coach.id, 1)
    delete_statement = session.execute.await_args.args[0]
    assert "DELETE FROM team_coaches" in str(delete_statement)
    memberships = session.add_all.call_args.args[0]
    assert {membership.team_id for membership in memberships} == set(team_ids)
    assert all(membership.user_id == coach.id for membership in memberships)
    assert coach.version_number == 2
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_team_assignments_rejects_duplicate_ids_before_writes() -> None:
    coach = CoachEntity(role=UserRole.ASSISTANT_COACH)
    team_id = uuid4()
    session = Mock()
    session.get = AsyncMock(return_value=coach)
    session.scalars = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    payload = CoachTeamUpdate.model_construct(
        team_ids=[team_id, team_id],
        version_number=1,
    )

    with pytest.raises(CoachTeamValidationError, match="duplicates"):
        await CoachService(session).update_team_assignments(coach.id, payload)

    session.scalars.assert_not_awaited()
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_team_assignments_validates_teams_and_active_status() -> None:
    coach = CoachEntity(role=UserRole.ASSISTANT_COACH)
    missing_team_id = uuid4()
    session = Mock()
    session.get = AsyncMock(return_value=coach)
    team_result = Mock()
    team_result.all.return_value = []
    session.scalars = AsyncMock(return_value=team_result)
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    with pytest.raises(CoachTeamValidationError, match="do not exist"):
        await CoachService(session).update_team_assignments(
            coach.id,
            CoachTeamUpdate(team_ids=[missing_team_id], version_number=1),
        )

    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()

    coach.is_active = False
    session.scalars.reset_mock()
    with pytest.raises(CoachInactiveError):
        await CoachService(session).update_team_assignments(
            coach.id,
            CoachTeamUpdate(team_ids=[], version_number=1),
        )
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_team_assignments_rolls_back_failed_replacement(
    mocker,
) -> None:
    coach = CoachEntity(role=UserRole.ASSISTANT_COACH)
    team_id = uuid4()
    team = SimpleNamespace(id=team_id, name="U13 Lions")
    session = Mock()
    session.get = AsyncMock(return_value=coach)
    team_result = Mock()
    team_result.all.return_value = [team]
    session.scalars = AsyncMock(return_value=team_result)
    session.execute = AsyncMock()
    session.add_all = Mock(side_effect=RuntimeError("insert failed"))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    mocker.patch(
        "src.services.coach_service.check_and_increment_version",
        new=AsyncMock(return_value=2),
    )

    with pytest.raises(RuntimeError, match="insert failed"):
        await CoachService(session).update_team_assignments(
            coach.id,
            CoachTeamUpdate(team_ids=[team_id], version_number=1),
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
