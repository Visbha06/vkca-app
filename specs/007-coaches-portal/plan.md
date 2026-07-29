# Implementation Plan: Coaches Portal

**Branch**: `007-coaches-portal` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-coaches-portal/spec.md`

## Summary

Build a role-gated Coaches Portal with a paginated card grid, status filtering, coach details modal, Add Coach with one-time temporary password, activate/deactivate with session revocation, and many-to-many team-coach assignment management. Backend adds a `team_coaches` join table, a coach-listing endpoint with server-side filtering and pagination, a coach-creation endpoint with temporary-password generation, a reactivation endpoint, team-assignment endpoints, and extends authorization checks. Frontend replaces the placeholder `CoachesPage` with a full feature module reusing existing card, modal, pagination, and form patterns.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy (async), Pydantic v2, asyncpg, Argon2 (backend); React 19, React Router, Tailwind CSS v4, Vitest, Playwright (frontend)

**Storage**: PostgreSQL 16 (Docker-hosted)

**Testing**: pytest + pytest-asyncio (backend unit/integration), Vitest + React Testing Library (frontend unit), Playwright (E2E)

**Target Platform**: Web application — Linux server (Uvicorn), modern evergreen browsers

**Project Type**: Full-stack web application (monorepo)

**Performance Goals**: Coach list rendered within 2s under normal network conditions (SC-001); status toggle reflected within 3s (SC-003); assignment update reflected within 5s (SC-004)

**Constraints**: WCAG 2.1 AA accessibility; responsive 320px–2560px viewports; no hardcoded pixel values per Tailwind scale rules (Constitution III, XI); one E2E Playwright test required (Constitution V)

**Scale/Scope**: Small academy — tens of coaches, tens of teams. No horizontal scaling concerns.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Code | ✅ PASS | New backend service (`CoachService`) and frontend feature module (`features/coaches/`) follow single-responsibility pattern. Existing patterns reused. |
| II. Simple UX | ✅ PASS | Coach cards are one-click triggers to details; Add Coach and Edit Assignments are straightforward modal workflows. Each screen has one primary action (browse/list). |
| III. Responsive Design | ✅ PASS | Coach card grid follows existing `PlayerCardGrid` responsive pattern (1 col mobile, 2 col tablet, 3 col desktop). Modals use existing `ModalDialog` with internal scrolling. |
| IV. Minimal Dependencies | ✅ PASS | No new dependencies. `secrets` (stdlib) for temporary password generation. All existing packages sufficient. |
| V. Testing Discipline | ✅ PASS | Unit tests mandatory for all new backend routes/services and frontend components. One E2E Playwright test covering full Head Coach journey. Quickstart validation test at `backend/tests/integration/quickstart/test_007_quickstart_flow.py`. |
| VI. MCP Server Priority | ✅ PASS | Codebase exploration uses MCP servers; no conflict. |
| VII. Database Schema Migrations | ✅ PASS | New `team_coaches` table requires an Alembic migration. |
| VIII. UX Completeness in Specs | ✅ PASS | Spec covers all UI states (loading, empty, error, filtered-no-results, success, permission, conflict), responsive behavior, accessibility, and references PRODUCT.md + DESIGN.md. |
| IX. Optimistic Concurrency Control | ✅ PASS | Coach status changes and team-assignment updates include `version_number`; stale writes rejected with HTTP 409. Uses existing `check_and_increment_version`. |
| X. Strongly-Typed API Boundaries | ✅ PASS | New frontend TypeScript types mirror new Pydantic schemas. No `any` types or inline objects. |
| XI. Tailwind CSS | ✅ PASS | Coach card styles follow existing patterns with standard Tailwind classes. No hardcoded pixel values. |
| XII. Documentation | ✅ PASS | `docs/coaches-portal.md` to be written after implementation (per Constitution). |

**Gate Result**: All 12 principles pass. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/007-coaches-portal/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── team_coach.py                    # NEW: TeamCoach join model
│   ├── schemas/
│   │   └── coach.py                         # NEW: CoachList, CoachDetail, CoachCreate, assignment schemas
│   ├── routes/
│   │   ├── coaches.py                       # NEW: /coaches endpoints
│   │   └── users.py                         # MODIFY: Add reactivate endpoint
│   ├── services/
│   │   ├── coach_service.py                 # NEW: coach list/create/status/assignment logic
│   │   └── user_service.py                  # MODIFY: add reactivate_user method
│   └── migrations/
│       └── versions/
│           └── XXXX_create_team_coaches.py   # NEW: Migration for team_coaches table
└── tests/
    ├── unit/
    │   ├── test_coach_routes.py             # NEW
    │   ├── test_coach_schemas.py            # NEW
    │   └── test_coach_service.py            # NEW
    └── integration/
        └── quickstart/
            └── test_007_quickstart_flow.py  # NEW (Constitution V)

frontend/
├── src/
│   ├── features/
│   │   └── coaches/                         # NEW: Feature module
│   │       ├── api/
│   │       │   └── coachApi.ts              # NEW: API client for coach endpoints
│   │       ├── components/
│   │       │   ├── coach-directory/         # NEW: CoachCard, CoachCardGrid, CoachesPageHeader, CoachStatusFilter
│   │       │   ├── coach-details/           # NEW: CoachDetailsModal, CoachIdentity, CoachRoleBadge, CoachStatusToggle
│   │       │   ├── coach-form/              # NEW: AddCoachModal, AddCoachForm, TemporaryPasswordDisplay
│   │       │   └── coach-assignments/       # NEW: TeamAssignmentsModal
│   │       ├── hooks/
│   │       │   └── useCoachDirectory.ts     # NEW: Data-fetching and state hook
│   │       ├── pages/
│   │       │   └── CoachesPage.tsx          # MODIFY: Replace placeholder
│   │       ├── types/
│   │       │   └── coach.ts                 # NEW: TypeScript types mirroring Pydantic schemas
│   │       └── index.ts                     # NEW: Barrel export
│   ├── pages/
│   │   ├── CoachesPage.tsx                  # REPLACE: Delegate to feature module page
│   │   └── ForbiddenPage.tsx                # NEW: Shared 403 page for Player-role route access
│   ├── layouts/
│   │   └── AppLayout.tsx                    # MODIFY: Hide Coaches Portal nav item for Player-role
│   └── app/
│       └── router.tsx                       # MODIFY: Add role guard for /coaches route
└── e2e/
    └── coaches-flow.spec.ts                 # NEW: Playwright E2E test (Constitution V)
```

**Structure Decision**: Follows the existing feature-module pattern established by `players/` and `teams/`. Backend follows existing `models/`, `schemas/`, `routes/`, `services/` conventions. New `ForbiddenPage` is shared across features. No new directory structure patterns introduced.

## Complexity Tracking

> No constitution violations. No justifications required.
