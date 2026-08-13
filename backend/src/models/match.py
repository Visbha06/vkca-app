"""Cricket match database model."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import MatchFormat, MatchParticipantType
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.team import Team


class Match(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A recorded cricket match and its outcome."""

    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint(
            "format IN ('T20', 'one-day', 'test', 'other')",
            name="ck_matches_format",
        ),
        CheckConstraint(
            "participant_type IN ('external', 'internal')",
            name="ck_matches_participant_type",
        ),
        CheckConstraint(
            "(participant_type = 'external' "
            "AND external_opponent_name IS NOT NULL "
            "AND btrim(external_opponent_name) <> '' "
            "AND ((home_team_id IS NOT NULL AND away_team_id IS NULL) "
            "OR (home_team_id IS NULL AND away_team_id IS NOT NULL))) "
            "OR (participant_type = 'internal' "
            "AND external_opponent_name IS NULL "
            "AND home_team_id IS NOT NULL "
            "AND away_team_id IS NOT NULL "
            "AND home_team_id <> away_team_id)",
            name="ck_matches_participants",
        ),
        Index(
            "ix_matches_match_date_home_team_id_id",
            "match_date",
            "home_team_id",
            "id",
        ),
        Index(
            "ix_matches_match_date_away_team_id_id",
            "match_date",
            "away_team_id",
            "id",
        ),
    )

    match_date: Mapped[date] = mapped_column(Date, nullable=False)
    format: Mapped[MatchFormat] = mapped_column(String(20), nullable=False)
    participant_type: Mapped[MatchParticipantType] = mapped_column(
        String(8),
        nullable=False,
    )
    home_team_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("teams.id", name="fk_matches_home_team_id_teams"),
        nullable=True,
    )
    away_team_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("teams.id", name="fk_matches_away_team_id_teams"),
        nullable=True,
    )
    external_opponent_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    venue: Mapped[str] = mapped_column(String(200), nullable=False)
    result: Mapped[str] = mapped_column(String(200), nullable=False)
    home_team: Mapped[Team | None] = relationship(
        foreign_keys=[home_team_id],
    )
    away_team: Mapped[Team | None] = relationship(
        foreign_keys=[away_team_id],
    )
