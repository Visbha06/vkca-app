# Implementation Plan: Calendar Interface

**Branch**: `008-calendar-interface` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-calendar-interface/spec.md`

## Summary

Build the authenticated VKCA Calendar page as a custom, accessible monthly grid with a Today briefing and coach-only event management. Add a PostgreSQL-backed event definition model with optional weekly/yearly recurrence and persisted occurrence exceptions; calculate only bounded academy-local ranges in `America/Los_Angeles`; expose typed calendar contracts; and reuse the project’s existing role, CSRF, modal, form, loading, toast, and optimistic-concurrency patterns.

The clarified design uses academy-local date/time fields, a stable `series_id + original_date` occurrence identity, a maximum 45-date normal range, February 29 → February 28 yearly fallback, confirmation-aware exception cleanup during series edits, and atomic hard deletion of series plus exceptions.

## Technical Context

**Language/Version**: Python 3.12+; TypeScript with React 19.2.7 and strict type checking

**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy 2 async, asyncpg, Alembic, PostgreSQL; React, React Router, Tailwind CSS, Vitest, Testing Library, Playwright. No new production dependency is required.

**Storage**: PostgreSQL with versioned Alembic migration; timezone-aware server timestamps plus academy-local event `date`/`time` fields.

**Testing**: pytest, pytest-asyncio, pytest-mock, Ruff, mypy, Vitest, Testing Library, Playwright; isolated unit tests plus the required backend quickstart integration test.

**Target Platform**: Existing Linux-hosted FastAPI service and authenticated browser application at 320px–2560px; PostgreSQL development service supplied by Docker Compose.

**Project Type**: Full-stack web application with a React frontend and FastAPI backend.

**Performance Goals**: At least 95% of normal bounded calendar-range requests display the selected month and Today state within 2 seconds under normal test conditions; recurrence expansion is bounded to at most 45 requested academy dates and configured occurrence safeguards.

**Constraints**: Academy time zone is `America/Los_Angeles`; browser local time cannot determine academy today. Normal ranges are one complete month grid plus a modest buffer and at most 45 dates. Players can read but cannot mutate. Mutations require CSRF and OCC versions, return 403/409 as specified, and do not auto-retry conflicts. No third-party full calendar, monthly recurrence, drag/drop, reminders, invitations, or external sync. React components should remain under 200 lines where practical and use existing Tailwind spacing tokens.

**Scale/Scope**: Three authenticated roles, four supported age groups, three event types, one visible month per request, weekly/yearly fixed-interval recurrence, calculated occurrences rather than future-row materialization, and one occurrence exception per series/original date.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / gate | Plan evidence | Status |
|---|---|---|
| I. Clean Code | Split recurrence/domain logic, API schemas, route handlers, hooks, grid, forms, and modals by responsibility; remove placeholder Calendar page. | PASS |
| II. Simple UX | Calendar has one clear primary coach action, direct month/year controls, shared details modal, and explicit but concise confirmation steps. | PASS |
| III. Responsive Design | Seven-column grid remains usable at 320px; controls/forms wrap or stack; responsive tests cover mobile and desktop. | PASS |
| IV. Minimal Dependencies | Use existing date utilities and Python `zoneinfo`; no calendar library or new production package. | PASS |
| V. Testing Discipline | Add backend unit/route/service tests, frontend component/API tests, `test_008_quickstart_flow.py`, and `calendar-flow.spec.ts`. | PASS |
| VI. MCP Server Priority | Existing repository patterns and literal searches were inspected before design; no additional external source is required for this local feature plan. | PASS |
| VII. Database Schema Migrations | Add a numbered reversible migration for calendar tables, constraints, indexes, and cascade relationships; verify clean upgrade/downgrade behavior. | PASS |
| VIII. UX Completeness | UI contract references `PRODUCT.md`, `DESIGN.md`, existing DateOfBirthPicker, ModalDialog, unsaved-change, toast, and focus patterns; loading/error/empty/responsive/a11y states are specified. | PASS |
| IX. Optimistic Concurrency | Event/series and exception versions are returned and checked; stale mutation responses remain HTTP 409 with reload-only recovery. | PASS |
| X. Strongly-Typed API Boundaries | Pydantic request/response schemas and mirrored frontend calendar types are defined in `contracts/calendar-api.md`. | PASS |
| XI. Frontend State & Component Discipline | Container hooks are separated from grid, event, form, and modal components; existing Tailwind tokens and shared overlays are reused. | PASS |
| XII. Documentation | Implementation must add a concise verified `docs/calendar-interface.md` after tests pass; this plan documents the intended API and validation flow. | PASS |

**Gate result**: PASS. No constitution violation requires complexity justification.

## Phase 0: Research Complete

Research decisions are recorded in [research.md](research.md). All planning unknowns are resolved:

- Academy-local wall-clock date/time fields with `zoneinfo` calculations.
- One versioned event definition with optional recurrence rule.
- Scope rows with explicit All Academy representation.
- Exception identity based on series and original date.
- Bounded 45-date range retrieval.
- Standard-library weekly/yearly recurrence arithmetic with Feb 29 fallback.
- Backend-authoritative role/OCC enforcement.
- Confirmation-aware cleanup of invalid series exceptions.
- Cascading hard deletion for series and exceptions.
- Typed range/detail/mutation contracts and existing UI infrastructure.

## Phase 1: Design & Contracts Complete

Generated artifacts:

- [data-model.md](data-model.md): entities, fields, constraints, identities, lifecycle, and transaction boundaries.
- [contracts/calendar-api.md](contracts/calendar-api.md): read, create, update, delete, conflict, and warning contracts.
- [contracts/calendar-ui.md](contracts/calendar-ui.md): roles, page structure, accessibility, states, responsive, and visual constraints.
- [quickstart.md](quickstart.md): backend quickstart, frontend tests, Playwright flow, manual checks, and quality gates.

## Project Structure

### Documentation (this feature)

```text
specs/008-calendar-interface/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── calendar-api.md
│   └── calendar-ui.md
└── tasks.md                         # created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── enums.py                     # EventType, recurrence, and scope enums
│   ├── models/
│   │   └── calendar.py              # event, recurrence, scope, exception models
│   ├── schemas/
│   │   └── calendar.py              # typed request/response contracts
│   ├── services/
│   │   ├── calendar_service.py      # validation, range expansion, mutations
│   │   └── calendar_recurrence.py   # bounded weekly/yearly calculation
│   ├── routes/
│   │   └── calendar.py              # authenticated read and coach mutation routes
│   └── migrations/versions/
│       └── 011_create_calendar.py   # calendar schema and cascade constraints
└── tests/
    ├── unit/
    │   ├── test_calendar_schemas.py
    │   ├── test_calendar_recurrence.py
    │   ├── test_calendar_service.py
    │   └── test_calendar_routes.py
    └── integration/
        ├── test_calendar_flow.py
        └── quickstart/test_008_quickstart_flow.py

frontend/
├── src/
│   ├── app/router.tsx               # retain /calendar in protected shell
│   ├── features/calendar/
│   │   ├── api/calendarApi.ts
│   │   ├── components/
│   │   │   ├── CalendarHeader.tsx
│   │   │   ├── CalendarMonthGrid.tsx
│   │   │   ├── CalendarDayCell.tsx
│   │   │   ├── CalendarEventEntry.tsx
│   │   │   ├── CalendarLoadingState.tsx
│   │   │   ├── CalendarErrorState.tsx
│   │   │   ├── TodaySection.tsx
│   │   │   ├── DayEventsModal.tsx
│   │   │   ├── EventDetailsModal.tsx
│   │   │   ├── EventFormModal.tsx
│   │   │   ├── EventForm.tsx
│   │   │   ├── RecurrenceFields.tsx
│   │   │   ├── SeriesExceptionWarning.tsx
│   │   │   └── CalendarDeleteDialog.tsx
│   │   ├── hooks/useCalendarData.ts
│   │   ├── pages/CalendarPage.tsx
│   │   ├── types/calendar.ts
│   │   └── utils/calendarLabels.ts
│   ├── pages/CalendarPage.tsx        # thin compatibility export or remove after route update
│   └── shared/
│       ├── components/icons/NavIcons.tsx       # event-type icons if shared
│       └── utils/calendarDate.ts                # extend grid/academy-date helpers
└── e2e/
    ├── calendar-flow.spec.ts
    └── calendar-api-mock.ts
```

**Structure Decision**: Use the existing two-project web application structure. Backend domain behavior belongs in `backend/src/models`, `schemas`, `services`, `routes`, and the next migration. Frontend behavior belongs in a new `features/calendar` slice with a thin route-facing page export, while stable date-grid and icon primitives stay shared only when they are genuinely reusable.

## Implementation Approach

### Backend foundation

1. Add typed event, recurrence frequency/termination, and scope enums without changing existing enum values.
2. Add the calendar migration with event definitions, optional recurrence rule, scope rows, occurrence exceptions, version fields, indexes for first dates/rule lookup and exception identity, and `ON DELETE CASCADE` relationships.
3. Add SQLAlchemy models and Pydantic schemas with database-safe constraints plus service-level cross-row invariants.
4. Implement a recurrence helper that accepts a bounded inclusive academy-local range, emits weekly/yearly dates, applies Feb 29 fallback, honors end-date/count termination, and never materializes future rows.

### Backend service and routes

1. Implement range and Today retrieval with `ZoneInfo("America/Los_Angeles")`, bounded range validation before expansion, exception suppression/application, stable identity generation, and specified ordering.
2. Implement typed event-instance detail retrieval and safe not-found behavior after concurrent changes.
3. Implement atomic standalone/series creation with scope deduplication and past/time validation.
4. Implement non-recurring update/delete with event version checks.
5. Implement occurrence-only update/delete with series and exception OCC checks, move suppression, effective snapshots, and deletion exceptions.
6. Implement series update impact calculation. Require explicit confirmation for invalidated exception dates, preserve valid exceptions, remove invalid exceptions, and update all related rows in one transaction.
7. Implement hard-delete series and cascaded exception cleanup in one transaction. Apply existing role dependencies so Player mutations return 403 before service mutation logic.

### Frontend data and interaction

1. Add mirrored TypeScript types and an API module using `apiClient`, `AbortController` signals for superseded range requests, and status-to-safe-message mapping.
2. Load Today first on initial entry to obtain the authoritative academy date and initial month; then load the complete month grid. Refresh Today after mutations when affected.
3. Build the month grid from the existing date utilities, add keyboard date movement and logical focus restoration, and render muted adjacent dates, current-date treatment, event icons, three-entry limit, and accessible overflow.
4. Build details, daily overflow, create/edit, series-warning, and delete modals on `ModalDialog`; use `useUnsavedChanges`, existing confirmation-dialog behavior, success toast, loading status, and conflict reload patterns.
5. Keep mutation controls derived from authenticated role for UX only; rely on the backend for authorization. Preserve form state across failures and block unsafe close/repeated submissions.
6. Apply `PRODUCT.md`/`DESIGN.md` tokens and responsive breakpoints; verify 320px, tablet, and desktop layouts without page overflow.

### Verification and documentation

1. Add unit coverage for recurrence arithmetic, schemas, service transitions, routes, API functions, date/grid ordering, role presentation, forms, modals, focus, loading/error/conflict, and responsive behavior.
2. Add the required isolated backend quickstart test and the Playwright coach journey with occurrence edit/delete and series deletion.
3. Run migration upgrade/downgrade verification, backend and frontend quality gates, and the quickstart guide.
4. After implementation is verified, write `docs/calendar-interface.md` as the concise built-feature documentation required by the constitution.

## Post-Design Constitution Check

| Gate | Post-design result |
|---|---|
| Clean code and component responsibility | PASS — bounded domain helpers and feature slices are explicit. |
| Responsive/accessibility/brand UX | PASS — UI contract and test matrix cover `PRODUCT.md`, `DESIGN.md`, WCAG 2.1 AA, reduced motion, and 320px use. |
| Minimal dependencies | PASS — no new production dependency is planned. |
| Migrations and database integrity | PASS — migration 011, unique occurrence identity, FK cascades, and transaction rules are defined. |
| Unit, quickstart, and E2E testing | PASS — paths and primary journey are defined. |
| OCC and authorization | PASS — event/series/exception versions and backend role guards are defined. |
| Typed API boundaries | PASS — Pydantic and TypeScript contracts are documented together. |
| Documentation | PASS — post-verification `docs/calendar-interface.md` is required. |

**Final gate result**: PASS. Ready for `/speckit-tasks`.

## Planning Tooling Note

The repository contains no `update-agent-context` script referenced by the generic workflow, so no agent-context file was modified. The plan and generated artifacts capture the project context explicitly.

## Complexity Tracking

No constitution violations identified; no complexity exception is required.
