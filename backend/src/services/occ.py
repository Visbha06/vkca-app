"""Optimistic concurrency control helpers."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession


class StaleVersionError(Exception):
    """Raised when an update targets an out-of-date entity version."""

    def __init__(
        self,
        model: type[Any],
        entity_id: UUID,
        incoming_version: int,
    ) -> None:
        self.model = model
        self.entity_id = entity_id
        self.incoming_version = incoming_version
        model_name = getattr(model, "__tablename__", model.__name__)
        super().__init__(
            f"Stale version {incoming_version} for {model_name} entity {entity_id}."
        )


async def check_and_increment_version(
    session: AsyncSession,
    model: type[Any],
    entity_id: UUID,
    incoming_version: int,
) -> int:
    """Atomically increment an entity version or reject a stale update."""

    statement = (
        update(model)
        .where(model.id == entity_id, model.version_number == incoming_version)
        .values(
            version_number=incoming_version + 1,
            updated_at=func.now(),
        )
        .returning(model.version_number)
    )
    new_version = (await session.execute(statement)).scalar_one_or_none()
    if new_version is None:
        raise StaleVersionError(model, entity_id, incoming_version)
    return int(new_version)
