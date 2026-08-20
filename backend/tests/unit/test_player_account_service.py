"""Unit tests for explicit Player-to-account association operations."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from src.enums import (
    AuditActionType,
    BattingStyle,
    BowlingStyle,
    PlayerType,
    UserRole,
)
from src.models.player import Player
from src.models.user import User
from src.schemas.player_account import (
    PlayerAccountLinkRequest,
    PlayerAccountLookupQuery,
    PlayerAccountReassignRequest,
    PlayerAccountUnlinkRequest,
)
from src.services.business_audit_service import AuditActorContext
from src.services.occ import StaleVersionError
from src.services.player_account_service import (
    PlayerAccountAuthorizationError,
    PlayerAccountConflictError,
    PlayerAccountService,
)


def make_player(*, user_id: UUID | None = None, version_number: int = 1) -> Player:
    now = datetime.now(UTC)
    return Player(
        id=uuid4(),
        user_id=user_id,
        first_name="Rohan",
        last_name="Patel",
        date_of_birth=date(2010, 1, 1),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=version_number,
    )


def make_user(*, role: UserRole = UserRole.PLAYER) -> User:
    now = datetime.now(UTC)
    user_id = uuid4()
    return User(
        id=user_id,
        first_name="Rohan",
        last_name="Account",
        email=f"{user_id.hex}@example.com",
        hashed_password="$argon2id$unit-test-only",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


def head_coach_actor() -> AuditActorContext:
    return AuditActorContext(
        user_id=uuid4(),
        display_name="Asha Coach",
        role=UserRole.HEAD_COACH,
        request_id="account-link-test",
    )


def service_session(player: Player, users: dict[UUID, User]) -> AsyncMock:
    session = AsyncMock()
    session.add = Mock()

    async def get(model, entity_id):
        if model is Player:
            return player if entity_id == player.id else None
        if model is User:
            return users.get(entity_id)
        return None

    session.get.side_effect = get
    session.scalar.return_value = None
    return session


@pytest.mark.asyncio
async def test_link_account_is_occ_safe_and_records_exactly_one_event(
    mocker,
) -> None:
    player = make_player()
    account = make_user()
    session = service_session(player, {account.id: account})
    increment = mocker.patch(
        "src.services.player_account_service.check_and_increment_version",
        new=AsyncMock(return_value=2),
    )
    audit = Mock()
    audit.record = AsyncMock()
    mocker.patch(
        "src.services.player_account_service.BusinessAuditService",
        return_value=audit,
    )
    background_staging = mocker.patch(
        "src.services.rag.registry.stage_rag_mutation_impact",
        new=AsyncMock(),
    )

    response = await PlayerAccountService(session).link_account(
        player.id,
        PlayerAccountLinkRequest(user_id=account.id, version_number=1),
        actor=head_coach_actor(),
    )

    assert player.user_id == account.id
    assert response.account is not None
    assert response.account.email == account.email
    assert response.player_version_number == 2
    increment.assert_awaited_once_with(session, Player, player.id, 1)
    assert audit.record.await_count == 1
    assert (
        audit.record.await_args.kwargs["action_type"]
        is AuditActionType.PLAYER_ACCOUNT_LINKED
    )
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()
    background_staging.assert_not_awaited()


@pytest.mark.asyncio
async def test_unlink_and_reassign_require_the_expected_current_association(
    mocker,
) -> None:
    old_account = make_user()
    new_account = make_user()
    player = make_player(user_id=old_account.id, version_number=4)
    session = service_session(
        player,
        {old_account.id: old_account, new_account.id: new_account},
    )
    mocker.patch(
        "src.services.player_account_service.check_and_increment_version",
        new=AsyncMock(side_effect=[5, 6]),
    )
    audit = Mock()
    audit.record = AsyncMock()
    mocker.patch(
        "src.services.player_account_service.BusinessAuditService",
        return_value=audit,
    )
    service = PlayerAccountService(session)

    unlinked = await service.unlink_account(
        player.id,
        PlayerAccountUnlinkRequest(version_number=4),
        actor=head_coach_actor(),
    )
    assert unlinked.account is None
    assert player.user_id is None

    player.user_id = old_account.id
    reassigned = await service.reassign_account(
        player.id,
        PlayerAccountReassignRequest(
            expected_user_id=old_account.id,
            new_user_id=new_account.id,
            version_number=5,
        ),
        actor=head_coach_actor(),
    )
    assert reassigned.account is not None
    assert reassigned.account.id == new_account.id
    assert player.user_id == new_account.id
    assert [call.kwargs["action_type"] for call in audit.record.await_args_list] == [
        AuditActionType.PLAYER_ACCOUNT_UNLINKED,
        AuditActionType.PLAYER_ACCOUNT_REASSIGNED,
    ]


@pytest.mark.asyncio
async def test_account_mutations_reject_wrong_actor_and_duplicate_links() -> None:
    account = make_user()
    player = make_player(user_id=uuid4())
    session = service_session(player, {account.id: account})
    service = PlayerAccountService(session)
    assistant = AuditActorContext(
        user_id=uuid4(),
        display_name="Assistant Coach",
        role=UserRole.ASSISTANT_COACH,
    )

    with pytest.raises(PlayerAccountAuthorizationError):
        await service.link_account(
            player.id,
            PlayerAccountLinkRequest(user_id=account.id, version_number=1),
            actor=assistant,
        )

    with pytest.raises(PlayerAccountConflictError, match="already linked"):
        await service.link_account(
            player.id,
            PlayerAccountLinkRequest(user_id=account.id, version_number=1),
            actor=head_coach_actor(),
        )


@pytest.mark.asyncio
async def test_stale_link_rolls_back_without_a_business_audit_event(mocker) -> None:
    account = make_user()
    player = make_player()
    session = service_session(player, {account.id: account})
    mocker.patch(
        "src.services.player_account_service.check_and_increment_version",
        new=AsyncMock(side_effect=StaleVersionError(Player, player.id, 1)),
    )
    audit = Mock()
    audit.record = AsyncMock()
    mocker.patch(
        "src.services.player_account_service.BusinessAuditService",
        return_value=audit,
    )

    with pytest.raises(StaleVersionError):
        await PlayerAccountService(session).link_account(
            player.id,
            PlayerAccountLinkRequest(user_id=account.id, version_number=1),
            actor=head_coach_actor(),
        )

    audit.record.assert_not_awaited()
    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_eligible_lookup_is_bounded_and_excludes_linked_accounts() -> None:
    account = make_user()
    session = AsyncMock()
    session.add = Mock()
    session.scalar.return_value = 1
    result = Mock()
    result.all.return_value = [(account,)]
    session.execute.return_value = result

    response = await PlayerAccountService(session).list_eligible_accounts(
        PlayerAccountLookupQuery(search="  rohan  ", page=1, page_size=20),
        actor=head_coach_actor(),
    )

    assert response.total_users == 1
    assert response.users[0].id == account.id
    statement = session.execute.await_args.args[0]
    sql = str(statement).lower()
    assert "users.role" in sql
    assert "not (exists" in sql or "not exists" in sql
    assert "limit" in sql
