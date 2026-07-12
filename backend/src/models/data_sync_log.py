"""Data synchronization audit log model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class DataSyncLog(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """Record synchronization outcomes and OCC conflicts."""

    __tablename__ = "data_sync_logs"

    source: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    target_table: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
