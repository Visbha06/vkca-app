"""Rename the staff user role to player.

Revision ID: 008
Revises: 007
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008"
down_revision: str | Sequence[str] | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_role(*, old: str, new: str) -> None:
    """Rename a role for both native-enum and check-constrained schemas."""

    op.execute(
        f"""
        DO $migration$
        DECLARE
            role_type_name text;
            role_type_schema text;
            role_type_kind "char";
        BEGIN
            SELECT type_namespace.nspname, role_type.typname, role_type.typtype
              INTO role_type_schema, role_type_name, role_type_kind
              FROM pg_attribute AS column_definition
              JOIN pg_class AS users_table
                ON users_table.oid = column_definition.attrelid
              JOIN pg_namespace AS table_namespace
                ON table_namespace.oid = users_table.relnamespace
              JOIN pg_type AS role_type
                ON role_type.oid = column_definition.atttypid
              JOIN pg_namespace AS type_namespace
                ON type_namespace.oid = role_type.typnamespace
             WHERE users_table.relname = 'users'
               AND table_namespace.nspname = current_schema()
               AND column_definition.attname = 'role'
               AND NOT column_definition.attisdropped;

            IF role_type_kind = 'e' THEN
                EXECUTE format(
                    'ALTER TYPE %I.%I RENAME VALUE %L TO %L',
                    role_type_schema,
                    role_type_name,
                    '{old}',
                    '{new}'
                );
            ELSE
                ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;
                UPDATE users SET role = '{new}' WHERE role = '{old}';
                ALTER TABLE users
                    ADD CONSTRAINT ck_users_role
                    CHECK (role IN ('head coach', 'assistant coach', '{new}'));
            END IF;
        END
        $migration$;
        """
    )


def upgrade() -> None:
    """Rename existing staff roles to player without changing permissions."""

    _rename_role(old="staff", new="player")


def downgrade() -> None:
    """Restore the player role name to staff."""

    _rename_role(old="player", new="staff")
