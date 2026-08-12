"""PostgreSQL integration coverage for Player account association invariants."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.database import AsyncSessionFactory
from src.enums import (
    AuditActionType,
    BattingStyle,
    BowlingStyle,
    PlayerType,
    UserRole,
)
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.models.user import User
from src.schemas.player import PlayerUpdate
from src.schemas.player_account import (
    PlayerAccountLinkRequest,
    PlayerAccountReassignRequest,
)
from src.services.business_audit_service import AuditActorContext
from src.services.password_service import PasswordService
from src.services.player_account_service import (
    PlayerAccountConflictError,
    PlayerAccountService,
)
from src.services.player_service import PlayerService


def account(email: str, role: UserRole = UserRole.PLAYER) -> User:
    return User(
        id=uuid4(),
        first_name="Integration",
        last_name="Account",
        email=email,
        hashed_password=PasswordService.hash_password("IntegrationP@ssword1"),
        role=role,
        is_active=True,
        version_number=1,
    )


def profile(label: str) -> Player:
    return Player(
        id=uuid4(),
        first_name=label,
        last_name="Player",
        date_of_birth=date(2010, 1, 1),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=True,
        version_number=1,
    )


def actor(user: User) -> AuditActorContext:
    return AuditActorContext.from_user(user, request_id="integration-account-link")


@pytest.mark.asyncio(loop_scope="session")
async def test_unique_link_reassignment_and_audit_cardinality() -> None:
    async with AsyncSessionFactory() as session:
        head_coach = account(f"hc-{uuid4().hex}@example.com", UserRole.HEAD_COACH)
        first_account = account(f"one-{uuid4().hex}@example.com")
        second_account = account(f"two-{uuid4().hex}@example.com")
        first_profile = profile("First")
        competing_profile = profile("Competing")
        session.add_all(
            [
                head_coach,
                first_account,
                second_account,
                first_profile,
                competing_profile,
            ]
        )
        await session.commit()
        first_profile_id = first_profile.id
        competing_profile_id = competing_profile.id
        first_account_id = first_account.id
        second_account_id = second_account.id
        audit_actor = actor(head_coach)

        service = PlayerAccountService(session)
        linked = await service.link_account(
            first_profile_id,
            PlayerAccountLinkRequest(user_id=first_account_id, version_number=1),
            actor=audit_actor,
        )

        with pytest.raises(PlayerAccountConflictError):
            await service.link_account(
                competing_profile_id,
                PlayerAccountLinkRequest(user_id=first_account_id, version_number=1),
                actor=audit_actor,
            )

        reassigned = await service.reassign_account(
            first_profile_id,
            PlayerAccountReassignRequest(
                expected_user_id=first_account_id,
                new_user_id=second_account_id,
                version_number=linked.player_version_number,
            ),
            actor=audit_actor,
        )

        events = list(
            (
                await session.scalars(
                    select(BusinessAuditEvent)
                    .where(BusinessAuditEvent.target_entity_id == first_profile_id)
                    .order_by(BusinessAuditEvent.created_at, BusinessAuditEvent.id)
                )
            ).all()
        )
        assert sorted(event.action_type for event in events) == sorted(
            [
            AuditActionType.PLAYER_ACCOUNT_LINKED.value,
            AuditActionType.PLAYER_ACCOUNT_REASSIGNED.value,
            ]
        )
        assert reassigned.account is not None
        assert reassigned.account.id == second_account_id


@pytest.mark.asyncio(loop_scope="session")
async def test_profile_deactivation_revokes_every_linked_session_atomically() -> None:
    async with AsyncSessionFactory() as session:
        head_coach = account(f"hc-{uuid4().hex}@example.com", UserRole.HEAD_COACH)
        player_account = account(f"player-{uuid4().hex}@example.com")
        player = profile("Deactivate")
        player.user_id = player_account.id
        session.add_all([head_coach, player_account, player])
        await session.flush()
        now = datetime.now(UTC)
        auth_sessions = [
            AuthSession(
                id=uuid4(),
                user_id=player_account.id,
                token_family_id=uuid4(),
                current_token_hash=uuid4().hex * 2,
                rotated_token_hashes=[],
                last_used_at=now,
                expires_at=now + timedelta(days=7),
                revoked_at=None,
                revocation_reason=None,
                version_number=1,
            )
            for _ in range(2)
        ]
        session.add_all(auth_sessions)
        await session.commit()

        updated = await PlayerService(session).update_player(
            player.id,
            PlayerUpdate(is_active=False, version_number=1),
            actor=actor(head_coach),
        )

        assert updated.is_active is False
        persisted_sessions = list(
            (
                await session.scalars(
                    select(AuthSession).where(AuthSession.user_id == player_account.id)
                )
            ).all()
        )
        assert len(persisted_sessions) == 2
        assert all(item.revoked_at is not None for item in persisted_sessions)
        assert {item.revocation_reason for item in persisted_sessions} == {
            "linked_player_inactive"
        }
