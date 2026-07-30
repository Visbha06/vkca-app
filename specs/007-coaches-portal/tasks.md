# Tasks: Coaches Portal

**Input**: Design documents from `/specs/007-coaches-portal/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit tests are MANDATORY per the constitution. One E2E Playwright test per spec is REQUIRED (Polish phase). Integration tests remain optional — the quickstart validation test is mandatory per Constitution V.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory structure and scaffold feature modules

- [X] T001 Create frontend feature module directories: `frontend/src/features/coaches/{api,components/coach-directory,components/coach-details,components/coach-form,components/coach-assignments,hooks,pages,types}` and `frontend/src/features/coaches/index.ts`
- [X] T002 [P] Create `backend/tests/unit/` scaffolding for coach test files: confirm `test_coach_routes.py`, `test_coach_schemas.py`, `test_coach_service.py` target paths exist

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database migration, backend models/schemas, frontend types, shared 403 page, nav/routing changes — everything that US1 and all subsequent stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database & Backend Models

- [X] T003 Create Alembic migration for `team_coaches` table with columns `team_id (UUID, PK, FK→teams.id)`, `user_id (UUID, PK, FK→users.id)`, `created_at`, `updated_at`, `version_number`, and unique constraint on `(team_id, user_id)` in `backend/src/migrations/versions/`
- [X] T004 [P] Create `TeamCoach` SQLAlchemy model extending `TimestampMixin`, `VersionMixin`, `Base` with composite PK (`team_id`, `user_id`) and relationship backrefs in `backend/src/models/team_coach.py`
- [X] T005 [P] Register `TeamCoach` in `backend/src/models/__init__.py` exports
- [X] T006 Apply migration and verify table creation against local Docker PostgreSQL

### Backend Schemas

- [X] T007 [P] Create `CoachResponse` Pydantic schema (id, first_name, last_name, email, role, is_active, version_number, created_at, updated_at, teams list) in `backend/src/schemas/coach.py`
- [X] T008 [P] Create `PaginatedCoachResponse` Pydantic schema (coaches list, page, page_size, total_coaches, total_pages, has_previous, has_next) in `backend/src/schemas/coach.py`
- [X] T009 [P] Create `CoachCreate` Pydantic schema (first_name, last_name, email, optional team_ids list) with email validation in `backend/src/schemas/coach.py`
- [X] T010 [P] Create `CoachTeamUpdate` Pydantic schema (team_ids list, version_number) in `backend/src/schemas/coach.py`
- [X] T011 Register coach schemas in `backend/src/schemas/__init__.py` exports

### Frontend Types & Shared Components

- [X] T012 [P] Create TypeScript types `CoachResponse`, `PaginatedCoachResponse`, `CoachCreatePayload`, `CoachTeamUpdatePayload` mirroring Pydantic schemas in `frontend/src/features/coaches/types/coach.ts`
- [X] T013 [P] Create `ForbiddenPage` component displaying 403 message with "Disciplined Clubhouse" styling (Practice Night heading, Body Copy description, "Return to Dashboard" link) in `frontend/src/pages/ForbiddenPage.tsx`
- [X] T014 Modify `AppLayout.tsx` to filter `navigationItems` array removing Coaches Portal entry when `user.role === 'player'` in `frontend/src/layouts/AppLayout.tsx`
- [X] T015 Modify `frontend/src/pages/CoachesPage.tsx` to delegate to `features/coaches/pages/CoachesPage.tsx` with role check: render `ForbiddenPage` for Player-role users, otherwise render feature page

---

## Phase 3: User Story 1 — Browse and Filter Coaches (Priority: P1) 🎯 MVP

**Goal**: Head Coach or Assistant Coach visits the Coaches Portal and sees a paginated, filterable grid of coach cards with avatars, names, roles, team assignments, and status indicators. Status filter (Active/Inactive/All) uses server-side filtering. Page size defaults to 12. Ordering: Head Coach first, then last name ascending, first name ascending, user ID ascending.

**Independent Test**: Log in as Head Coach, navigate to `/coaches`, verify active coach cards render with correct avatars, role badges, team names. Change filter to "Inactive" — grid refreshes, pagination resets to page 1. Verify Head Coach appears first.

### Tests for User Story 1 (MANDATORY) ⚠️

- [X] T016 [P] [US1] Unit tests for `GET /coaches` route: filtering (active/inactive/all), pagination, ordering, role-authorization (403 for player), 401 for unauthenticated in `backend/tests/unit/test_coach_routes.py`
- [X] T017 [P] [US1] Unit tests for `CoachResponse` and `PaginatedCoachResponse` schemas in `backend/tests/unit/test_coach_schemas.py`
- [X] T018 [P] [US1] Unit tests for `CoachService.list_coaches` method: status filtering, pagination math, stable ordering in `backend/tests/unit/test_coach_service.py`
- [X] T019 [P] [US1] Unit tests for `CoachesPage` component: renders coach cards, handles loading/empty/error states, filter interaction in `frontend/src/features/coaches/pages/CoachesPage.test.tsx`
- [X] T020 [P] [US1] Unit tests for `CoachCard` component: avatar styling (light red HC, light blue AC), full name, role badge, team display (≤2 plus "+N more"), status indicator in `frontend/src/features/coaches/components/coach-directory/CoachCard.test.tsx`
- [X] T021 [P] [US1] Unit tests for `CoachCardGrid`: skeleton loading, responsive grid, empty state with "No Assistant Coaches have been added yet." message in `frontend/src/features/coaches/components/coach-directory/CoachCardGrid.test.tsx`
- [X] T022 [P] [US1] Unit tests for `CoachStatusFilter`: renders all options, defaults to Active, calls onFilterChange in `frontend/src/features/coaches/components/coach-directory/CoachStatusFilter.test.tsx`
- [X] T023 [P] [US1] Unit tests for `CoachesPageHeader`: renders heading, Add Coach button visibility by role, filter integration in `frontend/src/features/coaches/components/coach-directory/CoachesPageHeader.test.tsx`

### Backend Implementation for User Story 1

- [X] T024 [US1] Implement `CoachService.list_coaches` with server-side filtering on `is_active` and `role IN ('head coach', 'assistant coach')`, `CASE`-based ordering, `LIMIT`/`OFFSET` pagination, `outerjoin` to `TeamCoach`+`Team` for eager-loaded team names in `backend/src/services/coach_service.py`
- [X] T025 [US1] Implement `GET /coaches` route with query params (`status`, `page`, `page_size`), authorization check (`require_role(HEAD_COACH, ASSISTANT_COACH)`), and `PaginatedCoachResponse` output in `backend/src/routes/coaches.py`
- [X] T026 [US1] Register coaches router in `backend/src/main.py` (mount under `/api/v1`)

### Frontend Implementation for User Story 1

- [X] T027 [US1] Implement `coachApi.fetchCoaches` function with query params (status, page, page_size), `AbortSignal` support, and typed response in `frontend/src/features/coaches/api/coachApi.ts`
- [X] T028 [US1] Implement `useCoachDirectory` hook wrapping `fetchCoaches` with state management for page, status filter, result, loading, error, retry, and success message in `frontend/src/features/coaches/hooks/useCoachDirectory.ts`
- [X] T029 [US1] Implement `CoachIdentity` component: initials avatar (light red HC, light blue AC), full name display in `frontend/src/features/coaches/components/coach-details/CoachIdentity.tsx`
- [X] T030 [US1] Implement `CoachRoleBadge` component: pill badge with role label in `frontend/src/features/coaches/components/coach-details/CoachRoleBadge.tsx`
- [X] T031 [US1] Implement `CoachCard` component: avatar, name, role badge, team list (first 2 + "+N more" indicator, or "No teams assigned"), active/inactive muted styling, full-card clickable button with Enter/Space in `frontend/src/features/coaches/components/coach-directory/CoachCard.tsx`
- [X] T032 [US1] Implement `CoachCardGrid` component: responsive grid (1/2/3 cols), skeleton loading state, true-empty state with "No Assistant Coaches have been added yet." message, filtered-no-results state in `frontend/src/features/coaches/components/coach-directory/CoachCardGrid.tsx`
- [X] T033 [US1] Implement `CoachStatusFilter` component: dropdown with Active/Inactive/All, defaults to Active, accessible label in `frontend/src/features/coaches/components/coach-directory/CoachStatusFilter.tsx`
- [X] T034 [US1] Implement `CoachesPageHeader` component: page heading, status filter, Add Coach button (visible only to Head Coach), result count in `frontend/src/features/coaches/components/coach-directory/CoachesPageHeader.tsx`
- [X] T035 [US1] Implement `CoachesPage` feature page: compose header, card grid, pagination controls (reusing shared `Pagination` component from `frontend/src/shared/components/navigation/Pagination.tsx`), all UI states (loading, empty, error, filtered-no-results, success) in `frontend/src/features/coaches/pages/CoachesPage.tsx`
- [X] T036 [US1] Implement barrel export in `frontend/src/features/coaches/index.ts` exporting `CoachesPage` and public types

**Checkpoint**: At this point, the Coaches Portal displays a functional card grid with status filtering and server-side pagination. No modals or mutations yet.

---

## Phase 4: User Story 2 — View Coach Details (Priority: P1)

**Goal**: Selecting an active coach card opens a Coach Details modal displaying full name, email, role, status, assigned teams, placeholder statistics ("Availability for next practice: Not available", "Notes made: 0"), and role-appropriate actions. Assistant Coaches cannot open inactive coach cards.

**Independent Test**: Click an active coach card — modal opens with all fields. Press Escape — modal closes, focus returns to card. As Assistant Coach, click an inactive card — no modal opens.

### Tests for User Story 2 (MANDATORY) ⚠️

- [X] T037 [P] [US2] Unit tests for `GET /coaches/{id}` route: returns 200 for active coach (any role), 403 for AC requesting inactive coach, 404 for non-coach user in `backend/tests/unit/test_coach_routes.py`
- [X] T038 [P] [US2] Unit tests for `CoachDetailsModal` component: renders all fields, placeholder stats, role-based action visibility, Escape/close button/focus trap/scroll lock in `frontend/src/features/coaches/components/coach-details/CoachDetailsModal.test.tsx`

### Backend Implementation for User Story 2

- [X] T039 [US2] Implement `CoachService.get_coach` method: fetch single User by ID with `role IN ('head coach', 'assistant coach')` filter, eager-load team assignments; raise 404 for non-coach or missing in `backend/src/services/coach_service.py`
- [X] T040 [US2] Implement `GET /coaches/{coach_id}` route with authorization: Head Coach can view any coach; Assistant Coach can only view active coaches (return 403 for inactive) in `backend/src/routes/coaches.py`

### Frontend Implementation for User Story 2

- [X] T041 [US2] Implement `coachApi.fetchCoachDetails` function in `frontend/src/features/coaches/api/coachApi.ts`
- [X] T042 [US2] Implement `CoachDetailsModal` component reusing `ModalDialog`: display full name, email, role badge, active/inactive status, assigned teams list or "No teams assigned", placeholder stats section with fixed values, role-appropriate action visibility, keyboard/close/Escape support in `frontend/src/features/coaches/components/coach-details/CoachDetailsModal.tsx`
- [X] T043 [US2] Wire `CoachCard` `onSelect` to open `CoachDetailsModal` in `CoachesPage`. For Assistant Coach users, inactive cards do not trigger modal open and MUST be removed from the tab order (e.g., `tabIndex={-1}`) so they do not appear keyboard-actionable per FR-052 in `frontend/src/features/coaches/pages/CoachesPage.tsx`

**Checkpoint**: Coach details modal fully functional. Store placeholder stat values ("Not available", "0") as constants.

---

## Phase 5: User Story 3 — Add an Assistant Coach (Priority: P2)

**Goal**: Head Coach clicks Add Coach, fills in first name, last name, email, and optional team assignments. Backend generates a temporary password returned once in the 201 response. Frontend displays it with a copy button and warning. Duplicate emails show field-level error. Account creation and team assignments are atomic.

**Independent Test**: Click Add Coach, fill valid details, select teams, submit. Verify success message with one-time password (copyable). Submit same email again — verify field-level error and form preserved.

### Tests for User Story 3 (MANDATORY) ⚠️

- [X] T044 [P] [US3] Unit tests for `POST /coaches` route: successful creation with temp password returned, duplicate email 409, missing-field 400, player-role 403, AC-role 403 in `backend/tests/unit/test_coach_routes.py`
- [X] T045 [P] [US3] Unit tests for `CoachCreate` schema validation in `backend/tests/unit/test_coach_schemas.py`
- [X] T046 [P] [US3] Unit tests for `CoachService.create_coach`: atomic account+assignment creation, temp password policy compliance, duplicate email rejection, team validation in `backend/tests/unit/test_coach_service.py`
- [X] T047 [P] [US3] Unit tests for `AddCoachModal` component: form rendering, validation errors, temp password display, copy behavior, Add Coach button visibility by role in `frontend/src/features/coaches/components/coach-form/AddCoachModal.test.tsx`

### Backend Implementation for User Story 3

- [X] T048 [US3] Implement `CoachService.generate_temporary_password` using `secrets.token_urlsafe(16)` with policy-compliance prefix, ensuring the hash passes `PasswordService.validate_password_policy` in `backend/src/services/coach_service.py`
- [X] T049 [US3] Implement `CoachService.create_coach`: validate email uniqueness (normalized), generate temp password, hash it via `PasswordService.hash_password`, create User with role="assistant coach" and is_active=true, optionally create TeamCoach rows for team_ids, commit atomically; rollback on any failure in `backend/src/services/coach_service.py`
- [X] T050 [US3] Implement `POST /coaches` route: accept `CoachCreate` payload, require Head Coach role, return 201 with `CoachResponse` + `temporary_password` field; return 409 on duplicate email in `backend/src/routes/coaches.py`

### Frontend Implementation for User Story 3

- [X] T051 [US3] Implement `coachApi.createCoach` function sending first_name, last_name, email, optional team_ids; handling 400/409/403 responses in `frontend/src/features/coaches/api/coachApi.ts`
- [X] T052 [US3] Implement `AddCoachForm` component: first_name, last_name, email fields with field-level validation; optional team multi-select reusing existing team types; submission loading/disabled state; duplicate email field error in `frontend/src/features/coaches/components/coach-form/AddCoachForm.tsx`
- [X] T053 [US3] Implement `TemporaryPasswordDisplay` component: password shown with copy-to-clipboard button, "This password will only be shown once" warning banner, not stored in state after dismiss in `frontend/src/features/coaches/components/coach-form/TemporaryPasswordDisplay.tsx`
- [X] T054 [US3] Implement `AddCoachModal` component wrapping `AddCoachForm` and `TemporaryPasswordDisplay` inside `ModalDialog`; unsaved-changes confirmation on close in `frontend/src/features/coaches/components/coach-form/AddCoachModal.tsx`
- [X] T055 [US3] Wire `AddCoachModal` into `CoachesPage`: open on "Add Coach" button click, on success add coach to local state and show success message, on error display field-level or generic error in `frontend/src/features/coaches/pages/CoachesPage.tsx`

**Checkpoint**: Head Coach can create Assistant Coach accounts with temp password display.

---

## Phase 6: User Story 4 — Activate and Deactivate Coaches (Priority: P2)

**Goal**: Head Coach toggles coach status in details modal. Deactivation sets `is_active=false`, atomically revokes all sessions, and prevents future login. Reactivation sets `is_active=true` but does NOT restore revoked sessions. Confirmation dialog before deactivation. Self-deactivation blocked frontend and backend.

**Independent Test**: Open active coach details, toggle to inactive, confirm dialog — card becomes muted, coach cannot log in. Toggle back to active — card normalizes, coach can log in fresh. Verify Head Coach cannot toggle their own status.

### Tests for User Story 4 (MANDATORY) ⚠️

- [X] T056 [P] [US4] Unit tests for `POST /users/{id}/disable` (modified): atomic is_active=false + session revocation, self-deactivation 403 in `backend/tests/unit/test_coach_routes.py`
- [X] T057 [P] [US4] Unit tests for `POST /users/{id}/reactivate`: sets is_active=true, does not restore sessions, 403 for non-HC, 404 for missing user in `backend/tests/unit/test_coach_routes.py`
- [X] T058 [P] [US4] Unit tests for `CoachService.toggle_coach_status`: OCC version check, session revocation on deactivate, no session restore on reactivate in `backend/tests/unit/test_coach_service.py`
- [X] T059 [P] [US4] Unit tests for `CoachStatusToggle` component: visible only to Head Coach, hidden/disabled for self, confirmation dialog content, loading state in `frontend/src/features/coaches/components/coach-details/CoachStatusToggle.test.tsx`

### Backend Implementation for User Story 4

- [X] T060 [US4] Modify `POST /users/{user_id}/disable` route to make `is_active=false` update and `revoke_user_sessions` call happen within a single `session.commit()` boundary (atomicity per FR-040). Add self-deactivation check returning 403 in `backend/src/routes/users.py`
- [X] T061 [US4] Implement `UserService.reactivate_user` method: accept user_id, set `is_active=true`, increment `version_number`, commit, return updated User in `backend/src/services/user_service.py`
- [X] T062 [US4] Implement `POST /users/{user_id}/reactivate` route: require Head Coach role, call `UserService.reactivate_user`, do NOT restore sessions, commit in `backend/src/routes/users.py`
- [X] T063 [US4] Implement `CoachService.toggle_coach_status`: accept user_id, desired is_active state, incoming version_number; use `check_and_increment_version` for OCC; on deactivate call `revoke_user_sessions`; on reactivate skip session restoration in `backend/src/services/coach_service.py`

### Frontend Implementation for User Story 4

- [X] T064 [US4] Implement `coachApi.deactivateCoach` and `coachApi.reactivateCoach` functions in `frontend/src/features/coaches/api/coachApi.ts`
- [X] T065 [US4] Implement `CoachStatusToggle` component: toggle control visible only to Head Coach, disabled/hidden with explanation for self, confirmation dialog explicitly stating: the coach will no longer be able to log in, all active sessions will be revoked, team assignments and historical data will be preserved, and the account can be reactivated later — in `frontend/src/features/coaches/components/coach-details/CoachStatusToggle.tsx`
- [X] T066 [US4] Wire `CoachStatusToggle` into `CoachDetailsModal`: on toggle, call API with version_number, handle 200 (refresh card), 409 (show conflict + reload), 403 (show permission message). Update card styling immediately on success in `frontend/src/features/coaches/components/coach-details/CoachDetailsModal.tsx`

**Checkpoint**: Coach status lifecycle fully functional with atomic deactivation and OCC protection.

---

## Phase 7: User Story 5 — Manage Team Assignments (Priority: P2)

**Goal**: Head Coach clicks "Edit Assignments" in coach details modal (visible for active coaches only, including self). Team Assignments modal opens showing all available teams with current assignments highlighted. Add/remove assignments, submit complete replacement set atomically. Version number bumped on success. Inactive coaches show assignments read-only with Edit Assignments disabled.

**Independent Test**: Open active coach details, click Edit Assignments — modal opens with all teams and current assignments. Add a team, remove one, submit — card and details modal update. Open inactive coach details — assignments visible but Edit Assignments disabled.

### Tests for User Story 5 (MANDATORY) ⚠️

- [ ] T067 [P] [US5] Unit tests for `PUT /coaches/{id}/teams` route: successful replacement, duplicate team rejection, inactive-coach 403, stale version 409, invalid team_id 400 in `backend/tests/unit/test_coach_routes.py`
- [ ] T068 [P] [US5] Unit tests for `CoachTeamUpdate` schema validation in `backend/tests/unit/test_coach_schemas.py`
- [ ] T069 [P] [US5] Unit tests for `CoachService.update_team_assignments`: atomic delete-all+insert-all, duplicate prevention, version_number increment on success, team validation in `backend/tests/unit/test_coach_service.py`
- [ ] T070 [P] [US5] Unit tests for `TeamAssignmentsModal` component: renders all teams, shows current assignments, add/remove behavior, submission, unsaved-changes confirmation, visibility gated by role and active status in `frontend/src/features/coaches/components/coach-assignments/TeamAssignmentsModal.test.tsx`

### Backend Implementation for User Story 5

- [ ] T071 [US5] Implement `CoachService.update_team_assignments`: accept user_id, team_ids list, version_number; validate all team_ids exist; delete all existing TeamCoach rows for user_id; insert new TeamCoach rows; increment coach user's version_number via `check_and_increment_version`; commit atomically in `backend/src/services/coach_service.py`
- [ ] T072 [US5] Implement `PUT /coaches/{coach_id}/teams` route: require Head Coach role, check coach is active (403 if inactive), accept `CoachTeamUpdate` payload, return updated `CoachResponse` in `backend/src/routes/coaches.py`

### Frontend Implementation for User Story 5

- [ ] T073 [US5] Implement `coachApi.updateTeamAssignments` function sending team_ids and version_number, handling 400/403/409 responses in `frontend/src/features/coaches/api/coachApi.ts`
- [ ] T074 [US5] Implement `TeamAssignmentsModal` component using `ModalDialog`: display all available teams (fetched via existing teams API), show currently assigned teams as selected, allow add/remove with duplicate prevention, submit sends complete team_ids set + version_number, loading/submission/success/error/validation states, unsaved-changes confirmation on close in `frontend/src/features/coaches/components/coach-assignments/TeamAssignmentsModal.tsx`
- [ ] T075 [US5] Wire "Edit Assignments" button into `CoachDetailsModal`: visible only to Head Coach for active coaches (including self), closes details modal then opens `TeamAssignmentsModal` (no stacked modals). On success, refresh coach card and details data in `frontend/src/features/coaches/components/coach-details/CoachDetailsModal.tsx` and `frontend/src/features/coaches/pages/CoachesPage.tsx`

**Checkpoint**: Team assignments fully editable for active coaches by Head Coach.

---

## Phase 8: User Story 6 — Handle Concurrent Edits Gracefully (Priority: P3)

**Goal**: When a Head Coach submits a status or assignment change with a stale `version_number`, the backend returns HTTP 409. Frontend displays a conflict message with a "Reload" action that replaces stale data and updates the version_number. No automatic retry.

**Independent Test**: Load coach details in two sessions. Modify status in session A. Attempt assignment update in session B — receive 409. Click Reload — current data loads with updated version_number.

### Implementation for User Story 6

*Note: OCC backend enforcement (HTTP 409 on stale version) was already built into US4 (T063) and US5 (T071). This phase adds consistent frontend conflict handling and the reload flow.*

- [ ] T076 [US6] Create shared `useConflictHandler` hook: detect 409 responses, manage conflict state (stale data, conflict message, reload action), return handler for wrapping API calls in `frontend/src/features/coaches/hooks/useConflictHandler.ts`
- [ ] T077 [US6] Integrate `useConflictHandler` into `CoachDetailsModal` for status toggle and assignment edit flows: on 409, show conflict message inline with "Reload" button; on reload, fetch fresh coach data, update version_number, clear conflict state in `frontend/src/features/coaches/components/coach-details/CoachDetailsModal.tsx`
- [ ] T078 [P] [US6] Unit tests for conflict handler hook: 409 detection, stale state management, reload flow in `frontend/src/features/coaches/hooks/useConflictHandler.test.ts`

**Checkpoint**: Concurrent edit conflicts handled gracefully with reload flow across both status and assignment operations.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: E2E test, documentation, quickstart validation, integration testing

- [ ] T079 [P] Write `docs/coaches-portal.md` — concise version of spec capturing feature purpose, key user flows, API surface, and configuration changes (MANDATORY per Constitution XII)
- [ ] T080 Implement Playwright E2E test covering full Head Coach journey: login, open Coaches Portal, create Assistant Coach, view temp password, assign to team, open details, deactivate (confirm card mutes), reactivate, edit team assignments in `frontend/e2e/coaches-flow.spec.ts` (MANDATORY per Constitution V)
- [ ] T081 [P] Create quickstart integration test at `backend/tests/integration/quickstart/test_007_quickstart_flow.py` validating all 14 backend scenarios from quickstart.md (MANDATORY per Constitution V)
- [ ] T082 Verify all frontend unit tests pass with `cd frontend && npm run test`
- [ ] T083 Verify all backend unit tests pass with `cd backend && uv run pytest tests/unit/ -v`
- [ ] T084 Run quickstart validation: `cd backend && uv run pytest tests/integration/quickstart/test_007_quickstart_flow.py -v`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (directories exist) — BLOCKS all user stories
- **US1 — Browse & Filter (Phase 3)**: Depends on Phase 2 — No dependencies on other stories 🎯 MVP
- **US2 — Coach Details (Phase 4)**: Depends on US1 (need card grid to open modal)
- **US3 — Add Coach (Phase 5)**: Depends on US1 (Add Coach button on coaches page); backend independent of US2
- **US4 — Activate/Deactivate (Phase 6)**: Depends on US2 (toggle in details modal); partially depends on US3 for having coaches to toggle
- **US5 — Manage Assignments (Phase 7)**: Depends on US2 (Edit Assignments in details modal)
- **US6 — Handle Conflicts (Phase 8)**: Depends on US4 and US5 (OCC endpoints already implemented)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Phase 2 (Foundational)
    │
    ▼
Phase 3: US1 ────────────────────────────────┐
    │                                         │
    ▼                                         │
Phase 4: US2 ◄────────────────────────────────┘
    │
    ├──▶ Phase 5: US3 (backend independent of US2)
    │
    ├──▶ Phase 6: US4 (needs US2 for modal)
    │
    └──▶ Phase 7: US5 (needs US2 for modal)
              │
              ▼
         Phase 8: US6 (needs US4 + US5 OCC endpoints)
              │
              ▼
         Phase 9: Polish
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Backend: schemas → service → routes
- Frontend: types → API client → components → page composition
- Core implementation before integration
- Story complete before moving to next dependency

### Parallel Opportunities

- All Setup tasks (T001-T002) can run in parallel
- Within Foundational: T004, T005 (model); T007-T010 (schemas); T012, T013 (frontend types/ForbiddenPage) — all [P] groups can run in parallel
- Within US1: all tests (T016-T023) run in parallel; backend T024-T025 can run parallel to frontend T027-T034
- Within US2: backend T039-T040 can run parallel to frontend T041-T042
- US4 and US5 backend work can run in parallel once US2 backend is done
- Polish: T078, T079, T080 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 backend tests together:
Task T016: "Unit tests for GET /coaches route in backend/tests/unit/test_coach_routes.py"
Task T017: "Unit tests for coach schemas in backend/tests/unit/test_coach_schemas.py"
Task T018: "Unit tests for CoachService.list_coaches in backend/tests/unit/test_coach_service.py"

# Launch all US1 frontend tests together:
Task T019: "Unit tests for CoachesPage in frontend/src/features/coaches/pages/CoachesPage.test.tsx"
Task T020: "Unit tests for CoachCard in frontend/src/features/coaches/components/coach-directory/CoachCard.test.tsx"
Task T021: "Unit tests for CoachCardGrid in frontend/src/features/coaches/components/coach-directory/CoachCardGrid.test.tsx"
Task T022: "Unit tests for CoachStatusFilter test"
Task T023: "Unit tests for CoachesPageHeader test"

# Backend and frontend implementation can also proceed in parallel:
Task T024-T025 (backend) parallel to Task T027-T034 (frontend)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T015) — **CRITICAL GATE**
3. Complete Phase 3: User Story 1 (T016-T036) — **🎯 MVP: Coaches Portal with browsable card grid**
4. **STOP and VALIDATE**: Deploy/demo the browsable coaches page
5. Begin adding stories incrementally

### Incremental Delivery

| Stage | Phases | What Users Can Do |
|-------|--------|-------------------|
| MVP | 1+2+3 | Browse and filter coach cards |
| +Details | +4 | Click cards to view coach details |
| +Creation | +5 | Head Coach creates Assistant Coach accounts |
| +Lifecycle | +6 | Head Coach activates/deactivates coaches |
| +Assignments | +7 | Head Coach manages team-coach assignments |
| +Resilience | +8 | Concurrent edits handled gracefully |
| Complete | +9 | E2E tested, documented, quickstart validated |
