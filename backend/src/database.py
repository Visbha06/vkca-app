"""Async SQLAlchemy engine and session management."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings
from src.models import Base

settings = get_settings()

engine = create_async_engine(
    str(settings.database_url),
    pool_pre_ping=True,
)
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Importing ``Base`` through ``src.models`` registers every mapped table before
# migrations, metadata inspection, or test fixtures consume this module.
model_metadata = Base.metadata


@dataclass(frozen=True, slots=True)
class DatabaseResources:
    """Explicitly owned engine and session factory for a non-API runtime."""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    async def close(self) -> None:
        """Release worker-owned connection-pool resources."""

        await self.engine.dispose()


def create_database_resources(database_url: object) -> DatabaseResources:
    """Create an isolated async engine/session pair for a dedicated worker."""

    worker_engine = create_async_engine(str(database_url), pool_pre_ping=True)
    worker_session_factory = async_sessionmaker(
        bind=worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return DatabaseResources(
        engine=worker_engine,
        session_factory=worker_session_factory,
    )


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield one async database session per request."""

    async with AsyncSessionFactory() as session:
        yield session
