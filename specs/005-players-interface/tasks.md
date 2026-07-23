# Tasks: Players Interface

**Input**: Design documents from `/specs/005-players-interface/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/players-api.md, quickstart.md

**Tests**: Unit tests are MANDATORY per the constitution. One E2E Playwright test per spec is REQUIRED (placed in the Polish phase). Integration quickstart test is REQUIRED per constitution V.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm dev environment is operational before extending

- [ ] T001 Verify backend and frontend dev environments run cleanly: `cd backend && uv run ruff check . && cd ../frontend && npm run lint && npm run test -- --run`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend pagination/filtering extension, frontend types, API client, and shared utilities — MUST complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Backend Schemas & Service

- [ ] T002 [P] Add `TeamSummary` and `PaginatedPlayerResponse` schemas in `backend/src/schemas/player.py`
- [ ] T003 [P] Extend `PlayerResponse` with `teams: list[TeamSummary]` field in `backend/src/schemas/player.py`
- [ ] T004 Extend `PlayerService.list_players` with `page`, `page_size`, `team_id`, `unassigned` parameters and pagination metadata in `backend/src/services/player_service.py`
- [ ] T005 Extend `GET /api/v1/players` route with query parameters (`page`, `page_size`, `team_id`, `unassigned`) returning `PaginatedPlayerResponse` in `backend/src/routes/players.py`
- [ ] T006 [P] Write backend unit tests for `PaginatedPlayerResponse` schema validation in `backend/tests/unit/test_player_schemas.py`
- [ ] T007 [P] Write backend unit tests for paginated/filtered list route in `backend/tests/unit/test_player_routes.py`

### Frontend Types & API Layer

- [ ] T008 [P] Create TypeScript types (`TeamSummary`, `PlayerResponse`, `PaginatedPlayerResponse`, `PlayerCreatePayload`, `PlayerUpdatePayload`, enum types) in `frontend/src/types/player.ts`
- [ ] T009 [P] Create player API client functions (`fetchPlayers`, `fetchPlayer`, `createPlayer`, `updatePlayer`) in `frontend/src/api/playerApi.ts`
- [ ] T010 [P] Create enum label mappings and `formatEnum` utility in `frontend/src/utils/enumLabels.ts`
- [ ] T011 [P] Create `toDisplayDate` and `toApiDate` formatting utilities in `frontend/src/utils/formatDate.ts`
- [ ] T012 [P] Create `useUnsavedChanges` hook for form exit confirmation in `frontend/src/hooks/useUnsavedChanges.ts`

**Checkpoint**: Foundation ready — paginated/team-filtered API works, frontend types and utilities available

---

## Phase 3: User Story 1 - Browse and View Active Players (Priority: P1) 🎯 MVP

**Goal**: Coaches and players can see a paginated grid of active player cards with team names, filter by team, page through results, open a Player Details modal showing all identity fields, and close the modal with keyboard support.

**Independent Test**: Log in as any role, navigate to Players page, verify player cards appear with team names, filter by a team, page through results, open a Player Details modal, verify player identity fields (name, DOB, styles, type, teams, stats placeholder), dismiss modal with Escape, and confirm focus returns to the originating card.

### Tests for User Story 1 (MANDATORY) ⚠️

- [ ] T013 [P] [US1] Write unit tests for `PlayerCard` (renders name, teams/"Unassigned", date, keyboard access) in `frontend/src/tests/PlayerCard.test.tsx`
- [ ] T014 [P] [US1] Write unit tests for `PlayerCardGrid` (renders cards, responsive grid, empty state) in `frontend/src/tests/PlayerCardGrid.test.tsx`
- [ ] T015 [P] [US1] Write unit tests for `PlayerDetailsModal` (displays all fields, opens on card click, closes on Escape/close button, focus trapping, stats placeholder) in `frontend/src/tests/PlayerDetailsModal.test.tsx`
- [ ] T016 [P] [US1] Write unit tests for `Pagination` (renders page numbers, disables prev/next at boundaries, calls onPageChange) in `frontend/src/tests/Pagination.test.tsx`
- [ ] T017 [P] [US1] Write unit tests for `TeamFilter` (renders All/team/Unassigned options, calls onChange, keyboard accessible) in `frontend/src/tests/TeamFilter.test.tsx`
- [ ] T018 [US1] Write unit tests for `PlayersPage` container (fetches players, passes data to children, loading/empty/error states, role-based controls) in `frontend/src/tests/PlayersPage.test.tsx`

### Implementation for User Story 1

- [ ] T019 [P] [US1] Create `PlayerCard` component (full name, team names or "Unassigned", date display, keyboard-focusable, Enter/Space to open) in `frontend/src/components/PlayerCard.tsx`
- [ ] T020 [P] [US1] Create `PlayerCardGrid` component (responsive grid of `PlayerCard`, loading/empty states) in `frontend/src/components/PlayerCardGrid.tsx`
- [ ] T021 [P] [US1] Create `Pagination` component (page controls, prev/next, disabled-at-bounds, accessible labels, loading state). In `PlayersPage`, guard pagination fetches with an AbortController — cancel in-flight request on rapid re-clicks so only the most recent page request is honored (spec edge case L123)
- [ ] T022 [P] [US1] Create `TeamFilter` component (select dropdown: All Players, each team, Unassigned Players, resets to page 1 on change) in `frontend/src/components/TeamFilter.tsx`
- [ ] T023 [US1] Create `PlayerDetailsModal` component (reuses `useModalDialog`, shows heading/DOB/batting/bowling/type/teams/stats-placeholder, Escape/close-button/backdrop-close, focus trapping, responsive scroll) in `frontend/src/components/PlayerDetailsModal.tsx`
- [ ] T024 [US1] Rewrite `PlayersPage` container (fetches paginated players with team filter, manages `page`/`teamFilter` state, renders `TeamFilter` + `PlayerCardGrid` + `Pagination`, handles `PlayerDetailsModal` open/close, role-based "Add Player" visibility). After successful create/edit mutations, increment a `refreshKey` counter to invalidate stale cached list data and trigger a fresh fetch (spec FR-035). in `frontend/src/pages/PlayersPage.tsx`

**Checkpoint**: User Story 1 fully functional — paginated player list with team filtering, player cards, and details modal all work end-to-end

---

## Phase 4: User Story 2 - View Bio and Metadata in Player Details (Priority: P2)

**Goal**: Within the Player Details modal, an expandable section reveals the player's bio text and metadata key-value pairs, or an empty-state message when none exists.

**Independent Test**: Open a Player Details modal for a player with bio and metadata, expand the section, verify bio text and key-value metadata display, then open a player with no bio/metadata and verify empty message appears.

### Tests for User Story 2 (MANDATORY) ⚠️

- [ ] T025 [P] [US2] Write unit tests for bio/metadata expandable section (displays bio, key-value pairs, empty message, expand/collapse toggle, nested objects flattened with JSON.stringify, keys/values rendered as text nodes not innerHTML) in `frontend/src/tests/PlayerDetailsModal.test.tsx`

### Implementation for User Story 2

- [ ] T026 [US2] Add bio/metadata expandable section to `PlayerDetailsModal` (info-icon toggle, collapsible panel, bio text display, key-value metadata rendering, empty message when absent). Render metadata keys and values as text content (not innerHTML) to prevent XSS; flatten nested objects with JSON.stringify for display. in `frontend/src/components/PlayerDetailsModal.tsx`

**Checkpoint**: Bio and metadata now viewable from Player Details — US1 + US2 both work

---

## Phase 5: User Story 3 - Add a New Player (Priority: P3)

**Goal**: Head coaches and assistant coaches can create a new player via a form modal with required fields, enum dropdowns, optional bio, and key-value metadata fields. Player-role users see no Add controls.

**Independent Test**: Log in as head coach, click "Add Player", fill all required fields with valid values, submit, verify new player appears in list without full page reload. Verify player-role user sees no Add Player button.

### Tests for User Story 3 (MANDATORY) ⚠️

- [ ] T027 [P] [US3] Write unit tests for `PlayerForm` (required field validation, enum dropdowns, date input, bio, metadata key-value fields, submit disabled during loading, human-readable labels, unsaved-changes prompt) in `frontend/src/tests/PlayerForm.test.tsx`
- [ ] T028 [P] [US3] Write unit tests for `AddPlayerModal` (opens from button, submits via POST, success closes modal and refreshes list, validation errors stay in form, generic server error, 403 permissions message) in `frontend/src/tests/AddPlayerModal.test.tsx`

### Implementation for User Story 3

- [ ] T029 [P] [US3] Create `PlayerForm` shared component (first_name, last_name, date_of_birth via native `<input type="date">` for user-friendly input, bio, batting_style/bowling_style/player_type dropdowns with human-readable labels, metadata key-value repeatable fields → JSON object, required-field validation, loading/disabled submit, success/error states, unsaved-changes confirmation via `useUnsavedChanges`) in `frontend/src/components/PlayerForm.tsx`
- [ ] T030 [US3] Create `AddPlayerModal` component (wraps `PlayerForm`, `POST /api/v1/players` on submit, on success closes and triggers list refresh, handles 403 and generic errors, uses `useModalDialog` + backdrop pattern) in `frontend/src/components/AddPlayerModal.tsx`
- [ ] T031 [US3] Integrate Add Player button and `AddPlayerModal` into `PlayersPage` (visible to Head Coach/Assistant Coach only, hidden from Player role per `useAuth().user.role`) in `frontend/src/pages/PlayersPage.tsx`
- [ ] T032 [US3] Wire dashboard "Add player" quick action to open `AddPlayerModal` via URL search param `?action=add`: `HomePage` link targets `/players?action=add`; `PlayersPage` reads the param on mount and opens the Add modal, then clears it from the URL. in `frontend/src/pages/HomePage.tsx` and `frontend/src/pages/PlayersPage.tsx`

**Checkpoint**: Coaches can create players — US1 + US2 + US3 all work

---

## Phase 6: User Story 4 - Edit an Existing Player (Priority: P4)

**Goal**: Head coaches and assistant coaches can edit a player from the Details modal. Form pre-fills with current values. Updates use `PUT` with `version_number`. OCC conflicts (409) show clear message with reload. Player-role users see no Edit control.

**Independent Test**: Log in as head coach, open Player Details, activate Edit, verify form pre-filled with current values including human-readable enum labels, change a field, submit, verify card and details reflect update. Test 409 conflict: submit with stale version, see conflict message, reload, re-apply changes.

### Tests for User Story 4 (MANDATORY) ⚠️

- [ ] T033 [P] [US4] Write unit tests for `EditPlayerModal` (pre-fills from player data, human-readable enum labels, date display format, submits with `version_number`, handles 409 conflict with reload action, handles 403 permissions, unsaved-changes prompt) in `frontend/src/tests/EditPlayerModal.test.tsx`

### Implementation for User Story 4

- [ ] T034 [US4] Add "Edit Player" control to `PlayerDetailsModal` (visible to Head Coach/Assistant Coach only, closes details before opening edit) in `frontend/src/components/PlayerDetailsModal.tsx`
- [ ] T035 [US4] Create `EditPlayerModal` component (wraps `PlayerForm` with `player` prop for pre-fill, `PUT /api/v1/players/{id}` on submit with `version_number`, handles 409 with conflict message + "Reload" button that re-fetches and replaces form state, handles 403 with permissions message, closes on success with list refresh) in `frontend/src/components/EditPlayerModal.tsx`
- [ ] T036 [US4] Integrate `EditPlayerModal` flow into `PlayersPage` (close details → open edit → on success refresh → re-open details with new data) in `frontend/src/pages/PlayersPage.tsx`

**Checkpoint**: Full player CRUD cycle works — US1 + US2 + US3 + US4

---

## Phase 7: User Story 5 - Handle Page and Form States Gracefully (Priority: P5)

**Goal**: Every UI state — loading, empty, filtered-no-results, error/retry, validation, submission-loading, success, conflict, permissions-denied — is communicated clearly and accessibly across the entire Players interface.

**Independent Test**: Trigger each state and verify the UI responds appropriately: loading indicator during fetch, empty-state message when no players exist, distinct no-results message when filter yields zero, error message with retry button on API failure, form validation errors per field, submit button disabled during submission, success feedback after create/update, conflict message with reload, permissions-denied message on 403, pagination controls disabled at boundaries.

### Tests for User Story 5 (MANDATORY) ⚠️

- [ ] T037 [P] [US5] Write unit tests for loading/empty/error/filtered-no-results states in `PlayersPage` in `frontend/src/tests/PlayersPage.test.tsx`
- [ ] T038 [P] [US5] Write unit tests for form submission loading/validation/success/403 states in `PlayerForm` in `frontend/src/tests/PlayerForm.test.tsx`

### Implementation for User Story 5

- [ ] T039 [P] [US5] Implement loading state (accessible spinner/skeleton) and empty state (message + Add Player action for coaches) in `PlayersPage` in `frontend/src/pages/PlayersPage.tsx`
- [ ] T040 [P] [US5] Implement filtered-no-results state (distinct from empty state) and error state (message + retry button) in `PlayersPage` in `frontend/src/pages/PlayersPage.tsx`
- [ ] T041 [US5] Write Vitest timing assertions for state transitions: assert loading indicator renders within 500ms of fetch start, assert success/error messages appear within 500ms of response, assert submit button disables immediately on click — across `PlayersPage`, `PlayerForm`, `AddPlayerModal`, `EditPlayerModal` in their respective test files

**Checkpoint**: All states handled — US1 through US5 complete

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Integration quickstart test, E2E test, documentation, final validation

### Backend Quickstart Test

- [ ] T042 Write integration quickstart test covering pagination, default ordering, team filtering, unassigned filtering, inactive exclusion, OCC conflict — executes scenarios from `quickstart.md` against real PostgreSQL test database in `backend/tests/integration/quickstart/test_005_quickstart_flow.py`

### Frontend E2E Test

- [ ] T043 Write Playwright E2E test covering login → Players page → team filter → open details modal → create/edit player as coach. Include viewport tests at 320px (mobile) and 1280px (desktop) to verify responsive grid reflow and no horizontal overflow per spec FR-066–070 / SC-005. in `frontend/e2e/players-flow.spec.ts`

### Documentation

- [ ] T044 Write feature documentation (concise version of spec, capturing purpose, key flows, API surface, configuration) in `docs/players-interface.md`

### Final Validation

- [ ] T045 Run full test suites: `cd backend && uv run pytest && cd ../frontend && npm run test -- --run && npm run test:e2e`
- [ ] T046 Run quickstart validation: `cd backend && uv run python -m pytest tests/integration/quickstart/test_005_quickstart_flow.py -v`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP
- **User Story 2 (Phase 4)**: Depends on US1 (extends PlayerDetailsModal)
- **User Story 3 (Phase 5)**: Depends on US1 (Add button on PlayersPage)
- **User Story 4 (Phase 6)**: Depends on US1 + US3 (Edit from Details, shares PlayerForm)
- **User Story 5 (Phase 7)**: Depends on US1–US4 (applies states across all components)
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no story dependencies
- **US2 (P2)**: Depends on US1 (PlayerDetailsModal must exist)
- **US3 (P3)**: Depends on US1 (PlayersPage must exist to host Add button and list refresh)
- **US4 (P4)**: Depends on US1 + US3 (shares PlayerForm from US3, Details modal from US1)
- **US5 (P5)**: Depends on US1–US4 (cross-cutting: applies to all prior components)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Components before container integration
- Tests before container-level testing
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 2**: T002–T003 (both schema files), T006–T007 (both unit test files), T008–T012 (all different frontend files) can run in parallel
- **Phase 3**: T013–T017 (all test files for different components), T019–T022 (all component files) can run in parallel
- **Phase 5**: T027–T028 (both test files) can run in parallel
- **Phase 7**: T037–T038 (both test files), T039–T040 (independent state implementations) can run in parallel
- **Phase 8**: T042 (backend quickstart) and T043 (E2E test) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all component tests together:
Task: "Write unit tests for PlayerCard in frontend/src/tests/PlayerCard.test.tsx"
Task: "Write unit tests for PlayerCardGrid in frontend/src/tests/PlayerCardGrid.test.tsx"
Task: "Write unit tests for PlayerDetailsModal in frontend/src/tests/PlayerDetailsModal.test.tsx"
Task: "Write unit tests for Pagination in frontend/src/tests/Pagination.test.tsx"
Task: "Write unit tests for TeamFilter in frontend/src/tests/TeamFilter.test.tsx"

# Launch all components together:
Task: "Create PlayerCard component in frontend/src/components/PlayerCard.tsx"
Task: "Create PlayerCardGrid component in frontend/src/components/PlayerCardGrid.tsx"
Task: "Create Pagination component in frontend/src/components/Pagination.tsx"
Task: "Create TeamFilter component in frontend/src/components/TeamFilter.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (paginated list + cards + details)
4. **STOP and VALIDATE**: Test US1 independently — browse, filter, page, view details
5. Deploy/demo if ready — US1 delivers the core player directory

### Incremental Delivery

1. Setup + Foundational → Backend pagination/filtering works, frontend types ready
2. Add US1 → Paginated player directory with cards and details modal (MVP!)
3. Add US2 → Bio/metadata expandable section in details
4. Add US3 → Coaches can create players with shared form
5. Add US4 → Coaches can edit players with OCC conflict handling
6. Add US5 → All states polished: loading, empty, error, success, conflict
7. Polish → Quickstart test, E2E test, documentation

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: Frontend components (US1 — T019–T023)
   - Developer B: Backend tests and frontend tests (T006–T007, T013–T018)
   - Developer C: Frontend API and utilities (T008–T012)
3. US1 container integration (T024) after components ready
4. US2 → Developer A, US3 → Developer B, US4 → Developer C (parallel after US1)
5. US5 → one developer after US1–US4

---

## Notes

- [P] tasks = different files, no dependencies — can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- No schema migrations needed — query-layer extension only
- No new dependencies — all formatting with pure TypeScript, modals reuse existing `useModalDialog`
- Design references: `PRODUCT.md` for brand personality, `DESIGN.md` for colors/typography/components
