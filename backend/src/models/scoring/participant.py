"""Fixed internal and external Match participant identities."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import MatchParticipantKind
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.match import Match
    from src.models.player import Player
    from src.models.scoring.batting_entry import BattingOrderEntry
    from src.models.scoring.match_side import MatchSide


class MatchParticipant(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A historical scoring identity fixed to one Match and side."""

    __tablename__ = "match_participants"
    __table_args__ = (
        CheckConstraint(
            "participant_kind IN ('internal', 'external')",
            name="ck_match_participants_kind",
        ),
        CheckConstraint(
            "(participant_kind = 'internal' AND player_id IS NOT NULL) OR "
            "(participant_kind = 'external' AND player_id IS NULL)",
            name="ck_match_participants_identity",
        ),
        CheckConstraint(
            "length(btrim(display_name_snapshot)) > 0",
            name="ck_match_participants_display_name_not_blank",
        ),
        CheckConstraint(
            "batting_order_position >= 1",
            name="ck_match_participants_batting_order_positive",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_match_participants_version_positive",
        ),
        Index(
            "uq_match_participants_side_batting_order",
            "side_id",
            "batting_order_position",
            unique=True,
        ),
        Index(
            "uq_match_participants_match_player_id",
            "match_id",
            "player_id",
            unique=True,
            postgresql_where=text("player_id IS NOT NULL"),
        ),
        Index(
            "ix_match_participants_match_side_order",
            "match_id",
            "side_id",
            "batting_order_position",
        ),
    )

    match_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "matches.id",
            ondelete="CASCADE",
            name="fk_match_participants_match_id_matches",
        ),
        nullable=False,
    )
    side_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_sides.id",
            ondelete="CASCADE",
            name="fk_match_participants_side_id_match_sides",
        ),
        nullable=False,
    )
    participant_kind: Mapped[MatchParticipantKind] = mapped_column(
        String(12),
        nullable=False,
    )
    player_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("players.id", name="fk_match_participants_player_id_players"),
        nullable=True,
    )
    display_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    batting_order_position: Mapped[int] = mapped_column(Integer, nullable=False)

    match: Mapped[Match] = relationship(back_populates="scoring_participants")
    side: Mapped[MatchSide] = relationship(back_populates="participants")
    player: Mapped[Player | None] = relationship()
    batting_entries: Mapped[list[BattingOrderEntry]] = relationship(
        back_populates="participant",
    )
