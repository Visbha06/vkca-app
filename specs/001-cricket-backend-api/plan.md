# Implementation Plan: Cricket Team Management Backend API

**Branch**: `001-cricket-backend-api` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-cricket-backend-api/spec.md`

## Summary

Backend-only FastAPI REST service providing CRUD endpoints for cricket players, teams, matches, and match performances, with read-only career statistics aggregation. The system enforces three critical backend rules: optimistic concurrency control on all mutating operations, atomic recalculation of aggregate statistics when match performances are recorded, and server-side UTC timestamp injection on every write. PostgreSQL (Docker) serves as the data store with 11 tables, all carrying `created_at`/`updated_at` timestamps and `version_number` for OCC.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (async with asyncpg), Alembic

**Storage**: PostgreSQL (Docker-hosted, per constitution Principle VII)

**Testing**: pytest with pytest-asyncio, httpx (async test client), pytest-mock

**Target Platform**: Linux server (Docker container)

**Project Type**: web-service (backend API only — no frontend)

**Performance Goals**: Player profile creation <2s (SC-001); batch match performance submission (11 players × 3 tables) <3s (SC-002); career stats retrieval <1s (SC-004)

**Constraints**: All batch performance writes within single atomic DB transaction (FR-011, FR-016); OCC version checks on all mutating operations (FR-015); server-side timestamps exclusive (FR-017)

**Scale/Scope**: 11 tables, ~15 API endpoints, single PostgreSQL instance, local Docker deployment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Code | ✅ APPLICABLE | Single-responsibility service/route/model layers; descriptive naming throughout |
| II. Simple UX | ⏭️ N/A | Backend-only spec; no user-facing UI |
| III. Responsive Design | ⏭️ N/A | Backend-only spec; no frontend components |
| IV. Minimal Dependencies | ✅ APPLICABLE | All new deps must be added via `uv add` with justification in `pyproject.toml` |
| V. Testing Discipline | ✅ APPLICABLE | Unit tests mandatory for all endpoint handlers, services, and models. E2E test waived (no frontend). Integration tests for atomic transaction + OCC flows |
| VI. MCP Server Priority | ⏭️ N/A | No existing codebase to explore; greenfield feature |
| VII. Database Schema Migrations | ✅ APPLICABLE | Alembic migrations for all 11 tables; versioned, reversible; tested against Docker PostgreSQL |
| VIII. UX Completeness in Specs | ⏭️ N/A | Backend-only spec; no UI elements |
| IX. Optimistic Concurrency Control | ✅ DIRECTLY APPLICABLE | Core requirement — `version_number` on all tables; HTTP 409 on mismatch; DataSyncLogs audit trail |
| X. Strongly-Typed API Boundaries | ✅ APPLICABLE | Pydantic v2 schemas for all request/response models; frontend types deferred (no frontend in scope) |
| XI. Frontend State & Component Discipline | ⏭️ N/A | Backend-only spec |
| XII. Documentation | ✅ APPLICABLE | Must produce `docs/cricket-backend-api.md` after implementation |

**Gate Result**: ALL APPLICABLE PRINCIPLES PASS. No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-cricket-backend-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-endpoints.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/          # SQLAlchemy ORM models (one per table)
│   ├── schemas/         # Pydantic request/response schemas
│   ├── routes/          # FastAPI APIRouter modules (one per entity group)
│   ├── services/        # Business logic (OCC checks, stat recalculation, atomic transactions)
│   ├── middleware/       # OCC middleware, timestamp injection
│   └── migrations/      # Alembic migration scripts
├── tests/
│   ├── unit/            # Unit tests for services, schemas, middleware
│   └── integration/     # Integration tests for DB operations + OCC flows
└── pyproject.toml
```

**Structure Decision**: Single backend project. The existing `backend/` directory already contains `main.py` and `pyproject.toml`. All new code lives under `backend/src/` for clean separation from config and root-level tooling.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| E2E Playwright test waived (Principle V) | Backend-only API; no browser-renderable frontend exists in this feature. Primary user journeys are exercised through httpx async integration tests (see T053 atomic transaction, T067 OCC conflict, T067a performance timing). | Adding a Playwright-based browser test for a JSON API would test HTTP/JSON parsing rather than user-facing UI behavior, adding false coverage without genuine user-journey validation. The quickstart.md validation flow (T068) plus integration tests serve as the equivalent end-to-end verification. |
