"""Player profile database model."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin

if TYPE_CHECKING:
    from src.models.user import User


class Player(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A cricket player whose profile and availability are tracked."""

    __tablename__ = "players"
    __table_args__ = (
        Index(
            "uq_players_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        UniqueConstraint(
            "first_name",
            "last_name",
            "date_of_birth",
            name="uq_players_name_date_of_birth",
        ),
        CheckConstraint(
            "batting_style IN ('right', 'left')",
            name="ck_players_batting_style",
        ),
        CheckConstraint(
            "bowling_style IN ("
            "'right-arm fast', 'right-arm medium', 'right-arm off-break', "
            "'right-arm leg-break', 'left-arm fast', 'left-arm medium', "
            "'left-arm orthodox', 'left-arm unorthodox')",
            name="ck_players_bowling_style",
        ),
        CheckConstraint(
            "player_type IN ('batter', 'bowler', 'all-rounder', 'wicket-keeper')",
            name="ck_players_player_type",
        ),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_players_user_id_users"),
        nullable=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    batting_style: Mapped[BattingStyle] = mapped_column(String(10), nullable=False)
    bowling_style: Mapped[BowlingStyle] = mapped_column(String(30), nullable=False)
    player_type: Mapped[PlayerType] = mapped_column(String(20), nullable=False)
    player_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    user: Mapped[User | None] = relationship(
        back_populates="player_profile",
        foreign_keys=[user_id],
        uselist=False,
    )
