# Implementation Plan: Dynamic Role-Aware Dashboard and Operational Summary

**Branch**: `011-role-aware-dashboard` | **Date**: 2026-08-10 | **Spec**:
[`spec.md`](./spec.md)

## Summary

Replace the static authenticated home dashboard with a read-time,
server-authorized operational projection for Head Coaches, Assistant Coaches,
linked Players, and unlinked Players. Extend the existing Player and Match
domain contracts without adding Match-management UI, preserve Calendar and
Business Audit semantics, and make Player-profile deactivation revoke and
reject linked Player sessions using the repository's authentication rules.

The design reuses the existing FastAPI route boundary, async SQLAlchemy
services, Calendar effective-occurrence engine, `require_role` dependency,
Business Audit registry/writer, optimistic-concurrency helpers, frontend API
client, and modal/loading/error patterns. Dashboard data is not persisted and
does not introduce background aggregation or new dependencies.

## Technical Context

**Language/Version**: Python 3.12+; TypeScript with React 19 and strict
TypeScript configuration

**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy 2 async,
asyncpg, Alembic, PostgreSQL; React, React Router, Tailwind CSS, Vitest,
Testing Library, Playwright, and the existing `openapi-typescript` toolchain

**Storage**: PostgreSQL. Current Alembic head is revision `012`; this feature
adds revision `013` for Player account linkage and final Match participant
columns, constraints, and indexes.

**Testing**: pytest, pytest-asyncio, pytest-mock, existing PostgreSQL
integration fixtures and SQL query counter, Vitest/Testing Library, and
Playwright. Ruff, mypy/strict typing, ESLint, and frontend build remain quality
gates.

**Target Platform**: Linux-hosted FastAPI service and responsive browser UI
from 320px through 2560px.

**Project Type**: Full-stack web application with an authenticated API and
React frontend.

**Performance Goals**: At least 95% of normal dashboard opens in the documented
local regression fixture reach a populated or explicit operational state within
two seconds. Dashboard projections remain bounded to at most five Upcoming
Events, twelve My Teams entries, and four Recent Academy Activity events, with
query regression coverage proving no N+1 loading.

**Constraints**: Scope comes only from the database-loaded authenticated User;
no client-supplied IDs or team sets. Calendar projection reuses the existing
45-day effective-occurrence bound and academy-local timezone. Dashboard data is
read-time only. No Match create/edit page, modal, or entry workflow is added;
no Assistant Coach capability is expanded. Successful account link/unlink/
reassignment mutations create exactly one semantically accurate Business Audit
event in the same transaction. Inactive linked Player profiles revoke sessions
and block authentication without an inactive authenticated dashboard state.

**Scale/Scope**: One academy and three database-authoritative roles. Source
record counts may grow, but each dashboard response has fixed presentation
bounds and set-based loading. The release covers dashboard projection,
participant-ready Match domain/API contracts, Player account association, and
the existing Player Directory integration; Match-management UI remains a
future feature.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Clean Code — PASS**: Extend existing domain/service seams, keep
  dashboard projection responsibilities separate, and split stateful frontend
  containers from presentational sections.
- **II. Simple UX — PASS**: Preserve the existing dashboard hierarchy, keep
  account linking inside the Player Directory, and omit the invalid Match
  quick action rather than create a dead-end route.
- **III. Responsive Design — PASS**: Use existing Tailwind scales and layout
  patterns across 320px, tablet, and desktop; add responsive and overflow tests.
- **IV. Minimal Dependencies — PASS**: No new runtime dependency is planned;
  use existing SQLAlchemy, Calendar, audit, and OpenAPI tooling.
- **V. Testing Discipline — PASS**: Add unit tests for public backend/frontend
  logic, required integration coverage for cross-module behavior, the mandated
  Playwright journey, and `test_011_quickstart_flow.py`.
- **VI. MCP Server Priority — PASS**: Codebase-memory and ripgrep MCP tools
  were used for architecture and literal repository discovery before planning.
- **VII. Database Schema Migrations — PASS**: Add reversible Alembic revision
  `013`, test upgrade/downgrade against the local PostgreSQL setup, and deploy
  schema before application code.
- **VIII. UX Completeness — PASS**: Use `PRODUCT.md` and `DESIGN.md` for the
  dashboard, Player account section, empty/loading/error/retry states,
  accessibility, and modal behavior.
- **IX. Optimistic Concurrency — PASS**: Carry Player and Match versions in
  mutations, use the existing OCC helpers, and return `409` on stale writes.
- **X. Strongly-Typed API Boundaries — PASS**: Generate TypeScript contracts
  from a repeatable OpenAPI export/check path and avoid duplicate response
  interfaces.
- **XI. Frontend State & Component Discipline — PASS**: Keep new dashboard and
  linking components modular, under the existing component-size convention,
  and use standard Tailwind spacing.
- **XII. Documentation — PASS WITH FOLLOW-UP**: Implementation must add the
  concise feature document under `docs/` after verification; planning records
  the required content in the quickstart and contract artifacts.

**Gate result**: PASS. No constitution violation requires complexity
justification.

## Project Structure

### Documentation (this feature)

```text
specs/011-role-aware-dashboard/
├── plan.md              # This implementation plan
├── research.md          # Phase 0 decisions and repository findings
├── data-model.md        # Phase 1 entities and invariants
├── quickstart.md        # Phase 1 runnable validation guide
├── contracts/
│   ├── dashboard-api.md
│   ├── player-account-linking-api.md
│   ├── match-participants-api.md
│   └── frontend-contract-generation.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── player.py
│   │   ├── match.py
│   │   └── ...existing models...
│   ├── schemas/
│   │   ├── dashboard.py       # new
│   │   ├── player_account.py  # new
│   │   ├── match.py
│   │   └── player.py
│   ├── services/
│   │   ├── dashboard_service.py       # new
│   │   ├── player_account_service.py  # new
│   │   ├── auth_service.py
│   │   ├── calendar_service.py
│   │   ├── match_service.py
│   │   └── business_audit_registry.py
│   ├── routes/
│   │   ├── dashboard.py       # new
│   │   ├── players.py
│   │   ├── matches.py
│   │   └── auth.py
│   └── migrations/versions/
│       └── 013_role_aware_dashboard_domain.py  # new
└── tests/
    ├── unit/
    ├── integration/
    └── integration/quickstart/

frontend/
├── src/
│   ├── pages/home/             # dashboard composition and sections
│   ├── features/dashboard/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── types/
│   └── features/players/       # account section and linking dialogs
├── scripts/
│   └── generate-role-aware-dashboard-types.mjs  # new
└── e2e/
    └── role-aware-dashboard-flow.spec.ts        # new
```

**Structure Decision**: This is the existing web-application layout. Backend
domain models, schemas, services, routes, and migration remain in their
current modules; dashboard-specific projection and contracts get focused
modules. The frontend retains the existing Home page and Player Directory
entry points. No `features/matches` page or Match management route is created
by this feature.

## Phase 0: Research Outcome

All technical-context unknowns are resolved in
[`research.md`](./research.md). The important implementation anchors are:

1. Server-derived role scope and a non-persisted dashboard projection.
2. A single discriminated Match participant representation with database and
   schema validation.
3. Player-side nullable unique account linkage with protected account-detail
   contracts.
4. Authentication/session enforcement for inactive linked Players, without
   restoring revoked sessions or independently disabled accounts.
5. Existing Calendar effective-occurrence and Business Audit transaction
   semantics.
6. Revision `013` and the existing OpenAPI type-generation/check pattern.

## Phase 1: Design & Contracts

### Data model design

[`data-model.md`](./data-model.md) defines the Player account FK/unique index,
Match participant columns/checks/indexes, dashboard read projections, and the
linking/deactivation state transitions. The model deliberately does not add a
dashboard table, Match participant join table, or account-claim state.

### API contract design

The `contracts/` documents define:

- the authenticated dashboard response and section states;
- Head Coach-only account lookup/link/unlink/reassignment requests and safe
  responses;
- external/internal Match create/update/read shapes and validation/error
  behavior; and
- the OpenAPI export and generated TypeScript drift-check workflow.

The dashboard route must use the authenticated User from `get_current_user`.
Account-linking routes must use Head Coach `require_role` authorization. Match
create/update contracts may support future UI callers, but this feature adds no
frontend Match management surface.

### Frontend and UX design

The Home page becomes a typed dashboard container with separate summary,
Upcoming Events, and role-panel sections. Initial loading uses reduced-motion
safe skeletons; empty, unlinked, unavailable, and retry states are explicit;
refresh preserves prior populated content. The Player Account section is
added to the existing edit/profile flow using the established dialog, focus,
conflict, and confirmation patterns. Assistant Coach action visibility is
derived from the existing usable workflows and never from a new permission.

### Validation guide

[`quickstart.md`](./quickstart.md) specifies the isolated backend quickstart,
API checks for all roles, Match invariants, Player account mutations, inactive
Player session enforcement, exact audit cardinality, migration validation, and
the Playwright journey.

## Implementation Sequencing Notes

The later task plan should sequence work in this dependency order:

1. Add revision `013` and ORM/enumeration foundations.
2. Add Match participant validation/service/API behavior and tests.
3. Add Player account contracts/service/routes, audit actions, OCC/conflict
   handling, inactive-profile session enforcement, and tests.
4. Add dashboard scoped query/projection service and endpoint tests, including
   Calendar effective-occurrence and query-bound coverage.
5. Generate frontend API types and build dashboard/account-linking API clients.
6. Replace static Home sections and integrate the Player Directory account
   section without adding Match UI.
7. Add unit, integration, quickstart, responsive/accessibility, and Playwright
   verification, then documentation under `docs/`.

## Post-Design Constitution Re-check

- **Migration and transaction ordering**: PASS — schema revision `013` is
  versioned/reversible and tested before dependent application behavior.
- **Security/session behavior**: PASS — all dashboard and linking scope is
  server-derived; linked inactive Players fail authentication and revoked
  sessions are never restored.
- **Audit behavior**: PASS — reads do not audit; successful association
  mutations stage one allowlisted event in the same transaction.
- **Typed boundary and UI states**: PASS — generated OpenAPI types, explicit
  state unions, responsive layout, focus behavior, and retry semantics are
  covered by the design artifacts.
- **Complexity**: PASS — no new dependency, persistence projection, parallel
  identity system, or Match-management UI is introduced.

**Post-design gate result**: PASS.

## Complexity Tracking

No constitution violations or complexity exceptions are planned.
