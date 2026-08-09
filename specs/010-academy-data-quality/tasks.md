---

description: "Implementation tasks for Academy Data Quality Checks and Remediation"
---

# Tasks: Academy Data Quality Checks and Remediation

**Input**: Design documents from `/specs/010-academy-data-quality/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Tests**: Unit tests are required by the constitution and feature
specification. Backend integration tests are required by the remediation and
quickstart requirements. One Playwright journey is required for the feature.

**Implementation boundary**: Do not add persisted findings, schema migrations,
background jobs, generic mutation, bulk remediation, or a Head Coach removal
action. `coach.inactive_assigned` and its direct action apply only to inactive
Assistant Coaches; sole Head Coach integrity is Critical/manual-review-only.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the planned source/test locations and confirm that the
existing stack is sufficient.

- [X] T001 [P] Create the backend feature module and test directories described in `specs/010-academy-data-quality/plan.md` under `backend/src/schemas/`, `backend/src/services/`, `backend/src/routes/`, `backend/tests/unit/`, and `backend/tests/integration/`.
- [X] T002 [P] Create the frontend Data Quality feature directories described in `specs/010-academy-data-quality/plan.md` under `frontend/src/features/data-quality/` and add the planned E2E path `frontend/e2e/data-quality-flow.spec.ts`.
- [X] T003 [P] Confirm test scripts, test database setup, and whether an existing repository tool can generate OpenAPI-to-TypeScript contracts in `backend/pyproject.toml`, `frontend/package.json`, and `docker-compose.yml`; reuse a suitable existing tool when available. Only if none can satisfy the requirement, add one pinned development-only OpenAPI-to-TypeScript generator. For any new dependency, require the PR description to explain why existing dependencies/tools are insufficient, why the new generator is necessary, that it is development-only and not a runtime dependency, and that it satisfies Constitution X’s strongly typed API-boundary requirement.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared typed contracts, rule registry, projection evaluator,
and isolated fixtures that every user story depends on.

**⚠️ CRITICAL**: No user story implementation begins until this phase is complete.

- [X] T004 Define strict quality severity/domain/action enums and Pydantic request/response schemas, including summary, finding, related-entity, pagination, and discriminated remediation variants, in `backend/src/enums.py` and `backend/src/schemas/data_quality.py` based on `specs/010-academy-data-quality/contracts/data-quality-api.md`.
- [X] T005 Configure a reproducible frontend OpenAPI type-generation command and drift check that writes generated Data Quality request/response types to `frontend/src/features/data-quality/api/generated.ts`; treat generated types for the read and remediation endpoints as the frontend API-boundary source of truth, retain only UI-local types in `frontend/src/features/data-quality/types/dataQuality.ts`, and export them from `frontend/src/features/data-quality/index.ts`.
- [X] T006 Implement the pure player-name normalization helper, team-name grouping helper, stable finding-ID builder, rule metadata, severity assignments, and the registry for all 17 initial rules in `backend/src/services/data_quality_rules.py`, including `coach.sole_head_coach_integrity` and Assistant-only `coach.inactive_assigned` eligibility.
- [X] T007 Implement `DataQualityService` projection loading, batched/grouped rule evaluation, rule precedence, deterministic ordering, unfiltered summary calculation, allowlisted filters, default/max pagination, and current-state finding serialization in `backend/src/services/data_quality_service.py`.
- [X] T008 [P] Add isolated quality-data builders and query-count/test helpers for players, teams, roster memberships, coaches, assignments, calendar series, and exceptions in `backend/tests/unit/conftest.py` and `backend/tests/integration/conftest.py`.

**Checkpoint**: Typed contracts, registry, evaluator, and fixtures are ready for
story-specific routes, UI, remediation, and test coverage.

## Phase 3: User Story 1 - Review Current Academy Health (Priority: P1) 🎯 MVP

**Goal**: Let a Head Coach open Data Quality and see current findings, severity
and domain summaries, explanations, and the explicit healthy empty state.

**Independent Test**: Seed healthy and unhealthy Player, Team/Roster, Coach, and
Calendar records; authenticate as a Head Coach; request/open Data Quality; verify
summary counts, deterministic finding details, and “No data quality issues found”
when all conditions are corrected.

### Tests for User Story 1 (write first)

- [X] T009 [P] [US1] Add unit fixtures and tests for every initial rule, healthy/unhealthy cases, severity, normalized duplicate behavior, permitted optional/Assistant states, database-guaranteed exclusions, and sole Head Coach healthy/broken cases in `backend/tests/unit/test_data_quality_rules.py`.
- [X] T010 [P] [US1] Add evaluator tests for finding serialization, stable IDs, deterministic ordering, unfiltered summary counts, filtered totals, default/max page bounds, and query-count/N+1 regression behavior in `backend/tests/unit/test_data_quality_service.py`.
- [X] T011 [P] [US1] Add read-route tests for Head Coach mixed/healthy responses, Assistant Coach and Player HTTP 403 responses before service evaluation, summary counts, deterministic ordering, bounded page metadata, absence of Business Audit events from scans, and OpenAPI response-model generation in `backend/tests/unit/test_data_quality_routes.py`.
- [X] T012 [P] [US1] Add page/component tests for summary rendering, finding explanation/action text, initial loading, healthy no-issues state, and accessible status announcements in `frontend/src/features/data-quality/pages/DataQualityPage.test.tsx` and `frontend/src/features/data-quality/components/DataQualityStates.test.tsx`.

### Implementation for User Story 1

- [X] T013 [US1] Implement the Head Coach-protected `GET /api/v1/data-quality` route and register `backend/src/routes/data_quality.py` in `backend/src/main.py`, mapping validation and service failures to existing API responses, then generate the read-endpoint frontend contract types from the registered FastAPI OpenAPI schema.
- [X] T014 [US1] Implement the API client and abort-safe initial/read hook with default page size 20, importing its request/response boundary types from `frontend/src/features/data-quality/api/generated.ts`, in `frontend/src/features/data-quality/api/dataQualityApi.ts` and `frontend/src/features/data-quality/hooks/useDataQuality.ts`.
- [X] T015 [US1] Implement the Data Quality page shell, summary band, finding card/list, initial loading/error/healthy states, and accessible live result status in `frontend/src/features/data-quality/pages/DataQualityPage.tsx`, `frontend/src/features/data-quality/components/DataQualitySummary.tsx`, `frontend/src/features/data-quality/components/DataQualityFindingList.tsx`, `frontend/src/features/data-quality/components/DataQualityFindingCard.tsx`, and `frontend/src/features/data-quality/components/DataQualityStates.tsx`.
- [X] T016 [US1] Export the feature page and shared types/API entry points from `frontend/src/features/data-quality/index.ts` and verify the Head Coach can render the page through the protected application shell in `frontend/src/app/router.tsx`.

**Checkpoint**: User Story 1 is independently usable as a read-only Head Coach
MVP and its backend/frontend tests pass.

## Phase 4: User Story 2 - Filter and Navigate to an Existing Fix Workflow (Priority: P1)

**Goal**: Let a Head Coach filter findings by severity, domain, and rule, use
bounded pagination, and navigate to the existing domain workflow for judgment.

**Independent Test**: Render multiple findings, select each filter, verify the
filtered result and global summary, exercise filtered no-results/Clear filters,
and activate navigation for Player, Team, Coach, Roster, and Calendar findings.

### Tests for User Story 2 (write first)

- [X] T017 [P] [US2] Add route/integration coverage for severity, domain, and rule filters, filtered totals, bounded pagination, invalid filters, deterministic filtered ordering, and no audit events from filtered reads in `backend/tests/integration/test_data_quality_read.py`.
- [X] T018 [P] [US2] Add frontend tests for filter controls, Clear filters, filtered no-results, pagination controls, and Navigate to Fix/manual-review behavior for all 17 rule IDs, including roster-to-Teams mappings and findings whose only valid action is manual review, in `frontend/src/features/data-quality/components/DataQualityFilters.test.tsx`, `frontend/src/features/data-quality/components/DataQualityFindingCard.test.tsx`, and `frontend/src/features/data-quality/hooks/useDataQuality.test.ts`.

### Implementation for User Story 2

- [X] T019 [US2] Extend the Data Quality API client and hook to serialize allowlisted severity/domain/rule filters, reset to page 1, retain global summary data, cancel superseded requests, and navigate pages in `frontend/src/features/data-quality/api/dataQualityApi.ts` and `frontend/src/features/data-quality/hooks/useDataQuality.ts`.
- [X] T020 [US2] Implement responsive severity/domain/rule filters, Clear filters, filtered result status, and the existing bounded `Pagination` control in `frontend/src/features/data-quality/components/DataQualityFilters.tsx`, `frontend/src/features/data-quality/pages/DataQualityPage.tsx`, and `frontend/src/shared/components/navigation/Pagination.tsx` only where reuse requires an additive change.
- [X] T021 [US2] Implement deterministic Navigate to Fix actions and entity-label status feedback for `/players`, `/teams`, `/coaches`, and `/calendar` in `frontend/src/features/data-quality/components/DataQualityFindingCard.tsx` and `frontend/src/features/data-quality/pages/DataQualityPage.tsx` without introducing a new deep-link contract.

**Checkpoint**: User Stories 1 and 2 both work independently; filtering never
removes the global summary and subjective corrections stay in existing workflows.

## Phase 5: User Story 3 - Apply One Safe Direct Remediation (Priority: P1)

**Goal**: Apply only deterministic, confirmation-gated corrections through
existing domain services, OCC, validation, and Business Audit behavior.

**Independent Test**: Seed one eligible correction, submit it with the finding
identity, current version, and confirmation, verify one normal domain mutation
and audit event, re-evaluate until the finding disappears, then verify stale,
invalid, Head Coach, and failed-transaction cases do not partially change data.

### Tests for User Story 3 (write first)

- [X] T022 [P] [US3] Add remediation command/route unit tests for action allowlisting, exact target identity, confirmation requirements, current-finding re-evaluation, Head Coach success, Assistant Coach/Player HTTP 403 before service evaluation for every remediation capability, and rejection of Head Coach assignment removal in `backend/tests/unit/test_data_quality_remediation.py` and `backend/tests/unit/test_data_quality_routes.py`.
- [X] T023 [P] [US3] Add domain-service unit tests for roster normalization/removal, Assistant-only inactive assignment removal, OCC conflicts, valid-roster preconditions, preserved unrelated relationships, and existing audit action classification in `backend/tests/unit/test_team_service.py` and `backend/tests/unit/test_coach_service.py`.
- [X] T024 [P] [US3] Add frontend tests for remediation action visibility, confirmation dialog copy/focus/keyboard behavior, submitting state, success refresh, safe failure, stale conflict recovery, and absence of Head Coach removal controls in `frontend/src/features/data-quality/components/DataQualityRemediationDialog.test.tsx` and `frontend/src/features/data-quality/pages/DataQualityRemediation.test.tsx`.

### Implementation for User Story 3

- [X] T025 [US3] Add TeamService operations for normalize-roster-order and remove-one-inactive-player that re-check the target, enforce team OCC and 7–15 active-player rules, preserve unrelated membership, and reuse `roster.reordered`/`roster.removed` audit behavior in `backend/src/services/team_service.py`.
- [X] T026 [US3] Add a CoachService removal-only operation for one inactive Assistant Coach/team assignment that rejects Head Coach targets, re-checks user OCC and exact membership, preserves other assignments, and reuses `coach.team_assignments_updated` in `backend/src/services/coach_service.py`.
- [X] T027 [US3] Implement the typed `POST /api/v1/data-quality/remediations` request dispatch, confirmation validation, in-transaction finding/precondition re-evaluation, domain-service delegation, HTTP 400/404/409 mapping, and one-event transaction behavior in `backend/src/routes/data_quality.py`, `backend/src/services/data_quality_service.py`, and `backend/src/schemas/data_quality.py`, then regenerate remediation contract types from the registered FastAPI OpenAPI schema.
- [X] T028 [US3] Add remediation client calls using generated API-boundary types, confirmation state, API error handling, success toast/status, conflict recovery, and post-mutation re-evaluation in `frontend/src/features/data-quality/api/dataQualityApi.ts`, `frontend/src/features/data-quality/hooks/useDataQuality.ts`, `frontend/src/features/data-quality/components/DataQualityRemediationDialog.tsx`, and `frontend/src/features/data-quality/pages/DataQualityPage.tsx`.
- [X] T029 [US3] Add integration coverage for successful direct correction, resolved-finding disappearance, stale rejection, confirmation enforcement, domain-validation retention, rollback/no incorrect audit, exactly one existing Business Audit event, and no duplicate event in `backend/tests/integration/test_data_quality_remediation.py`.

**Checkpoint**: User Stories 1–3 are independently testable; direct actions are
strictly allowlisted and no Head Coach assignment can be removed from Data Quality.

## Phase 6: User Story 4 - Preserve Role Boundaries (Priority: P1)

**Goal**: Make Data Quality visible and callable only by authenticated Head
Coaches while preserving the existing 403/Forbidden and security-audit behavior.

**Independent Test**: Authenticate as Head Coach, Assistant Coach, and Player;
verify sidebar visibility/order, direct route behavior, absence of unauthorized
API requests, and HTTP 403 for every read/remediation capability.

### Tests for User Story 4 (write first)

- [X] T030 [P] [US4] Add cross-endpoint authorization integration tests for Head Coach success, Assistant Coach/Player HTTP 403 across every Data Quality read/remediation endpoint, and separation of authorization-denial security audit from Business Audit in `backend/tests/integration/test_data_quality_authorization.py`.
- [X] T031 [P] [US4] Add frontend tests for Data Quality sidebar visibility/order, protected route rendering, unauthorized no-request behavior, and configurable Forbidden copy in `frontend/src/layouts/AppLayout.test.tsx`, `frontend/src/app/router.test.tsx`, and `frontend/src/app/HeadCoachRoute.test.tsx`.

### Implementation for User Story 4

- [X] T032 [US4] Add or reuse a navigation icon and insert the Head Coach-only `Data Quality` item immediately after `Audit Log` in `frontend/src/shared/components/icons/NavIcons.tsx` and `frontend/src/layouts/AppLayout.tsx`.
- [X] T033 [US4] Make the existing HeadCoachRoute accept feature-specific forbidden title/description while preserving Audit Log behavior, and wrap `/data-quality` with it in `frontend/src/app/HeadCoachRoute.tsx` and `frontend/src/app/router.tsx`.
- [X] T034 [US4] Verify every backend Data Quality route uses `require_role(UserRole.HEAD_COACH)` before service evaluation or mutation and retains existing denial behavior in `backend/src/routes/data_quality.py` and `backend/src/main.py`.

**Checkpoint**: User Stories 1–4 preserve the existing role boundary in both
navigation and direct API access.

## Phase 7: User Story 5 - Recover from Normal Operational States (Priority: P2)

**Goal**: Keep the page understandable during loading, refresh, errors, retry,
remediation updates, filtered emptiness, and narrow responsive layouts.

**Independent Test**: Exercise initial/background loading, initial/background
failure, retry success, filtered no-results, healthy no-issues, remediation
success/failure/conflict, keyboard operation, and 320px mobile, 768px tablet,
and desktop rendering.

### Tests for User Story 5 (write first)

- [X] T035 [P] [US5] Add state and accessibility tests for loading, background refresh, initial error, retry, background error with retained data, healthy/filtered empty states, remediation status, and visible focus at 320px mobile, 768px tablet, and desktop widths in `frontend/src/features/data-quality/components/DataQualityStates.test.tsx`, `frontend/src/features/data-quality/pages/DataQualityPage.test.tsx`, and `frontend/src/features/data-quality/hooks/useDataQuality.test.ts`.

### Implementation for User Story 5

- [X] T036 [US5] Implement abort-safe request sequencing, retained-result refresh/error behavior, retry transitions, live status text, and stale-data recovery in `frontend/src/features/data-quality/hooks/useDataQuality.ts` and `frontend/src/features/data-quality/pages/DataQualityPage.tsx`.
- [X] T037 [US5] Finalize responsive filter/finding/dialog layout, semantic status regions, visible focus, reduced-motion-safe loading, 44px-class controls, and no page-level horizontal overflow at 320px mobile, 768px tablet, and desktop widths in `frontend/src/features/data-quality/components/`, `frontend/src/features/data-quality/pages/DataQualityPage.tsx`, and `frontend/src/styles/index.css` only where existing tokens require an additive rule.

**Checkpoint**: All five user stories have automated frontend state/accessibility
coverage and the page remains usable at the supported narrow viewport.

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify the complete feature, performance regressions, documentation,
and repository quality gates.

- [ ] T038 [P] Add the required end-to-end Playwright journey covering seeded/mocked multiple findings, Head Coach sidebar entry, summary, filters, entity review, inactive Assistant Coach remediation, resolved finding, underlying domain state, Business Audit Log event, and Assistant Coach/Player denial at 320px mobile, 768px tablet, and desktop viewport sizes in `frontend/e2e/data-quality-flow.spec.ts` and supporting `frontend/e2e/data-quality-fixtures.ts`.
- [ ] T039 [P] Implement the required backend quickstart flow described in `specs/010-academy-data-quality/quickstart.md`, including isolated seed/cleanup and current findings/remediation/audit assertions, in `backend/tests/integration/quickstart/test_010_quickstart_flow.py`.
- [ ] T040 [P] Add realistic seeded dataset query-count and scan-regression coverage for bounded projections, batching/joins/aggregates/grouping, deterministic repeated results, and no N+1 growth in `backend/tests/integration/test_data_quality_performance.py`.
- [ ] T041 Write verified feature documentation covering purpose, Head Coach flows, API surface, remediation safety, audit behavior, and configuration in `docs/academy-data-quality.md` after implementation and tests pass.
- [ ] T042 Run the documented focused tests, quickstart, generated-OpenAPI-type drift check, lint/build checks, and full repository gates from `specs/010-academy-data-quality/quickstart.md`; resolve failures without weakening the Head Coach, OCC, audit, boundedness, or accessibility requirements.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001–T003 can run in parallel.
- **Foundational (Phase 2)**: Depends on Setup; T004 and T008 can run in parallel, T005 depends on T003/T004, T006 depends on T004, and T007 depends on T004/T006.
- **User Story 1 (Phase 3)**: Depends on the complete Foundational phase; it is the MVP read-only increment.
- **User Story 2 (Phase 4)**: Depends on US1’s page/API shell but adds independently testable filters, pagination, and navigation.
- **User Story 3 (Phase 5)**: Depends on the finding/read contracts from Foundation/US1 and adds domain mutations plus direct actions.
- **User Story 4 (Phase 6)**: Depends on the page/route shell and read/write endpoints. Read-route authorization tests are completed before T013 and remediation-route authorization tests before T027; this phase adds the final cross-endpoint integration coverage and frontend role-boundary checks.
- **User Story 5 (Phase 7)**: Depends on the assembled page and remediation behavior from US1–US4.
- **Polish (Phase 8)**: Depends on all desired stories; E2E, quickstart, performance, docs, and final gates are the handoff criteria.

### User Story Dependencies

```text
Foundation
   └── US1 Review current health (MVP)
       ├── US2 Filter and Navigate to Fix
       ├── US3 Safe Direct Remediation
       └── US4 Role Boundaries
           └── US5 Operational States
               └── Polish / cross-cutting verification
```

US2 and US4 can be developed in parallel after the US1 shell exists if file
ownership is separated. US3’s backend service tests can proceed after
Foundation, but its UI integration depends on the US1 finding card. US5 and
Polish should follow the assembled page so state tests exercise the final flows.

### Parallel Execution Examples

```text
Setup:
  T001, T002, T003

Foundation:
  T004, T008 → T005 and T006 → T007

US1 tests:
  T009, T010, T011, T012

US2 tests:
  T017, T018

US3 tests and domain work:
  T022, T023, T024 → T025 and T026 → T027 → T028 → T029

US4 tests:
  T030, T031

Polish:
  T038, T039, T040, T041 → T042
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and the Foundational phase.
2. Complete US1’s deterministic evaluator, Head Coach read route, summary,
   findings, healthy state, and focused unit/route/frontend tests.
3. Stop and validate the read-only MVP with the independent US1 test criteria.
4. Continue to US2–US5 only after the current-state scan, ordering, summary,
   and no-issues behavior are stable.

### Incremental Delivery

1. Foundation → evaluator and contracts.
2. US1 → review current health MVP.
3. US2 → filters, bounded navigation, and existing workflow links.
4. US3 → safe direct remediation and audit/OCC integration.
5. US4 → complete role-boundary verification.
6. US5 → resilience, responsive, and accessibility completeness.
7. Polish → quickstart, Playwright, performance regression, docs, and gates.

### Parallel Team Strategy

After Foundation:

- Backend evaluator/route owner: T009–T013 and T017.
- Frontend page/filter owner: T012, T014–T021.
- Remediation/domain owner: T022–T029.
- Role/state/test owner: T030–T037.

Each owner must preserve the exact file boundaries and dependencies above to
avoid conflicting edits to the shared page, service, and route files.

## Notes

- Every task uses the required checkbox, sequential ID, optional `[P]`, required
  story label in user-story phases, and an explicit repository path.
- Tests must be written before the corresponding implementation within each
  story and should fail for the intended missing behavior.
- No new data-quality audit action is planned; successful remediation reuses
  `roster.reordered`, `roster.removed`, or `coach.team_assignments_updated`.
- The agent-context updater referenced by the generic planning workflow is not
  present in this repository; no context file task is included.
