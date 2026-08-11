---

description: "Implementation tasks for the dynamic role-aware dashboard and operational summary"
---

# Tasks: Dynamic Role-Aware Dashboard and Operational Summary

**Input**: Design documents from `/specs/011-role-aware-dashboard/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Unit tests are mandatory under the project constitution and the feature specification. The feature also requires one Playwright journey and the isolated backend quickstart. Integration tests below are included because the specification explicitly requires cross-module, migration, audit, session, and query-bound verification.

**Organization**: Tasks are grouped by user story. All three core stories are P1; their phase order follows the implementation dependencies in `plan.md`: Match participant domain, Player account association, then the dashboard projection. The labels remain the spec's US1–US4 identifiers.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish focused module boundaries, contract-generation tooling, and reusable feature fixtures without adding dependencies.

- [X] T001 [P] Create the dashboard module entry points in `backend/src/routes/dashboard.py`, `backend/src/schemas/dashboard.py`, `backend/src/services/dashboard_service.py`, `frontend/src/features/dashboard/api/index.ts`, `frontend/src/features/dashboard/components/index.ts`, `frontend/src/features/dashboard/hooks/index.ts`, and `frontend/src/features/dashboard/types/index.ts` while preserving the existing backend and frontend directory conventions.
- [X] T002 [P] Implement the contract-only OpenAPI exporter scaffold in `backend/scripts/export_role_aware_dashboard_openapi.py` and the frontend generator scaffold in `frontend/scripts/generate-role-aware-dashboard-types.mjs` using the existing Data Quality export/generation workflow.
- [X] T003 [P] Add `generate:role-aware-dashboard-types` and `check:role-aware-dashboard-types` scripts to `frontend/package.json` without adding a runtime dependency.
- [X] T004 [P] Add deterministic role-aware seed builders and SQL statement-count helpers in `backend/tests/integration/role_aware_dashboard_fixtures.py` and `backend/tests/integration/conftest.py` for teams, memberships, Calendar occurrences, Matches, audit events, linked accounts, and isolated sessions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the reversible schema and shared typed boundaries required by every story. No story implementation should begin until this phase is complete.

- [X] T005 Create `backend/src/migrations/versions/013_role_aware_dashboard_domain.py` as the Alembic revision after `012_create_business_audit_events`, adding nullable unique `players.user_id`, final external/internal Match participant columns, foreign keys, checks, and date/team indexes with a safe downgrade path.
- [X] T006 Map the migration contract into `backend/src/models/player.py`, `backend/src/models/match.py`, and `backend/src/models/user.py`, including the nullable Player-to-User relationship, participant discriminator, participant-side foreign keys, nonblank/exclusive constraints, and Match version-aware fields.
- [X] T007 Define the shared Pydantic contract boundaries in `backend/src/schemas/match.py`, `backend/src/schemas/player_account.py`, and `backend/src/schemas/dashboard.py`, including discriminated participant unions, safe account snapshots, bounded pagination, and `ready`/`empty`/`unlinked`/`unavailable` section states.
- [X] T008 Generate the initial API artifact at `frontend/src/features/dashboard/api/generated.ts` from the contract exporter and wire the generated `components` types into the feature barrel exports in `frontend/src/features/dashboard/api/index.ts`.

**Checkpoint**: Revision `013`, ORM mappings, shared API unions, and local query/test fixtures are ready for story work.

---

## Phase 3: User Story 2 - Correctly represent upcoming Match participants (Priority: P1)

**Goal**: Replace opponent-only Match ambiguity with validated external and internal participant semantics that the dashboard and future callers can consume exactly once per relevant fixture.

**Independent Test**: Use the Match API and domain service to create, update, and read valid external and internal fixtures; assert mixed, missing, blank, unknown-Team, and same-Team payloads fail before persistence and that a valid internal Match is not duplicated when both sides are in one viewer's scope.

### Tests for User Story 2 (write before implementation)

- [ ] T009 [P] [US2] Extend `backend/tests/unit/test_match_schemas.py` with valid external/home, external/away, and internal participant cases plus mixed-field, missing-side, blank-opponent, same-Team, and unknown-shape validation failures.
- [ ] T010 [P] [US2] Add `backend/tests/unit/test_match_service.py` covering participant-to-column mapping, Team existence checks, chronological ordering, optimistic-concurrency conflicts, and the absence of successful audit events for rejected mutations.
- [ ] T011 [P] [US2] Extend `backend/tests/unit/test_match_routes.py` for POST, PUT, and GET participant response shapes, retained authorization, malformed payloads, unknown Teams, and stale-version `409` responses.
- [ ] T012 [P] [US2] Add `backend/tests/integration/test_match_participants.py` to exercise revision `013` constraints against PostgreSQL, verify rollback/no-audit behavior, and prove internal participant fields cannot be mixed with external fields.

### Implementation for User Story 2

- [ ] T013 [US2] Implement the external/internal discriminated request validators and participant response adapters in `backend/src/schemas/match.py`, preserving all existing Match metadata and explicitly excluding the legacy opponent-only shape.
- [ ] T014 [US2] Implement participant persistence, set-based Team loading, chronological reads, and OCC-aware replacement updates in `backend/src/services/match_service.py` without introducing a second Match-to-Team relationship.
- [ ] T015 [US2] Update `backend/src/routes/matches.py` to expose the participant contract for POST/GET, add complete OCC-aware PUT support, map validation/conflict errors to repository conventions, and keep Match management out of the frontend route surface.

**Checkpoint**: External and internal Matches persist and serialize unambiguously, invalid participant combinations are rejected before commit, and the backend contract is ready for role-scoped dashboard lookup.

---

## Phase 4: User Story 3 - Link a Player account to the correct Player profile (Priority: P1)

**Goal**: Give Head Coaches a verified, auditable, optimistic-concurrency-safe link/unlink/reassignment flow inside the existing Player Directory, while enforcing inactive linked-Player session security.

**Independent Test**: As a Head Coach, list eligible unlinked Player accounts, link one to an unlinked profile, unlink it with confirmation, reassign it explicitly, and verify safe responses, uniqueness, authorization, exactly one audit event per committed mutation, no audit event on failures, and session revocation when the linked profile becomes inactive.

### Tests for User Story 3 (write before implementation)

- [ ] T016 [P] [US3] Extend `backend/tests/unit/test_player_schemas.py` for safe account lookup/link/unlink/reassign requests and responses, pagination bounds, and omission of credentials/session fields from normal Player responses.
- [ ] T017 [P] [US3] Add `backend/tests/unit/test_player_account_service.py` for valid link/unlink/reassignment, wrong-role and duplicate rejection, stale Player version, expected-account mismatch, transaction rollback, and exactly-one Business Audit event semantics.
- [ ] T018 [P] [US3] Extend `backend/tests/unit/test_player_routes.py` for Head Coach-only lookup and mutations plus `401`, `403`, `404`, `409`, and `422` mappings.
- [ ] T019 [P] [US3] Extend `backend/tests/unit/test_auth_service.py`, `backend/tests/unit/test_auth_routes.py`, and `backend/tests/unit/test_auth_middleware.py` for linked inactive-Player login, refresh, bearer rejection, session revocation, reactivation without session restoration, and independently disabled User preservation.
- [ ] T020 [P] [US3] Add `backend/tests/integration/test_player_account_linking.py` to verify the nullable unique FK, concurrent association races, audit cardinality, rollback behavior, and deactivation of every active linked session.
- [ ] T021 [P] [US3] Extend `frontend/src/features/players/api/playerApi.test.ts`, `frontend/src/features/players/components/player-account/PlayerAccountSection.test.tsx`, and `frontend/src/features/players/components/player-account/PlayerAccountLinkDialog.test.tsx` for safe lookup, explicit selection/confirmation, forbidden controls, conflict reload, unlink, and reassignment states; verify clean dismissal without a warning, dirty dismissal from the close control, Escape, and permitted backdrop interaction, Continue Editing preservation of all values, Discard Changes clearing transient state and closing the dialog, correct focus restoration, and no link/unlink/reassign save request when changes are discarded.

### Implementation for User Story 3

- [ ] T022 [US3] Add `player.account_linked`, `player.account_unlinked`, and `player.account_reassigned` to `backend/src/enums.py` and register their exact target types, summaries, and allowlisted metadata in `backend/src/services/business_audit_registry.py`.
- [ ] T023 [US3] Complete `backend/src/schemas/player_account.py` and update `backend/src/schemas/player.py` so protected linking responses expose only the safe account snapshot while ordinary Player list/detail responses expose no account credentials or session data.
- [ ] T024 [US3] Implement `backend/src/services/player_account_service.py` with Head Coach validation, eligible unlinked Player-role lookup, one-to-one link/unlink/reassign mutations, Player OCC checks, database-integrity conflict mapping, and one staged Business Audit event per successful transaction.
- [ ] T025 [US3] Extend `backend/src/routes/players.py` with `GET /account-linking/users`, `PUT /{player_id}/account`, `DELETE /{player_id}/account`, and `POST /{player_id}/account/reassign`, enforcing `require_role(UserRole.HEAD_COACH)` and the documented error contracts.
- [ ] T026 [US3] Update `backend/src/services/player_service.py`, `backend/src/services/auth_service.py`, `backend/src/middleware/auth.py`, and `backend/src/routes/auth.py` so an active-to-inactive linked Player profile revokes sessions in the same transaction and blocks bearer, login, and refresh use until reactivation without restoring revoked sessions.
- [ ] T027 [US3] Add the account-linking API functions and generated-type adapters to `frontend/src/features/players/api/playerApi.ts` and `frontend/src/features/players/types/player.ts`, including safe search pagination, OCC payloads, and typed conflict/error handling.
- [ ] T028 [US3] Build `frontend/src/features/players/components/player-account/PlayerAccountSection.tsx` and `frontend/src/features/players/components/player-account/PlayerAccountLinkDialog.tsx` with explicit account selection, confirmation, unlink/reassign paths, keyboard/focus behavior, internal narrow-viewport scrolling, and no credential rendering; track clean/dirty dialog state, allow normal clean dismissal, and intercept dirty close-control, Escape, and permitted backdrop dismissal with an accessible Continue Editing/Discard Changes confirmation that preserves entered values on continue, clears transient state and performs no mutation on discard, and retains the existing focus conventions.
- [ ] T029 [US3] Integrate `PlayerAccountSection` into `frontend/src/features/players/components/player-form/EditPlayerModal.tsx` and `frontend/src/features/players/components/PlayersPageModals.tsx`, showing controls only to Head Coaches and reusing the shared dialog, toast, conflict, and modal-focus conventions.

**Checkpoint**: A Head Coach can safely correct account associations from the existing Player workflow; non-Head Coaches cannot discover or mutate them, and inactive linked Player sessions are rejected consistently.

---

## Phase 5: User Story 1 - Review a live academy briefing (Priority: P1) 🎯 MVP

**Goal**: Replace the static authenticated Home page with a server-authorized, read-time dashboard briefing containing live greeting, summary, upcoming Calendar events, Match relevance, bounded context data, and explicit operational states for every role.

**Independent Test**: Seed representative Practice events, external/internal Matches, teams, memberships, and audit activity; authenticate as Head Coach, Assistant Coach, linked Player, and unlinked Player; open `/` and verify live values, server-derived scope, deduplication, bounds, no-placeholder behavior, and retry/partial-failure handling without visiting another workflow.

### Tests for User Story 1 (write before implementation)

- [ ] T030 [P] [US1] Extend `backend/tests/unit/test_dashboard_schemas.py` for response envelopes, discriminated section states, role-specific player slots, participant labels, bounded collections, and rejection of client-supplied scope fields.
- [ ] T031 [P] [US1] Add `backend/tests/unit/test_dashboard_service.py` for Head Coach, Assistant Coach, linked Player, and unlinked Player scope derivation, summary selection, internal-Match deduplication, deterministic ordering, and explicit empty/unlinked states.
- [ ] T032 [P] [US1] Add `backend/tests/unit/test_dashboard_routes.py` for authenticated `GET /api/v1/dashboard`, forbidden/session-expiry behavior, ignored/rejected arbitrary scope parameters, and no audit writes on reads or retries.
- [ ] T033 [P] [US1] Add `backend/tests/integration/test_dashboard_projection.py` to verify Calendar effective occurrences, recurrence/move/delete exceptions, age-group/all-academy scope, Match date ordering, bounded five-event/twelve-team/four-activity projections, and no-N+1 query counts using `backend/tests/integration/role_aware_dashboard_fixtures.py`.
- [ ] T034 [P] [US1] Add `frontend/src/features/dashboard/api/dashboardApi.test.ts` and `frontend/src/features/dashboard/hooks/useDashboard.test.ts` for typed requests, loading, populated data, background refresh retention, initial failure, section retry, and the absence of static fallback values.
- [ ] T035 [P] [US1] Extend `frontend/src/pages/home/HomePage.test.tsx`, `frontend/src/pages/home/HomeSummary.test.tsx`, and `frontend/src/pages/home/HomeSchedule.test.tsx` for the preserved composition, current-user greeting, live summary values, event rows without location, empty states, and partial failures; verify Head Coach, Assistant Coach, linked Player, and unlinked Player states render exactly one primary action, deterministically fall back from View Upcoming Events to an already permitted View Teams destination only when scoped Teams exist, and never expose an unauthorized destination.

### Implementation for User Story 1

- [ ] T036 [US1] Complete the discriminated response serializers and presentation bounds in `backend/src/schemas/dashboard.py`, keeping server-derived scope internal and making `ready`, `empty`, `unlinked`, and `unavailable` states explicit.
- [ ] T037 [US1] Implement `backend/src/services/dashboard_service.py` with role scope resolution from the authenticated database User, set-based Team/Player/membership/Calendar/Match/audit loading, effective-occurrence reuse, one-row internal-Match relevance, deterministic limits, and zero Business Audit writes.
- [ ] T038 [US1] Implement `backend/src/routes/dashboard.py` and register it in `backend/src/main.py` at `GET /api/v1/dashboard`, using `get_current_user` and rejecting client-selected User, Player, coach, or team scope.
- [ ] T039 [US1] Implement the typed dashboard API client, query hook, generated contract imports, and UI-state wrappers in `frontend/src/features/dashboard/api/dashboardApi.ts`, `frontend/src/features/dashboard/hooks/useDashboard.ts`, and `frontend/src/features/dashboard/types/dashboard.ts`.
- [ ] T040 [US1] Build reusable dashboard presentational sections in `frontend/src/features/dashboard/components/DashboardLoadingState.tsx`, `frontend/src/features/dashboard/components/DashboardErrorState.tsx`, `frontend/src/features/dashboard/components/DashboardSummary.tsx`, and `frontend/src/features/dashboard/components/DashboardUpcomingEvents.tsx` with reduced-motion-safe loading, explicit empty/unavailable states, semantic regions, and retry actions.
- [ ] T041 [US1] Replace hardcoded content in `frontend/src/pages/home/HomePage.tsx`, `frontend/src/pages/home/HomeSummary.tsx`, and `frontend/src/pages/home/HomeSchedule.tsx` with the live dashboard container while preserving the shared summary surface, event-first layout, responsive stacking, and no page-level overflow.
- [ ] T042 [US1] Wire `frontend/src/features/dashboard/hooks/useDashboard.ts` and `frontend/src/pages/home/HomePage.tsx` for section-level retry, populated-content retention during refresh, current-user role wording, and an exactly-one capability-derived primary-action selector: use only already permitted Schedule event or Add player shortcuts in that order, otherwise View Upcoming Events, with the deterministic authorized View Teams fallback for an empty event section and no new Assistant Coach, Player, or Match-management permission.

**Checkpoint**: The authenticated Home route is live, bounded, role-isolated, typed, responsive, and state-resilient with no sample greeting, metric, event, or audit data remaining.

---

## Phase 6: User Story 4 - Work with role-specific dashboard context (Priority: P2)

**Goal**: Make the right-side contextual panel useful and stable for every role: Head Coach activity, Assistant Coach My Teams, and linked Player My Teams, with explicit no-team and unavailable states.

**Independent Test**: Seed bounded audit events, assigned teams, rosters, coaches, and relevant events; render the dashboard for Head Coach, Assistant Coach with/without assignments, linked Player with/without memberships, and unlinked Player; verify panel kind, fields, navigation, bounds, empty states, and absence of restricted data.

### Tests for User Story 4 (write before implementation)

- [ ] T043 [P] [US4] Add `backend/tests/unit/test_dashboard_context.py` for Recent Academy Activity eligibility, My Teams fields, active-player distinct counts, next-event selection, deterministic ordering, and role-denied audit data.
- [ ] T044 [P] [US4] Add `frontend/src/features/dashboard/components/DashboardContextPanel.test.tsx`, `frontend/src/features/dashboard/components/RecentAcademyActivity.test.tsx`, and `frontend/src/features/dashboard/components/MyTeamsPanel.test.tsx` for role-specific rendering, no-team/unlinked/unavailable states, bounded rows, permitted navigation, and keyboard semantics.

### Implementation for User Story 4

- [ ] T045 [US4] Complete the contextual response mapping in `backend/src/schemas/dashboard.py` and `backend/src/services/dashboard_service.py` for four-event Recent Academy Activity, twelve-row My Teams, permitted coach context, next relevant event, and explicit no-team/unavailable states.
- [ ] T046 [US4] Build `frontend/src/features/dashboard/components/DashboardContextPanel.tsx`, `frontend/src/features/dashboard/components/RecentAcademyActivity.tsx`, and `frontend/src/features/dashboard/components/MyTeamsPanel.tsx`, then compose them into `frontend/src/pages/home/HomeSchedule.tsx` without removing the right column on narrow or empty states.
- [ ] T047 [US4] Add role-safe panel navigation, accessible status announcements, visible focus, 44px targets, reduced-motion behavior, and responsive wrapping for team/event metadata in `frontend/src/features/dashboard/components/DashboardContextPanel.tsx`, `frontend/src/features/dashboard/components/MyTeamsPanel.tsx`, and `frontend/src/pages/home/HomeSchedule.tsx` using `PRODUCT.md` and `DESIGN.md`.

**Checkpoint**: The right panel remains present and useful for all roles without exposing unrelated teams, Players, Business Audit data, or invented permissions.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the complete feature across migration, backend quickstart, generated contracts, browser behavior, accessibility, and quality gates; then document the verified implementation.

- [ ] T048 [P] Add `backend/tests/integration/quickstart/test_011_quickstart_flow.py` implementing every `quickstart.md` checkpoint: four roles, Match invariants, role-scoped dashboard data, linking lifecycle, exact audit cardinality, inactive linked-Player sessions, rollback, and bounded query behavior.
- [ ] T049 [P] Add `frontend/e2e/role-aware-dashboard-flow.spec.ts` and `frontend/e2e/role-aware-dashboard-fixtures.ts` covering Head Coach, Assistant Coach, linked Player, and unlinked Player dashboards, including exactly one permitted primary action per role, the empty-Events/View Teams fallback, the absence of unauthorized destinations, Player Directory account linking, unauthorized data absence, retry states, and no Match-management UI navigation.
- [ ] T050 [P] Add `backend/tests/integration/test_role_aware_dashboard_migration.py` to run Alembic upgrade from revision `012`, assert revision `013` constraints/indexes and existing account-less Players, then validate the repository's downgrade convention.
- [ ] T051 Regenerate and drift-check `frontend/src/features/dashboard/api/generated.ts` with `frontend/scripts/generate-role-aware-dashboard-types.mjs` after all backend routes and schemas are complete, including dashboard, Player account-linking, and Match participant operations.
- [ ] T052 Add responsive and accessibility regression coverage in `frontend/src/features/dashboard/components/DashboardResponsiveAccessibility.test.tsx` and `frontend/e2e/role-aware-dashboard-flow.spec.ts` for 320px, tablet, desktop, and an explicit 2560px desktop viewport; verify keyboard/focus behavior, live status announcements, reduced motion, and zero page-level horizontal overflow. At 2560px, verify no clipped content or broken alignment, dashboard sections and controls remain usable rather than excessively stretched, and the existing max-width/layout constraints continue to govern the composition.
- [ ] T053 Add `frontend/e2e/role-aware-dashboard-performance.spec.ts` and extend `frontend/e2e/role-aware-dashboard-fixtures.ts` with a deterministic local populated Head Coach fixture (current name, three summary slots, next Practice, next Match, five Upcoming Events, and four Recent Academy Activity entries). Use the existing Playwright Chromium runner with one worker; after ten warm-up opens, measure 100 sequential dashboard navigations from immediately before `page.goto('/')` until the greeting, all summaries, seeded events, and contextual panel are visible; sort durations ascending, assert the 95th value is at most 2,000 ms, and fail otherwise. Document the local command `cd frontend && npm run test:e2e -- role-aware-dashboard-performance.spec.ts --project=chromium --workers=1`; do not treat this mocked local result as production-network performance.
- [ ] T054 Run the repository quality gates from `backend/pyproject.toml` and `frontend/package.json`—Ruff, mypy/strict typing, unit/integration tests, generated-type check, ESLint, frontend build, quickstart, Playwright, and `cd frontend && npm run test:e2e -- role-aware-dashboard-performance.spec.ts --project=chromium --workers=1`—and resolve feature regressions in the paths above without adding unplanned dependencies or Match UI.
- [ ] T055 Write or update the verified feature documentation in `docs/role-aware-dashboard.md` only after T054 completes successfully, covering role-specific dashboard behavior, account/profile linking, external/internal Match semantics, API boundaries, authorization, audit/session behavior, and operational verification commands.

---

## Dependencies & Execution Order

### Phase Dependencies

Setup (Phase 1) has no prerequisites and its four tasks can run in parallel. Foundational work (Phase 2) depends on the setup boundaries and blocks all story implementation. The P1 stories then follow the plan's dependency chain: User Story 2 establishes participant semantics, User Story 3 establishes explicit Player account scope and session behavior, User Story 1 consumes both for the live dashboard, and User Story 4 refines the contextual panel. Polish depends on the desired stories being complete.

### User Story Dependencies

User Story 2 depends only on Phase 2. User Story 3 depends on Phase 2 and the shared audit/OCC conventions; it may begin after User Story 2's migration/domain checkpoint. User Story 1 depends on the completed Match and Player account contracts/services because its role scope and Next Match projection consume both persisted relationships. User Story 4 depends on User Story 1's dashboard response and layout. The stories should remain independently testable at their checkpoints even though the full browser journey exercises them together.

### Within Each User Story

Tests are written before implementation. Schemas and persistence mappings precede services; services precede routes and UI integration; bounded query and authorization behavior is verified before the story checkpoint. Frontend components must consume generated API types rather than duplicate backend response shapes.

### Parallel Opportunities

Setup tasks T001–T004 can run in parallel. Within User Story 2, T009–T012 can run in parallel. Within User Story 3, T016–T021 can run in parallel, followed by independent backend/frontend implementation files where their listed dependencies are satisfied. Within User Story 1, T030–T035 can run in parallel, and the dashboard presentational components in T040 can proceed independently from the route registration in T038 after the shared response contract exists. Within User Story 4, T043–T044 can run in parallel. Polish tasks T048–T052 can run in parallel after the story checkpoints, with T051 run after all backend contract operations exist; complete T053 after the role-aware dashboard fixtures and UI are ready, then run T054, followed by T055 only after T054 succeeds.

## Parallel Example: User Story 2

```text
After Phase 2, start T009, T010, T011, and T012 together.
Then implement T013, followed by T014 and T015.
```

## Parallel Example: User Story 3

```text
After the User Story 2 checkpoint, start T016, T017, T018, T019, T020, and T021 together.
Then implement T022–T026 for the backend and T027–T029 for the frontend once the generated contract artifact is available.
```

## Parallel Example: User Story 1

```text
After the User Story 3 checkpoint, start T030, T031, T032, T033, T034, and T035 together.
Then implement T036–T038 for the backend and T039–T042 for the frontend in parallel where their file dependencies permit.
```

## Parallel Example: User Story 4

```text
After the User Story 1 checkpoint, start T043 and T044 together.
Then implement T045, T046, and T047 as the response and panel composition are completed.
```

## Implementation Strategy

### MVP First

The MVP is the live P1 briefing in User Story 1, delivered with the required P1 prerequisites from User Stories 2 and 3: revision `013`, valid Match participant semantics, explicit Player account linkage, and inactive linked-Player session enforcement. Complete those prerequisites, finish User Story 1, stop at its checkpoint, and validate the authenticated dashboard independently. User Story 4's panel refinements and the final cross-cutting verification follow as the P2 increment.

### Incremental Delivery

Complete Setup and Foundational first. Deliver Match participants, then Player account association/security, then the live dashboard. Add the role-specific contextual panel as a separate P2 increment. Finish with quickstart, migration, generated-contract, responsive/accessibility, Playwright, and the local dashboard performance regression; run the quality gates, then write the verified documentation.

### Notes

`[P]` marks tasks that touch different files and have no incomplete prerequisite. `[US1]`–`[US4]` map directly to the user stories in `spec.md`; Setup, Foundational, and Polish tasks intentionally carry no story label. No task creates a Match-management page, modal, dashboard Create match route, dashboard persistence table, background aggregation, or new runtime dependency.
