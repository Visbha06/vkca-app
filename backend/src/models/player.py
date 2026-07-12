"""Player profile database model."""

from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class Player(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A cricket player whose profile and availability are tracked."""

    __tablename__ = "players"
    __table_args__ = (
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
