# Tasks: Background Jobs and Reliable Processing Foundation

**Input**: Design documents from `/specs/013-background-jobs-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/background-jobs.md`, and `quickstart.md`

**Tests**: Unit tests are mandatory for all new backend logic. The feature
spec explicitly requires PostgreSQL/Redis integration coverage, the Spec 013
quickstart, and one Playwright E2E journey.

**Organization**: Tasks are grouped by the four prioritized user stories.
Shared persistence, registry, dispatcher, and worker prerequisites are in the
Foundational phase so every story uses the same durable processing path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the dependency, configuration, local services, and package
entry points required before implementing the processing foundation.

- [X] T001 Add exact production dependency `arq==0.28.0` with the required dependency rationale in `backend/pyproject.toml` and refresh `backend/uv.lock` using `uv add arq==0.28.0`.
- [X] T002 [P] Add validated Redis, queue, worker, retry, dispatcher, lease, and retention settings with safe defaults to `backend/src/config.py`, `.env.example`, and `.env.test.example`.
- [X] T003 [P] Add the local backend runtime image and Redis/dedicated-worker Compose services in `backend/Dockerfile` and `docker-compose.yml` while preserving the existing PostgreSQL/pgvector service.
- [X] T004 [P] Create background-processing package and command entry points in `backend/src/services/background_jobs/__init__.py`, `backend/src/services/background_jobs/handlers/__init__.py`, `backend/scripts/background_worker.py`, and `backend/scripts/background_jobs.py`.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the shared durable state, typed contracts, registry,
retry policy, dispatcher, and worker runtime. No user-story implementation can
start until this phase is complete.

### Contract, validation, and policy tests first

- [X] T005 [P] Write unit tests for JSON-compatible job envelopes, payload size/type/version validation, forbidden fields, and unknown payload rejection in `backend/tests/unit/test_background_jobs_contracts.py`.
- [X] T006 [P] Write unit tests for duplicate registry registration, unregistered job rejection, handler allowlisting, and definition validation in `backend/tests/unit/test_background_jobs_registry.py`.
- [X] T007 [P] Write unit tests for retry classification, bounded exponential backoff, jitter bounds, attempt exhaustion, and delayed `run_after` validation in `backend/tests/unit/test_background_jobs_retry.py`.
- [X] T008 [P] Write unit tests for failure-category/message sanitization and structured-log redaction in `backend/tests/unit/test_background_jobs_redaction.py`.
- [X] T009 [P] Write migration upgrade/downgrade tests for the durable work table, constraints, partial indexes, payload bounds, and OCC columns in `backend/tests/integration/test_background_job_migration.py`.

### Shared contract and persistence implementation

- [X] T010 Implement typed job envelopes, versioned payload schema adapters, JSON serializer/deserializer, safe status projections, and bounded validation in `backend/src/services/background_jobs/contracts.py` and `backend/src/schemas/background_jobs.py`.
- [X] T011 Implement failure categories, retry policy/backoff with injectable clock/randomness, sanitized error mapping, and safe structured logging in `backend/src/services/background_jobs/retry.py` and `backend/src/services/background_jobs/logging.py`.
- [X] T012 Implement the explicit `BackgroundJobDefinition` registry, registration validation, handler allowlist, retry/idempotency/coalescing metadata, and resource-bound declarations in `backend/src/services/background_jobs/registry.py`.
- [X] T013 Implement `BackgroundWorkItem`, register it in `backend/src/models/__init__.py`, and add Alembic revision 015 with state checks, idempotency/coalescing indexes, eligible/recovery/retention indexes, leases, sanitized failures, and `version_number` in `backend/src/models/background_work_item.py` and `backend/src/migrations/versions/015_background_processing_foundation.py`.
- [X] T014 [P] Write unit tests for transaction-local work staging, idempotency resolution, bounded coalescing, successor creation for running work, OCC conflicts, and rollback behavior in `backend/tests/unit/test_background_jobs_outbox.py`.
- [X] T015 Implement transaction-local staging/coalescing, durable state transitions, lease predicates, manual requeue guards, retention eligibility, and OCC-safe reload behavior in `backend/src/services/background_jobs/outbox.py`.

### Dispatcher and worker runtime

- [X] T016 [P] Write unit tests for bounded dispatcher claiming, deterministic ARQ IDs, successful/failed enqueue transitions, expired leases, and competing dispatcher conflicts in `backend/tests/unit/test_background_jobs_dispatcher.py`.
- [X] T017 [P] Write unit tests for worker startup/shutdown resources, generic handler dispatch, timeout/cancellation behavior, unknown job rejection, terminal transitions, and stale-worker OCC conflicts in `backend/tests/unit/test_background_jobs_worker.py`.
- [X] T018 Implement bounded PostgreSQL claim batches, post-commit Redis enqueue, custom JSON work-ID envelopes, deterministic ARQ `_job_id` assignment, broker failure retry, and safe dispatch reports in `backend/src/services/background_jobs/dispatcher.py`.
- [X] T019 Implement startup-owned database/Redis/provider resources, one generic ARQ worker function, bounded concurrency/timeouts, retry/defer integration, graceful shutdown, lease recovery, and resource cleanup in `backend/src/database.py`, `backend/src/services/background_jobs/runtime.py`, and `backend/scripts/background_worker.py`.

**Checkpoint**: Migration 015 is reversible, contracts reject unsafe work,
the dispatcher never loses a committed row when Redis is unavailable, and a
worker can claim/complete/retry generic registered work without FastAPI.

## Phase 3: User Story 1 - Keep Academy Mutations Immediate and Durable (Priority: P1) 🎯 MVP

**Goal**: Existing academy mutation services commit authoritative data and the
required background intent atomically, without waiting for Redis or embedding
generation and without creating technical audit events.

**Independent Test**: Execute eligible Player, Team, roster, assignment,
Match, performance, statistics, and Calendar mutations with a delayed or failed
provider; verify the domain commit and durable/coalesced work, verify rollback
leaves no executable work, and verify Business/Auth Audit behavior is unchanged.

### Tests for User Story 1 (MANDATORY)

- [X] T020 [P] [US1] Write unit tests for domain-to-RAG impact mapping, stable source references, relationship/deletion hints, no-op authorization changes, and no network/audit calls in `backend/tests/unit/test_background_mutation_impacts.py`.
- [X] T021 [P] [US1] Write integration tests for committed mutation plus outbox, rolled-back mutation with zero work, PostgreSQL-to-Redis dispatch, generic registered-worker execution, provider/Redis unavailability, OCC conflict, and Business/Auth Audit isolation in `backend/tests/integration/test_background_outbox.py`.

### Implementation for User Story 1

- [X] T022 [US1] Implement the shared RAG mutation-impact/dependency staging contract using stable source IDs and bounded old/new references in `backend/src/services/rag/contracts.py` and `backend/src/services/rag/registry.py`.
- [X] T023 [US1] Wire Player create/update/activation and Team create/update/TeamPlayer roster mutation paths to stage eligible impacts before existing commits in `backend/src/services/player_service.py` and `backend/src/services/team_service.py`.
- [X] T024 [US1] Wire TeamCoach semantic assignment, Match create/update/supported delete, and performance/statistics mutation paths to stage impacts without changing existing domain audit rules in `backend/src/services/coach_service.py`, `backend/src/services/match_service.py`, `backend/src/services/performance_service.py`, and `backend/src/services/stats_service.py`.
- [X] T025 [US1] Wire standalone Calendar, recurrence-series, occurrence, and exception create/update/delete paths to stage projected occurrence impacts through the existing Calendar service boundary in `backend/src/services/calendar_service.py` and `backend/src/services/calendar_recurrence.py`.
- [X] T026 [US1] Add regression assertions that Player-account/authentication changes and Data Quality reads/remediation do not enqueue implicit work or technical audit events unless an explicit registered semantic impact exists in `backend/tests/unit/test_player_account_service.py`, `backend/tests/unit/test_data_quality_service.py`, and `backend/tests/integration/test_background_outbox.py`.
- [X] T027 [US1] Complete cross-session mutation-boundary fixtures and assertions proving requests do not wait for provider calls, external calls occur after commit, and normal Business Audit events remain owned by existing services in `backend/tests/integration/conftest.py` and `backend/tests/integration/test_background_outbox.py`.
- [X] T028 [US1] Run the focused User Story 1 unit/integration suite and verify atomic commit, rollback, non-blocking mutation, safe coalescing, and no-audit acceptance criteria in `backend/tests/unit/test_background_mutation_impacts.py` and `backend/tests/integration/test_background_outbox.py`.

**Checkpoint**: User Story 1 is independently demonstrable through existing
authenticated mutation/service paths and leaves durable work for a later
dispatcher/worker run.

## Phase 4: User Story 2 - Reconcile Protected RAG Retrieval to Current Academy Data (Priority: P1)

**Goal**: A registered RAG work item reloads current source truth, reconciles
the declared dependency closure narrowly, remains safe under duplicate delivery,
and preserves protected retrieval and Calendar projection semantics.

**Independent Test**: Mutate a registered source, dispatch and execute its job,
repeat delivery and rapid mutations, then verify current protected retrieval,
duplicate-free RAG state, dependency coverage, deletion handling, and projected
Calendar occurrences.

### Tests for User Story 2 (MANDATORY)

- [ ] T029 [P] [US2] Write unit tests for RAG payload handling, handler delegation to `RagIndexingService`, current-state reload, duplicate replay, unregistered source rejection, and no direct provider/CLI calls in `backend/tests/unit/test_background_rag_reconciliation.py`.
- [ ] T030 [P] [US2] Write integration tests for targeted Player/Team/Match/performance/statistics reconciliation, dependency closure, ineligible/deleted sources, duplicate delivery, coalescing, active-version uniqueness, and protected retrieval in `backend/tests/integration/test_background_rag_reconciliation.py`.

### Implementation for User Story 2

- [ ] T031 [US2] Extend the RAG source registry contracts with target selection, mutation-impact resolution, dependency closure, and bounded deletion/ineligibility handling without introducing a second dependency map in `backend/src/services/rag/contracts.py` and `backend/src/services/rag/registry.py`.
- [ ] T032 [US2] Add a targeted reconciliation operation to `RagIndexingService` that accepts stable source references, reloads current rows, resolves declared dependents, preserves claims/fingerprints/provider bounds, and avoids unrelated full-corpus work in `backend/src/services/rag/indexing.py` and `backend/src/services/rag/loaders.py`.
- [ ] T033 [US2] Implement the registered `rag_reconciliation` handler for targeted and incremental-safety payloads, including retry classification and idempotent current-state delegation, in `backend/src/services/background_jobs/handlers/rag_reconciliation.py` and `backend/src/services/background_jobs/registry.py`.
- [ ] T034 [US2] Implement RAG-specific bounded coalescing for repeated logical source edits so pending work merges targets while running work gets a successor and never drops the final reconciliation in `backend/src/services/background_jobs/handlers/rag_reconciliation.py` and `backend/src/services/background_jobs/outbox.py`.
- [ ] T035 [US2] Preserve Calendar effective-occurrence targeting for recurrence, exception, moved, deleted, timezone, scope, and bounded-horizon changes by routing through existing projection/loaders in `backend/src/services/rag/loaders.py`, `backend/src/services/rag/builders/calendar.py`, and `backend/src/services/calendar_service.py`.
- [ ] T036 [US2] Complete integration assertions for current protected retrieval, no duplicate RAG rows/chunks/active versions, dependency closure, no full-corpus work for one source, and zero Business/Auth Audit pollution in `backend/tests/integration/test_background_rag_reconciliation.py` and `backend/tests/integration/test_rag_authorization.py`.
- [ ] T037 [US2] Add the request-level authenticated mutation-to-retrieval Playwright journey without a jobs UI in `frontend/e2e/background-jobs-foundation-flow.spec.ts`, reusing the existing API-boundary conventions and typed response checks.
- [ ] T038 [US2] Run the focused User Story 2 unit, RAG integration, protected retrieval, and Playwright acceptance checks in `backend/tests/unit/test_background_rag_reconciliation.py`, `backend/tests/integration/test_background_rag_reconciliation.py`, and `frontend/e2e/background-jobs-foundation-flow.spec.ts`.

**Checkpoint**: User Story 2 is independently demonstrable through automatic
RAG freshness and existing protected retrieval; repeated or stale queue
delivery cannot overwrite newer authoritative data.

## Phase 5: User Story 3 - Recover Work After Infrastructure Failure (Priority: P1)

**Goal**: Operators can inspect and safely recover work after Redis/provider/
worker/database failures, including bounded retry exhaustion, abandoned leases,
manual retry, and worker restart.

**Independent Test**: Interrupt dispatch and worker execution, make Redis and
the provider unavailable, restart/recreate the worker, and verify durable
backlog retention, bounded retry/dead status, safe manual recovery, and no
authoritative academy-data edits.

### Tests for User Story 3 (MANDATORY)

- [ ] T039 [P] [US3] Write unit tests for expired leases, retry exhaustion, terminal/dead transitions, manual-retry guards, safe status projections, and recovery OCC conflicts in `backend/tests/unit/test_background_job_recovery.py`.
- [ ] T040 [P] [US3] Write integration tests for Redis outage/recovery, dispatcher competition, worker crash/timeout/restart, provider failure with committed domain data, retry exhaustion, terminal inspection, and manual retry in `backend/tests/integration/test_background_failure_recovery.py`.

### Implementation for User Story 3

- [ ] T041 [US3] Implement expired dispatch/worker lease recovery, bounded retry/dead transitions, terminal retention eligibility, and manual requeue OCC behavior in `backend/src/services/background_jobs/outbox.py`, `backend/src/services/background_jobs/dispatcher.py`, and `backend/src/services/background_jobs/runtime.py`.
- [ ] T042 [US3] Implement bounded operator status, dispatch, recover, retry, and approved RAG-trigger commands with sanitized output and bounded limits in `backend/scripts/background_jobs.py` and `backend/src/schemas/background_jobs.py`.
- [ ] T043 [US3] Complete failure-recovery integration assertions for safe structured logs, no raw provider/Redis/database exception leakage, no Business/Auth Audit pollution, and no duplicate RAG active state in `backend/tests/integration/test_background_failure_recovery.py` and `backend/tests/integration/test_background_rag_reconciliation.py`.
- [ ] T044 [US3] Verify the dedicated worker stops accepting new work, closes resources, and reclaims incomplete work after restart or cancellation in `backend/src/services/background_jobs/runtime.py` and `backend/tests/integration/test_background_failure_recovery.py`.
- [ ] T045 [US3] Run the focused User Story 3 recovery suite and confirm Redis downtime degrades freshness only, terminal work remains inspectable, and approved manual retry reaches eventual success in `backend/tests/unit/test_background_job_recovery.py` and `backend/tests/integration/test_background_failure_recovery.py`.

**Checkpoint**: User Story 3 is independently demonstrable through operator
commands and restart/outage scenarios without direct database edits.

## Phase 6: User Story 4 - Add Future Background Work Without a New Queue Architecture (Priority: P2)

**Goal**: A future registered job can use the same typed payload, dispatcher,
worker, retry, scheduling, logging, and recovery infrastructure, while unknown
jobs/versions remain safely rejected.

**Independent Test**: Register a synthetic bounded job in tests, execute it
through the same worker, schedule it with `run_after`, and verify an
unregistered type or unsupported version never runs.

### Tests for User Story 4 (MANDATORY)

- [ ] T046 [P] [US4] Write unit tests for synthetic job registration, typed payload validation, delayed eligibility, declared retry/idempotency semantics, resource bounds, and unknown type/version rejection in `backend/tests/unit/test_background_jobs_extensibility.py`.
- [ ] T047 [P] [US4] Write integration tests proving a synthetic job uses the existing PostgreSQL/Redis/ARQ path without dispatcher or worker changes and that delayed work becomes eligible in `backend/tests/integration/test_background_job_extensibility.py`.

### Implementation for User Story 4

- [ ] T048 [US4] Complete the generic registry extension contract and validated future `run_after`/manual-trigger path without adding a scheduler or new queue system in `backend/src/services/background_jobs/registry.py`, `backend/src/services/background_jobs/outbox.py`, and `backend/scripts/background_jobs.py`.
- [ ] T049 [US4] Add the approved incremental/repair RAG safety trigger as a registered extension point that reuses existing `RagIndexingService` behavior in `backend/src/services/background_jobs/handlers/rag_reconciliation.py` and `backend/scripts/background_jobs.py`.
- [ ] T050 [US4] Run the focused User Story 4 extensibility suite and verify future-job onboarding requires only a versioned payload, handler, policy declaration, registration, and tests in `backend/tests/unit/test_background_jobs_extensibility.py` and `backend/tests/integration/test_background_job_extensibility.py`.

**Checkpoint**: User Story 4 is independently demonstrable with a synthetic
job and does not require a new queue, worker runtime, persistence model, or
recovery mechanism.

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete feature, document actual behavior, and run
all constitution and security gates after the stories are complete.

- [ ] T051 Run the complete isolated 20-step quickstart and implement any missing assertions in `backend/tests/integration/quickstart/test_013_quickstart_flow.py` according to `specs/013-background-jobs-foundation/quickstart.md`.
- [ ] T052 Write verified implementation documentation covering architecture, dependency rationale, outbox semantics, retries, dead work, Redis outage behavior, RAG synchronization, configuration, local Docker workflow, commands, and future job extension in `docs/background-jobs.md`.
- [ ] T053 Update the local development workflow references for PostgreSQL, Redis, FastAPI, and the worker in `README.md` without changing the existing RAG CLI recovery documentation.
- [ ] T054 Run Ruff, mypy, mandatory unit tests, migration/integration tests, the quickstart, and the Spec 013 Playwright journey across `backend/src`, `backend/tests`, and `frontend/e2e/background-jobs-foundation-flow.spec.ts`.
- [ ] T055 Perform the final security, privacy, audit-isolation, dead-code, and redundancy review across `backend/src/services/background_jobs`, `backend/src/models/background_work_item.py`, `backend/src/services/rag`, `backend/scripts/background_jobs.py`, and `backend/scripts/background_worker.py`; remove any introduced unused or duplicate implementation.
- [ ] T056 Verify migration-before-runtime deployment order, Docker Compose startup/shutdown, safe status/log output, no unresolved task/spec markers, and `git diff --check` for the completed feature in `backend/src/migrations/versions/015_background_processing_foundation.py`, `docker-compose.yml`, `docs/background-jobs.md`, and `specs/013-background-jobs-foundation/`.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001–T004 can be started in parallel
  where their files do not overlap.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
  Contract/migration tests should be written before their implementations.
- **User Story 1 (Phase 3)**: Depends on Foundational and establishes the
  mutation-to-outbox path used by automatic RAG synchronization.
- **User Story 2 (Phase 4)**: Depends on Foundational and the US1 mutation
  impact path for end-to-end automatic triggers; its handler can be unit-tested
  independently against a staged work item.
- **User Story 3 (Phase 5)**: Depends on Foundational; the RAG provider-failure
  and duplicate-state scenarios also depend on US2's registered handler.
- **User Story 4 (Phase 6)**: Depends on Foundational; the RAG safety trigger
  portion depends on US2, while the synthetic-job portion is independently
  testable after Phase 2.
- **Polish (Phase 7)**: Depends on all desired stories and their checkpoints.

### User Story Dependencies

- **US1 (P1)**: Foundational only; MVP starting point.
- **US2 (P1)**: Foundational plus US1's durable mutation impact staging for the
  real automatic path.
- **US3 (P1)**: Foundational plus US2 for full provider-failure/RAG recovery;
  generic Redis/worker recovery can proceed after Phase 2.
- **US4 (P2)**: Foundational for synthetic jobs; US2 only for the RAG safety
  trigger extension.

### Parallel Opportunities

- Setup tasks T002, T003, and T004 can run in parallel with T001 once the
  dependency/configuration contract is agreed.
- Foundational tests T005–T009 can be authored in parallel; T014, T016, and
  T017 can be authored in parallel after the shared contracts are understood.
- US1 test tasks T020/T021 can run in parallel; after T022, Player/Team wiring
  T023 and Coach/Match/performance wiring T024 can proceed in parallel, with
  Calendar wiring T025 separate.
- US2 unit/integration tests T029/T030 can run in parallel; Calendar-focused
  work T035 can proceed alongside handler implementation T033 after T031.
- US3 unit and integration tests T039/T040 can run in parallel; CLI work T042
  is separate from runtime hardening T041/T044.
- US4 unit/integration tests T046/T047 can run in parallel; T048 and T049 touch
  different extension surfaces after the generic registry is complete.
- Final documentation T052/T053 can proceed in parallel with final code audit
  T055 after the acceptance artifacts are stable.

## Parallel Execution Examples

### User Story 1

```text
Parallel A: T020 unit impact tests
Parallel B: T021 transaction/outbox integration tests
After T022: T023 Player/Team wiring and T024 Coach/Match/performance wiring
can proceed in separate worktrees; T025 covers Calendar paths independently.
```

### User Story 2

```text
Parallel A: T029 handler/target unit tests
Parallel B: T030 RAG integration tests
After T031: T032 indexing-service targeting and T033 handler registration can
be split by file ownership; T035 covers Calendar projection cases.
```

### User Story 3

```text
Parallel A: T039 terminal/recovery unit tests
Parallel B: T040 Redis/worker/provider failure integration tests
After the tests establish behavior: T041 runtime recovery and T042 operator
commands can proceed in separate files.
```

### User Story 4

```text
Parallel A: T046 synthetic registry unit tests
Parallel B: T047 delayed-job integration tests
After the generic registry is complete: T048 scheduling/manual-trigger work
and T049 RAG safety-trigger work can proceed independently.
```

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases, including migration 015, JSON
   contracts, registry, dispatcher, and worker runtime.
2. Complete US1 to make valid academy mutations durable and non-blocking.
3. Validate US1 independently at the existing service/API boundary.
4. Complete US2 immediately after US1 because automatic RAG reconciliation is
   the first production workload and is required for the feature's production
   value.

The smallest technical MVP is US1. The smallest production-meaningful MVP is
US1 plus US2; US3 and US4 harden operations and prove extensibility.

### Incremental Delivery

1. Setup + Foundational: durable generic processing foundation.
2. US1: atomic mutation intent and non-blocking request path.
3. US2: automatic targeted RAG freshness and protected retrieval.
4. US3: outage, restart, terminal failure, inspection, and recovery behavior.
5. US4: synthetic future jobs, delayed work, and safety reconciliation hook.
6. Polish: quickstart, Playwright, documentation, security review, and quality
   gates.

Each checkpoint must pass its story's independent test before the next story
widens the implementation surface.

## Notes

- Every task uses the required `- [ ] T###` checklist form.
- `[P]` is used only where tasks touch separate files and have no incomplete
  prerequisite dependency.
- Story tasks carry `[US1]` through `[US4]`; setup, foundational, and polish
  tasks intentionally have no story label.
- No task adds a dashboard, user-created scheduler, chatbot, second queue, or
  duplicate RAG/domain mutation implementation.
