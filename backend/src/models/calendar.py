"""Persisted calendar event, recurrence, scope, and exception entities."""

from __future__ import annotations

from datetime import date, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.enums import (
    AgeGroup,
    EventType,
    RecurrenceFrequency,
    RecurrenceTermination,
    ScopeKind,
)
from src.models.base import Base, TimestampMixin, UUIDMixin, VersionMixin


class CalendarEvent(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A standalone event or the shared definition for a recurring series."""

    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('practice', 'game', 'miscellaneous')",
            name="ck_calendar_events_event_type",
        ),
        CheckConstraint(
            "length(btrim(name)) > 0",
            name="ck_calendar_events_name_not_blank",
        ),
        CheckConstraint(
            "(is_all_day AND event_type = 'miscellaneous' "
            "AND start_time IS NULL AND end_time IS NULL) OR "
            "(NOT is_all_day AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND start_time < end_time)",
            name="ck_calendar_events_time_configuration",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_calendar_events_version_positive",
        ),
        Index("ix_calendar_events_first_date", "first_date"),
    )

    event_type: Mapped[EventType] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_all_day: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    scopes: Mapped[list[CalendarEventScope]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recurrence_series: Mapped[RecurrenceSeries | None] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
        uselist=False,
    )


class CalendarEventScope(UUIDMixin, Base):
    """One academy-wide or age-group audience row for a calendar event."""

    __tablename__ = "calendar_event_scopes"
    __table_args__ = (
        CheckConstraint(
            "(scope_kind = 'age_group' "
            "AND age_group IN ('J', 'U11', 'U13', 'U15')) OR "
            "(scope_kind = 'all_academy' AND age_group IS NULL)",
            name="ck_calendar_event_scopes_kind_age_group",
        ),
        UniqueConstraint(
            "event_id",
            "scope_kind",
            "age_group",
            name="uq_calendar_event_scopes_event_kind_age_group",
        ),
        Index(
            "uq_calendar_event_scopes_all_academy",
            "event_id",
            unique=True,
            postgresql_where=text("scope_kind = 'all_academy'"),
        ),
    )

    event_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_kind: Mapped[ScopeKind] = mapped_column(String(20), nullable=False)
    age_group: Mapped[AgeGroup | None] = mapped_column(String(10), nullable=True)

    event: Mapped[CalendarEvent] = relationship(back_populates="scopes")


class RecurrenceSeries(UUIDMixin, TimestampMixin, Base):
    """A fixed weekly or yearly recurrence rule owned by one event."""

    __tablename__ = "recurrence_series"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('weekly', 'yearly')",
            name="ck_recurrence_series_frequency",
        ),
        CheckConstraint(
            "termination IN ('never', 'end_date', 'occurrence_count')",
            name="ck_recurrence_series_termination",
        ),
        CheckConstraint(
            "(frequency = 'weekly' AND weekday BETWEEN 0 AND 6 "
            "AND month IS NULL AND month_day IS NULL) OR "
            "(frequency = 'yearly' AND weekday IS NULL "
            "AND month BETWEEN 1 AND 12 "
            "AND month_day BETWEEN 1 AND 31)",
            name="ck_recurrence_series_frequency_fields",
        ),
        CheckConstraint(
            "(termination = 'never' AND end_date IS NULL "
            "AND occurrence_count IS NULL) OR "
            "(termination = 'end_date' AND end_date IS NOT NULL "
            "AND occurrence_count IS NULL) OR "
            "(termination = 'occurrence_count' AND end_date IS NULL "
            "AND occurrence_count > 0)",
            name="ck_recurrence_series_termination_fields",
        ),
        UniqueConstraint(
            "event_id",
            name="uq_recurrence_series_event_id",
        ),
        Index(
            "ix_recurrence_series_frequency_termination",
            "frequency",
            "termination",
        ),
    )

    event_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    frequency: Mapped[RecurrenceFrequency] = mapped_column(
        String(20),
        nullable=False,
    )
    weekday: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    month_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    termination: Mapped[RecurrenceTermination] = mapped_column(
        String(20),
        nullable=False,
    )
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    occurrence_count: Mapped[int | None] = mapped_column(nullable=True)

    event: Mapped[CalendarEvent] = relationship(
        back_populates="recurrence_series",
    )
    exceptions: Mapped[list[OccurrenceException]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OccurrenceException(UUIDMixin, TimestampMixin, VersionMixin, Base):
    """A stable occurrence-level replacement, move, or deletion."""

    __tablename__ = "occurrence_exceptions"
    __table_args__ = (
        CheckConstraint(
            "(is_deleted AND event_type IS NULL AND name IS NULL "
            "AND is_all_day IS NULL AND start_time IS NULL "
            "AND end_time IS NULL) OR "
            "(NOT is_deleted AND event_type IS NOT NULL "
            "AND event_type IN ('practice', 'game', 'miscellaneous') "
            "AND name IS NOT NULL AND length(btrim(name)) > 0 "
            "AND is_all_day IS NOT NULL AND "
            "((is_all_day AND event_type = 'miscellaneous' "
            "AND start_time IS NULL AND end_time IS NULL) OR "
            "(NOT is_all_day AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND start_time < end_time)))",
            name="ck_occurrence_exceptions_snapshot",
        ),
        CheckConstraint(
            "version_number >= 1",
            name="ck_occurrence_exceptions_version_positive",
        ),
        UniqueConstraint(
            "series_id",
            "original_date",
            name="uq_occurrence_exceptions_series_original_date",
        ),
        Index(
            "ix_occurrence_exceptions_series_replacement_date",
            "series_id",
            "replacement_date",
        ),
    )

    series_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("recurrence_series.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_date: Mapped[date] = mapped_column(Date, nullable=False)
    replacement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_type: Mapped[EventType | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_all_day: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    series: Mapped[RecurrenceSeries] = relationship(back_populates="exceptions")
    scopes: Mapped[list[OccurrenceExceptionScope]] = relationship(
        back_populates="exception",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class OccurrenceExceptionScope(UUIDMixin, Base):
    """One effective audience row belonging to an occurrence exception."""

    __tablename__ = "occurrence_exception_scopes"
    __table_args__ = (
        CheckConstraint(
            "(scope_kind = 'age_group' "
            "AND age_group IN ('J', 'U11', 'U13', 'U15')) OR "
            "(scope_kind = 'all_academy' AND age_group IS NULL)",
            name="ck_occurrence_exception_scopes_kind_age_group",
        ),
        UniqueConstraint(
            "exception_id",
            "scope_kind",
            "age_group",
            name="uq_occurrence_exception_scopes_exception_kind_age_group",
        ),
        Index(
            "uq_occurrence_exception_scopes_all_academy",
            "exception_id",
            unique=True,
            postgresql_where=text("scope_kind = 'all_academy'"),
        ),
    )

    exception_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("occurrence_exceptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_kind: Mapped[ScopeKind] = mapped_column(String(20), nullable=False)
    age_group: Mapped[AgeGroup | None] = mapped_column(String(10), nullable=True)

    exception: Mapped[OccurrenceException] = relationship(
        back_populates="scopes",
    )
