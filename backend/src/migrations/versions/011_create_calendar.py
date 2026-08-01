"""Create calendar event, recurrence, scope, and exception tables.

Revision ID: 011
Revises: 010
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | Sequence[str] | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_primary_key() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def _version_number() -> sa.Column:
    return sa.Column(
        "version_number",
        sa.Integer(),
        server_default=sa.text("1"),
        nullable=False,
    )


def upgrade() -> None:
    """Create the complete persisted calendar foundation."""

    op.create_table(
        "calendar_events",
        _uuid_primary_key(),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("first_date", sa.Date(), nullable=False),
        sa.Column(
            "is_all_day",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        _created_at(),
        _updated_at(),
        _version_number(),
        sa.CheckConstraint(
            "event_type IN ('practice', 'game', 'miscellaneous')",
            name="ck_calendar_events_event_type",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0",
            name="ck_calendar_events_name_not_blank",
        ),
        sa.CheckConstraint(
            "(is_all_day AND event_type = 'miscellaneous' "
            "AND start_time IS NULL AND end_time IS NULL) OR "
            "(NOT is_all_day AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND start_time < end_time)",
            name="ck_calendar_events_time_configuration",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_calendar_events_version_positive",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calendar_events_first_date",
        "calendar_events",
        ["first_date"],
    )

    op.create_table(
        "calendar_event_scopes",
        _uuid_primary_key(),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("scope_kind", sa.String(length=20), nullable=False),
        sa.Column("age_group", sa.String(length=10), nullable=True),
        sa.CheckConstraint(
            "(scope_kind = 'age_group' "
            "AND age_group IN ('J', 'U11', 'U13', 'U15')) OR "
            "(scope_kind = 'all_academy' AND age_group IS NULL)",
            name="ck_calendar_event_scopes_kind_age_group",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["calendar_events.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "scope_kind",
            "age_group",
            name="uq_calendar_event_scopes_event_kind_age_group",
        ),
    )
    op.create_index(
        "uq_calendar_event_scopes_all_academy",
        "calendar_event_scopes",
        ["event_id"],
        unique=True,
        postgresql_where=sa.text("scope_kind = 'all_academy'"),
    )

    op.create_table(
        "recurrence_series",
        _uuid_primary_key(),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
        sa.Column("month", sa.SmallInteger(), nullable=True),
        sa.Column("month_day", sa.SmallInteger(), nullable=True),
        sa.Column("termination", sa.String(length=20), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "frequency IN ('weekly', 'yearly')",
            name="ck_recurrence_series_frequency",
        ),
        sa.CheckConstraint(
            "termination IN ('never', 'end_date', 'occurrence_count')",
            name="ck_recurrence_series_termination",
        ),
        sa.CheckConstraint(
            "(frequency = 'weekly' AND weekday BETWEEN 0 AND 6 "
            "AND month IS NULL AND month_day IS NULL) OR "
            "(frequency = 'yearly' AND weekday IS NULL "
            "AND month BETWEEN 1 AND 12 "
            "AND month_day BETWEEN 1 AND 31)",
            name="ck_recurrence_series_frequency_fields",
        ),
        sa.CheckConstraint(
            "(termination = 'never' AND end_date IS NULL "
            "AND occurrence_count IS NULL) OR "
            "(termination = 'end_date' AND end_date IS NOT NULL "
            "AND occurrence_count IS NULL) OR "
            "(termination = 'occurrence_count' AND end_date IS NULL "
            "AND occurrence_count > 0)",
            name="ck_recurrence_series_termination_fields",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["calendar_events.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            name="uq_recurrence_series_event_id",
        ),
    )
    op.create_index(
        "ix_recurrence_series_frequency_termination",
        "recurrence_series",
        ["frequency", "termination"],
    )

    op.create_table(
        "occurrence_exceptions",
        _uuid_primary_key(),
        sa.Column(
            "series_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("original_date", sa.Date(), nullable=False),
        sa.Column("replacement_date", sa.Date(), nullable=True),
        sa.Column("event_type", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("is_all_day", sa.Boolean(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        _created_at(),
        _updated_at(),
        _version_number(),
        sa.CheckConstraint(
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
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_occurrence_exceptions_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["recurrence_series.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "original_date",
            name="uq_occurrence_exceptions_series_original_date",
        ),
    )
    op.create_index(
        "ix_occurrence_exceptions_series_replacement_date",
        "occurrence_exceptions",
        ["series_id", "replacement_date"],
    )

    op.create_table(
        "occurrence_exception_scopes",
        _uuid_primary_key(),
        sa.Column(
            "exception_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("scope_kind", sa.String(length=20), nullable=False),
        sa.Column("age_group", sa.String(length=10), nullable=True),
        sa.CheckConstraint(
            "(scope_kind = 'age_group' "
            "AND age_group IN ('J', 'U11', 'U13', 'U15')) OR "
            "(scope_kind = 'all_academy' AND age_group IS NULL)",
            name="ck_occurrence_exception_scopes_kind_age_group",
        ),
        sa.ForeignKeyConstraint(
            ["exception_id"],
            ["occurrence_exceptions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exception_id",
            "scope_kind",
            "age_group",
            name="uq_occurrence_exception_scopes_exception_kind_age_group",
        ),
    )
    op.create_index(
        "uq_occurrence_exception_scopes_all_academy",
        "occurrence_exception_scopes",
        ["exception_id"],
        unique=True,
        postgresql_where=sa.text("scope_kind = 'all_academy'"),
    )


def downgrade() -> None:
    """Drop calendar children before their owning event definitions."""

    op.drop_index(
        "uq_occurrence_exception_scopes_all_academy",
        table_name="occurrence_exception_scopes",
    )
    op.drop_table("occurrence_exception_scopes")
    op.drop_index(
        "ix_occurrence_exceptions_series_replacement_date",
        table_name="occurrence_exceptions",
    )
    op.drop_table("occurrence_exceptions")
    op.drop_index(
        "ix_recurrence_series_frequency_termination",
        table_name="recurrence_series",
    )
    op.drop_table("recurrence_series")
    op.drop_index(
        "uq_calendar_event_scopes_all_academy",
        table_name="calendar_event_scopes",
    )
    op.drop_table("calendar_event_scopes")
    op.drop_index(
        "ix_calendar_events_first_date",
        table_name="calendar_events",
    )
    op.drop_table("calendar_events")
