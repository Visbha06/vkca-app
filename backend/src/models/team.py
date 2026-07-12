"""Cricket team database model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class Team(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A named cricket squad for an age group."""

    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    age_group: Mapped[str] = mapped_column(String(50), nullable=False)
