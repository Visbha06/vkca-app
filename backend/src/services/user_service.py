"""Application service for user account operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.user import UserCreate
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

    async def create_user(self, payload: UserCreate) -> User:
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
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise UserAlreadyExistsError(normalized_email) from exc
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
    ) -> User:
        """Reactivate an account without restoring any revoked sessions."""

        user = await self.session.get(User, user_id)
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
            user.is_active = True
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(user)
        return user
