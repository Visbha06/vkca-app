"""Application service for user account operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import AuditActionType, AuditEntityType, UserRole
from src.models.user import User
from src.schemas.user import UserCreate
from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.business_audit_service import (
    AuditActorContext,
    AuditTargetContext,
    BusinessAuditService,
)
from src.services.occ import check_and_increment_version
from src.services.password_service import PasswordService


class UserAlreadyExistsError(Exception):
    """Raised when an email address is already registered."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"A user with email '{email}' already exists.")


class UserNotFoundError(Exception):
    """Raised when a requested user account does not exist."""

    def __init__(self) -> None:
        super().__init__("User not found")


class UserService:
    """Create and list user accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(
        self,
        payload: UserCreate,
        *,
        actor: AuditActorContext | None = None,
    ) -> User:
        """Normalize and securely persist a new account."""

        normalized_email = payload.email.strip().lower()
        duplicate_statement = select(User.id).where(User.email == normalized_email)
        if await self.session.scalar(duplicate_statement) is not None:
            raise UserAlreadyExistsError(normalized_email)

        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=normalized_email,
            hashed_password=PasswordService.hash_password(payload.password),
            role=payload.role,
        )
        self.session.add(user)
        try:
            await self.session.flush()
            if actor is not None and user.role is UserRole.ASSISTANT_COACH:
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=AuditActionType.COACH_CREATED,
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.COACH,
                        entity_id=user.id,
                        label=f"{user.first_name} {user.last_name}".strip(),
                    ),
                    metadata={
                        "assigned_team_ids": [],
                        "assigned_team_count": 0,
                    },
                )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise UserAlreadyExistsError(normalized_email) from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(user)
        return user

    async def list_users(self) -> list[User]:
        """Return all accounts in stable name order."""

        statement = select(User).order_by(User.last_name, User.first_name, User.id)
        return list((await self.session.scalars(statement)).all())

    async def reactivate_user(
        self,
        user_id: UUID,
        version_number: int | None = None,
        *,
        actor: AuditActorContext | None = None,
    ) -> User:
        """Reactivate an account without restoring any revoked sessions."""

        return await self.set_user_active(
            user_id,
            is_active=True,
            version_number=version_number,
            actor=actor,
        )

    async def disable_user(
        self,
        user_id: UUID,
        version_number: int | None = None,
        *,
        actor: AuditActorContext | None = None,
    ) -> User:
        """Disable an account and revoke its sessions in one transaction."""

        return await self.set_user_active(
            user_id,
            is_active=False,
            version_number=version_number,
            actor=actor,
        )

    async def set_user_active(
        self,
        user_id: UUID,
        *,
        is_active: bool,
        version_number: int | None = None,
        actor: AuditActorContext | None = None,
    ) -> User:
        """Own coach status, session, security-log, and business-log atomicity."""

        user = await self.session.scalar(select(User).where(User.id == user_id))
        if user is None:
            raise UserNotFoundError

        try:
            if version_number is None:
                user.version_number += 1
            else:
                user.version_number = await check_and_increment_version(
                    self.session,
                    User,
                    user_id,
                    version_number,
                )
            user.is_active = is_active
            if not is_active:
                await AuthService(self.session).revoke_user_sessions(
                    user.id,
                    reason="user_disabled",
                    target_resource=f"/api/v1/users/{user.id}/disable",
                )
                await AuditService.log_event(
                    self.session,
                    "user_disablement",
                    user_id=user.id,
                    result="success",
                    target_resource=f"/api/v1/users/{user.id}/disable",
                )
            if actor is not None and user.role in {
                UserRole.HEAD_COACH,
                UserRole.ASSISTANT_COACH,
            }:
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=(
                        AuditActionType.COACH_ACTIVATED
                        if is_active
                        else AuditActionType.COACH_DEACTIVATED
                    ),
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.COACH,
                        entity_id=user.id,
                        label=f"{user.first_name} {user.last_name}".strip(),
                    ),
                    metadata={"changed_fields": ["is_active"]},
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(user)
        return user
