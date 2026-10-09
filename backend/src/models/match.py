"""Cricket match database model."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import (
    MatchFormat,
    MatchLifecycleState,
    MatchParticipantType,
    MatchResultCode,
    ScoringAuthority,
)
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.scoring.innings import Innings
    from src.models.scoring.match_participant_performance import (
        MatchParticipantPerformance,
    )
    from src.models.scoring.match_side import MatchSide
    from src.models.scoring.participant import MatchParticipant
    from src.models.scoring.scoring_policy import ScoringPolicy
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
            "lifecycle_state IN ('scheduled', 'in_progress', 'completed', "
            "'abandoned', 'correction_reprocessing')",
            name="ck_matches_lifecycle_state",
        ),
        CheckConstraint(
            "scoring_authority IN ('legacy_aggregate', 'delivery_history')",
            name="ck_matches_scoring_authority",
        ),
        CheckConstraint(
            "result_code IN ('pending', 'win_by_runs', 'win_by_wickets', "
            "'tie', 'draw', 'no_result', 'declared', 'manual')",
            name="ck_matches_result_code",
        ),
        CheckConstraint(
            "jsonb_typeof(result_details) = 'object'",
            name="ck_matches_result_details_object",
        ),
        CheckConstraint(
            "octet_length(result_details::text) <= 4096",
            name="ck_matches_result_details_bounded",
        ),
        CheckConstraint(
            "(scoring_authority = 'legacy_aggregate' AND configured_at IS NULL) OR "
            "(scoring_authority = 'delivery_history' AND configured_at IS NOT NULL)",
            name="ck_matches_scoring_configuration_state",
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
        Index("ix_matches_lifecycle_state", "lifecycle_state"),
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
    lifecycle_state: Mapped[MatchLifecycleState] = mapped_column(
        String(32),
        nullable=False,
        default=MatchLifecycleState.SCHEDULED,
        server_default=text("'scheduled'"),
    )
    scoring_authority: Mapped[ScoringAuthority] = mapped_column(
        String(24),
        nullable=False,
        default=ScoringAuthority.LEGACY_AGGREGATE,
        server_default=text("'legacy_aggregate'"),
    )
    result_code: Mapped[MatchResultCode] = mapped_column(
        String(24),
        nullable=False,
        default=MatchResultCode.PENDING,
        server_default=text("'pending'"),
    )
    result_details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    configured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    home_team: Mapped[Team | None] = relationship(
        foreign_keys=[home_team_id],
    )
    away_team: Mapped[Team | None] = relationship(
        foreign_keys=[away_team_id],
    )
    scoring_sides: Mapped[list[MatchSide]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scoring_policy: Mapped[ScoringPolicy | None] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
        uselist=False,
    )
    scoring_participants: Mapped[list[MatchParticipant]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scoring_innings: Mapped[list[Innings]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scoring_performances: Mapped[list[MatchParticipantPerformance]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
