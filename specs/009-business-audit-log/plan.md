# Implementation Plan: Business Audit Log and Recent Academy Activity

**Branch**: `009-business-audit-log` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-business-audit-log/spec.md`

## Summary

Create a separate append-only business-audit capability for successful coach, player, team, roster, and calendar mutations. Each externally initiated mutation will stage exactly one `BusinessAuditEvent` in the existing mutation service transaction, using immutable actor/target snapshots, allowlisted metadata, and historical UUIDs without strict foreign keys. A Head Coach-only `/api/v1/audit-log` page and bounded `/api/v1/audit-log/recent?limit=4` query will use the same retrieval service. The frontend will add role-protected navigation, a responsive filterable Audit Log page, and real Head Coach dashboard activity while leaving the existing authentication/security audit system untouched.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript with React 19.2.7

**Primary Dependencies**: FastAPI 0.139+, SQLAlchemy 2.x async sessions, Alembic, Pydantic 2.x, PostgreSQL/asyncpg, React Router 8, Tailwind CSS 4, Vitest, Testing Library, Playwright

**Storage**: PostgreSQL with a new append-only `business_audit_events` table and reversible Alembic migration `012`; historical actor and polymorphic target UUIDs have no strict foreign keys.

**Testing**: `pytest`, `pytest-asyncio`, `pytest-mock`, backend integration fixtures, Vitest, Testing Library, and Playwright. Existing Ruff, mypy, ESLint, TypeScript build, and migration checks remain required.

**Target Platform**: Linux-hosted FastAPI web service and responsive browser application from 320px through desktop widths.

**Project Type**: Full-stack web application with a PostgreSQL-backed API and React frontend.

**Runtime behavior**: Every list request is bounded to at most 100 events; the dashboard request is bounded to four. The Recent academy activity request must load independently and must not block or fail the remaining dashboard sections. Indexed newest-first retrieval and stored snapshots avoid N+1 feed queries.

**Constraints**: Preserve the existing authentication/security audit boundary; no new runtime dependencies; one event per external mutation; no audit updates/deletes/cleanup; existing optimistic-concurrency and safe-error behavior must remain intact; timestamps display in `America/Los_Angeles`; sensitive metadata is allowlisted and sanitized before persistence.

**Scale/Scope**: Long-lived append-only history with potentially millions of events over time; initial action catalogue is limited to coach, player, team, roster, and calendar workflows. Full-log pages contain 20 events by default and at most 100; dashboard activity contains at most four. Match, performance, player-statistics, Assistant Coach feed, and Player feed remain out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Clean Code**: PASS. The design introduces focused model, service, schema, route, feature-hook, and presentation responsibilities and avoids low-level event hooks that would duplicate business events.
- **II. Simple UX**: PASS. The dashboard keeps its existing activity composition; Audit Log uses familiar filters, pagination, disclosures, and retry states.
- **III. Responsive Design**: PASS. The design explicitly supports 320px through desktop widths, wrapping filters, visible focus, touch targets, and no horizontal overflow.
- **IV. Minimal Dependencies**: PASS. No new dependency is required; `Intl.DateTimeFormat` supplies timezone and relative-time formatting.
- **V. Testing Discipline**: PASS. The plan includes backend unit/integration tests, frontend unit/component tests, the required quickstart test, and one Playwright journey.
- **VI. MCP Server Priority**: PASS WITH FALLBACK. Codebase-memory was used during specification/clarification; its transport was unavailable during this plan turn, so direct repository inspection and bounded research were used as the documented fallback.
- **VII. Database Schema Migrations**: PASS. Migration `012_create_business_audit_events.py` is required, reversible where possible, and included in PostgreSQL validation.
- **VIII. UX Completeness in Specs**: PASS. The spec and UI contract reference `PRODUCT.md` and `DESIGN.md` and define all primary loading, empty, error, unauthorized, disclosure, responsive, and accessibility states.
- **IX. Optimistic Concurrency Control**: PASS. Existing domain OCC remains authoritative; audit events deliberately have no version field and commit in the same transaction as the mutation.
- **X. Strongly-Typed API Boundaries**: PASS. Pydantic response models and mirrored TypeScript types are planned; no inline `any` shapes are introduced.
- **XI. Frontend State & Component Discipline**: PASS. The feature is split into API, hook, page, list item, filters, states, and time utilities; existing shared components are reused.
- **XII. Documentation**: PASS. Implementation tasks include `docs/business-audit-log.md` after verification, including purpose, flows, API surface, and retention policy.

## Project Structure

### Documentation (this feature)

```text
specs/009-business-audit-log/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── business-audit-api.md
│   └── business-audit-ui.md
└── tasks.md                         # created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── business_audit_event.py          # new
│   │   └── __init__.py                      # export new model
│   ├── services/
│   │   ├── business_audit_service.py        # new writer/query service
│   │   ├── player_service.py                # audited transaction boundary
│   │   ├── team_service.py                  # audited team/roster boundary
│   │   ├── coach_service.py                 # audited coach boundary
│   │   ├── user_service.py                  # centralized activation/deactivation boundary
│   │   └── calendar_service.py              # audited event/series/occurrence boundary
│   ├── schemas/
│   │   └── business_audit.py                # new typed API contracts
│   ├── routes/
│   │   ├── business_audit.py                # new Head Coach-only read routes
│   │   ├── players.py                       # pass actor context
│   │   ├── teams.py                         # pass actor context
│   │   ├── coaches.py                       # pass actor context
│   │   ├── users.py                         # pass actor context/centralize coach status
│   │   └── calendar.py                      # pass actor context
│   ├── main.py                              # register separate router
│   └── migrations/versions/
│       └── 012_create_business_audit_events.py # new reversible migration
└── tests/
    ├── unit/
    │   ├── test_business_audit_service.py
    │   ├── test_business_audit_routes.py
    │   └── existing domain/route tests extended
    ├── integration/
    │   ├── test_business_audit_logging.py
    │   └── quickstart/test_009_quickstart_flow.py
    └── conftest.py                          # isolated fixtures as needed

frontend/
├── src/
│   ├── features/audit/
│   │   ├── api/businessAuditApi.ts
│   │   ├── types/businessAudit.ts
│   │   ├── hooks/useBusinessAudit.ts
│   │   ├── components/
│   │   │   ├── BusinessAuditFilters.tsx
│   │   │   ├── BusinessAuditEventItem.tsx
│   │   │   ├── BusinessAuditEventList.tsx
│   │   │   └── BusinessAuditStates.tsx
│   │   ├── pages/BusinessAuditLogPage.tsx
│   │   └── utils/businessAuditTime.ts
│   ├── layouts/AppLayout.tsx                 # Head Coach nav item
│   ├── app/router.tsx                        # role-protected route
│   ├── pages/ForbiddenPage.tsx               # generalized forbidden copy
│   ├── pages/home/HomeSchedule.tsx           # dynamic four-item activity
│   ├── pages/home/HomePage.tsx               # auth-aware dashboard composition
│   └── shared/components/icons/NavIcons.tsx  # category/navigation icon if needed
├── e2e/
│   └── audit-log-flow.spec.ts                # required journey
└── playwright.config.ts

docs/
└── business-audit-log.md                     # written after implementation verification
```

**Structure Decision**: Use the existing split `backend/src` + `backend/tests` and `frontend/src` + `frontend/e2e` web-application structure. Business audit code gets its own backend modules and `frontend/src/features/audit` module; existing domain services, routes, shell, dashboard, shared UI components, and test fixtures are extended rather than parallel infrastructure being created. Security audit files remain untouched.

## Design Decisions

### Transaction integration

Each externally initiated mutation receives an immutable actor context from its route. The outer public service method validates and applies its complete mutation, flushes domain rows, creates exactly one `BusinessAuditEvent`, flushes it, and commits. Existing service rollback paths cover both domain and audit rows. Internal helpers, ORM listeners, `AuthService`, and security `AuditService` never create business events.

For calendar deletion and occurrence operations, target labels/IDs are captured before deletion. For updates, changed field names and safe counts are computed from the pre/post business values without storing unrestricted snapshots. For occurrence operations, the recurrence-series UUID is the target ID and original occurrence date is allowlisted metadata.

### Historical identifiers

The new migration does not add foreign keys for actor or polymorphic target UUID fields. It adds ordinary indexes for filtering. Domain deletion therefore cannot cascade to audit rows, and the stored snapshots remain sufficient for feed rendering.

### Read contracts

`GET /api/v1/audit-log` provides Head Coach-only filtering and pagination. `GET /api/v1/audit-log/recent?limit=4` provides a strict bounded dashboard query. `GET /api/v1/audit-log/actors` provides bounded Head Coach-only actor filter options derived from historical actor snapshots. The full-log and recent routes call one query/service implementation and serialize the same safe event shape.

### Frontend role protection

The route is nested under the existing authenticated app layout and wrapped in a reusable Head Coach role guard. The sidebar filters the item for usability; the backend `require_role(HEAD_COACH)` dependency remains authoritative. The generalized forbidden page accepts feature-specific copy instead of hard-coding Coaches Portal text.

## Implementation Phases

### Phase 1: Backend foundation and migration

1. Add `BusinessAuditEvent`, action/category/entity vocabulary, indexes, and migration `012` with no strict actor/target foreign keys and no update timestamp.
2. Add immutable actor/target contexts, action registry, allowlist sanitizer, summary builders, and `BusinessAuditService.record()` that accepts the caller session, flushes, and never commits.
3. Add typed list/recent schemas, filter validation, inclusive academy-local date conversion, deterministic ordering, and bounded query methods.
4. Add bounded actor-options schemas/query behavior and a separate Head Coach-only `business_audit` router for the full-log, recent-activity, and actor-options routes; register it in `src/main.py` without touching auth audit routes.

### Phase 2: Transactional domain integration

1. Pass actor/request context from player and team routes into services; add one event at each outer mutation boundary.
2. Integrate coach creation and team assignment replacement; ensure Assistant Coach creation is audited once regardless of the canonical creation route.
3. Centralize coach activation/deactivation in the existing user/coach service transaction so status/session changes and exactly one business event commit together.
4. Integrate standalone calendar, series, and occurrence mutation methods with pre-delete snapshots and allowlisted recurrence/occurrence metadata.
5. Update existing unit/route tests whose service signatures or commit expectations change; verify security audit behavior is unchanged.

### Phase 3: Frontend Audit Log and dashboard

1. Add typed API client, actor-options query, query hooks, filter state, abort/stale-result protection, and dedicated `America/Los_Angeles` timestamp/relative-time utilities.
2. Build the Audit Log page using shared shell, pagination, empty/error/loading patterns, accessible filters, native disclosures, and responsive layout.
3. Add Head Coach-only navigation and route guard; generalize forbidden copy while preserving existing Coaches Portal behavior.
4. Replace static `HomeSchedule` activity data with the bounded recent query, retaining the current timeline composition and adding View all activity, empty, and compact retry states; gate the section and request on the authenticated Head Coach role so Assistant Coaches and Players do not initiate the query.

### Phase 4: Verification and documentation

1. Add business-audit unit, route, integration, quickstart, frontend, and Playwright coverage required by the spec.
2. Validate migration upgrade/downgrade and transaction rollback behavior against local PostgreSQL.
3. Run backend/frontend lint, type checks, unit tests, build, and Playwright journey.
4. Write `docs/business-audit-log.md` after verification, including business/security boundary, action catalogue, API surface, safe metadata rules, and intended future retention policy.

## Verification Plan

- **Persistence**: inspect the migration for creation-only timestamp, UUID generation, indexes, no strict historical-ID foreign keys, and reversible downgrade.
- **Atomicity**: assert one event on each successful external mutation; inject event flush/commit failures and assert domain rollback; assert failed validation/authorization creates no business event.
- **Safety**: test allowlist rejection/removal of credentials, tokens, secrets, raw payloads, raw exceptions, and unrestricted snapshots; verify security audit tables/routes remain unchanged.
- **Retrieval**: test filters, bounded actor options, inclusive date boundaries, rejection of ranges over 366 academy dates before query execution, invalid combinations, page metadata, `created_at DESC, id DESC`, and recent limit enforcement.
- **Authorization**: test Head Coach `200`, Assistant Coach/Player `403`, unauthenticated `401`, hidden navigation, direct forbidden route, and no unauthorized data rendering.
- **UI**: test all loading/empty/no-results/error/retry/disclosure states, dashboard isolation, focus/status announcements, responsive wrapping, and academy-local timestamp/relative-time formatting.
- **E2E**: perform existing administrative actions as Head Coach, verify dashboard latest four, navigate to full log, filter, expand details, and verify unauthorized role access.

## Constitution Re-check After Design

- **I–V**: PASS. The design remains modular, simple for users, responsive, dependency-neutral, and fully testable with required unit/integration/E2E coverage.
- **VI**: PASS WITH FALLBACK. Research used codebase-memory output where available and direct inspection when its transport closed; no design decision depends on an unverified external source.
- **VII**: PASS. The data-model and migration artifact specify the required reversible schema migration and PostgreSQL validation.
- **VIII**: PASS. UI behavior, design references, states, accessibility, and responsive requirements are represented in the UI contract and quickstart.
- **IX**: PASS. Existing OCC checks remain at mutation boundaries; immutable audit records have no version field and cannot be edited.
- **X–XI**: PASS. API/UI types are explicit and the frontend work is split into focused modules using existing components.
- **XII**: PASS. Post-implementation documentation is included as a Phase 4 deliverable.

## Complexity Tracking

No constitution violations require justification. The feature adds a new domain capability and migration because the specification requires a separate append-only business history; no parallel security logging infrastructure or new dependency is introduced.
