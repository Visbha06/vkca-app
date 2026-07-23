# Implementation Plan: Players Interface

**Branch**: `005-players-interface` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-players-interface/spec.md`

## Summary

Build a full Players interface for the VK Cricket Academy web application. The backend `GET /api/v1/players` endpoint is extended with server-side pagination, team filtering (including unassigned players), and pagination metadata. The frontend renders a paginated, filterable grid of player cards within the existing `AppLayout`, a Player Details modal, and Add/Edit Player modals with shared form logic, role-based visibility, OCC conflict handling, and unsaved-changes protection. All interactions are keyboard-accessible and responsive from 320px to 2560px.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript ~6.0 (frontend)

**Primary Dependencies**: FastAPI 0.139+ / SQLAlchemy 2.0+ / asyncpg 0.31+ (backend), React 19 / React Router 7 / Tailwind CSS 4.3 (frontend)

**Storage**: PostgreSQL (Docker-hosted, via SQLAlchemy async + asyncpg)

**Testing**: pytest + pytest-asyncio + httpx (backend unit/integration), Vitest + @testing-library/react + jsdom (frontend unit), Playwright (E2E)

**Target Platform**: Web application — Linux server (backend), modern browsers (frontend, desktop + mobile)

**Project Type**: Web application — React SPA frontend + FastAPI REST backend

**Performance Goals**: Player list loads in <3s (SC-001), filter results update in <2s (SC-002), state changes communicated in <500ms (SC-007)

**Constraints**: WCAG 2.1 AA accessibility, responsive from 320px–2560px, no hardcoded pixel values, 44px minimum touch targets, Tailwind spacing scale only, no new backend or frontend dependencies expected, OCC version-check on updates

**Scale/Scope**: Academy-scale — dozens to low hundreds of active players, ~5–10 teams, single-academy instance

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Code | ✅ PASS | Shared form logic (FR-017), centralized enum mapping (FR-045–049), single-responsibility components ≤200 lines per XI |
| II. Simple UX | ✅ PASS | Three-click max: filter → card → modal or filter → "Add Player" → submit. Clear primary actions per screen |
| III. Responsive Design | ✅ PASS | Spec requires 320px–2560px (FR-066–070). Tailwind breakpoints, no hardcoded px. Mobile modals with internal scroll |
| IV. Minimal Dependencies | ✅ PASS | No new dependencies required. Existing stack covers all needs (React, Tailwind, FastAPI, SQLAlchemy) |
| V. Testing Discipline | ✅ PASS | Unit tests mandatory for all new logic (FR-071–072). Quickstart test at `backend/tests/integration/quickstart/test_005_quickstart_flow.py`. One E2E Playwright test (FR-073) |
| VI. MCP Server Priority | N/A | Not applicable to this feature |
| VII. Database Schema Migrations | ✅ PASS | No schema changes — existing `players`, `teams`, `team_players` tables suffice. Query-layer extension only |
| VIII. UX Completeness in Specs | ✅ PASS | Spec references PRODUCT.md and DESIGN.md. All states covered: loading, empty, error, filtered no-results, conflict, permissions-denied |
| IX. Optimistic Concurrency Control | ✅ PASS | Existing `version_number` on Player model. Frontend must send version with updates (FR-035) and handle 409 (FR-036–037) |
| X. Strongly-Typed API Boundaries | ✅ PASS | Frontend types must mirror backend Pydantic PlayerResponse. No `any` in components. Enum types consistent |
| XI. Frontend State & Component Discipline | ✅ PASS | Components ≤200 lines; split container/presentational as needed. Tailwind spacing scales only, no arbitrary px values |
| XII. Documentation | ✅ PASS | `docs/players-interface.md` to be created after implementation |

**Gate Result (Pre-Design)**: ALL PASS. No violations or complexity justification needed.

**Re-evaluation (Post-Design, 2026-07-22)**: After completing Phase 1 design artifacts (research.md, data-model.md, contracts/, quickstart.md), all 12 principles remain satisfied. Key confirmations:
- IV. Minimal Dependencies: No new packages. Research §11 confirms pure TS/Date for formatting, existing useModalDialog for modals.
- VII. DB Migrations: No schema changes. All additions are query-layer extensions.
- X. Strongly-Typed API: TypeScript types in data-model.md strictly mirror Pydantic schemas. No `any` types.
- XI. Component Discipline: Planned components (PlayerCard, PlayerCardGrid, PlayerDetailsModal, PlayerForm, TeamFilter, Pagination, EnumLabel) are all single-responsibility, estimated well under 200 lines each.

**Gate Result (Post-Design)**: ALL PASS.

## Project Structure

### Documentation (this feature)

```text
specs/005-players-interface/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/          # Player, Team, TeamPlayer (existing — no changes)
│   ├── schemas/         # PlayerResponse extended with teams, PaginatedResponse (new)
│   ├── services/        # player_service.py extended with pagination + filtering
│   └── routes/          # players.py extended with page/page_size/team_id/unassigned params
└── tests/
    ├── unit/            # test_player_routes.py (extend), test_player_schemas.py (extend)
    └── integration/
        └── quickstart/  # test_005_quickstart_flow.py (new)

frontend/
├── src/
│   ├── api/             # client.ts (existing — no changes), playerApi.ts (new)
│   ├── components/      # PlayerCard, PlayerCardGrid, PlayerDetailsModal, PlayerForm (new)
│   │                    # TeamFilter, Pagination, EnumLabel (new)
│   ├── pages/           # PlayersPage.tsx (rewrite stub)
│   ├── types/           # player.ts (new — PlayerResponse, PaginatedResponse, etc.)
│   └── tests/           # PlayersPage.test.tsx, PlayerCard.test.tsx, PlayerForm.test.tsx, etc. (new)
└── e2e/                 # players-flow.spec.ts (new)
```

**Structure Decision**: Web application (frontend + backend). Existing directory layout is retained. New frontend components go under `components/` (shared) and new types under `types/`. The backend extends existing routes/services/schemas without new top-level modules.

## Complexity Tracking

> No constitution violations. This section is intentionally empty.
