"""Coach assignments for cricket teams."""

from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, VersionMixin


class TeamCoach(TimestampMixin, VersionMixin, Base):
    """Join a coach account to a team without duplicating membership rows."""

    __tablename__ = "team_coaches"

    team_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("teams.id"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id"),
        primary_key=True,
    )

    team = relationship("Team", backref="coach_assignments")
    user = relationship("User", backref="team_assignments")
