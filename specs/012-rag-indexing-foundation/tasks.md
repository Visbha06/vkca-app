# Tasks: Authorization-Aware RAG Indexing Foundation

**Input**: Design documents from
specs/012-rag-indexing-foundation/

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/,
quickstart.md

**Tests**: Unit tests are mandatory by the project constitution. Integration
tests are included because the specification explicitly requires PostgreSQL,
pgvector, migration, authorization, synchronization, and quickstart
verification. One authenticated request-level Playwright test is included for
the feature.

**Organization**: Tasks are grouped by user story. Shared contracts and
blocking infrastructure are in Setup/Foundational phases; source-specific
behavior is in the story that owns it.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize dependencies, settings, package boundaries, and test
scaffolding without implementing story behavior.

- [X] T001 Add google-genai 1.45.0 with its dependency rationale using `uv add google-genai==1.45.0` in backend/pyproject.toml, and lock that exact resolved package in backend/uv.lock.
- [X] T002 Add RAG provider, model, dimension, timeout, batch, chunking, query, and result-bound settings in backend/src/config.py with safe placeholders in .env.example and .env.test.example.
- [X] T003 [P] Create the RAG package and schema module boundaries in backend/src/services/rag/__init__.py and backend/src/schemas/rag.py without initializing provider clients at import time.
- [X] T004 [P] Add isolated RAG unit/integration fixture helpers and fake-provider configuration seams in backend/tests/conftest.py and backend/tests/integration/conftest.py.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the reusable typed, persistence, embedding, and loading
boundaries required by every user story.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is
complete.

- [X] T005 Define the typed RAG contracts for canonical documents, scope metadata, chunk candidates, source definitions, embedding profiles/results, run reports, and status values in backend/src/services/rag/contracts.py.
- [X] T006 Implement deterministic Unicode/whitespace normalization, stable date/time/decimal/list formatting, source/document/chunk ID derivation, and content hashing in backend/src/services/rag/canonical.py.
- [X] T007 Implement the versioned bounded chunking policy with semantic boundaries, minimal continuation context, stable ordinals, stable IDs, and chunk hashes in backend/src/services/rag/chunking.py.
- [X] T008 Implement the source registry protocol, registration validation, dependency declarations, eligibility hooks, and deletion-policy interfaces in backend/src/services/rag/registry.py.
- [X] T009 Create the RagIndexRun, RagSourceState, RagDocument, and RagChunk SQLAlchemy models with safe JSON/array facets, version columns, status constraints, uniqueness, and referential relationships in backend/src/models/rag_index_run.py, backend/src/models/rag_source_state.py, backend/src/models/rag_document.py, and backend/src/models/rag_chunk.py.
- [X] T010 Register the RAG models with the existing SQLAlchemy model import and migration metadata conventions in backend/src/models/__init__.py and backend/src/database.py.
- [X] T011 Create Alembic revision 014_rag_indexing_foundation.py under backend/src/migrations/versions/ to enable the vector extension, create all RAG tables and constraints, add GIN/B-tree indexes, add the vector(1536) cosine HNSW index, and provide safe downgrade behavior.
- [X] T012 [P] Add migration upgrade/downgrade integration coverage for revision 014, including extension setup and restoration to revision 013, in backend/tests/integration/test_rag_migration.py.
- [X] T013 Define the centralized EmbeddingProvider protocol, fake deterministic provider, provider error categories, batching contract, and sanitized validation errors in backend/src/services/rag/embedding.py.
- [X] T014 Implement the Gemini adapter using google-genai for gemini-embedding-001 with RETRIEVAL_DOCUMENT and RETRIEVAL_QUERY task types, bounded async batches, timeouts, sanitized failures, 1536-dimensional output, and manual normalization for the selected reduced dimension in backend/src/services/rag/gemini_provider.py.
- [X] T015 Implement provider selection, model/dimension compatibility validation, fake-provider selection for tests, and explicit provider/model transition checks in backend/src/services/rag/embedding.py and backend/src/config.py.
- [X] T016 Implement bounded set-based loader interfaces, cursor/batch limits, source fingerprint hooks, and declared relationship-dependency loading seams in backend/src/services/rag/loaders.py.
- [X] T017 Implement RAG-specific run/source claim, optimistic version, lease, status, and sanitized technical telemetry helpers without extending DataSyncLog or emitting Business Audit/authentication audit events in backend/src/services/rag/indexing.py.
- [X] T018 [P] Add unit coverage for canonical normalization, deterministic IDs/hashes, chunking boundaries, source registry validation, and exclusion of LLM/provider/persistence knowledge from builders in backend/tests/unit/test_rag_documents.py, backend/tests/unit/test_rag_chunking.py, and backend/tests/unit/test_rag_registry.py.
- [X] T019 [P] Add provider unit coverage for Gemini-compatible model reporting, batching, timeouts, malformed counts, wrong dimensions, non-finite vectors, partial failures, replacement-provider compatibility, and secret redaction in backend/tests/unit/test_rag_embedding.py.
- [X] T020 Add PostgreSQL/pgvector persistence integration coverage for vector insertion, dimensionality, cosine similarity syntax, relational/GIN scope indexes, duplicate constraints, and non-exposure of raw vectors in backend/tests/integration/test_rag_pgvector.py.

## Phase 3: User Story 1 - Build a trustworthy academy knowledge index (Priority: P1) 🎯 MVP

**Goal**: Build a deterministic, safe, provenance-preserving corpus from every
explicitly registered academy source using the shared pipeline and initial
Gemini-compatible provider contract.

**Independent Test**: Seed one representative record for each of the nine
registered source types, run a full build with the deterministic fake provider,
verify counts/status/documents/chunks/embeddings/provenance, rerun it to prove
idempotency, and confirm no audit or security records are created.

**Tests must be added first and should fail before implementation.**

### Tests for User Story 1

- [X] T021 [P] [US1] Add builder contract tests for player_profile, team, match, all three performance families, and both statistics families covering allowlists, deterministic text/hashes, provenance, scope facets, invalid-source eligibility, and sensitive-field exclusion in backend/tests/unit/test_rag_builders.py.
- [X] T022 [P] [US1] Add projected Calendar occurrence tests covering recurrence, moved/deleted exceptions, timezone conversion, age-group/all-academy scope, stable occurrence IDs, use of the existing `MAX_CALENDAR_RANGE_DATES` 45-day Calendar bound without a RAG-specific setting, and absence of raw event-definition documents in backend/tests/unit/test_rag_calendar_builder.py.
- [X] T023 [P] [US1] Add full-build integration tests covering representative source counts, canonical/chunk/embedding persistence, aggregate run counters, stable rerun IDs/hashes, zero duplicate rows, and zero new fake-provider calls for unchanged chunks in backend/tests/integration/test_rag_indexing.py.
- [X] T024 [P] [US1] Add privacy and audit-isolation tests proving password hashes, tokens, sessions, CSRF values, arbitrary JSON, emails, dates of birth, credentials, audit payloads, full bodies, and vectors are absent from provider inputs/logs/status and that indexing emits no Business Audit or security-audit event in backend/tests/unit/test_rag_privacy.py and backend/tests/integration/test_rag_indexing.py.

### Implementation for User Story 1

- [X] T025 [P] [US1] Implement the player_profile and team builders with safe profile fields, bounded roster/coaching context, deterministic labels/order, source versions, provenance, and intrinsic Player/Team/age-group scope in backend/src/services/rag/builders/player.py and backend/src/services/rag/builders/team.py.
- [X] T026 [P] [US1] Implement the match builder with explicit internal/external participant semantics, academy Team relationships, date/format/home-away/venue/result fields, and no opponent-string identity inference in backend/src/services/rag/builders/match.py.
- [X] T027 [P] [US1] Implement the batting, bowling, and fielding performance builders with linked Player/Match context, recorded numeric figures, relationship fingerprints, and no unapproved free-text notes in backend/src/services/rag/builders/performance.py.
- [X] T028 [P] [US1] Implement the player batting-statistics and player bowling-statistics builders with explicit aggregate numeric allowlists, format context, Player provenance, and current relationship facets in backend/src/services/rag/builders/statistics.py.
- [X] T029 [US1] Implement the calendar_occurrence builder and projected-occurrence adapter using CalendarService.get_range() and the existing `MAX_CALENDAR_RANGE_DATES` 45-day Calendar horizon, with existing recurrence/exception/timezone/scope semantics, stable occurrence_id keys, and no independent recurrence logic or RAG-specific horizon setting in backend/src/services/rag/builders/calendar.py.
- [X] T030 [US1] Implement set-based loaders and eligibility/dependency loading for all nine initial sources, including active Player filtering, TeamPlayer/TeamCoach context, explicit Match participants, performance/statistics joins, Data Quality checks, and the Calendar service's existing `MAX_CALENDAR_RANGE_DATES` 45-day effective-occurrence horizon in backend/src/services/rag/loaders.py.
- [X] T031 [US1] Register the nine initial source definitions with builders, versions, loaders, dependency fingerprints, scope strategies, eligibility policies, and deletion handling in backend/src/services/rag/registry.py.
- [X] T032 [US1] Implement full-corpus source traversal and targeted registered-source traversal over committed authoritative records in backend/src/services/rag/indexing.py.
- [X] T033 [US1] Implement deterministic candidate preparation, chunk generation, batch embedding, finite/dimension/order validation, atomic active-version activation, safe chunk replacement, and aggregate counters for full builds in backend/src/services/rag/indexing.py.
- [X] T034 [US1] Implement the full and targeted command modes with bounded aggregate output, sanitized errors, explicit source-type validation, and no academy-data mutation in backend/scripts/rag_index.py.

**Checkpoint**: User Story 1 is independently demonstrable as a deterministic,
idempotent, privacy-safe full index build.

## Phase 4: User Story 2 - Synchronize only changed academy knowledge (Priority: P1)

**Goal**: Reconcile only changed, deleted, ineligible, or incompatible source
state while preserving usable derived content through provider failures and
keeping normal academy mutations independent from embedding calls.

**Independent Test**: Build the seeded corpus, mutate one Player/Match and one
Calendar exception, change a relationship, delete or inactivate a source,
exercise a builder/model change, and simulate provider failures; verify only
affected derived state changes and the prior eligible index remains usable.

**Tests must be added first and should fail before implementation.**

### Tests for User Story 2

- [X] T035 [P] [US2] Add incremental synchronization unit tests for source versions, dependency hashes, scope-only changes, chunk reuse, changed chunk replacement, builder-version targeting, model compatibility, and unchanged-source skipping in backend/tests/unit/test_rag_indexing_sync.py.
- [X] T036 [P] [US2] Add provider-failure integration tests for timeout, malformed response, wrong dimension, partial batch failure, preserved prior active chunks, sanitized source/run failure state, and committed domain mutation in backend/tests/integration/test_rag_mutation_boundary.py.
- [X] T037 [P] [US2] Add Calendar reconciliation integration tests for moved, replaced, deleted, out-of-horizon, timezone, and scope-changed projected occurrences in backend/tests/integration/test_rag_calendar_sync.py.
- [X] T038 [P] [US2] Add synchronization query-count and dependency regression tests proving set-based loading, no N+1 preparation, unrelated source-type stability, and bounded batch behavior in backend/tests/integration/test_rag_indexing_performance.py.

### Implementation for User Story 2

- [X] T039 [US2] Implement source version, dependency fingerprint, canonical hash, scope fingerprint, eligibility, and model/chunking compatibility comparison in backend/src/services/rag/indexing.py and backend/src/services/rag/loaders.py.
- [X] T040 [US2] Implement incremental mode to skip compatible unchanged sources, regenerate changed documents, re-embed only changed chunks, and preserve stable identities where content remains stable in backend/src/services/rag/indexing.py.
- [X] T041 [US2] Implement chunk-level reconciliation that reuses compatible unchanged embeddings, replaces changed/obsolete child chunks atomically, and prevents duplicate derived records in backend/src/services/rag/indexing.py.
- [X] T042 [US2] Implement deletion and ineligibility reconciliation for missing records, inactive Players, invalid relationships, deleted Teams/Matches, and no-longer-indexable Calendar occurrences so old chunks become non-searchable or are removed in backend/src/services/rag/indexing.py.
- [X] T043 [US2] Implement targeted builder-version and provider/model transition handling that identifies affected source types, refuses incompatible vector mixing, and requires the documented targeted/full rebuild path in backend/src/services/rag/indexing.py and backend/src/services/rag/embedding.py.
- [X] T044 [US2] Implement source claim leases, version checks, stale-claim recovery, pre-activation fingerprint rechecks, and optimistic concurrency conflict handling for overlapping or interrupted runs in backend/src/services/rag/indexing.py.
- [X] T045 [US2] Enforce the provider transaction boundary by keeping embedding calls and derived-state writes outside normal Player, Team, Match, performance, statistics, Calendar, User, assignment, and membership mutation transactions in backend/src/services/rag/indexing.py and the affected domain service integration points.
- [X] T046 [US2] Implement recoverable repair/restart behavior that reconciles from committed source truth, retains the last usable eligible index on failed refresh, and invalidates ineligible content even when embedding is unavailable in backend/src/services/rag/indexing.py.
- [X] T047 [US2] Add incremental, targeted, and repair command modes with source filtering, compatibility checks, aggregate counters, documented exit statuses, and sanitized recovery output in backend/scripts/rag_index.py.

**Checkpoint**: User Story 2 is independently demonstrable through repeated
incremental, deletion, compatibility, and failure-recovery runs.

## Phase 5: User Story 3 - Retrieve only knowledge the current user may see (Priority: P1)

**Goal**: Resolve current authorization from the authenticated database User
and constrain pgvector candidates before release for Head Coach, Assistant
Coach, linked Player, and unlinked Player states.

**Independent Test**: Seed overlapping Teams, active/inactive Players,
performance/statistics/Match/Calendar context, and all required account states;
retrieve with the same query as each role; change assignments, memberships,
links, roles, and active state without re-embedding; verify zero unauthorized
results.

**Tests must be added first and should fail before implementation.**

### Tests for User Story 3

- [X] T048 [P] [US3] Add RagAccessScope unit tests for Head Coach academy scope, Assistant Coach TeamCoach assignments, every active Player in assigned Teams, linked Player TeamPlayer memberships, unlinked Player denial, inactive account denial, and current age-group/all-academy facets in backend/tests/unit/test_rag_scope.py.
- [X] T049 [P] [US3] Add retrieval-service unit tests for bounded query input, provider query embedding, deterministic tie-breaking, maximum result limits, empty authorized candidates, safe provenance, and rejection of client-selected scope in backend/tests/unit/test_rag_retrieval.py.
- [X] T050 [P] [US3] Add role/source visibility integration tests for Head Coach, relevant and irrelevant Assistant Coaches, all active assigned-Team Players, inactive Player exclusion, linked Player, and unlinked Player in backend/tests/integration/test_rag_authorization.py.
- [X] T051 [P] [US3] Add pgvector integration tests proving source/membership/role/age-group predicates are included in the candidate query before cosine ordering and that raw vectors are not returned in backend/tests/integration/test_rag_pgvector.py.
- [X] T052 [P] [US3] Add unit tests for the authenticated retrieval route handler with mocked authentication and retrieval-service dependencies, plus route contract tests for 401, bounded 200 responses, empty unlinked results, 422 validation, sanitized 503 errors, ignored/rejected client scope fields, and absence of LLM answers in backend/tests/unit/test_rag_route.py and backend/tests/integration/test_rag_retrieval_api.py.

### Implementation for User Story 3

- [X] T053 [US3] Extract or reuse the existing dashboard role-scope relationship logic to implement request-time RagAccessScope resolution from User, Player, TeamCoach, TeamPlayer, and Player.is_active state in backend/src/services/rag/scope.py.
- [X] T054 [US3] Implement source-specific SQLAlchemy authorization predicates for the complete visibility matrix, including every active Player in assigned Assistant Coach Teams, related permitted Match/performance/statistics/Team context, Calendar all-academy/assigned-age-group context, linked Player self scope, and unlinked denial in backend/src/services/rag/retrieval.py.
- [X] T055 [US3] Implement the bounded retrieval service with server-side query embedding through EmbeddingProvider, one authorization-constrained pgvector candidate query, cosine ordering, deterministic tie-breaking, safe provenance, and no vector/provider-error leakage in backend/src/services/rag/retrieval.py.
- [X] T056 [US3] Define Pydantic request/response schemas for bounded retrieval parameters, safe result metadata, provenance, scores, and sanitized error payloads in backend/src/schemas/rag.py.
- [X] T057 [US3] Implement the authenticated GET /api/v1/rag/retrieval route with existing bearer/session authentication, server-derived scope, bounded query/limit validation, no client authorization parameters, and no answer generation in backend/src/routes/rag.py.
- [X] T058 [US3] Wire the protected RAG route and service dependencies into the FastAPI application without exposing a generic vector-search route in backend/src/main.py.
- [X] T059 [US3] Add relationship-change integration coverage proving TeamCoach assignment, TeamPlayer membership, Player/User link, User role, Player.is_active, and account activation changes affect the next retrieval request without re-embedding in backend/tests/integration/test_rag_authorization.py.
- [X] T060 [US3] Add retrieval redaction and audit-isolation assertions proving forbidden chunks never reach the service response and retrieval creates neither Business Audit nor authentication/security audit events in backend/tests/integration/test_rag_retrieval_api.py.

**Checkpoint**: User Story 3 is independently demonstrable through the
protected service and optional HTTP boundary with database-side authorization.

## Phase 6: User Story 4 - Add a future registered source safely (Priority: P2)

**Goal**: Prove that a synthetic opt-in source can use the shared builder,
chunking, embedding, persistence, synchronization, and retrieval boundaries
without core redesign, while unregistered models remain excluded.

**Independent Test**: Register a synthetic source with safe fields, loader,
version, eligibility, scope, dependency, and deletion behavior; run full,
incremental, deletion, and protected retrieval flows; verify an unregistered
synthetic model produces no derived records.

**Tests must be added first and should fail before implementation.**

- [X] T061 [P] [US4] Add source-registry contract tests for a valid synthetic registration, required extension metadata, targeted selection, dependency declaration, eligibility, and deletion callbacks in backend/tests/unit/test_rag_registry.py.
- [X] T062 [P] [US4] Add exclusion tests proving an SQLAlchemy model without a registry entry creates no documents, chunks, embeddings, or retrieval candidates in backend/tests/unit/test_rag_registry_exclusion.py.
- [X] T063 [P] [US4] Add boundary tests rejecting synthetic builders that access provider SDKs, write vector persistence directly, store User-ID ACLs, serialize unapproved fields, or bypass shared authorization in backend/tests/unit/test_rag_extension_boundaries.py.

### Implementation for User Story 4

- [X] T064 [US4] Add a synthetic registered source fixture with an allowlisted builder, deterministic source version, provenance, scope metadata, eligibility, dependency fingerprint, and deletion policy in backend/tests/fixtures/rag_synthetic.py.
- [X] T065 [US4] Generalize registry dispatch and source loading/building/reconciliation so new registered adapters flow through the existing canonical, chunk, provider, persistence, and authorization contracts without source-type conditionals in backend/src/services/rag/registry.py, backend/src/services/rag/indexing.py, and backend/src/services/rag/retrieval.py.
- [X] T066 [US4] Add synthetic-source integration coverage for full build, incremental change, deletion, targeted mode, fake embedding, persistence, and protected retrieval without changing core pipeline code in backend/tests/integration/test_rag_extensibility.py.
- [X] T067 [US4] Add a registry extension regression test proving builder-version changes target only the synthetic source type and leave unrelated initial source states and embeddings untouched in backend/tests/integration/test_rag_extensibility.py.

**Checkpoint**: User Story 4 is independently demonstrable by adding one
registered fixture and observing unchanged core pipeline behavior.

## Phase 7: User Story 5 - Inspect index health without exposing indexed content (Priority: P2)

**Goal**: Provide bounded operational run/source status, sanitized failure
information, and recoverable repair visibility without exposing semantic bodies,
vectors, provider requests, or secrets.

**Independent Test**: Create completed, skipped, partial, failed,
model-incompatible, deleted, and interrupted states; inspect CLI/service status;
verify counts, state transitions, sanitized errors, prior chunk retention, and
redacted output.

**Tests must be added first and should fail before implementation.**

- [X] T068 [P] [US5] Add status/report unit tests for run counters, source states, timestamps, compatibility failures, stale/failed/ineligible/deleted states, bounded messages, and omission of bodies/chunks/vectors/secrets in backend/tests/unit/test_rag_status.py.
- [X] T069 [P] [US5] Add operational status integration tests for successful, skipped, partial-failure, interrupted, repair, model-mismatch, and deletion scenarios in backend/tests/integration/test_rag_status.py.

### Implementation for User Story 5

- [X] T070 [US5] Implement status queries and bounded run/source summaries over RagIndexRun and RagSourceState without selecting semantic bodies or vectors in backend/src/services/rag/indexing.py.
- [X] T071 [US5] Implement the --status command, sanitized failure categories, aggregate counters, source filters, documented exit statuses, and repair guidance in backend/scripts/rag_index.py.
- [X] T072 [US5] Implement redacted provider/application logging and error mapping that excludes request bodies, vectors, credentials, raw provider errors, sensitive source values, and audit payloads in backend/src/services/rag/embedding.py, backend/src/services/rag/indexing.py, and backend/src/routes/rag.py.
- [X] T073 [US5] Implement status-aware stale, failed, indexing, current, ineligible, and deleted transitions plus interrupted-run recovery inspection in backend/src/services/rag/indexing.py.
- [X] T074 [US5] Add status response and command-output regression coverage proving no canonical text, full chunks, vectors, secrets, or unapproved fields appear in backend/tests/unit/test_rag_privacy.py and backend/tests/integration/test_rag_status.py.

**Checkpoint**: User Story 5 is independently demonstrable through safe status
inspection and repair of recoverable derived-state failures.

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify the full feature workflow, document implemented behavior,
and run project quality gates.

- [ ] T075 Run the complete isolated feature quickstart test covering database startup, migration, representative seed data, projected Calendar occurrences, full build, idempotent rerun, mutation, incremental sync, deletion, provider failure, all role retrievals, client-scope rejection, audit isolation, and status repair in backend/tests/integration/quickstart/test_012_quickstart_flow.py.
- [ ] T076 Add the required authenticated request-level Playwright test for the protected retrieval boundary, including bounded result assertions and forbidden-result absence, in frontend/e2e/rag-indexing-foundation-flow.spec.ts.
- [ ] T077 Perform a final security/data-exclusion review across builders, provider payload construction, logs, status responses, and retrieval responses; apply and record any required fixes in backend/src/services/rag/, backend/src/routes/rag.py, and backend/tests/ before final verification.
- [ ] T078 Add representative seeded-dataset regression measurements for source loading, embedding batches, retrieval bounds, authorization-filtered vector queries, and absence of N+1 preparation in backend/tests/integration/test_rag_indexing_performance.py.
- [ ] T079 Run backend formatting, linting, type checking, unit tests, migration/pgvector integration tests, authorization tests, synchronization tests, and the feature-012 quickstart with uv in backend/pyproject.toml and backend/tests/.
- [ ] T080 Run the request-level frontend E2E command and verify the Playwright test uses the existing runner without introducing a chat UI or frontend RAG surface in frontend/playwright.config.ts and frontend/e2e/rag-indexing-foundation-flow.spec.ts.
- [ ] T081 Execute the complete acceptance checklist after T079 and T080 pass against spec.md, plan.md, data-model.md, contracts/, and quickstart.md; confirm every FR-001 through FR-060, SC-001 through SC-013, and explicit exclusion is covered by an implemented task/test in specs/012-rag-indexing-foundation/.
- [ ] T082 After successful T081 acceptance, write implemented-behavior documentation covering architecture, nine registered sources, canonical contract, source-builder extension process, projected Calendar indexing, chunking, Gemini configuration, pgvector persistence, authorization matrix, commands, recovery, exclusions, and local verification in docs/rag-indexing-foundation.md.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; dependency/configuration and test
  scaffolding can begin immediately.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
  The provider, registry, canonical, chunking, persistence, migration, and
  shared loader contracts must exist before story-specific behavior.
- **User Story 1 (Phase 3)**: Depends on Foundational. It is the MVP because
  it establishes the registered source corpus and full-build path.
- **User Story 2 (Phase 4)**: Depends on User Story 1's full-build activation
  path, then adds incremental/recovery behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational persistence/provider
  contracts and a populated corpus from User Story 1 for end-to-end tests.
- **User Story 4 (Phase 6)**: Depends on Foundational registry contracts and
  the generic pipeline; its end-to-end retrieval test also uses User Story 3's
  protected retrieval boundary.
- **User Story 5 (Phase 7)**: Depends on the run/source state transitions from
  User Story 2 and the command/status boundaries used by all indexing modes.
- **Polish (Phase 8)**: Depends on all desired stories being complete.

### User Story Dependencies

- **US1 (P1)**: Foundational only; no other story is required for its MVP test.
- **US2 (P1)**: Foundational + US1 full-build persistence/activation.
- **US3 (P1)**: Foundational + US1 populated source/chunk data; the scope and
  retrieval service can be implemented in parallel with US2 after US1.
- **US4 (P2)**: Foundational registry/pipeline contracts; protected retrieval
  integration depends on US3.
- **US5 (P2)**: Foundational status models + US2 recovery states and commands.

### Parallel Opportunities

- Setup tasks T001-T004 can run in parallel because they touch independent
  dependency, configuration, package, and fixture surfaces.
- Foundational work can parallelize contracts/canonical/chunking (T005-T007),
  persistence/migration (T009-T012), provider implementation/tests
  (T013-T019), and loader interfaces (T016), subject to contract handoff.
- US1 builder tests T021-T024 can run in parallel; builder implementations
  T025-T029 can run in parallel once canonical contracts are stable.
- US2 tests T035-T038 can run in parallel; fingerprint/reconciliation,
  transaction-boundary, and recovery work can be split across T039-T047 after
  the indexing service is available.
- US3 tests T048-T052 can run in parallel; scope, SQL predicates, retrieval
  service, schemas, and route wiring T053-T058 can be split after persistence
  and provider contracts are complete.
- US4 contract tests T061-T063 can run in parallel; synthetic fixture and
  generic registry work T064-T067 can then proceed independently from US2.
- US5 tests T068-T069 can run in parallel; status query, CLI, redaction, and
  transition work T070-T074 can be split by file boundary.
- After story completion, T075, T076, and T078 can proceed by independent
  validation surface. T077 security fixes must complete before the final T079
  backend gates and T080 E2E gate; T081 is the final acceptance gate, followed
  by T082 documentation of the verified implementation.

### Parallel Example: User Story 1

    T021 builder contract tests
    T022 projected Calendar occurrence tests
    T023 full-build integration tests
    T024 privacy/audit-isolation tests

After the tests are in place, implementation can split into:

    T025 player/team builders
    T026 match builder
    T027 performance builders
    T028 statistics builders
    T029 Calendar builder

### Parallel Example: User Story 3

    T048 RagAccessScope tests
    T049 retrieval service tests
    T050 role/source authorization integration tests
    T051 pgvector predicate tests
    T052 route-handler unit and HTTP contract tests

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
2. Complete User Story 1, including all nine builders/source registrations,
   deterministic chunking, fake/Gemini-compatible provider boundaries,
   PostgreSQL persistence, full/targeted commands, and idempotency tests.
3. Run T023, T024, and T075's full-build subset and stop for independent MVP
   validation before adding synchronization or retrieval.

### Incremental Delivery

1. Add User Story 2 for incremental, deletion, compatibility, and provider
   failure recovery.
2. Add User Story 3 for current-user SQL authorization and protected retrieval.
3. Add User Story 4 for synthetic-source extensibility guarantees.
4. Add User Story 5 for status inspection, repair, and redacted operations.
5. Complete Polish and cross-cutting acceptance tasks.

### Recommended Execution Order

For a single implementer, use:

    Setup → Foundational → US1 → US2 → US3 → US4 → US5 → Polish

With multiple implementers, complete Setup/Foundational together, then split
US2 synchronization and US3 retrieval after US1's persistence contracts are
stable. US4 can proceed against the shared registry contract while US2/US3
are in progress; US5 should follow the finalized run-state transitions.

## Notes

- Every task has a sequential ID, checkbox, and exact repository file path.
- [P] marks only work designed for independent parallel execution.
- Story tasks carry exactly one [USn] label; Setup, Foundational, and Polish
  tasks intentionally have no story label.
- Unit and explicitly required integration tests are included before the
  corresponding implementation tasks in each story phase.
- The Calendar RAG horizon is the existing Calendar service
  `MAX_CALENDAR_RANGE_DATES` 45-day bound; this feature introduces no separate
  RAG horizon setting.
- No task introduces chatbot UI, LLM answer generation, user-configurable
  permissions, external document ingestion, Business Audit summarization, or
  automatic indexing of unregistered models.
