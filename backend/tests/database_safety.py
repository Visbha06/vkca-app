"""Fail-fast protections for database-writing backend tests."""

import re

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

TEST_DATABASE_NAME_PATTERN = re.compile(r"(?:^|[._-])test(?:$|[._-])", re.IGNORECASE)


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when pytest resolves a database that is not clearly test-only."""


def database_name_from_url(database_url: str) -> str:
    """Return the decoded database-name component of a SQLAlchemy URL."""

    try:
        database_name = make_url(database_url).database
    except ArgumentError as exc:
        raise UnsafeTestDatabaseError(
            "Refusing to run backend tests because the resolved test DATABASE_URL "
            "is invalid."
        ) from exc
    if not database_name:
        raise UnsafeTestDatabaseError(
            "Refusing to run backend tests because the resolved test DATABASE_URL "
            "does not name a database."
        )
    return database_name


def assert_safe_test_database_url(database_url: str) -> str:
    """Reject URLs whose database name lacks a distinct test marker."""

    database_name = database_name_from_url(database_url)
    if TEST_DATABASE_NAME_PATTERN.search(database_name) is None:
        raise UnsafeTestDatabaseError(
            "Refusing to run backend tests against database "
            f"{database_name!r}. The resolved test DATABASE_URL must name a "
            "dedicated database with 'test' as a distinct name segment "
            "(for example, 'academy_test')."
        )
    return database_name
