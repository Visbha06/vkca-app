"""Stable side snapshots owned by a configured Match."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import MatchSideCode, MatchSideKind
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.match import Match
    from src.models.scoring.innings import Innings
    from src.models.scoring.participant import MatchParticipant
    from src.models.team import Team


class MatchSide(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """One immutable academy or external side identity in a Match."""

    __tablename__ = "match_sides"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "side_code",
            name="uq_match_sides_match_side_code",
        ),
        CheckConstraint(
            "side_code IN ('home', 'away')",
            name="ck_match_sides_side_code",
        ),
        CheckConstraint(
            "side_kind IN ('academy', 'external')",
            name="ck_match_sides_side_kind",
        ),
        CheckConstraint(
            "(side_kind = 'academy' AND team_id IS NOT NULL) OR "
            "(side_kind = 'external' AND team_id IS NULL)",
            name="ck_match_sides_identity",
        ),
        CheckConstraint(
            "length(btrim(display_name_snapshot)) > 0",
            name="ck_match_sides_display_name_not_blank",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_match_sides_version_positive",
        ),
        Index(
            "uq_match_sides_match_team_id",
            "match_id",
            "team_id",
            unique=True,
            postgresql_where=text("team_id IS NOT NULL"),
        ),
        Index("ix_match_sides_team_id", "team_id"),
    )

    match_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "matches.id",
            ondelete="CASCADE",
            name="fk_match_sides_match_id_matches",
        ),
        nullable=False,
    )
    side_code: Mapped[MatchSideCode] = mapped_column(String(8), nullable=False)
    side_kind: Mapped[MatchSideKind] = mapped_column(String(12), nullable=False)
    team_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("teams.id", name="fk_match_sides_team_id_teams"),
        nullable=True,
    )
    display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)

    match: Mapped[Match] = relationship(back_populates="scoring_sides")
    team: Mapped[Team | None] = relationship()
    participants: Mapped[list[MatchParticipant]] = relationship(
        back_populates="side",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    batting_innings: Mapped[list[Innings]] = relationship(
        back_populates="batting_side",
        foreign_keys="Innings.batting_side_id",
    )
    fielding_innings: Mapped[list[Innings]] = relationship(
        back_populates="fielding_side",
        foreign_keys="Innings.fielding_side_id",
    )
