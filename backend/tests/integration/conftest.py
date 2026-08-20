"""Shared fixtures for authenticated and Data Quality integration tests."""

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory, engine, get_db
from src.enums import UserRole
from src.main import app
from src.models.auth_audit_log import AuthAuditLog
from src.models.auth_session import AuthSession
from src.models.calendar import OccurrenceException, RecurrenceSeries
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.services.password_service import PasswordService
from tests.data_quality_builders import (
    PersistedQualityDataBuilder,
    assert_projection_query_count,
    build_quality_calendar_exception,
    build_quality_calendar_series,
    build_quality_coach,
    build_quality_coach_assignment,
    build_quality_player,
    build_quality_projection_session,
    build_quality_roster_membership,
    build_quality_team,
)
from tests.database_safety import assert_safe_test_database_url
from tests.integration.role_aware_dashboard_fixtures import (
    build_role_aware_calendar_occurrence,
    build_role_aware_dashboard_seed,
    build_role_aware_internal_match,
    build_role_aware_isolated_session,
    build_role_aware_linked_account,
    build_role_aware_match,
    build_role_aware_membership,
    build_role_aware_player,
    build_role_aware_team,
)


@pytest.fixture
def rag_integration_provider_config() -> dict[str, object]:
    """Expose the fake-provider seam used by isolated RAG integration tests."""

    return {
        "provider": "fake",
        "model": "gemini-embedding-001",
        "dimension": 1536,
        "batch_size": 32,
        "timeout_seconds": 30.0,
    }


@dataclass(slots=True)
class SqlQueryCounter:
    """Statements observed inside one explicitly bounded test block."""

    statements: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.statements)

    @property
    def select_count(self) -> int:
        return sum(
            statement.lstrip().upper().startswith("SELECT")
            for statement in self.statements
        )

    def assert_at_most(self, maximum: int) -> None:
        assert self.total <= maximum, (
            f"expected at most {maximum} SQL statements, observed {self.total}"
        )


class DataQualityQueryCounter:
    """Attach and safely remove a SQLAlchemy statement listener."""

    @contextmanager
    def count(self) -> Iterator[SqlQueryCounter]:
        counter = SqlQueryCounter()

        def record_statement(
            connection,
            cursor,
            statement: str,
            parameters,
            execution_context,
            executemany: bool,
        ) -> None:
            del connection, cursor, parameters, execution_context, executemany
            counter.statements.append(statement)

        sqlalchemy_event.listen(
            engine.sync_engine,
            "before_cursor_execute",
            record_statement,
        )
        try:
            yield counter
        finally:
            sqlalchemy_event.remove(
                engine.sync_engine,
                "before_cursor_execute",
                record_statement,
            )


def assert_role_aware_dashboard_query_count(
    counter: SqlQueryCounter, maximum: int
) -> None:
    """Assert a bounded SQL statement count for dashboard projections."""

    counter.assert_at_most(maximum)


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def isolated_test_database() -> AsyncIterator[None]:
    """Contain every integration test inside one rollback-only transaction."""

    assert_safe_test_database_url(str(engine.url))
    async with engine.connect() as connection:
        outer_transaction = await connection.begin()
        AsyncSessionFactory.configure(
            bind=connection,
            join_transaction_mode="create_savepoint",
        )

        async def override_get_db() -> AsyncIterator[AsyncSession]:
            async with AsyncSessionFactory() as request_session:
                yield request_session

        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = override_get_db
        try:
            yield
        finally:
            app.dependency_overrides.clear()
            transaction_was_active = outer_transaction.is_active
            try:
                if transaction_was_active:
                    await outer_transaction.rollback()
            finally:
                AsyncSessionFactory.configure(
                    bind=engine,
                    join_transaction_mode="conditional_savepoint",
                )
            if not transaction_was_active:
                raise RuntimeError(
                    "Integration test code escaped the rollback-only outer "
                    "database transaction."
                )


@pytest_asyncio.fixture
async def business_audit_transaction_session() -> AsyncIterator[AsyncSession]:
    """Yield a caller-owned transaction for flush/rollback audit assertions."""

    async with AsyncSessionFactory() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()


@pytest.fixture
def background_session_factory():
    """Expose sequential cross-session boundaries on the isolated connection."""

    return AsyncSessionFactory


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_client(
    client: httpx.AsyncClient,
) -> AsyncIterator[None]:
    """Authenticate the module's API client as a temporary Head Coach."""

    user_id = uuid4()
    email = f"integration-head-coach-{user_id.hex}@example.com"
    password = "IntegrationP@ssword1"

    async with AsyncSessionFactory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                first_name="Integration",
                last_name="Head Coach",
                email=email,
                hashed_password=PasswordService.hash_password(password),
                role=UserRole.HEAD_COACH,
                is_active=True,
            )
        )
        await setup_session.commit()

    try:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200, login.text
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield
    finally:
        client.headers.pop("Authorization", None)
        async with AsyncSessionFactory() as cleanup_session:
            await cleanup_session.execute(
                delete(AuthAuditLog).where(AuthAuditLog.user_id == user_id)
            )
            await cleanup_session.execute(
                delete(AuthSession).where(AuthSession.user_id == user_id)
            )
            await cleanup_session.execute(delete(User).where(User.id == user_id))
            await cleanup_session.commit()


@pytest.fixture
def quality_player_builder() -> Callable[..., Player]:
    """Expose isolated player records for integration datasets."""

    return build_quality_player


@pytest.fixture
def quality_team_builder() -> Callable[..., Team]:
    """Expose isolated team records for integration datasets."""

    return build_quality_team


@pytest.fixture
def quality_roster_membership_builder() -> Callable[..., TeamPlayer]:
    """Expose exact roster relationship records."""

    return build_quality_roster_membership


@pytest.fixture
def quality_coach_builder() -> Callable[..., User]:
    """Expose coach and invalid-role account records."""

    return build_quality_coach


@pytest.fixture
def quality_coach_assignment_builder() -> Callable[..., TeamCoach]:
    """Expose exact account/team assignment records."""

    return build_quality_coach_assignment


@pytest.fixture
def quality_calendar_series_builder() -> Callable[..., RecurrenceSeries]:
    """Expose recurrence series with complete owning events."""

    return build_quality_calendar_series


@pytest.fixture
def quality_calendar_exception_builder() -> Callable[..., OccurrenceException]:
    """Expose complete occurrence exception snapshots."""

    return build_quality_calendar_exception


@pytest.fixture
def quality_projection_session_builder() -> Callable[..., AsyncMock]:
    """Expose fixed projection rows for service-level integration tests."""

    return build_quality_projection_session


@pytest.fixture
def projection_query_count_assertion() -> Callable[[AsyncMock, int], None]:
    """Expose the fixed projection-query assertion."""

    return assert_projection_query_count


@pytest.fixture
def data_quality_query_counter() -> DataQualityQueryCounter:
    """Expose an engine-level SQL counter for N+1 regression tests."""

    return DataQualityQueryCounter()


@pytest.fixture
def role_aware_dashboard_seed():
    """Expose the deterministic Phase 1 dashboard seed builders."""

    return build_role_aware_dashboard_seed


@pytest.fixture
def role_aware_dashboard_query_counter() -> DataQualityQueryCounter:
    """Expose the engine-level SQL counter for dashboard tests."""

    return DataQualityQueryCounter()


@pytest.fixture
def role_aware_dashboard_query_count_assertion():
    """Expose the dashboard projection query-count assertion."""

    return assert_role_aware_dashboard_query_count


@pytest.fixture
def role_aware_dashboard_builders():
    """Expose focused deterministic builders for future dashboard scenarios."""

    return {
        "team": build_role_aware_team,
        "player": build_role_aware_player,
        "membership": build_role_aware_membership,
        "occurrence": build_role_aware_calendar_occurrence,
        "match": build_role_aware_match,
        "internal_match": build_role_aware_internal_match,
        "linked_account": build_role_aware_linked_account,
        "session": build_role_aware_isolated_session,
    }


@pytest_asyncio.fixture
async def quality_data_builder() -> AsyncIterator[PersistedQualityDataBuilder]:
    """Stage quality records inside the suite's rollback-only connection."""

    async with AsyncSessionFactory() as session:
        builder = PersistedQualityDataBuilder(session)
        try:
            yield builder
        finally:
            await session.rollback()
