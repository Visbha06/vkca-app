# Tasks: Teams Interface

**Input**: Design documents from `/specs/006-teams-interface/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit tests are MANDATORY per the constitution. One E2E Playwright test per spec is REQUIRED. Integration quickstart test is REQUIRED per constitution V.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`
- Backend tests: `backend/tests/unit/`, `backend/tests/integration/quickstart/`
- Frontend tests: `frontend/src/tests/`, `frontend/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and shared enum for all user stories

- [X] T001 Add `AgeGroup` enum (J, U11, U13, U15) to `backend/src/enums.py`
- [X] T002 [P] Add `roster_order` column (Integer, NOT NULL, DEFAULT 0) and `(team_id, roster_order)` index to `TeamPlayer` model in `backend/src/models/team_player.py`
- [X] T003 [P] Add DB check constraint `ck_teams_age_group` on `teams.age_group` in `backend/src/models/team.py`
- [X] T004 Generate and run Alembic migration for T001–T003 in `backend/src/migrations/versions/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend schemas, service contract, and frontend API client that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Update `TeamResponse` schema: add `player_count: int` in `backend/src/schemas/team.py`
- [X] T006 [P] Add `PaginatedTeamResponse` schema (teams, page, page_size, total_teams, total_pages) in `backend/src/schemas/team.py`
- [X] T007 [P] Add `TeamCreate` schema: name (1–200), age_group (AgeGroup), player_ids (list[UUID], 7–15) in `backend/src/schemas/team.py`
- [X] T008 [P] Add `TeamUpdate` schema: name, age_group, player_ids (7–15), version_number (ge=1) in `backend/src/schemas/team.py`
- [X] T009 [P] Add `TeamRosterPlayerResponse` schema: player_id, first_name, last_name, is_active, roster_order in `backend/src/schemas/team.py`
- [X] T010 [P] Add `TeamRosterResponse` schema: team_id, players (list[TeamRosterPlayerResponse]) in `backend/src/schemas/team.py`
- [X] T011 [P] Create frontend TypeScript types mirroring all backend team schemas in `frontend/src/types/team.ts`
- [X] T012 [P] Create `teamApi.ts` with API client functions (fetchTeams, createTeam, updateTeam, fetchTeamRoster) in `frontend/src/api/teamApi.ts`
- [X] T013 [P] Create `AgeGroupBadge` component with human-readable labels (J→Juniors, U11, U13, U15) following `player-type-badge` design tokens in `frontend/src/components/AgeGroupBadge.tsx`

**Checkpoint**: Foundation ready — all schemas, types, and API client available for user story implementation

---

## Phase 3: User Story 1 - Browse Teams (Priority: P1) 🎯 MVP

**Goal**: Replace Teams placeholder page with paginated team cards in a responsive grid, with loading/empty/error states

**Independent Test**: Log in as any role, navigate to Teams page, verify team cards display with name, age-group badge, roster count, and pagination works

### Tests for User Story 1 (MANDATORY) ⚠️

- [X] T014 [P] [US1] Unit test for paginated team list route (200, 401, 422) in `backend/tests/unit/test_team_routes.py`
- [X] T015 [P] [US1] Unit test for paginated team list service (ordering, count, page bounds) in `backend/tests/unit/test_team_service.py`
- [X] T016 [P] [US1] Unit test for `TeamCard` component (renders name, age group, player count, keyboard activation) in `frontend/src/tests/TeamCard.test.tsx`
- [X] T017 [P] [US1] Unit test for `TeamsPage` page states (loading, empty, error, retry) in `frontend/src/tests/TeamsPage.test.tsx`
- [X] T018 [P] [US1] Unit test for `teamApi.fetchTeams` (request shape, response parsing, error handling) in `frontend/src/tests/teamApi.test.ts`
- [X] T019 [P] [US1] Unit test for new `TeamCreate`/`TeamUpdate`/`TeamRosterPlayerResponse` schema validation in `backend/tests/unit/test_team_schemas.py`

### Implementation for User Story 1

- [X] T020 [US1] Implement `TeamService.list_teams()` with pagination (count query + offset/limit, default page_size=12, order by name/age_group/id) in `backend/src/services/team_service.py`
- [X] T021 [US1] Implement `GET /api/v1/teams` route with page/page_size query params, returning `PaginatedTeamResponse` in `backend/src/routes/teams.py`
- [X] T022 [US1] Create `TeamCard` component: button card with name, AgeGroupBadge, "N / 15 players" roster count, keyboard-accessible, academy branding (Clubhouse White bg, Boundary Line border, 12px rounded, teal hover/focus) in `frontend/src/components/TeamCard.tsx`
- [X] T023 [US1] Create `TeamCardGrid` responsive grid component using Tailwind grid with breakpoint reflow in `frontend/src/components/TeamCardGrid.tsx`
- [X] T024 [US1] Create `TeamPageLoadingSkeleton` matching card anatomy in `frontend/src/components/TeamPageLoadingSkeleton.tsx`
- [X] T025 [US1] Create `useTeams` hook with page state, fetch on mount/page change, AbortController, loading/error/data states in `frontend/src/hooks/useTeams.ts`
- [X] T026 [US1] Replace `TeamsPage.tsx` placeholder with full page: page heading, Create Team button (role-gated), `TeamCardGrid`, `Pagination`, all states (loading skeleton, empty message, error+retry) in `frontend/src/pages/TeamsPage.tsx`

**Checkpoint**: Team list page functional — paginated cards with loading/empty/error states

---

## Phase 4: User Story 2 - View Team Details and Roster (Priority: P1)

**Goal**: Team Details modal showing team info, ordered roster with player info links, non-stacking modal behavior

**Independent Test**: Click a team card, verify modal shows name, age group, player count, ordered roster. Click player info — team modal closes, player details modal opens

### Tests for User Story 2 (MANDATORY) ⚠️

- [X] T027 [P] [US2] Unit test for roster retrieval route (200, 404) in `backend/tests/unit/test_team_routes.py`
- [X] T028 [P] [US2] Unit test for roster retrieval service (ordering, inactive included) in `backend/tests/unit/test_team_service.py`
- [X] T029 [P] [US2] Unit test for `TeamDetailsModal` (renders team info, roster, empty roster state, close behavior) in `frontend/src/tests/TeamDetailsModal.test.tsx`

### Implementation for User Story 2

- [X] T030 [US2] Implement `TeamService.get_team_roster()`: join TeamPlayer+Player, order by roster_order ASC, include inactive players with is_active flag in `backend/src/services/team_service.py`
- [X] T031 [US2] Implement `GET /api/v1/teams/{team_id}/players` route returning `TeamRosterResponse` in `backend/src/routes/teams.py`
- [X] T032 [US2] Create `useTeamRoster` hook with fetch on team_id change in `frontend/src/hooks/useTeamRoster.ts`
- [X] T033 [US2] Create `TeamDetailsModal` using `ModalDialog`: team name, age group, player count, ordered roster list, Edit Team button (role-gated), close button, focus trap, Escape close, empty-roster message. Inactive players shown with muted styling in `frontend/src/components/TeamDetailsModal.tsx`
- [X] T034 [US2] Wire `TeamCard` onClick to open `TeamDetailsModal` from `TeamsPage` state. Implement player info click → close team modal → open `PlayerDetailsModal` (no stacking) in `frontend/src/pages/TeamsPage.tsx`

**Checkpoint**: Team details modal working — ordered roster visible, player detail navigation non-stacking

---

## Phase 5: User Story 3 - Create a Team (Priority: P2)

**Goal**: Team creation form modal with 15 player rows, searchable dropdowns, atomic backend creation, role-gated

**Independent Test**: As head coach, click Create Team, fill name/age_group, select 8 distinct players, submit. Verify 201, team appears in list with correct roster order

### Tests for User Story 3 (MANDATORY) ⚠️

- [ ] T035 [P] [US3] Unit test for create team route (201, 400 min players, 400 duplicate, 409 name conflict, 403 unauthorized) in `backend/tests/unit/test_team_routes.py`
- [ ] T036 [P] [US3] Unit test for create team service (atomic rollback, name uniqueness, player validation) in `backend/tests/unit/test_team_service.py`
- [ ] T037 [P] [US3] Unit test for `TeamForm` create mode (renders empty form, validation errors for <7 players, duplicate rejection) in `frontend/src/tests/TeamForm.test.tsx`
- [ ] T038 [P] [US3] Unit test for `TeamRosterRow` (searchable dropdown, info icon disabled when empty, remove clears selection) in `frontend/src/tests/TeamRosterRow.test.tsx`

### Implementation for User Story 3

- [ ] T039 [US3] Implement `TeamService.create_team()`: validate player_ids exist+active, 7≤len≤15, no duplicates, name uniqueness (case-insensitive whitespace-normalized within age group), create Team, flush, bulk insert TeamPlayer with roster_order, commit — all in one transaction. Rollback on any failure in `backend/src/services/team_service.py`
- [ ] T040 [US3] Implement `POST /api/v1/teams` route with role guard (HEAD_COACH, ASSISTANT_COACH), returning 201 `TeamResponse` in `backend/src/routes/teams.py`
- [ ] T041 [US3] Create `PlayerSearchDropdown` component: controlled input with debounced search (300ms), calls `GET /api/v1/players?search=...&page_size=50`, loading spinner, "No players found" empty state, error+retry, excludes already-selected players in `frontend/src/components/PlayerSearchDropdown.tsx`
- [ ] T042 [US3] Create `TeamRosterRow` component: grip icon (drag handle), `PlayerSearchDropdown`, info icon (disabled+greyed when empty, opens player details), remove icon (red trash, disabled when empty), accessible labels in `frontend/src/components/TeamRosterRow.tsx`
- [ ] T043 [US3] Create `TeamForm` component (shared create/edit): team name input, age_group dropdown (J/U11/U13/U15 with human-readable labels), 15 ordered `TeamRosterRow` slots (rows 1–7 required, 8–15 optional), form-level validation (7–15 players, no duplicates), submission state (disable submit, prevent double-click, accessible progress), success/error feedback in `frontend/src/components/TeamForm.tsx`
- [ ] T044 [US3] Create `TeamFormModal` wrapping `TeamForm` in `ModalDialog` with title "Create Team", passing create mode config in `frontend/src/components/TeamFormModal.tsx`
- [ ] T045 [US3] Wire Create Team button in `TeamsPage` (visible only for HEAD_COACH/ASSISTANT_COACH) to open `TeamFormModal`. On success, close modal, refresh team list, show success feedback in `frontend/src/pages/TeamsPage.tsx`

**Checkpoint**: Team creation fully functional — atomic create with 7–15 players, searchable dropdowns, role-gated

---

## Phase 6: User Story 4 - Edit Team and Roster (Priority: P2)

**Goal**: Edit team form pre-filled with current data, atomic update with OCC, version conflict handling

**Independent Test**: Open team details, click Edit, change name, add/remove/reorder players, submit. Verify update persists. Submit stale version — verify 409 with reload action

### Tests for User Story 4 (MANDATORY) ⚠️

- [ ] T046 [P] [US4] Unit test for update team route (200, 400, 404, 409 stale version, 409 name conflict, 403) in `backend/tests/unit/test_team_routes.py`
- [ ] T047 [P] [US4] Unit test for update team service (atomic rollback, version check, full roster replacement) in `backend/tests/unit/test_team_service.py`
- [ ] T048 [P] [US4] Unit test for `TeamForm` edit mode (pre-filled fields, version_number in payload, 409 conflict handling) in `frontend/src/tests/TeamForm.test.tsx`

### Implementation for User Story 4

- [ ] T049 [US4] Implement `TeamService.update_team()`: fetch team, check_and_increment_version, validate player_ids, validate name uniqueness (excluding current team), update team name/age_group, delete existing TeamPlayer rows, bulk insert new rows with roster_order, commit — all in one transaction. Rollback on failure in `backend/src/services/team_service.py`
- [ ] T050 [US4] Implement `PUT /api/v1/teams/{team_id}` route with role guard, returning 200 `TeamResponse`. Map StaleVersionError → 409, TeamNotFoundError → 404 in `backend/src/routes/teams.py`
- [ ] T051 [US4] Extend `TeamForm` for edit mode: pre-fill name, age_group, roster (populate dropdowns with current players in saved order), include hidden version_number, diff detection for unsaved changes in `frontend/src/components/TeamForm.tsx`
- [ ] T052 [US4] Create `ConfirmationDialog` component: modal with "You have unsaved changes" message, Continue Editing and Discard buttons in `frontend/src/components/ConfirmationDialog.tsx`
- [ ] T053 [US4] Create `useUnsavedChanges` hook: `isDirty` flag, `beforeunload` listener, modal close interceptor in `frontend/src/hooks/useUnsavedChanges.ts`
- [ ] T054 [US4] Wire Edit Team button in `TeamDetailsModal` (role-gated) → close details modal → open `TeamFormModal` in edit mode with pre-filled data. On success, close form, refresh team list, show success feedback. On 409, show conflict message with reload action in `frontend/src/pages/TeamsPage.tsx`
- [ ] T055 [US4] Add unsaved-changes protection to `TeamFormModal`: on close attempt with dirty state, show `ConfirmationDialog` in `frontend/src/components/TeamFormModal.tsx`

**Checkpoint**: Team editing fully functional — atomic update, OCC conflict handling, unsaved changes protection

---

## Phase 7: User Story 5 - Reorder Roster (Priority: P2)

**Goal**: Drag-and-drop roster reordering with keyboard-accessible Move Up/Move Down alternatives

**Independent Test**: In team form with 10 players, drag player 5 to position 2, use Move Up on player 8 to position 7. Submit, reload, verify saved order persisted

### Tests for User Story 5 (MANDATORY) ⚠️

- [ ] T056 [P] [US5] Unit test for `TeamRosterList` drag-and-drop (order update after drop) in `frontend/src/tests/TeamRosterRow.test.tsx`
- [ ] T057 [P] [US5] Unit test for move up/down controls (disabled at list boundaries, order update) in `frontend/src/tests/TeamRosterRow.test.tsx`

### Implementation for User Story 5

- [ ] T058 [US5] Add drag-and-drop to `TeamRosterRow`: six-dot grip icon with `draggable`, `dragstart`/`dragover`/`drop` handlers, visual feedback (opacity-50 on dragged, border-dashed on drop target) in `frontend/src/components/TeamRosterRow.tsx`
- [ ] T059 [US5] Create `TeamRosterList` component: manages roster order state, handles drop reorder (reindex roster_order), passes reorder callbacks. Wraps ordered `TeamRosterRow` items in `frontend/src/components/TeamRosterList.tsx`
- [ ] T060 [US5] Add Move Up / Move Down buttons to `TeamRosterRow`: accessible labels ("Move [Player] up/down"), disabled at list boundaries, preserve player data on move in `frontend/src/components/TeamRosterRow.tsx`
- [ ] T061 [US5] Integrate `TeamRosterList` into `TeamForm` (create and edit modes), replacing flat row rendering in `frontend/src/components/TeamForm.tsx`
- [ ] T062 [US5] Verify roster_order persistence: confirm `GET /api/v1/teams/{id}/players` returns order set by drag/drop and move controls across page reloads in `frontend/src/pages/TeamsPage.tsx`

**Checkpoint**: Roster reordering fully functional — drag-and-drop + keyboard Move Up/Down, order persists across reloads

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: E2E test, quickstart validation test, documentation, and final verification

- [ ] T063 [P] Write E2E Playwright test: login, open Teams page, create team as coach, select+reorder 8 players, submit, open details, edit roster, verify order persists after reload in `frontend/e2e/teams-flow.spec.ts`
- [ ] T064 Write quickstart integration test covering all 12 scenarios from quickstart.md in `backend/tests/integration/quickstart/test_006_quickstart_flow.py`
- [ ] T065 Implement `TeamService` name uniqueness helper: `LOWER(TRIM(name)) = LOWER(TRIM(:name)) AND age_group = :age_group` query, used in both create and update in `backend/src/services/team_service.py`
- [ ] T066 Verify `GET /api/v1/players?search=` supports first_name/last_name/full_name matching (per research, already implemented — validate with test) in `backend/tests/unit/test_player_routes.py`
- [ ] T067 Write feature documentation in `docs/teams-interface.md` (MANDATORY per constitution XII — concise version of spec, written after implementation)
- [ ] T068 Run full test suite: backend unit tests, frontend unit tests, E2E test, quickstart test. Fix any failures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001–T004) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (T005–T013) — P1
- **User Story 2 (Phase 4)**: Depends on US1 (T022, T026 for cards+page) and Foundational — P1
- **User Story 3 (Phase 5)**: Depends on Foundational (T005–T013) — P2
- **User Story 4 (Phase 6)**: Depends on US2 (T033 for details modal), US3 (T041–T045 for form/dropdown) — P2
- **User Story 5 (Phase 7)**: Depends on US3 (T042–T043 for roster rows/form) — P2
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (Browse Teams)**: Standalone after Foundational → can deliver MVP independently
- **US2 (View Details)**: Depends on US1 (team cards must exist to click) → builds on US1
- **US3 (Create Team)**: Depends on Foundational only → can run in parallel with US1+US2 if team has capacity
- **US4 (Edit Team)**: Depends on US2 (details modal) and US3 (form components) → sequential after US2+US3
- **US5 (Reorder Roster)**: Depends on US3 (roster rows/form) → sequential after US3

### Within Each User Story

- Backend tests (unit) → Frontend tests (unit) → Backend implementation → Frontend implementation
- Models/schemas before services, services before routes
- Components before integration into pages

### Parallel Opportunities

- T002, T003 (model changes) can run in parallel
- T005–T010 (all schemas) can run in parallel
- T011, T012, T013 (frontend types, API, badge) can run in parallel
- All test tasks within a phase marked [P] can run in parallel
- US1 (Phase 3) and US3 (Phase 5) backend work can run in parallel after Foundational
- T041, T042 (PlayerSearchDropdown, TeamRosterRow) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task T014: "Unit test paginated team list route in backend/tests/unit/test_team_routes.py"
Task T015: "Unit test paginated team list service in backend/tests/unit/test_team_service.py"
Task T016: "Unit test TeamCard component in frontend/src/tests/TeamCard.test.tsx"
Task T017: "Unit test TeamsPage states in frontend/src/tests/TeamsPage.test.tsx"
Task T018: "Unit test teamApi.fetchTeams in frontend/src/tests/teamApi.test.ts"
Task T019: "Unit test new schemas in backend/tests/unit/test_team_schemas.py"

# Then implement backend:
Task T020: "Implement TeamService.list_teams() in backend/src/services/team_service.py"
Task T021: "Implement GET /api/v1/teams route in backend/src/routes/teams.py"

# Then implement frontend (components can be parallel):
Task T022: "Create TeamCard in frontend/src/components/TeamCard.tsx"
Task T023: "Create TeamCardGrid in frontend/src/components/TeamCardGrid.tsx"
Task T024: "Create TeamPageLoadingSkeleton in frontend/src/components/TeamPageLoadingSkeleton.tsx"
Task T025: "Create useTeams hook in frontend/src/hooks/useTeams.ts"

# Finally integrate:
Task T026: "Replace TeamsPage.tsx with full page"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration)
2. Complete Phase 2: Foundational (schemas, types, API client)
3. Complete Phase 3: User Story 1 (Browse Teams)
4. **STOP and VALIDATE**: Team list page works with pagination, cards render correctly, all states handled
5. Deploy/demo if ready

### Incremental Delivery

1. MVP: US1 (Browse Teams) → Team list visible to all users
2. + US2 (View Details) → Teams are now browsable and inspectable
3. + US3 (Create Team) → Coaches can create teams
4. + US5 (Reorder) → Coaches can order rosters
5. + US4 (Edit Team) → Coaches can edit teams with OCC safety
6. + Polish → E2E tests, docs, quickstart validation

### Recommended Execution Order

Since US1 (Browse) and US2 (View Details) are both P1 and sequential, start with US1+US2 as a combined first delivery. Then US3 (Create) + US5 (Reorder) since reorder controls are embedded in the create form. Finally US4 (Edit) which depends on all previous stories.
