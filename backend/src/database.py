"""Async SQLAlchemy engine and session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
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


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield one async database session per request."""

    async with AsyncSessionFactory() as session:
        yield session
