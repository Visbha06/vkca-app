"""Pydantic schemas for data synchronization audit logs."""

from pydantic import Field

from src.schemas.base import BaseRequestSchema


class DataSyncLogCreate(BaseRequestSchema):
    """Validated input for a DataSyncLog record."""

    source: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=20)
    target_table: str = Field(min_length=1, max_length=100)
    error_message: str | None = None
