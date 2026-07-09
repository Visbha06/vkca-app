# Research: Cricket Team Management Backend API

**Date**: 2026-07-08

**Purpose**: Resolve all technical decisions and unknowns before Phase 1 design.

## Decisions

### 1. ORM & Database Driver

**Decision**: SQLAlchemy 2.0 with asyncpg (async driver)

**Rationale**:
- FastAPI's native async support pairs best with async database access to avoid blocking the event loop.
- SQLAlchemy 2.0's async session and declarative mapping provide a mature, well-documented ORM.
- asyncpg is the fastest async PostgreSQL driver for Python.
- Aligns with constitution Principle IV (Minimal Dependencies): SQLAlchemy is already the de facto standard for FastAPI + PostgreSQL — no need for additional abstraction layers.

**Alternatives considered**:
- psycopg (psycopg3) raw — more control, but requires manual SQL for relationships and migrations.
- Tortoise ORM — simpler but less mature ecosystem, fewer community resources.
- raw asyncpg with hand-written SQL — maximum performance but loses ORM productivity for 11-table schema.

### 2. Database Migrations

**Decision**: Alembic (async mode with asyncpg)

**Rationale**:
- Alembic is the official migration tool for SQLAlchemy.
- Constitution Principle VII mandates versioned, reversible migration scripts.
- Async Alembic configuration supports the asyncpg driver without blocking.
- All 11 tables + indexes + constraints defined in order: Users → Players → Teams → TeamPlayers → Matches → MatchBattingPerformance → MatchBowlingPerformance → MatchFieldingPerformance → PlayerBattingStats → PlayerBowlingStats → DataSyncLogs.

**Alternatives considered**: None — Alembic is the standard choice for SQLAlchemy projects.

### 3. Atomic Transaction Strategy

**Decision**: Explicit SQLAlchemy async session transaction context manager for batch performance submissions.

**Rationale**:
- FR-011 and FR-016 require a single atomic transaction spanning multiple table writes and aggregate recalculations.
- SQLAlchemy's `async with session.begin():` provides a clean context manager that commits on success and rolls back on any exception.
- Within the transaction: validate all player_ids and match_id → insert MatchBattingPerformance rows → insert MatchBowlingPerformance rows → insert MatchFieldingPerformance rows → SELECT existing aggregate stats → UPDATE aggregate stats → commit.
- Any validation failure or DB error triggers a rollback of all writes.

**Alternatives considered**:
- Database-level stored procedure — more performant but harder to test, version, and maintain; violates Clean Code principle.
- Application-level saga pattern — unnecessary complexity for a single-database operation.

### 4. Optimistic Concurrency Control Pattern

**Decision**: version_number column on all tables; checked in WHERE clause during UPDATE; HTTP 409 + DataSyncLogs entry on mismatch.

**Rationale**:
- Matches constitution Principle IX (Optimistic Concurrency Control).
- Pattern: `UPDATE ... SET ... version_number = :incoming_version + 1 WHERE id = :id AND version_number = :incoming_version RETURNING version_number`.
- If `rowcount = 0` → version mismatch → INSERT into DataSyncLogs → return HTTP 409.
- OCC applies to: Players (profile updates), PlayerBattingStats (stat recalculation), PlayerBowlingStats (stat recalculation), Users (profile updates). Performance tables (MatchBatting/Bowling/FieldingPerformance) are insert-only per match so OCC is not needed, but they carry `version_number` for consistency.

**Alternatives considered**:
- Pessimistic locking (SELECT FOR UPDATE) — simpler logic but blocks concurrent readers; violates async principles.
- No OCC on performance tables — considered but rejected; uniform schema simplifies tooling and future-proofs for potential updates.

### 5. Timestamp Injection

**Decision**: SQLAlchemy column defaults with `server_default=func.now()` at the database level, plus `onupdate=func.now()` for `updated_at`. Pydantic schemas exclude `created_at` and `updated_at` from request models.

**Rationale**:
- FR-017: server-side timestamps only; client-supplied values must be ignored.
- Database-level defaults ensure consistency even if application code has bugs.
- SQLAlchemy's `server_default` and `onupdate` use PostgreSQL's native `NOW()`.
- No middleware needed — the ORM layer handles it declaratively.
- Timestamps are always UTC (PostgreSQL `NOW()` returns transaction start time in server timezone; server timezone set to UTC in Docker).

**Alternatives considered**:
- Application-level `datetime.utcnow()` — works but bypasses DB consistency for direct SQL execution.
- Middleware-based injection — unnecessary overhead for a DB-level concern.

### 6. Uniqueness Constraints

**Decision**: Database-level unique constraints backed by application-level validation.

**Rationale**:
- User email: `UNIQUE` constraint on `users.email`.
- Player composite: `UNIQUE (first_name, last_name, date_of_birth)` on `players`.
- Team names: no uniqueness constraint (per spec clarification Q1).
- Database constraints are the final guard; application catches duplicates early with a SELECT-before-INSERT check and returns HTTP 409.

**Alternatives considered**:
- Application-only uniqueness — vulnerable to race conditions between concurrent inserts.
- Team name uniqueness within age_group — explicitly rejected by spec.

### 7. Enum Handling

**Decision**: Python `enum.StrEnum` classes in a shared `enums.py` module; stored as VARCHAR in PostgreSQL with CHECK constraints.

**Rationale**:
- Python 3.12 `StrEnum` provides type-safe string enums that serialize directly to JSON for API responses.
- VARCHAR storage with CHECK constraints is simpler to migrate and manage than PostgreSQL ENUM types.
- Pydantic v2 validation uses the enum class for automatic request validation.
- Enums: `UserRole`, `BattingStyle`, `BowlingStyle`, `PlayerType`, `MatchFormat`, `DismissalType`.

**Alternatives considered**:
- PostgreSQL ENUM type — requires `ALTER TYPE` for additions; harder to manage in CI/CD.
- Integer enums — less readable in database inspection; requires mapping layer.

### 8. JSON Metadata Field

**Decision**: PostgreSQL JSONB for `player_metadata`; Pydantic `dict[str, Any]` with no schema enforcement.

**Rationale**:
- The spec defines `player_metadata` as a free-form extensible JSON blob.
- JSONB supports indexing and querying if needed later.
- Pydantic v2 validates that the value is valid JSON/dict but does not enforce internal schema (per spec assumption).

**Alternatives considered**:
- JSON (non-binary) — slower queries, no indexing, deprecated in favor of JSONB.
- EAV (Entity-Attribute-Value) pattern — unnecessary complexity for metadata.

### 9. API Versioning

**Decision**: URL-prefix versioning: `/api/v1/...` as specified in the user requirements.

**Rationale**:
- Explicit version prefix in URL is the most transparent versioning strategy.
- FastAPI's `APIRouter(prefix="/api/v1")` makes this trivial.
- Future spec changes can introduce `/api/v2/` without breaking existing clients.

**Alternatives considered**:
- Header-based versioning (`Accept: application/vnd.vkca.v1+json`) — cleaner URLs but harder to discover and test.
- Query parameter versioning — non-standard.

### 10. Testing Strategy

**Decision**: pytest-asyncio with httpx.AsyncClient for API tests; separate test database.

**Rationale**:
- Constitution Principle V: unit tests mandatory for all endpoint handlers and services.
- `httpx.AsyncClient` with `ASGITransport` tests the full FastAPI stack without a running server.
- Integration tests use a real PostgreSQL test database (Docker) for OCC and atomic transaction verification.
- `pytest-mock` for isolating external dependencies (none expected in this backend-only feature).
- Test database is created fresh per test session via Alembic migrations.

**Alternatives considered**:
- `TestClient` (sync) — doesn't test async code paths properly.
- SQLite for tests — different database engine; OCC and JSONB behavior would differ from production PostgreSQL.

## Unresolved

None. All technical decisions are resolved with clear rationale.
