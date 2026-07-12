"""Application service for user account operations."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.schemas.user import UserCreate


class UserAlreadyExistsError(Exception):
    """Raised when an email address is already registered."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"A user with email '{email}' already exists.")


class UserService:
    """Create and list user accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(self, payload: UserCreate) -> User:
        """Create an account after an application-level duplicate check."""

        duplicate_statement = select(User.id).where(User.email == payload.email)
        if await self.session.scalar(duplicate_statement) is not None:
            raise UserAlreadyExistsError(payload.email)

        user = User(**payload.model_dump())
        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise
        await self.session.refresh(user)
        return user

    async def list_users(self) -> list[User]:
        """Return all accounts in stable name order."""

        statement = select(User).order_by(User.last_name, User.first_name, User.id)
        return list((await self.session.scalars(statement)).all())
