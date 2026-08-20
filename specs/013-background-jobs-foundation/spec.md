# Feature Specification: Background Jobs and Reliable Processing Foundation

**Feature Branch**: `013-background-jobs-foundation`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Background Jobs and Reliable Processing Foundation with automatic RAG reconciliation"

## Scope and Boundaries

This feature gives the backend a durable way to perform work that should not
hold an academy request open. Its first production workload is reconciliation
of the existing authorization-aware RAG index after committed academy-data
changes.

The relational PostgreSQL database remains the source of truth for academy
data. Background records, Redis state, worker memory, RAG documents, chunks,
and embeddings are technical or derived state; they must be rebuildable and
must never authoritatively change academy records.

The implemented flow is:

```text
Existing application service
  -> domain mutation + outbox intent in one database transaction
  -> commit
  -> dedicated dispatcher
  -> Redis execution queue
  -> dedicated ARQ worker
  -> registered handler
  -> existing application/RAG service
```

There is no new background-job dashboard, arbitrary user-created job, general
workflow engine, chatbot, notification product, or new frontend workflow.
Existing authenticated mutation and protected retrieval boundaries provide the
user-visible verification surface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep Academy Mutations Immediate and Durable (Priority: P1)

As a coach using a normal academy workflow, I want a successful Player, Team,
Match, performance, statistics, roster, assignment, or Calendar mutation to
finish without waiting for embedding work while still recording the required
follow-up work reliably.

**Why this priority**: Routine academy operations must feel immediate, and a
successful domain mutation must not silently leave search and retrieval stale.

**Independent Test**: Perform one eligible mutation through its existing
application-service or authenticated API path while the embedding provider is
delayed or unavailable. Verify that the authoritative mutation commits, the
request does not wait for embedding generation, one durable or safely
coalescible work intent exists, and the work can later be dispatched.

**Acceptance Scenarios**:

1. **Given** a valid Player mutation and available PostgreSQL, **When** the
   existing mutation service commits, **Then** the domain change and its
   required background-work intent commit atomically, and no provider or Redis
   network call occurs before that commit.
2. **Given** a domain validation, authorization, or optimistic-concurrency
   failure, **When** the mutation rolls back, **Then** no executable outbox
   intent remains for that attempted change.
3. **Given** a committed eligible mutation and an unavailable embedding
   provider, **When** the request completes, **Then** the domain data remains
   committed, the work remains inspectable and retryable, and no Business Audit
   or authentication/security audit entry is created by the background
   mechanics.

### User Story 2 - Reconcile Protected RAG Retrieval to Current Academy Data (Priority: P1)

As an authenticated coach or player, I want protected RAG retrieval to reflect
current committed academy data after background processing completes, without
stale queued snapshots overwriting newer source truth.

**Why this priority**: Automatic RAG synchronization is the first concrete
benefit of the foundation and must preserve the source registry, dependency,
privacy, Calendar, and request-time authorization behavior already established
by Spec 012.

**Independent Test**: Mutate a registered RAG-backed source, process its
registered reconciliation job, and retrieve through the existing protected
retrieval boundary. Repeat the same job and perform rapid successive mutations;
verify current content, no duplicate active rows, no forbidden results, and no
unrelated full-corpus embedding work.

**Acceptance Scenarios**:

1. **Given** a committed Player, Team, Match, performance, statistics, roster,
   coach-assignment, or Calendar change that affects a registered source,
   **When** its reconciliation work runs, **Then** the handler reloads current
   authoritative rows and reconciles every source and dependency declared by
   the existing RAG registry.
2. **Given** two queued requests for the same logical source and newer source
   data is committed before either runs, **When** either request is processed,
   **Then** the resulting RAG state represents the newest committed data and an
   early payload snapshot cannot restore older content.
3. **Given** the same logical work is delivered more than once, **When** the
   handler replays it, **Then** content hashes, source fingerprints, stable
   document identities, chunk identities, and active versions remain
   duplicate-free and already-current sources are skipped.
4. **Given** a Calendar recurrence, moved occurrence, deleted occurrence,
   exception, timezone boundary, or scope change, **When** reconciliation runs,
   **Then** retrieval reflects projected effective occurrences using the
   existing Calendar semantics and bounded horizon rather than raw Calendar
   definitions.

### User Story 3 - Recover Work After Infrastructure Failure (Priority: P1)

As a developer or operator, I want to see and recover pending, retrying,
abandoned, and terminal work after API, worker, database, provider, or Redis
failures without editing authoritative academy data manually.

**Why this priority**: The foundation is valuable only if committed intent
survives ordinary restarts and temporary infrastructure outages.

**Independent Test**: Commit work, interrupt dispatch or worker execution,
make Redis or the provider unavailable, restart the worker, and restore the
dependency. Verify bounded retries, recovery of abandoned work, safe terminal
status after exhaustion, and a bounded manual retry path.

**Acceptance Scenarios**:

1. **Given** Redis is unavailable after the domain transaction commits, **When**
   dispatch is attempted, **Then** PostgreSQL retains the eligible intent and a
   later dispatcher run can enqueue it without creating another domain change.
2. **Given** a worker crashes, times out, or loses connectivity during a job,
   **When** the recovery lease or retry window expires, **Then** the work becomes
   executable again and a replay remains safe.
3. **Given** a non-retryable error or exhausted retry limit, **When** the work
   reaches a terminal state, **Then** it remains inspectable with bounded,
   sanitized failure information and an operator can retry it only through an
   approved, contract-valid recovery command.
4. **Given** two dispatchers or workers compete for the same persisted state,
   **When** one state transition wins, **Then** the other detects the version
   conflict, reloads or retries safely, and cannot silently overwrite the
   winner.

### User Story 4 - Add Future Background Work Without a New Queue Architecture (Priority: P2)

As a backend developer, I want to add a future Data Quality scan, maintenance
task, summary recomputation, import/export operation, notification, or AI
preprocessing job by extending a typed registry rather than redesigning
dispatch, retries, persistence, or worker startup.

**Why this priority**: The first job must establish a reusable foundation while
keeping all future workloads opt-in and bounded.

**Independent Test**: Register a small synthetic job with a versioned payload,
handler, retry policy, idempotency rule, and resource bounds. Run it through the
same dispatch and worker path, and verify that an unregistered job or unknown
payload version is rejected without execution.

**Acceptance Scenarios**:

1. **Given** a new registered job definition, **When** a valid versioned payload
   is submitted, **Then** the common dispatcher and worker execute the handler
   with the declared timeout, concurrency, retry, idempotency, and logging
   behavior.
2. **Given** an unregistered job type or unsupported payload version, **When** a
   worker receives it, **Then** it does not execute arbitrary code and records a
   safe non-retryable failure.
3. **Given** a delayed or future `run_after` value, **When** the job becomes
   eligible, **Then** it is dispatchable without requiring a user-facing
   scheduler or a new queue technology.

### Edge Cases

- A transaction fails after domain validation but before commit: no executable
  intent may be visible to a dispatcher.
- The dispatcher dies after claiming an outbox row, after enqueueing, or before
  recording its dispatch result: the row must be recoverable without producing
  an unbounded duplicate stream.
- Multiple dispatcher processes claim the same row, or a worker and recovery
  process update the same execution state: optimistic version checks must
  prevent silent last-write-wins behavior.
- Redis is unavailable for an extended period, has queued work when the API is
  restarted, or is replaced by another compatible deployment: PostgreSQL work
  intent remains the recovery record and no vendor-specific feature is required.
- A provider timeout, malformed response, incompatible embedding profile,
  transient PostgreSQL error, or permanent source/validation error occurs while
  RAG work is running: the previous usable RAG version remains safe where the
  existing RAG service supports that behavior.
- A job is delivered after its source was updated, deleted, deactivated, or
  made ineligible: the handler reloads the current state and reconciles or
  safely no-ops; it never resurrects deleted or ineligible content.
- A Player is edited repeatedly before the first job runs: coalescing reduces
  redundant work but does not remove the final required reconciliation.
- A TeamPlayer or TeamCoach relationship changes the dependencies of several
  canonical documents: all registry-declared dependents are included, without
  making relationship rows standalone RAG sources.
- A Match mutation affects performance or statistics context, or a performance
  batch recalculates aggregate statistics: each declared source family is
  reconciled from current rows rather than from the mutation payload.
- A Calendar series is moved, edited, deleted, or given an occurrence
  exception: old and new projected identities are reconciled within the
  existing bounded horizon, and no second recurrence implementation is added.
- A handler receives a payload containing a password, token, credential,
  unrestricted snapshot, raw document, raw vector, or arbitrary user scope:
  validation rejects it and logs do not include it.
- A worker is asked to process more jobs than the configured concurrency,
  provider batch, timeout, or Redis free-tier capacity permits: work remains
  queued or retryable rather than creating unbounded resource usage.
- A worker shuts down while work is in flight: no authoritative domain record
  is partially mutated, and the background work becomes recoverable.
- Completed technical records reach their retention boundary while failed/dead
  records are still within their longer investigation window: cleanup must not
  remove work needed for safe recovery or deduplication.

## Requirements *(mandatory)*

### Functional Requirements

#### Source of truth and transaction boundary

- **FR-001**: The system MUST treat the relational PostgreSQL academy database
  as the sole authoritative source for Player, Team, roster, coach assignment,
  Match, performance, statistics, Calendar, and authorization state. Redis,
  worker memory, job payloads, and RAG-derived records MUST NOT become a second
  source of truth.
- **FR-002**: The first implementation MUST use ARQ for asynchronous worker
  execution, Redis as the execution broker/coordination mechanism, and a
  PostgreSQL transactional outbox as the durable handoff. The design MUST NOT
  rely on Redis-vendor-specific features and MUST NOT add Celery, RabbitMQ,
  Kafka, or another queue system alongside this foundation.
- **FR-003**: The application MUST keep the responsibilities of domain
  transaction, transactional outbox, post-commit dispatch, Redis queue, ARQ
  worker, registered handler, and underlying application service distinct. The
  FastAPI request process MUST NOT perform durable background work itself or
  require an HTTP request to remain open.
- **FR-004**: When a successful eligible academy mutation requires background
  work, the existing application service MUST stage the authoritative mutation
  and the minimal outbox intent in the same database transaction and commit
  them atomically. A rolled-back transaction MUST leave no executable intent.
- **FR-005**: The normal academy-domain transaction MUST perform only
  validation, authoritative mutation, existing normal audit work where
  applicable, outbox staging, and commit. It MUST NOT hold the transaction open
  across Redis, ARQ, Gemini, or another external provider/network call.
- **FR-006**: A temporary Redis, worker, provider, or embedding failure MUST
  reduce background freshness only; it MUST NOT roll back an otherwise valid
  committed academy mutation.

#### Durable outbox and persisted processing state

- **FR-007**: Dedicated PostgreSQL persistence MUST represent durable work
  intent and, where needed for recovery, execution state without overloading
  `DataSyncLog`, Business Audit events, authentication/security audit logs, or
  RAG source/run state as generic job records.
- **FR-008**: Each durable work intent MUST include a stable work/outbox ID,
  registered job type, payload version, minimal validated JSON-compatible
  payload, creation time, optional `run_after` time, dispatch/execution state,
  attempt data, an idempotency or deduplication identity where applicable,
  safe correlation/source metadata, optimistic version state, and sanitized
  failure/retention metadata as appropriate.
- **FR-009**: Outbox payloads MUST primarily contain stable identifiers and
  instructions. They MUST NOT contain large ORM snapshots, unrestricted domain
  objects, full canonical RAG documents, raw vectors, or data that can override
  newer authoritative state.
- **FR-010**: Persisted state MUST distinguish at least eligible/pending,
  scheduled, dispatching or claimed, dispatched, running, retrying, completed,
  and failed/dead outcomes whenever those distinctions are needed for durable
  recovery. A cancellation state MAY be added only for a concrete safe use
  case.
- **FR-011**: Completed technical records MUST have bounded retention and a
  cleanup eligibility policy. Failed/dead records MUST remain inspectable for a
  longer defined retention period and MUST NOT disappear silently. Retention
  MUST preserve enough history for debugging, recovery, and safe deduplication.
- **FR-012**: Every new table, column, constraint, and index MUST be introduced
  through a versioned Alembic migration following the repository's sequential
  migration conventions, with reversible downgrade behavior where practical.
  Migration upgrade, downgrade, constraints, indexes, and recovery state MUST
  be tested against isolated Docker PostgreSQL.

#### Typed job contract and registry

- **FR-013**: Every job MUST have a stable job/work identity, registered job
  type, explicit payload schema and version, creation/scheduling metadata,
  attempt/execution state, idempotency identity, safe correlation metadata, and
  sanitized failure information where applicable.
- **FR-014**: Job payloads MUST use bounded, explicit, JSON-compatible
  representations. Python pickle or any arbitrary-code deserialization MUST
  NOT be used as the application-level job payload format.
- **FR-015**: Payload validation MUST run before handler execution. Unknown
  versions, malformed payloads, unsupported fields, unregistered job types, and
  invalid schedules MUST fail safely and MUST NOT execute a handler.
- **FR-016**: An explicit job registry MUST be the only execution allowlist.
  Each registered definition MUST declare its job-type identifier, payload
  schema/version, handler, retry classification, idempotency strategy,
  deduplication/coalescing strategy where applicable, concurrency/resource
  requirements, and bounded timeout.
- **FR-017**: Adding a future job type MUST primarily require defining its
  versioned payload, implementing its handler, declaring retry/idempotency and
  resource semantics, registering it, and adding tests. Core worker code MUST
  NOT grow a centralized `if job_type == ...` chain, and adding a model or
  service MUST NOT automatically enqueue work without explicit opt-in.
- **FR-018**: Manual triggers MUST accept only approved registered job types
  and contract-valid payloads. They MUST use the same validation, dispatch,
  retry, idempotency, authorization, and operational-state rules as automatic
  work.

#### Dispatch, worker execution, and recovery

- **FR-019**: A dedicated dispatcher MUST process only committed and eligible
  outbox rows in bounded batches, safely claim rows, tolerate multiple
  dispatcher processes, enqueue to Redis after commit, record successful
  dispatch distinctly from undispatched work, and retain enough recovery state
  to re-execute abandoned work.
- **FR-020**: Dispatcher claims and all competing persisted state transitions
  MUST use the repository's version-aware optimistic-concurrency pattern or an
  equivalent atomic version/lease predicate. A conflict MUST fail safely and
  reload or retry; it MUST NOT silently overwrite a newer state.
- **FR-021**: A dispatched work item MUST remain recoverable until the system
  has a durable completion or terminal outcome. If a worker crashes, loses
  connectivity, times out, or fails before acknowledging completion, an
  expired lease/visibility state MUST make the work executable again.
- **FR-022**: The worker runtime MUST be a separate asynchronous ARQ process or
  container from FastAPI. It MUST load settings, validate required database and
  Redis configuration, create provider/database/Redis resources during worker
  startup rather than import time, register only known handlers, enforce
  bounded concurrency, and close resources cleanly on shutdown.
- **FR-023**: Worker shutdown MUST stop accepting new work, allow bounded
  in-flight completion where practical, and safely release or abandon incomplete
  work for later retry. Restarting the API or worker MUST NOT lose committed
  PostgreSQL work intent.
- **FR-024**: The shared retry policy MUST classify retryable and non-retryable
  failures, use bounded exponential backoff with jitter where practical, and
  enforce a finite retry limit. Retryable examples include temporary provider,
  Redis, PostgreSQL, timeout, and retry-safe dependency failures; invalid
  payloads, unknown job types/versions, incompatible contracts, and permanent
  source failures MUST not be retried indefinitely.
- **FR-025**: Failure state MUST use bounded sanitized categories such as
  transient dependency failure, timeout, invalid payload, unregistered job,
  incompatible payload version, permanent domain/source failure, unexpected
  internal error, and retry limit exhausted. Raw provider, database, Redis,
  stack-trace, credential, and unrestricted exception content MUST NOT be
  exposed in job status or structured logs.
- **FR-026**: After retry exhaustion, work MUST transition to an inspectable
  terminal/dead state containing only safe work ID, job type, attempt count,
  timestamps, sanitized failure category/message, safe source/correlation
  identity, and whether manual retry is permitted.
- **FR-027**: Each job type MUST be idempotent, reconciliatory, or explicitly
  protected against duplicate delivery. The system MUST claim at-least-once
  delivery and MUST NOT claim exactly-once processing.
- **FR-028**: The foundation MUST support deduplication or coalescing for
  logical reconciliation work. Coalescing MUST never discard the final
  required reconciliation, and a stale payload MUST never be treated as final
  source data.
- **FR-029**: Each job type MUST have bounded concurrency, resource usage, and
  execution timeout. The system MUST not create an unbounded number of
  simultaneous jobs or provider requests. Timeout and cancellation handling
  MUST leave authoritative data consistent and replayable.

#### Scheduling and operational visibility

- **FR-030**: Work MUST support a validated future `run_after` or equivalent
  delayed eligibility field. The foundation MUST expose a clean extension point
  for recurring or periodic jobs without implementing arbitrary user-created
  schedules or a general workflow engine.
- **FR-031**: The feature MUST provide a direct extension point for a
  low-frequency incremental RAG safety reconciliation that reuses existing
  incremental/repair behavior. Mutation-triggered targeted reconciliation MUST
  remain the primary freshness mechanism; automatic Data Quality scheduling is
  out of scope for this release.
- **FR-032**: Bounded operator visibility MUST cover pending outbox work,
  dispatch backlog, queued/processing counts where available, retrying work,
  terminal failures, job type, attempt count, timestamps, and safe
  source/correlation metadata without returning sensitive payloads, full RAG
  documents, raw vectors, unrestricted ORM snapshots, credentials, passwords,
  or tokens.
- **FR-033**: Worker and dispatcher structured logs MUST include safe work/job
  ID, job type, attempt, duration, outcome, retry status, and safe
  correlation/source identity. Logs MUST NOT dump full serialized payloads or
  raw provider/database/Redis exception content.
- **FR-034**: Developer/operator commands MUST cover the functionality actually
  implemented, including starting the worker, inspecting pending/retrying/
  failed work, recovering undispatched or abandoned outbox entries, retrying
  eligible terminal work, and manually triggering approved registered jobs.
  Existing `backend/scripts/rag_index.py` full, targeted, incremental, repair,
  and status commands MUST remain available as independent RAG recovery tools.

#### RAG reconciliation workload

- **FR-035**: The registered RAG reconciliation job MUST invoke the existing
  `RagIndexingService` and RAG service/registry boundaries directly. It MUST
  NOT shell out to `backend/scripts/rag_index.py`, duplicate indexing logic,
  implement a second source registry, or call Gemini directly from the
  background-job layer.
- **FR-036**: The RAG job MUST identify dirty logical sources and declared
  dependency closure through the existing RAG source registry and dependency
  metadata. The background-job layer MUST NOT duplicate source dependency
  rules or treat every mutation as a complete corpus rebuild.
- **FR-037**: Relevant successful mutations MUST request reconciliation only
  when they affect a registered RAG source or a declared dependency. The
  initial mutation families to review and wire through existing application
  service boundaries are:
  Player create/update/activation-related changes; Team create/update changes;
  TeamPlayer membership and roster changes; TeamCoach assignment changes when
  indexed team context changes; Match create/update/delete changes wherever a
  supported domain mutation exists; batting, bowling, and fielding performance
  changes; Player batting and bowling statistics changes; and Calendar event,
  recurrence, and occurrence-exception changes.
- **FR-038**: The RAG job MUST prefer the narrowest safe reconciliation
  supported by the source/dependency contract. A single Player or Match change
  MUST NOT require an unrelated full-corpus rebuild. A roster or assignment
  change MUST reconcile all affected Team, Player, Match, performance, or
  statistics sources declared by the registry, and no others.
- **FR-039**: RAG handlers MUST reload current committed authoritative state
  before building documents. Queued IDs or dirty markers are instructions for
  re-resolution only; they MUST NOT override newer source rows or resurrect
  deleted/ineligible sources.
- **FR-040**: RAG idempotency MUST continue to rely on the existing source
  fingerprints, dependency hashes, content hashes, builder/chunking versions,
  embedding profile checks, stable document/chunk identities, and active-version
  activation behavior. Replayed work MUST skip already-current sources and MUST
  not create duplicate documents, chunks, embeddings, or active versions.
- **FR-041**: RAG provider batching, timeouts, model compatibility checks,
  source claims, leases, and optimistic version checks MUST remain enforced by
  the existing RAG service. The background layer MUST NOT bypass the fake
  provider seam, embedding batch-size bounds, or provider compatibility checks.
- **FR-042**: Calendar reconciliation MUST operate on projected effective
  occurrences using the existing `CalendarService`, recurrence and exception
  behavior, `America/Los_Angeles` academy timezone, scope semantics, stable
  occurrence identities, and bounded 45-day horizon. It MUST NOT introduce a
  separate recurrence implementation or index raw event/series/exception rows
  as standalone RAG documents.
- **FR-043**: Future registered RAG source models MUST be able to participate in
  automatic background reconciliation by declaring source identity, safe
  loader/builder, eligibility, dependency metadata, version/fingerprint
  behavior, and deletion handling through the existing registry extension
  architecture.

#### Audit, security, authorization, and privacy

- **FR-044**: Outbox creation, dispatch, enqueue, worker claim, retry,
  completion, failure, dead-letter transition, repair/requeue, and RAG
  indexing/reconciliation MUST create no Business Audit event and no
  authentication/security audit event.
- **FR-045**: If a future registered background job performs a real academy
  domain mutation, that mutation MUST call the same application service and
  follow the existing Business Audit and authentication/security audit rules
  exactly as its synchronous counterpart. RAG reconciliation itself MUST only
  update derived RAG/background state.
- **FR-046**: Every job payload and manual trigger MUST use an explicit schema
  and allowlist. Payloads and logs MUST never contain plaintext passwords,
  password hashes, access or refresh tokens, sessions, CSRF values, provider
  keys, database credentials, unrestricted security/audit records, raw vectors,
  full canonical documents, or arbitrary client-provided role/User/team scope.
- **FR-047**: Authorization MUST be enforced at the originating user-triggered
  operation. A background job MUST NOT grant capabilities beyond its declared
  contract, widen a user's scope, impersonate a user, or trust client-selected
  authorization fields. System maintenance jobs MUST have explicit trusted
  system semantics, and RAG reconciliation MUST operate on derived state rather
  than impersonating a user.

#### Configuration, deployment, dependencies, and documentation

- **FR-048**: Configuration MUST follow the existing settings/environment
  conventions and provide bounded, safe local defaults for Redis URL/queue,
  worker concurrency and timeout, maximum attempts, backoff bounds, dispatch
  batch/poll intervals, claim or lease duration, and completed-record
  retention. Connections MUST not be initialized when settings modules are
  imported.
- **FR-049**: ARQ MUST be added with `uv add` as an exact compatible production
  dependency for the project's Python 3.12 async architecture, with a rationale
  recorded in `pyproject.toml` or the implementation change description. The
  rationale MUST explain why the standard library and FastAPI
  `BackgroundTasks` cannot provide durable processing, why ARQ fits the existing
  async service layer, and why Redis is required as the broker. No unnecessary
  queue or workflow dependencies may be added.
- **FR-050**: Docker Compose MUST add local Redis and a dedicated worker service
  where practical while keeping the existing PostgreSQL/pgvector service as
  the authoritative database. Local documentation MUST make it straightforward
  to run PostgreSQL, Redis, FastAPI, and the worker together. Tests MUST use the
  deterministic fake embedding provider and MUST not require Internet, Gemini,
  or an external Redis service for unit execution.
- **FR-051**: The feature MUST include `docs/background-jobs.md` after
  implementation and verification. It MUST describe the implemented
  architecture, dependency rationale, transactional outbox, delivery and
  idempotency guarantees, registry extension process, startup/shutdown,
  retries/dead work, Redis outage behavior, RAG mutation synchronization,
  local Docker workflow, configuration, status/recovery commands, and how to
  add a future job type. It MUST describe actual behavior, not unbuilt plans.

#### Testing and acceptance gates

- **FR-052**: Unit tests MUST cover every public function added by this feature
  and, at minimum, payload validation/versioning, registry validation, handler
  dispatch, unregistered-job rejection, outbox creation, idempotency keys,
  coalescing, retry classification, jittered backoff, terminal transitions,
  redaction/safe logging, graceful handler failures, RAG handler delegation,
  and delay validation. `pytest-mock` MUST isolate Redis, providers, network,
  and database dependencies where appropriate.
- **FR-053**: Integration tests MUST cover migration upgrade/downgrade,
  committed mutation plus durable outbox, rolled-back mutation with zero work,
  PostgreSQL-to-Redis dispatch, worker execution, duplicate at-least-once
  processing, worker crash/retry, Redis outage and recovery, competing
  dispatcher OCC, retry exhaustion, terminal/manual retry, coalescing, restart,
  automatic RAG reconciliation, provider-failure retry with committed domain
  data, and no Business Audit/authentication-audit pollution.
- **FR-054**: The feature MUST include
  `backend/tests/integration/quickstart/test_013_quickstart_flow.py`. Its
  isolated end-to-end flow MUST:

  1. start isolated PostgreSQL and Redis;
  2. apply the background-job migration(s);
  3. start or instantiate the dispatcher/worker test boundary;
  4. seed representative academy data;
  5. create or update an eligible RAG-backed source through its normal service
     or API path;
  6. verify the domain transaction commits;
  7. verify durable outbox work exists;
  8. verify the request did not wait for embedding generation;
  9. dispatch work to Redis;
  10. execute it through the registered ARQ handler;
  11. verify RAG reconciliation reaches current state;
  12. verify protected retrieval reflects the updated source;
  13. perform rapid mutations and verify safe deduplication/coalescing;
  14. simulate provider failure and bounded retry;
  15. restart or recreate the worker and verify recovery;
  16. restore the provider and verify eventual successful reconciliation;
  17. verify no duplicate RAG rows;
  18. verify no unintended Business Audit/authentication-audit entries;
  19. inspect safe job/outbox status; and
  20. verify no sensitive payload or log leakage.
- **FR-055**: The feature MUST include at least one Playwright E2E test for
  Spec 013 using an existing authenticated workflow. The test MUST authenticate
  as an authorized role, perform a normal RAG-backed mutation, verify the
  user-facing/API mutation succeeds, and verify eventual behavior through the
  existing protected retrieval boundary where practical. It MUST NOT add a
  jobs dashboard or chatbot UI merely to satisfy the E2E requirement.
- **FR-056**: Completion MUST be gated by passing Ruff, backend type checking,
  mandatory unit tests, required PostgreSQL/Redis integration tests, migration
  tests, RAG-background integration tests, the Spec 013 quickstart, and the
  Spec 013 Playwright E2E. Dead or redundant code introduced by the feature
  MUST be removed, and the Constitution Check MUST pass.

### Key Entities

- **Background Work Intent**: A durable PostgreSQL record that says a specific
  registered job should eventually run. It contains a stable identity, typed
  versioned payload, scheduling and dispatch metadata, attempt/recovery state,
  safe correlation/source identifiers, OCC state, and bounded retention data.
- **Background Job Definition**: The registered contract for one job type,
  including its payload version, handler, retry classification, idempotency and
  coalescing strategy, timeout, and resource/concurrency bounds.
- **Job Execution State**: Durable technical status needed to distinguish
  pending, dispatched, running, retrying, completed, recoverable abandoned, and
  terminal work. It is separate from Business Audit, Auth Audit, Data Quality,
  and RAG source-state meaning.
- **RAG Reconciliation Work**: The first registered job type. It contains only
  safe source/dependency instructions and stable identifiers; it reloads
  current source truth and delegates to the existing RAG indexing service.
- **RAG Source Dependency**: A registry-declared relationship or projection
  input that determines which canonical source identities become dirty after a
  domain mutation. It is not a copy of dependency logic in the job layer.
- **RAG Derived State**: Existing RAG runs, source states, documents, chunks,
  embeddings, content hashes, and leases that are updated by reconciliation but
  never become authoritative academy data.
- **Domain Mutation Boundary**: The existing Player, Team, Match, performance,
  statistics, Calendar, roster, coach-assignment, and account-related
  application services that own validation, OCC, domain commits, and existing
  Business/Auth Audit behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the required integration and quickstart flows, 100% of valid
  eligible committed mutations produce a durable or safely coalesced work
  intent, and 100% of rolled-back mutations produce zero executable work.
- **SC-002**: In the request-boundary tests, a normal eligible academy mutation
  completes without waiting for embedding generation; a delayed or failed
  provider cannot prevent the domain commit.
- **SC-003**: After temporary queue/provider recovery, 100% of committed eligible changes
  in the required failure scenarios reach a successful or explicitly
  inspectable terminal outcome within the configured finite retry policy.
- **SC-004**: Replaying every required duplicate-delivery scenario produces
  zero duplicate active RAG documents, chunks, or source identities and never
  replaces newer source truth with an older queued snapshot.
- **SC-005**: In concurrent dispatcher and worker scenarios, zero committed
  work intents are silently lost and zero newer persisted states are silently
  overwritten by stale transitions.
- **SC-006**: A single-source Player or Match change causes no unrelated
  full-corpus reconciliation in the targeted integration scenarios, while every
  registry-declared dependent source is reconciled.
- **SC-007**: Calendar reconciliation matches the existing effective
  occurrence projection for standalone, recurring, moved, deleted, scoped, and
  timezone-bound cases across the configured bounded horizon.
- **SC-008**: Operators can inspect all pending, retrying, abandoned, and dead
  records used by the quickstart and can recover each eligible terminal or
  undispatched case through a bounded command without direct database edits.
- **SC-009**: Technical background processing creates zero Business Audit and
  zero authentication/security audit entries in the required unit,
  integration, quickstart, and authenticated workflow tests.
- **SC-010**: Automated status, log, payload, and retrieval checks expose zero
  passwords, hashes, tokens, sessions, CSRF values, credentials, unrestricted
  snapshots, full RAG documents, raw vectors, or arbitrary authorization scope.
- **SC-011**: Automated unit tests run without Internet or third-party
  services, and the isolated quickstart completes with deterministic
  embeddings and local infrastructure.
- **SC-012**: A synthetic future job can be added using only a versioned
  payload, handler, declared policies, registration, and tests; it executes
  through the existing processing and recovery behavior, while an unregistered
  equivalent is rejected safely.
- **SC-013**: In the required Playwright journey, an authorized user can
  complete the existing mutation workflow successfully and observe the updated
  result through the protected retrieval boundary after background processing.

## Assumptions

- Spec 012's RAG source registry, dependency metadata, provider seam, projected
  Calendar behavior, source claims, content hashes, and retrieval authorization
  are the baseline and will be extended rather than replaced.
- Existing application services remain the only domain mutation boundaries.
  The current repository has public Match create/update paths but no public
  Match delete route; delete reconciliation is required wherever the supported
  service-level delete operation exists, without inventing a parallel product
  mutation API solely for background processing.
- Player account linking, role changes, assignment changes, and activation
  state may affect request-time authorization without requiring re-embedding
  unless the registered RAG dependency metadata declares a semantic source
  change. Retrieval authorization remains derived live from current relational
  state.
- Match, performance, and player-statistics mutations currently have less
  Business Audit coverage than Player, Team, Coach, roster, and Calendar
  mutations. This feature must preserve that existing behavior and must not add
  technical or incidental audit events.
- The initial deployment targets a small academy workload and a cost-conscious
  Redis tier. Payloads remain small, Redis is not a history store, concurrency
  and polling are bounded, and PostgreSQL carries durable operational history
  only where recovery or debugging justifies it.
- The deterministic fake embedding provider is the default for automated tests;
  a private Gemini credential may be used for local or production operation but
  is never committed, serialized into work, or printed.
- An HTTP administration API is not required if bounded CLI/internal commands
  provide the specified inspection and recovery capabilities. Any endpoint
  added later must use typed, sanitized schemas and must not expose raw job
  payloads.
- No frontend surface is introduced. The existing product and design guidance
  therefore applies only to the existing authenticated workflow used by the
  Playwright acceptance test; no new responsive visual states or frontend types
  are part of this scope.
- Completed and dead technical records use separate bounded retention windows;
  exact default durations are implementation configuration decisions, but both
  windows must be documented and tested.
