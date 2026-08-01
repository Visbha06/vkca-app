# Tasks: Calendar Interface

**Input**: Design documents from `/specs/008-calendar-interface/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), and [quickstart.md](quickstart.md)

**Tests**: Unit tests are mandatory by the project constitution. The specification also requires backend coverage, frontend coverage, and one Playwright E2E journey. Integration coverage is included where the specification requires cross-module persistence, authorization, OCC, and atomicity verification.

**Organization**: Tasks are ordered by dependency and grouped by the four user stories in the specification. Each story has an independent test criterion and can be validated at its checkpoint.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the calendar feature paths and test scaffolding without adding a new production dependency.

- [X] T001 Create the calendar feature package/index paths in `backend/src/models/__init__.py`, `backend/src/schemas/__init__.py`, `backend/src/services/__init__.py`, and `frontend/src/features/calendar/index.ts`.
- [X] T002 [P] Add reusable calendar fixture builders and academy-time test constants in `backend/tests/unit/conftest.py` and `frontend/src/features/calendar/testFixtures.ts`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the shared data, typed contracts, recurrence primitives, routing, and date utilities required by every story.

**⚠️ CRITICAL**: No user story implementation should begin until this phase is complete.

- [X] T003 Add `EventType`, `ScopeKind`, `RecurrenceFrequency`, and `RecurrenceTermination` enums without changing existing enum values in `backend/src/enums.py`.
- [X] T004 Create migration `backend/src/migrations/versions/011_create_calendar.py` for event definitions, recurrence rules, scope rows, occurrence exceptions, OCC versions, indexes, uniqueness constraints, and cascading hard-delete foreign keys.
- [X] T005 Implement SQLAlchemy calendar entities and relationships in `backend/src/models/calendar.py` from `data-model.md`, including the UUID `RecurrenceSeries.id`, unique one-to-one `event_id`, stable `(series_id, original_date)` exception identity, canonical owning-event OCC version, and cascade behavior.
- [X] T006 Implement Pydantic calendar request/response schemas in `backend/src/schemas/calendar.py`, including scope, recurrence, effective instance, owning-event/exception mutation versions, and exception-removal-warning payloads.
- [X] T007 Implement bounded weekly/yearly recurrence arithmetic in `backend/src/services/calendar_recurrence.py`, including `America/Los_Angeles` date rules, Feb 29 → Feb 28 fallback, end-date/count termination, and no multi-year expansion.
- [X] T008 Add mirrored TypeScript calendar types for event instances, scopes, recurrence, versions, warning responses, and API errors in `frontend/src/features/calendar/types/calendar.ts`.
- [X] T009 Add the typed calendar API client surface in `frontend/src/features/calendar/api/calendarApi.ts` for range, Today, instance details, create, standalone update/delete, occurrence update/delete, series update/delete, and `AbortSignal` support.
- [X] T010 Extend `frontend/src/shared/utils/calendarDate.ts` and its tests in `frontend/src/shared/utils/calendarDate.test.ts` with complete-week grid helpers, academy-date parsing/formatting, focus movement, and dynamic 2026-to-current-year-plus-five calculations.
- [X] T011 Register the backend calendar router in `backend/src/main.py`, preserve the protected `/calendar` route in `frontend/src/app/router.tsx`, and update the retained route wrapper in `frontend/src/pages/CalendarPage.tsx` to delegate to the feature page entry point.
- [X] T012 Add safe calendar error-code mapping and typed exception-removal warning handling in `frontend/src/features/calendar/utils/calendarErrors.ts`, preserving the existing `ApiClientError` and raw-error redaction behavior.

**Checkpoint**: Migration, models, schemas, recurrence primitives, typed API boundaries, and protected route wiring are ready for story work.

---

## Phase 3: User Story 1 - Review the Academy Calendar (Priority: P1) 🎯 MVP

**Goal**: Let every authenticated role open Calendar, see the current academy month and event instances, open event details, and use a read-only view as a Player.

**Independent Test**: Authenticate as Head Coach, Assistant Coach, and Player; open `/calendar`; verify the server-provided current academy month, complete grid, adjacent-month dates, event ordering/icons, Today-independent event details, and absence of Player mutation controls.

### Tests for User Story 1 (MANDATORY)

- [X] T013 [P] [US1] Add recurrence and range projection unit tests for Pacific-time current-date interpretation, complete-grid intersection, event ordering, stable occurrence identity, adjacent-month instances, and effective event instances intersecting the current academy day in `backend/tests/unit/test_calendar_recurrence.py` and `backend/tests/unit/test_calendar_service.py`.
- [X] T014 [P] [US1] Add authenticated read-route tests for Head Coach, Assistant Coach, and Player range/detail/Today access plus malformed and over-45-date range rejection in `backend/tests/unit/test_calendar_routes.py`; cover empty Today, all-day/timed ordering, recurring occurrences, moved/deleted exceptions, authorization, and Pacific-time boundaries.
- [X] T015 [P] [US1] Add typed read-client tests for range, Today, detail, query serialization, `AbortSignal`, and safe error mapping in `frontend/src/features/calendar/api/calendarApi.test.ts`.
- [X] T016 [P] [US1] Add component tests for event-type icons, age-group/All Academy labels, adjacent-month styling, current-date treatment, event ordering, three-entry limit, and accessible `+N more` labels in `frontend/src/features/calendar/components/CalendarMonthGrid.test.tsx`.

### Implementation for User Story 1

- [X] T017 [US1] Implement read-side range, Today-day retrieval, instance projection, scope display data, stable ordering, and safe not-found behavior in `backend/src/services/calendar_service.py` (depends on T005–T007 and T013–T014).
- [X] T018 [US1] Implement authenticated `GET /api/v1/calendar/events`, `GET /api/v1/calendar/today`, and `GET /api/v1/calendar/instances/{occurrence_id}` handlers with safe status/code mapping in `backend/src/routes/calendar.py` (depends on T006, T017).
- [X] T019 [US1] Implement initial Today-first loading, range state, selected instance state, and superseded-request guards in `frontend/src/features/calendar/hooks/useCalendarData.ts` (depends on T008–T009 and T015).
- [X] T020 [P] [US1] Implement event-type labels/icons and age-group/All Academy presentation helpers in `frontend/src/features/calendar/utils/calendarLabels.ts` and `frontend/src/features/calendar/components/CalendarEventIcon.tsx` (depends on T008).
- [X] T021 [P] [US1] Implement structure-preserving initial/navigation loading and calendar-load error/retry components in `frontend/src/features/calendar/components/CalendarLoadingState.tsx` and `frontend/src/features/calendar/components/CalendarErrorState.tsx` (depends on T008, T012).
- [X] T022 [US1] Implement the semantic seven-column grid, focusable date cells, adjacent-month cells, current-date styling, accessible event entries, and `+N more` trigger in `frontend/src/features/calendar/components/CalendarMonthGrid.tsx`, `frontend/src/features/calendar/components/CalendarDayCell.tsx`, and `frontend/src/features/calendar/components/CalendarEventEntry.tsx` (depends on T010, T016, T019–T021).
- [X] T023 [US1] Implement the shared event details and full-day overflow modal flows with read-only presentation and focus restoration in `frontend/src/features/calendar/components/EventDetailsModal.tsx` and `frontend/src/features/calendar/components/DayEventsModal.tsx` (depends on T019, T022).
- [X] T024 [US1] Compose the protected Calendar page shell and role-aware read-only rendering in `frontend/src/features/calendar/pages/CalendarPage.tsx` and `frontend/src/pages/CalendarPage.tsx` using `ModalDialog`, `PRODUCT.md`, and `DESIGN.md` tokens (depends on T019–T023).
- [X] T025 [US1] Add page-level tests for all authenticated roles, current academy month bootstrap, read-only Player details, modal focus behavior, and empty calendar days in `frontend/src/features/calendar/pages/CalendarPage.test.tsx` (depends on T024).

**Checkpoint**: All authenticated roles can review the monthly calendar and open details; Player users have no mutation affordances.

---

## Phase 4: User Story 2 - Navigate the Calendar and Today Briefing (Priority: P1)

**Goal**: Let users move month-by-month and year-by-year, navigate before 2026 with arrows, preserve focus, and read a correctly ordered Today briefing.

**Independent Test**: From the current academy month, move across a year boundary, select a permitted future year, navigate back to a pre-2026 month with arrows, verify loading/stale-response behavior, and validate populated/empty/error Today states.

### Tests for User Story 2 (MANDATORY)

- [X] T026 [P] [US2] Add navigation and year-selector tests for one-month movement, year boundaries, 2026-to-current-year-plus-five options, pre-2026 arrow access, month preservation, focus restoration, and dynamic range reloads in `frontend/src/features/calendar/components/CalendarHeader.test.tsx` and `frontend/src/features/calendar/hooks/useCalendarData.test.ts`.
- [X] T027 [P] [US2] Add Today-section tests for academy-local date selection, all-day/timed ordering, recurring summaries, empty copy, inline loading, retry, and event selection in `frontend/src/features/calendar/components/TodaySection.test.tsx`.
- [X] T028 [P] [US2] Add responsive keyboard-navigation tests for 320px, tablet, and desktop grid usability, visible focus, semantic date labels, and no horizontal page overflow in `frontend/src/features/calendar/pages/CalendarPage.test.tsx`.

### Implementation for User Story 2

- [X] T029 [US2] Implement the calendar header with active-year selector, previous/next month controls, dynamic year range, disabled/loading states, and accessible announcements in `frontend/src/features/calendar/components/CalendarHeader.tsx` (depends on T010 and T026).
- [X] T030 [US2] Extend `useCalendarData.ts` to load the newly visible complete grid range, cancel/ignore superseded requests, retain structure while loading, and restore focus after month/year changes (depends on T019, T026).
- [X] T031 [US2] Implement Today retrieval/rendering with inline loading/error/retry, exact empty copy, academy-local ordering, recurrence indicators, and shared event selection in `frontend/src/features/calendar/components/TodaySection.tsx` (depends on T009, T027).
- [X] T032 [US2] Integrate header navigation, Today refresh, selected date announcements, and responsive wrapping into `frontend/src/features/calendar/pages/CalendarPage.tsx` and `frontend/src/features/calendar/components/CalendarMonthGrid.tsx` (depends on T022, T024, T028–T031).

**Checkpoint**: Users can navigate the full supported calendar range and receive an accurate Today briefing without stale results or focus loss.

---

## Phase 5: User Story 3 - Create and Manage Events (Priority: P1)

**Goal**: Let coaches create, edit, move, and delete standalone events, recurring series, and individual occurrences with complete validation, scope, recurrence, warning, and OCC behavior.

**Independent Test**: As a coach, create a timed weekly series, edit one occurrence only, confirm other occurrences remain unchanged, delete that occurrence, then delete the entire series and confirm all series data disappears.

### Tests for User Story 3 (MANDATORY)

- [ ] T033 [P] [US3] Add schema tests for event types, timed/all-day rules, same-day end times, unique scope/All Academy validation, past-date validation, recurrence termination, Feb 29 fallback inputs, and mutation versions in `backend/tests/unit/test_calendar_schemas.py`.
- [ ] T034 [P] [US3] Add service tests for atomic creation, weekly/yearly expansion, never-ending bounds, end-date/count termination, standalone updates/deletes, occurrence snapshots/moves/deletes, series exception impact confirmation, cascade hard deletion, owning-event/exception OCC, and UUID series identity in `backend/tests/unit/test_calendar_service.py` and `backend/tests/unit/test_calendar_recurrence.py`.
- [ ] T035 [P] [US3] Add mutation-route tests for coach authorization, Player HTTP 403 responses, HTTP 409 stale owning-event/exception versions, HTTP 422 exception-removal warnings, and safe validation errors in `backend/tests/unit/test_calendar_routes.py`.
- [ ] T036 [P] [US3] Add frontend mutation-client tests for create/update/delete payloads, owning-event and exception version fields, warning responses, 403/409 mapping, CSRF-compatible requests, and no automatic conflict retry in `frontend/src/features/calendar/api/calendarApi.test.ts`.

### Implementation for User Story 3

- [ ] T037 [US3] Implement atomic standalone/series creation and standalone update/delete validation and persistence in `backend/src/services/calendar_service.py` (depends on T004–T007 and T033–T035).
- [ ] T038 [US3] Implement occurrence-only update/delete using owning-event and exception OCC, stable exception snapshots, moved-occurrence suppression, series update impact calculation, explicit exception-removal confirmation, preservation of still-valid original identities, removal of invalid exceptions, and entire-series cascade deletion in `backend/src/services/calendar_service.py` (depends on T037, T034).
- [ ] T039 [US3] Implement coach-only create/update/delete and occurrence/series mutation routes in `backend/src/routes/calendar.py`, including HTTP 403/409/422 behavior and transaction-safe response models (depends on T006, T035, T037–T038).
- [ ] T040 [US3] Implement event form state and associated validation in `frontend/src/features/calendar/components/EventForm.tsx` for name/type/date, same-day times, Miscellaneous all-day, unique scope, All Academy, past-date feedback, and dirty tracking (depends on T008, T012, T033, T036).
- [ ] T041 [US3] Implement recurrence frequency/termination controls and accessible conditional fields in `frontend/src/features/calendar/components/RecurrenceFields.tsx` (depends on T040).
- [ ] T042 [US3] Implement create/edit modal submission, occurrence-vs-series choice, version payloads, unsaved-change confirmation, progress/error preservation, and conflict reload in `frontend/src/features/calendar/components/EventFormModal.tsx` and `frontend/src/features/calendar/hooks/useCalendarConflict.ts` (depends on T036, T040–T041).
- [ ] T043 [US3] Implement series exception-removal warning and delete confirmation flows in `frontend/src/features/calendar/components/SeriesExceptionWarning.tsx` and `frontend/src/features/calendar/components/CalendarDeleteDialog.tsx` (depends on T039, T042).
- [ ] T044 [US3] Add coach-only Edit Event/Delete Event actions and occurrence/series selection behavior to `frontend/src/features/calendar/components/EventDetailsModal.tsx` (depends on T023, T042–T043).
- [ ] T045 [US3] Integrate mutation success toast, visible-range refresh, Today refresh when affected, modal transitions, and duplicate-submission guards in `frontend/src/features/calendar/hooks/useCalendarData.ts` and `frontend/src/features/calendar/pages/CalendarPage.tsx` (depends on T030–T032, T039, T042–T044).
- [ ] T046 [US3] Add cross-module backend integration coverage for atomic event/series persistence, range projection, role authorization, exception behavior, OCC, and hard deletion in `backend/tests/integration/test_calendar_flow.py` (depends on T037–T039).
- [ ] T047 [US3] Add the required coach Playwright journey and stateful API mock for timed recurring creation, occurrence-only edit, occurrence deletion, and entire-series deletion in `frontend/e2e/calendar-flow.spec.ts` and `frontend/e2e/calendar-api-mock.ts` (depends on T045 and `specs/008-calendar-interface/contracts/calendar-api.md`).

**Checkpoint**: Coaches can perform the complete recurring-event lifecycle, while Players remain read-only and the backend remains authoritative.

---

## Phase 6: User Story 4 - Recover from Errors and Concurrent Changes (Priority: P2)

**Goal**: Make calendar loading, details, forms, warnings, conflicts, retries, and responsive/accessibility failures safe and recoverable without data loss.

**Independent Test**: Inject range/Today/detail/network/validation/403/409 failures, verify safe messages and retry/reload actions, preserve dirty form values, prevent duplicate mutation, and verify no stale request replaces current data.

### Tests for User Story 4 (MANDATORY)

- [ ] T048 [P] [US4] Add backend error/OCC integration tests for excessive ranges, malformed recurrence, past-date rejection, Player mutation denial, stale owning-event/exception versions, and rollback after failed atomic operations in `backend/tests/integration/test_calendar_conflicts.py`.
- [ ] T049 [P] [US4] Add frontend failure-state tests for calendar/Today/detail retries, safe network messages, 403/409 conflict reload, preserved form data, removal-warning cancel, repeated-submit blocking, and unsaved-change confirmation in `frontend/src/features/calendar/hooks/useCalendarData.test.ts`, `frontend/src/features/calendar/components/EventDetailsModal.test.tsx`, and `frontend/src/features/calendar/components/EventFormModal.test.tsx`.
- [ ] T050 [P] [US4] Add accessibility and responsive regression tests for modal focus trap/restoration, Escape behavior, associated errors/status announcements, reduced motion, forced colors, touch targets, and 320px internal scrolling in `frontend/src/features/calendar/components/CalendarAccessibility.test.tsx`.

### Implementation for User Story 4

- [ ] T051 [US4] Implement centralized calendar status/error mapping, retry actions, and stale-response guards in `frontend/src/features/calendar/utils/calendarErrors.ts` and `frontend/src/features/calendar/hooks/useCalendarData.ts` (depends on T012, T030, T049).
- [ ] T052 [US4] Harden event details/forms/warnings/delete dialogs for unsafe-close blocking, background scroll lock, focus trap/restoration, inline progress, preserved values, and accessible error/status announcements in `frontend/src/features/calendar/components/EventDetailsModal.tsx`, `frontend/src/features/calendar/components/EventFormModal.tsx`, `frontend/src/features/calendar/components/SeriesExceptionWarning.tsx`, and `frontend/src/features/calendar/components/CalendarDeleteDialog.tsx` (depends on T042–T044, T049–T050).
- [ ] T053 [US4] Harden backend transaction rollback, safe error codes, range guards, and no-partial-delete guarantees in `backend/src/services/calendar_service.py` and `backend/src/routes/calendar.py` (depends on T038–T039, T048).

**Checkpoint**: Calendar failures are retryable, conflicts are explicit, dirty work is protected, and stale or unauthorized mutations cannot alter shared data.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify the complete feature, apply documentation requirements, and run all project quality gates.

- [ ] T054 [P] Add the required isolated backend quickstart journey covering the steps in `specs/008-calendar-interface/quickstart.md` in `backend/tests/integration/quickstart/test_008_quickstart_flow.py`.
- [ ] T055 [P] Add verified feature documentation covering purpose, user flows, API surface, timezone behavior, recurrence/exception rules, and configuration in `docs/calendar-interface.md` after implementation and tests pass.
- [ ] T056 Run migration upgrade/downgrade verification and the full backend checks from `specs/008-calendar-interface/quickstart.md` against `backend/src/migrations/versions/011_create_calendar.py`, `backend/src`, and `backend/tests`.
- [ ] T057 Run frontend lint, unit tests, strict build, Playwright E2E, and 320px/tablet/desktop checks from `specs/008-calendar-interface/quickstart.md` against `frontend/src` and `frontend/e2e`.
- [ ] T058 Review the completed implementation against `PRODUCT.md`, `DESIGN.md`, `spec.md`, `data-model.md`, `contracts/calendar-api.md`, and `contracts/calendar-ui.md`; remove dead code and record any justified deviations in `docs/calendar-interface.md`.
- [ ] T059 [P] Add `backend/tests/integration/test_calendar_performance.py` for bounded-range performance validation that repeatedly requests one complete six-week calendar grid with representative standalone events, recurring series, and occurrence exceptions; record elapsed samples and p95, and verify at least 95% complete within the two-second success criterion under the documented local test environment.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001–T002 can begin immediately.
- **Foundational (Phase 2)**: Depends on Setup; T003–T012 block all story work.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers the MVP read surface.
- **User Story 2 (Phase 4)**: Depends on Foundational and the US1 calendar data/page shell for integrated navigation/Today behavior; date/header tests can begin after T010.
- **User Story 3 (Phase 5)**: Depends on Foundational and the read surface from US1; mutation backend tests can begin after schemas/models, while UI mutation work depends on the US1 details/page components.
- **User Story 4 (Phase 6)**: Depends on the implemented read and mutation flows from US1–US3 because it hardens their failure paths.
- **Polish (Phase 7)**: Depends on all desired stories; T054–T059 are final validation gates.

### Dependency Graph

```text
T001-T002
   ↓
T003-T012
   ├──> T013-T025 (US1: calendar review MVP)
   │       └──> T026-T032 (US2: navigation + Today)
   └──> T033-T047 (US3: coach mutations; UI also uses US1/US2)
             └──> T048-T053 (US4: recovery + concurrency hardening)
                         └──> T054-T058 (polish, docs, full validation)
```

### User Story Dependencies

- **US1 (P1)**: Starts after T012; no dependency on another story.
- **US2 (P1)**: Core date utility tests can run after T010, but integrated navigation/Today completion depends on US1 page/data components.
- **US3 (P1)**: Backend mutation implementation can proceed after T006–T007; integrated coach UI depends on US1 details and US2 page refresh behavior.
- **US4 (P2)**: Intentionally follows the primary flows so retry/conflict tests exercise the final mutation and modal paths.

### Parallel Opportunities

- **Setup**: T002 can run in parallel with the package/index work after the feature paths are identified.
- **Foundational**: T003, T008, and T010 can proceed in parallel; T004/T005/T006 then align the database and typed schema layers; T009 follows T008 and T006.
- **US1**: T013, T014, T015, and T016 are separate test files/concerns and can be written in parallel before implementation. T020 and T021 can run in parallel after shared types/error mapping.
- **US2**: T026, T027, and T028 are independent test concerns; T029 and T031 can be implemented in parallel after the tests and shared data hook are ready.
- **US3**: T033–T036 are separate schema/service/route/frontend API test concerns. T040/T041 and backend T037/T038 can proceed in parallel once foundational contracts exist; T043 and T044 can proceed after the mutation modal contracts are established.
- **US4**: T048–T050 are independent backend/frontend/accessibility test work; T051 and T053 can proceed in parallel after their respective tests.
- **Polish**: T054, T055, T056, and T059 can proceed in parallel after implementation; T057 and T058 follow the final code state.

## Parallel Example: User Story 1

```text
Task: "Add backend range and recurrence tests in backend/tests/unit/test_calendar_recurrence.py and backend/tests/unit/test_calendar_service.py"
Task: "Add authenticated read-route tests in backend/tests/unit/test_calendar_routes.py"
Task: "Add typed read-client tests in frontend/src/features/calendar/api/calendarApi.test.ts"
Task: "Add grid rendering and accessibility tests in frontend/src/features/calendar/components/CalendarMonthGrid.test.tsx"
```

## Parallel Example: User Story 3

```text
Task: "Add calendar schema validation tests in backend/tests/unit/test_calendar_schemas.py"
Task: "Add calendar service mutation tests in backend/tests/unit/test_calendar_service.py and backend/tests/unit/test_calendar_recurrence.py"
Task: "Add mutation route tests in backend/tests/unit/test_calendar_routes.py"
Task: "Add frontend mutation API tests in frontend/src/features/calendar/api/calendarApi.test.ts"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001–T012 to establish the schema, bounded recurrence/read projection, typed client, and protected route.
2. Complete T013–T025 to deliver the current-month grid, event details, accessible overflow, and read-only behavior for all authenticated roles.
3. Stop at the US1 checkpoint and run its independent tests before beginning mutations.

### Incremental Delivery

1. Deliver US1 calendar review as the read-only MVP.
2. Add US2 month/year navigation and Today briefing without changing the read contract.
3. Add US3 coach creation, recurring series, occurrence exceptions, and deletion with the required E2E journey.
4. Add US4 failure and concurrency hardening.
5. Complete quickstart, documentation, migration verification, full quality gates, and design review.

### Parallel Team Strategy

1. Complete T001–T012 together because migration, types, recurrence, and routing are shared foundations.
2. After T012, assign one developer to US1 read/UI, one to US2 navigation/Today, and one to US3 backend mutations; coordinate shared files `calendar_service.py`, `calendarApi.ts`, and `CalendarPage.tsx` through the listed task order.
3. After primary flows land, assign US4 hardening and final validation/documentation in parallel where the dependency graph permits.

## Notes

- Every task uses the required `- [ ] T###` checklist prefix, includes a story label for story-phase tasks, includes `[P]` only where file/dependency boundaries permit parallel work, and names the exact implementation or test path.
- Backend and frontend test tasks are included because the specification explicitly requires them and the constitution makes unit tests mandatory.
- The required E2E journey is T047; the required backend quickstart test is T054.
- The recommended MVP is US1 only, after the foundational phase.
