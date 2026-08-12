"""Migration regression coverage for revision 013 in an isolated schema."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from src.database import engine
from tests.database_safety import assert_safe_test_database_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _revision_chain() -> tuple[list[object], object]:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)
    baseline = list(reversed(list(scripts.iterate_revisions("012", "base"))))
    revision_013 = scripts.get_revision("013")
    assert revision_013 is not None
    return baseline, revision_013


def _exercise_revision_013(connection: Connection, schema_name: str) -> None:
    connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    connection.execute(text(f'SET LOCAL search_path TO "{schema_name}", public'))
    migration_context = MigrationContext.configure(connection)
    baseline, revision_013 = _revision_chain()

    with Operations.context(migration_context):
        for revision in baseline:
            revision.module.upgrade()

        user_id = uuid4()
        player_id = uuid4()
        home_team_id = uuid4()
        away_team_id = uuid4()
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, first_name, last_name, email, hashed_password, role
                ) VALUES (
                    :id, 'Migration', 'Player', :email, 'hash', 'player'
                )
                """
            ),
            {"id": user_id, "email": f"migration-{user_id.hex}@example.com"},
        )
        connection.execute(
            text(
                """
                INSERT INTO players (
                    id, first_name, last_name, date_of_birth,
                    batting_style, bowling_style, player_type
                ) VALUES (
                    :id, 'Existing', 'Accountless', DATE '2010-01-01',
                    'right', 'right-arm medium', 'all-rounder'
                )
                """
            ),
            {"id": player_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO teams (id, name, age_group)
                VALUES (:home_id, 'Home Team', 'U15'),
                       (:away_id, 'Away Team', 'U13')
                """
            ),
            {"home_id": home_team_id, "away_id": away_team_id},
        )

        revision_013.module.upgrade()

        inspector = inspect(connection)
        player_columns = {item["name"] for item in inspector.get_columns("players")}
        match_columns = {item["name"] for item in inspector.get_columns("matches")}
        assert "user_id" in player_columns
        assert {
            "participant_type",
            "home_team_id",
            "away_team_id",
            "external_opponent_name",
        } <= match_columns
        assert "opponent_name" not in match_columns
        assert (
            connection.scalar(
                text("SELECT user_id FROM players WHERE id = :id"),
                {"id": player_id},
            )
            is None
        )

        index_names = {item["name"] for item in inspector.get_indexes("matches")}
        assert {
            "ix_matches_match_date_home_team_id_id",
            "ix_matches_match_date_away_team_id_id",
        } <= index_names
        assert any(
            item["name"] == "uq_players_user_id" and item["unique"]
            for item in inspector.get_indexes("players")
        )
        assert {
            item["name"] for item in inspector.get_check_constraints("matches")
        } >= {"ck_matches_participant_type", "ck_matches_participants"}
        assert {item["name"] for item in inspector.get_foreign_keys("matches")} >= {
            "fk_matches_home_team_id_teams",
            "fk_matches_away_team_id_teams",
        }

        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    text(
                        """
                        INSERT INTO matches (
                            match_date, format, venue, result,
                            participant_type, home_team_id, away_team_id
                        ) VALUES (
                            CURRENT_DATE, 'T20', 'Academy', 'Scheduled',
                            'internal', :team_id, :team_id
                        )
                        """
                    ),
                    {"team_id": home_team_id},
                )

        connection.execute(
            text(
                """
                INSERT INTO matches (
                    match_date, format, venue, result, participant_type,
                    home_team_id, external_opponent_name
                ) VALUES (
                    CURRENT_DATE, 'T20', 'Academy', 'Scheduled', 'external',
                    :team_id, 'Northside CC'
                )
                """
            ),
            {"team_id": home_team_id},
        )
        connection.execute(text("DELETE FROM matches"))

        revision_013.module.downgrade()

        downgraded = inspect(connection)
        downgraded_player_columns = {
            item["name"] for item in downgraded.get_columns("players")
        }
        downgraded_match_columns = {
            item["name"] for item in downgraded.get_columns("matches")
        }
        assert "user_id" not in downgraded_player_columns
        assert "opponent_name" in downgraded_match_columns
        assert "participant_type" not in downgraded_match_columns
        assert (
            connection.scalar(
                text("SELECT count(*) FROM players WHERE id = :id"),
                {"id": player_id},
            )
            == 1
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_revision_013_upgrade_constraints_and_downgrade() -> None:
    """Upgrade a real revision-012 schema, validate 013, then restore 012."""

    assert_safe_test_database_url(str(engine.url))
    schema_name = f"migration_013_{uuid4().hex}"
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(_exercise_revision_013, schema_name)
        finally:
            await transaction.rollback()
