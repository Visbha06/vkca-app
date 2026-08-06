---

description: "Implementation tasks for the Business Audit Log and Recent Academy Activity feature"
---

# Tasks: Business Audit Log and Recent Academy Activity

**Input**: Design documents from `/specs/009-business-audit-log/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), and [quickstart.md](quickstart.md)

**Tests**: Unit tests and the required Playwright journey are mandatory. Integration tests are included because the specification explicitly requires cross-module transaction and workflow verification.

**Scope guard**: All tasks below are business-audit-specific. Do not modify or integrate `backend/src/models/auth_audit_log.py`, `backend/src/services/audit_service.py`, `/api/v1/auth/audit-log`, or security-log UI behavior.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the feature boundaries and test seams without changing existing security-audit infrastructure.

- [X] T001 [P] Establish the backend business-audit module boundaries in `backend/src/models/business_audit_event.py`, `backend/src/services/business_audit_service.py`, `backend/src/schemas/business_audit.py`, and `backend/src/routes/business_audit.py`, reusing existing project naming and import conventions.
- [X] T002 [P] Establish the frontend feature module structure under `frontend/src/features/audit/` for API access, typed models, hooks, components, page composition, and academy-local time utilities.
- [X] T003 [P] Add isolated business-audit test seams in `backend/tests/conftest.py`, `backend/tests/unit/`, `backend/tests/integration/`, `frontend/src/features/audit/`, and `frontend/e2e/` without changing security-audit fixtures or tests.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build persistence, safe writing, bounded retrieval, typed contracts, and shared client behavior required by every user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T004 Create `BusinessAuditEvent` and reversible migration `backend/src/migrations/versions/012_create_business_audit_events.py`, including UUID conventions, creation-only timezone-aware timestamp, nullable actor/request IDs, polymorphic target IDs without foreign keys, JSONB metadata, and justified retrieval indexes; export the model from `backend/src/models/__init__.py`.
- [ ] T005 Define the typed action/category/entity registry, immutable actor context, immutable target context, and safe metadata field definitions in `backend/src/services/business_audit_service.py` or focused adjacent modules under `backend/src/services/`, with the initial action catalogue from `specs/009-business-audit-log/data-model.md`.
- [ ] T006 Implement the append-only writer in `backend/src/services/business_audit_service.py`: accept the caller’s `AsyncSession`, sanitize only allowlisted metadata, construct consistent safe summaries from snapshots, add and flush exactly one event, never commit independently, and expose no update/delete mutation method.
- [ ] T007 Implement typed request/filter/response schemas in `backend/src/schemas/business_audit.py`, including page/page-size bounds, registered enum values, UUID validation, inclusive academy-local dates, rejection of ranges over 366 dates before query execution, and the bounded actor-option response.
- [ ] T008 Implement the shared bounded retrieval methods in `backend/src/services/business_audit_service.py`, including full-log filters, recent limit enforcement at four, actor options limited to 100 distinct historical snapshots, `created_at DESC, id DESC` ordering, page metadata, snapshot-only serialization, and no linked-record N+1 queries.
- [ ] T009 Add Head Coach-only business-audit read routes in `backend/src/routes/business_audit.py` for `/api/v1/audit-log`, `/api/v1/audit-log/recent`, and `/api/v1/audit-log/actors`, register only this new router in `backend/src/main.py`, and preserve the existing authentication audit routes and 401/403 error conventions.
- [ ] T010 Add reusable actor/event factories and transaction fixtures in `backend/tests/conftest.py` and `backend/tests/integration/fixtures/` (or the repository’s established fixture location) for historical snapshots, equal timestamps, filter combinations, deleted linked records, and simulated persistence failures.
- [ ] T011 Add mirrored TypeScript types and the API client in `frontend/src/features/audit/types/businessAudit.ts` and `frontend/src/features/audit/api/businessAuditApi.ts` for the full page response, recent response, bounded actor options, filters, safe metadata, and established API error handling.
- [ ] T012 Add the shared business-audit query hooks in `frontend/src/features/audit/hooks/useBusinessAudit.ts`, including Head Coach-only actor-options loading, bounded recent requests, AbortSignal/stale-result protection, loading/error state, filter/page state, page reset on filter changes, and retry support.
- [ ] T013 Add and unit-test academy-local timestamp and relative-time utilities in `frontend/src/features/audit/utils/businessAuditTime.ts`, using stored ISO timestamps and `America/Los_Angeles` across daylight-saving transitions.

**Checkpoint**: The separate business-audit table, safe writer, bounded queries, typed client, and test fixtures are ready; no user story may use the security audit service.

## Phase 3: User Story 1 - Capture Administrative and Academy Activity (Priority: P1) 🎯 MVP

**Goal**: Record exactly one safe, transactional business-audit event for every successful externally initiated coach, player, team, roster, and calendar mutation in scope.

**Independent Test**: Run `backend/tests/unit/test_business_audit_service.py` and `backend/tests/integration/test_business_audit_logging.py` against isolated fixtures. Each successful API mutation has one event, composite mutations have no duplicate row-level events, failed validation/authorization/stale-version/persistence operations roll back both sides, and sensitive data never persists.

### Tests for User Story 1 (write first and make fail before implementation)

- [ ] T014 [P] [US1] Add unit coverage in `backend/tests/unit/test_business_audit_service.py` for caller-session use, flush-without-commit, allowlist sanitization, sensitive-field exclusion, safe summary construction, historical snapshots, exactly-one-event behavior, rollback propagation, persistence-failure propagation, and the absence of update/delete APIs.
- [ ] T015 [P] [US1] Add the required workflow matrix in `backend/tests/integration/test_business_audit_logging.py` for Assistant Coach creation, activation/deactivation, coach-team assignment replacement, player mutations, team mutations, roster add/remove/reorder and composite replacement, standalone calendar mutations, recurring-series mutations, and occurrence-only mutations, asserting one event per external mutation and none for rejected attempts.

### Implementation for User Story 1

- [ ] T016 [US1] Integrate actor context, outer transaction ownership, target snapshots, one allowlisted event, and rollback behavior into player creation/profile-update workflows in `backend/src/services/player_service.py` and `backend/src/routes/players.py`, updating focused existing tests under `backend/tests/`.
- [ ] T017 [US1] Integrate team details and roster add/remove/reorder/replacement auditing at the outer mutation boundary in `backend/src/services/team_service.py` and `backend/src/routes/teams.py`, using composite metadata instead of per-row duplicate events and updating existing team/roster tests under `backend/tests/`.
- [ ] T018 [US1] Integrate Assistant Coach creation and coach-team assignment replacement in `backend/src/services/coach_service.py`, `backend/src/routes/coaches.py`, and the canonical account-creation route, ensuring one event regardless of internal assignment operations and extending focused coach tests under `backend/tests/`.
- [ ] T019 [US1] Centralize coach activation/deactivation auditing in the existing status transaction in `backend/src/services/user_service.py` and `backend/src/routes/users.py`, preserving existing authorization/session behavior and extending status mutation tests under `backend/tests/`.
- [ ] T020 [US1] Integrate standalone event, recurring-series, occurrence edit/move/delete, and pre-delete snapshot auditing in `backend/src/services/calendar_service.py` and `backend/src/routes/calendar.py`, with recurrence/occurrence details restricted to the allowlist and focused calendar tests under `backend/tests/`.
- [ ] T021 [US1] Complete and run cross-workflow assertions in `backend/tests/integration/test_business_audit_logging.py` and existing domain tests to prove one event per external mutation, atomic domain-plus-audit commit/rollback, historical readability after linked-record deletion/rename, and unchanged security-audit behavior in `backend/src/services/audit_service.py` and `backend/src/models/auth_audit_log.py`.

**Checkpoint**: The MVP capture slice is independently usable and verifiable through backend workflows, even before the new UI is connected.

## Phase 4: User Story 2 - Review and Investigate the Business Audit Log (Priority: P1)

**Goal**: Give an authorized Head Coach a safe, filterable, paginated, newest-first business activity feed with useful disclosures and complete state handling.

**Independent Test**: Seed business events directly through the feature fixtures, run backend route tests, and render the page with frontend tests. A Head Coach can filter/page/disclose safely; the page distinguishes initial empty from filtered no-results and recovers from errors; no security event or raw payload appears.

### Tests for User Story 2 (write first and make fail before implementation)

- [ ] T022 [P] [US2] Add backend route coverage in `backend/tests/unit/test_business_audit_routes.py` for Head Coach access to `GET /api/v1/audit-log/actors`, Assistant Coach/Player HTTP 403 responses, alphabetical actor-option ordering, actor-ID deduplication, the 100-option bound, null-actor exclusion, empty actor-option results, every supported audit-log filter, date validation, pagination bounds, stable newest-first ordering, recent limit enforcement, initial empty history, filtered no-results, safe failures, and absence of update/delete routes.
- [ ] T023 [P] [US2] Add API client unit tests in `frontend/src/features/audit/api/businessAuditApi.test.ts` for query serialization, pagination parameters, filter serialization, recent-activity limit enforcement, `AbortSignal`, 403 and validation errors, and safe error mapping.
- [ ] T024 [P] [US2] Add query-hook unit tests in `frontend/src/features/audit/hooks/useBusinessAudit.test.ts` for initial load, filter changes resetting page, pagination, stale-request protection, retry, empty versus filtered no-results, bounded dashboard activity loading, and Head Coach-only actor-options loading.
- [ ] T025 [P] [US2] Add frontend feature tests under `frontend/src/features/audit/` for feed rendering, filters and page reset, actor-option selection, pagination controls, loading, initial empty, filtered no-results, retryable error, safe expandable details, status announcements, and academy-local timestamp presentation.

### Implementation for User Story 2

- [ ] T026 [US2] Implement labeled responsive filter controls in `frontend/src/features/audit/components/BusinessAuditFilters.tsx`, loading the bounded Head Coach-only actor options, including actor/category/action/entity/date inputs, clear behavior, validation feedback, keyboard focus, and small-screen wrapping.
- [ ] T027 [US2] Implement safe event presentation and native keyboard-operable disclosure in `frontend/src/features/audit/components/BusinessAuditEventItem.tsx` and `frontend/src/features/audit/components/BusinessAuditEventList.tsx`, showing snapshots and allowlisted details only with category text plus icon.
- [ ] T028 [US2] Implement loading, initial-empty, filtered-no-results, unauthorized, and retryable-error states in `frontend/src/features/audit/components/BusinessAuditStates.tsx`, using existing status/alert/empty patterns and accessible result-change announcements.
- [ ] T029 [US2] Compose the full page in `frontend/src/features/audit/pages/BusinessAuditLogPage.tsx` with the existing shell/page-header, shared pagination component, actor-options/filter/query state, stable event list, bounded requests, no horizontal overflow from 320px through desktop widths, and no authentication/security audit content.

**Checkpoint**: The Audit Log component is independently testable with seeded business events and all required loading, empty, no-results, error, disclosure, pagination, and accessibility behavior.

## Phase 5: User Story 3 - See Recent Activity on the Head Coach Dashboard (Priority: P1)

**Goal**: Replace static dashboard activity with the latest four business-audit events while keeping the existing section’s placement and preserving dashboard resilience.

**Independent Test**: Render `frontend/src/pages/home/HomeSchedule.tsx` with recent-event, empty, and failure fixtures. Verify exactly four or fewer events, category-aware summaries and relative academy-local time, View all activity navigation, and that a recent-query failure leaves the rest of the dashboard usable.

### Tests for User Story 3 (write first and make fail before implementation)

- [ ] T030 [P] [US3] Add dashboard tests in `frontend/src/pages/home/HomePage.test.tsx` and the applicable `frontend/src/pages/home/HomeSchedule.test.tsx` for Head Coach visibility, Assistant Coach/Player absence, no recent-activity endpoint call for unauthorized roles, latest-four rendering, concise descriptions, relative timestamps, empty state, retryable compact failure isolation, performance-event exclusion, and navigation to `/audit-log`.

### Implementation for User Story 3

- [ ] T031 [US3] Replace static activity entries in `frontend/src/pages/home/HomeSchedule.tsx` with the shared bounded recent query from `frontend/src/features/audit/hooks/useBusinessAudit.ts`, rendering Recent academy activity only for authenticated Head Coaches so Assistant Coaches and Players neither issue the request nor receive placeholder UI; preserve the current visual composition, add category icons/text, relative time, empty/error/retry states, and the View all activity link; update `frontend/src/pages/home/HomePage.tsx` only as needed for Head Coach composition.

**Checkpoint**: Head Coach dashboard activity is dynamic, bounded to four records, sourced from the same business-audit retrieval path, and failure-isolated from the rest of the dashboard.

## Phase 6: User Story 4 - Preserve Clear Permissions and Accessible Recovery (Priority: P2)

**Goal**: Make business-audit access unmistakably Head Coach-only in navigation, routing, and backend enforcement while preserving usable recovery and accessibility across responsive layouts.

**Independent Test**: Run role-specific frontend route/navigation tests and the backend 403 tests, then verify at 320px and desktop widths that keyboard users can operate filters, disclosures, retry, and pagination with visible focus and announcements.

### Tests for User Story 4 (write first and make fail before implementation)

- [ ] T032 [P] [US4] Add role-protection tests in `frontend/src/layouts/AppLayout.test.tsx`, `frontend/src/app/router.test.tsx`, and `frontend/src/pages/ForbiddenPage.test.tsx` for Head Coach visibility, hidden unauthorized navigation, direct unauthorized navigation, preserved existing forbidden behavior, no unauthorized event rendering, and backend 403 behavior for direct business-audit requests.
- [ ] T033 [P] [US4] Add responsive/accessibility assertions under `frontend/src/features/audit/` for 320px layout, no page overflow, visible focus, touch targets, keyboard disclosures, filter/pagination labels, live status/error announcements, and category identification without icon-only meaning.

### Implementation for User Story 4

- [ ] T034 [US4] Add a reusable Head Coach route guard and feature-specific forbidden behavior in `frontend/src/app/router.tsx` and `frontend/src/pages/ForbiddenPage.tsx`, preserving existing authenticated route and Coaches Portal semantics.
- [ ] T035 [US4] Add the `Audit Log` navigation item immediately beneath Calendar and render it only for Head Coaches in `frontend/src/layouts/AppLayout.tsx`, extending `frontend/src/shared/components/icons/NavIcons.tsx` only if an established icon is unavailable.
- [ ] T036 [US4] Harden responsive and accessible behavior in `frontend/src/features/audit/` and `frontend/src/layouts/AppLayout.tsx`, including stacked/wrapping controls, focus retention, disclosure announcements, safe retry/clear-filter actions, and no horizontal page overflow.

**Checkpoint**: Backend and frontend independently enforce Head Coach-only access, unauthorized users see no business audit data, and the page remains operable and understandable across required widths and assistive technologies.

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete feature, document the boundary and retention policy, and prove the required end-to-end journey.

- [ ] T037 [P] Add the required Playwright journey in `frontend/e2e/audit-log-flow.spec.ts`: sign in as Head Coach, perform several existing administrative actions, verify dashboard Recent academy activity, open full Audit Log, verify newest-first order, filter, expand safe details, and verify Assistant Coach/Player denial.
- [ ] T038 [P] Add the required automated quickstart flow in `backend/tests/integration/quickstart/test_009_quickstart_flow.py`, covering one-event composite behavior, rollback, historical snapshots, Head Coach-only retrieval, actor options, filters/bounds, dashboard role gating, and accessibility-related API states from `specs/009-business-audit-log/quickstart.md`.
- [ ] T039 Validate migration upgrade/downgrade, index shape, no historical-ID foreign keys, and creation-only timestamp behavior using `backend/src/migrations/versions/012_create_business_audit_events.py`, the repository’s migration test conventions, and PostgreSQL in the local validation environment.
- [ ] T040 Run the complete verification commands documented in `specs/009-business-audit-log/quickstart.md`, including backend unit/integration/quickstart tests, frontend feature/shell/dashboard tests, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `npm run lint`, `npm run build`, and the Playwright journey; resolve only feature-scoped failures.
- [ ] T041 Write `docs/business-audit-log.md` after T039 and T040 complete, documenting the business/security boundary, action catalogue, transaction contract, metadata allowlist, historical-ID/snapshot policy, API/UI behavior, and intended future retention policy without implementing cleanup.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001–T003 may run in parallel.
- **Foundational (Phase 2)**: Depends on Setup; T004–T013 block all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP capture slice.
- **User Story 2 (Phase 4)**: Depends on Foundational; it can use seeded events independently of User Story 1, but production validation should include User Story 1 events.
- **User Story 3 (Phase 5)**: Depends on Foundational and the shared API/query hook; it can be tested independently with seeded recent events.
- **User Story 4 (Phase 6)**: Depends on the Audit Log page and shared shell work from User Story 2, plus the dashboard link and role-gated request behavior from User Story 3.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only; no dependency on UI stories.
- **US2 (P1)**: Foundational only for independent seeded-event testing; integrates with US1’s persisted event output in end-to-end validation.
- **US3 (P1)**: Foundational plus the shared business-audit hook; independent from the full-log page for implementation and tests.
- **US4 (P2)**: Depends on US2’s page and US3’s dashboard link/request gating because it hardens their route/navigation access and recovery behavior.

### Within Each User Story

- Write the story’s tests first and make them fail before implementation tasks.
- Complete shared model/service/query prerequisites before mutation integrations or UI composition.
- Keep one externally initiated mutation as the audit boundary; internal row helpers never emit events.
- Verify each story at its checkpoint before moving to the next priority.

### Parallel Opportunities

- Setup: T001, T002, and T003 can run in parallel.
- Foundation: after T004/T005 establish the vocabulary, T007, T011, and T013 can proceed in parallel; T006 and T008 then depend on those contracts.
- US1: T014 and T015 can run in parallel; after the writer is ready, player (T016), team/roster (T017), coach (T018), status (T019), and calendar (T020) integrations touch different primary service files and can proceed in parallel with coordinated shared-service review.
- US2: T022–T025 can run in parallel; filter (T026), event presentation (T027), and state components (T028) can then proceed in parallel before page composition (T029).
- US3: T030 can be written while US2 is being completed; T031 starts once the shared hook from Phase 2 is stable.
- US4: T032 and T033 can run in parallel; T034 and T035 touch different application-shell files and can be implemented in parallel before T036’s cross-cutting pass.
- Polish: T037 and T038 can run in parallel after their story checkpoints; T039 and T040 are final validation tasks, and T041 follows both so documentation reflects verified implementation.

## Parallel Example: Backend Capture MVP

```text
T014  business-audit service unit tests
T015  end-to-end mutation matrix
  └── after foundational writer contracts:
      T016  player integration
      T017  team/roster integration
      T018  coach integration
      T019  activation/deactivation integration
      T020  calendar integration
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational; this is the blocking transaction/query boundary.
3. Complete Phase 3 User Story 1 and run its unit/integration checkpoint.
4. Stop and validate that every successful in-scope mutation has exactly one event and every failure rolls back both domain and audit rows.
5. Add the read page, dashboard, and access hardening incrementally.

### Incremental Delivery

1. Setup + Foundation → reusable append-only business-audit capability.
2. US1 → transactional capture MVP.
3. US2 → Head Coach full Audit Log with filters and pagination.
4. US3 → bounded dashboard Recent academy activity.
5. US4 → role-protected navigation/routing and responsive accessibility hardening.
6. Polish → documentation, quickstart, migration validation, lint/type/build checks, and E2E journey.

### Task Count Breakdown

- Setup: 3 tasks (T001–T003)
- Foundational: 10 tasks (T004–T013)
- US1: 8 tasks (T014–T021)
- US2: 8 tasks (T022–T029)
- US3: 2 tasks (T030–T031)
- US4: 5 tasks (T032–T036)
- Polish: 5 tasks (T037–T041)
- **Total: 41 tasks**

## Notes

- `[P]` means the task can be worked in parallel without depending on an unfinished task in the same phase; shared-service changes still require normal review before merge.
- Story labels map implementation and test tasks to the four user stories in `spec.md`.
- All list retrieval remains bounded; the dashboard never requests complete history.
- No task adds authentication/security logging, security-event display, automatic retention cleanup, export, undo/rollback UI, or deferred match/performance/statistics activity.
