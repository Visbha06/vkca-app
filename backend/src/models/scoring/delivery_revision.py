"""Immutable observed and derived facts for attempted deliveries."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import DeliveryRevisionState
from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.scoring.delivery import Delivery
    from src.models.scoring.delivery_fielder import DeliveryFielder
    from src.models.scoring.participant import MatchParticipant
    from src.models.scoring.wicket_event import WicketEvent
    from src.models.user import User


class DeliveryRevision(UUIDMixin, Base):
    """One immutable version of observed delivery facts and their derivation."""

    __tablename__ = "delivery_revisions"
    __table_args__ = (
        UniqueConstraint(
            "delivery_id",
            "revision_number",
            name="uq_delivery_revisions_delivery_number",
        ),
        CheckConstraint(
            "revision_number >= 1",
            name="ck_delivery_revisions_number_positive",
        ),
        CheckConstraint(
            "revision_state IN ('active', 'superseded')",
            name="ck_delivery_revisions_state",
        ),
        CheckConstraint(
            "striker_participant_id <> non_striker_participant_id",
            name="ck_delivery_revisions_distinct_batters",
        ),
        CheckConstraint(
            "runs_off_bat BETWEEN 0 AND 2147483647 "
            "AND wide_runs BETWEEN 0 AND 2147483647 "
            "AND no_ball_penalty_runs BETWEEN 0 AND 1 "
            "AND bye_runs BETWEEN 0 AND 2147483647 "
            "AND leg_bye_runs BETWEEN 0 AND 2147483647 "
            "AND penalty_runs BETWEEN 0 AND 2147483647",
            name="ck_delivery_revisions_component_bounds",
        ),
        CheckConstraint(
            "NOT (bye_runs > 0 AND leg_bye_runs > 0) "
            "AND NOT (wide_runs > 0 AND no_ball_penalty_runs > 0)",
            name="ck_delivery_revisions_extras_exclusive",
        ),
        CheckConstraint(
            "total_runs BETWEEN 0 AND 2147483647 "
            "AND completed_runs BETWEEN 0 AND 2147483647 "
            "AND bowler_conceded_runs BETWEEN 0 AND 2147483647",
            name="ck_delivery_revisions_derived_run_bounds",
        ),
        CheckConstraint(
            "total_runs::bigint = runs_off_bat::bigint + wide_runs::bigint + "
            "no_ball_penalty_runs::bigint + bye_runs::bigint + "
            "leg_bye_runs::bigint + penalty_runs::bigint",
            name="ck_delivery_revisions_total_components",
        ),
        CheckConstraint(
            "is_legal = (wide_runs = 0 AND no_ball_penalty_runs = 0)",
            name="ck_delivery_revisions_legal_derivation",
        ),
        CheckConstraint(
            "over_number >= 0 AND ball_in_over >= 1",
            name="ck_delivery_revisions_over_position",
        ),
        CheckConstraint(
            "(revision_number = 1 AND replacement_reason IS NULL "
            "AND supersedes_revision_id IS NULL) OR "
            "(revision_number > 1 AND replacement_reason IS NOT NULL "
            "AND length(btrim(replacement_reason)) BETWEEN 1 AND 500 "
            "AND supersedes_revision_id IS NOT NULL)",
            name="ck_delivery_revisions_replacement_provenance",
        ),
        Index(
            "uq_delivery_revisions_active_delivery",
            "delivery_id",
            unique=True,
            postgresql_where=text("revision_state = 'active'"),
        ),
        Index(
            "uq_delivery_revisions_supersedes_revision_id",
            "supersedes_revision_id",
            unique=True,
            postgresql_where=text("supersedes_revision_id IS NOT NULL"),
        ),
        Index(
            "ix_delivery_revisions_delivery_state",
            "delivery_id",
            "revision_state",
        ),
    )

    delivery_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "deliveries.id",
            ondelete="CASCADE",
            name="fk_delivery_revisions_delivery_id_deliveries",
        ),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_state: Mapped[DeliveryRevisionState] = mapped_column(
        String(16),
        nullable=False,
        default=DeliveryRevisionState.ACTIVE,
        server_default=text("'active'"),
    )
    striker_participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_delivery_revisions_striker_id_match_participants",
        ),
        nullable=False,
    )
    non_striker_participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_delivery_revisions_non_striker_id_match_participants",
        ),
        nullable=False,
    )
    bowler_participant_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "match_participants.id",
            name="fk_delivery_revisions_bowler_id_match_participants",
        ),
        nullable=False,
    )
    runs_off_bat: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    wide_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    no_ball_penalty_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bye_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    leg_bye_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    penalty_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    is_legal: Mapped[bool] = mapped_column(Boolean, nullable=False)
    completed_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    balls_faced: Mapped[bool] = mapped_column(Boolean, nullable=False)
    bowler_conceded_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    over_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ball_in_over: Mapped[int] = mapped_column(Integer, nullable=False)
    replacement_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supersedes_revision_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "delivery_revisions.id",
            name="fk_delivery_revisions_supersedes_id_delivery_revisions",
        ),
        nullable=True,
    )
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_delivery_revisions_recorded_by_user_id_users",
        ),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    delivery: Mapped[Delivery] = relationship(back_populates="revisions")
    striker: Mapped[MatchParticipant] = relationship(
        foreign_keys=[striker_participant_id]
    )
    non_striker: Mapped[MatchParticipant] = relationship(
        foreign_keys=[non_striker_participant_id]
    )
    bowler: Mapped[MatchParticipant] = relationship(
        foreign_keys=[bowler_participant_id]
    )
    supersedes: Mapped[DeliveryRevision | None] = relationship(
        remote_side="DeliveryRevision.id",
        foreign_keys=[supersedes_revision_id],
        uselist=False,
    )
    recorded_by: Mapped[User] = relationship()
    wicket_event: Mapped[WicketEvent | None] = relationship(
        back_populates="delivery_revision",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
        uselist=False,
    )
    fielders: Mapped[list[DeliveryFielder]] = relationship(
        back_populates="delivery_revision",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DeliveryFielder.ordinal",
    )
