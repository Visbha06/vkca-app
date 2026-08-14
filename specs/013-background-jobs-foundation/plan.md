# Implementation Plan: Background Jobs and Reliable Processing Foundation

**Branch**: `013-background-jobs-foundation`
**Date**: 2026-08-14
**Spec**: [spec.md](./spec.md)

**Input**: Feature specification from
`specs/013-background-jobs-foundation/spec.md`

## Summary

Build a reusable backend processing foundation around a PostgreSQL
transactional outbox, Redis, and a dedicated ARQ worker. Existing application
services will stage a typed, bounded work intent in the same transaction as an
eligible academy mutation. A bounded dispatcher will claim committed intents,
enqueue only a JSON work-ID envelope, and record dispatch with optimistic
concurrency. A separate worker will claim the durable row, validate it through
an explicit registry, invoke the registered handler, and persist retry,
completion, or terminal state.

The first registered handler will be RAG reconciliation. It will extend the
existing RAG registry and `RagIndexingService` with targeted stable source
references and dependency closure, reload current PostgreSQL state, and retain
all current RAG provider, content-hash, claim, active-version, authorization,
and Calendar projection behavior. No domain mutation, RAG source registry, or
embedding implementation will be duplicated in the worker layer.

Phase 0 research resolves the exact ARQ target, JSON serialization boundary,
outbox/OCC transitions, coalescing, recovery, RAG impact routing, and local
development defaults in [research.md](./research.md). Phase 1 design is defined
in [data-model.md](./data-model.md),
[contracts/background-jobs.md](./contracts/background-jobs.md), and
[quickstart.md](./quickstart.md).

## Technical Context

**Language/Version**: Python 3.12+ for backend/runtime; TypeScript/React only
for the existing request-level Playwright acceptance boundary. No frontend
feature surface.

**Primary Dependencies**: Existing FastAPI, Pydantic/Pydantic Settings,
SQLAlchemy 2 async, asyncpg, Alembic, pgvector, pytest, pytest-asyncio,
pytest-mock, Ruff, mypy, and Playwright. Add only exact production dependency
`arq==0.28.0` with rationale in `backend/pyproject.toml`; use its supported
Redis client dependency rather than adding another queue client unless the
lockfile requires a direct import.

**Storage**: Existing PostgreSQL 16/pgvector is authoritative for academy and
durable processing state. Add one dedicated `background_work_items` table in
Alembic revision 015. Add local Redis through Docker Compose as an execution
broker/coordination store; Redis is not authoritative and is not permanent
history.

**Testing**: Unit tests with `pytest-mock` isolation and no external services;
PostgreSQL/Redis integration tests for migration, transaction, dispatch,
worker, retry, restart, and concurrency behavior; the required
`backend/tests/integration/quickstart/test_013_quickstart_flow.py`; one
request-level authenticated Playwright test under `frontend/e2e`; Ruff,
mypy, and existing test commands.

**Target Platform**: Linux-hosted FastAPI API, dedicated Linux async worker,
Docker-hosted PostgreSQL/Redis for local development, and operator commands
run from `backend/` with `uv`.

**Project Type**: Authenticated backend web service with existing application
services, Alembic migrations, operator CLI scripts, a dedicated worker runtime,
and an existing protected RAG retrieval route used for acceptance verification.

**Performance Goals**: Domain mutation latency must not include Redis, ARQ,
Gemini, or other provider calls. Dispatcher batches, worker concurrency,
provider requests, payload sizes, retry count, and status output are bounded.
One targeted Player or Match mutation must not initiate an unrelated full
corpus reconciliation. Exact production latency SLOs are not promised by this
foundation.

**Constraints**: At-least-once delivery; no exactly-once claim; JSON-compatible
payloads only; no pickle; PostgreSQL remains source of truth; all competing
state transitions use version/lease-aware OCC; provider calls remain outside
academy transactions; only registered job types execute; no secrets, snapshots,
documents, vectors, or client authorization scope in payloads/logs; no UI,
dashboard, arbitrary user jobs, general scheduler, workflow engine, or new
queue system.

**Scale/Scope**: One academy and the existing nine initial RAG source families,
with small/free-tier Redis compatibility. Initial safe defaults are worker
concurrency 4, generic timeout 300 seconds, five attempts, retry backoff 5–300
seconds with 5 seconds jitter, dispatcher batch 50, five-second polling,
120-second claim lease, seven-day completed retention, and 30-day dead
retention. All are validated settings rather than hard-coded operational
limits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Clean Code — PASS**: Keep payload contracts, persistence, dispatcher,
  retry policy, worker lifecycle, registry, and RAG handler responsibilities
  separate. Use a registry rather than a growing job-type conditional chain.
- **II. Simple UX — PASS/N/A**: No user-facing screen or workflow is added.
  Existing authenticated mutation and protected retrieval boundaries provide
  the user-visible verification surface; operator commands are bounded.
- **III. Responsive Design — N/A**: No React UI, layout, or visual state is
  introduced.
- **IV. Minimal Dependencies — PASS**: Add only exact `arq==0.28.0` with a
  `pyproject.toml` rationale. Do not add Celery, RabbitMQ, Kafka, a workflow
  engine, or an independent queue client without a later concrete requirement.
- **V. Testing Discipline — PASS**: Unit coverage is mandatory for every new
  public backend function, pytest-mock isolates external dependencies, required
  integration coverage is specified by the feature, the quickstart path uses
  `test_013_quickstart_flow.py`, and a Playwright journey is included.
- **VI. MCP Server Priority — PASS**: Repository architecture and literal
  searches were reviewed through the configured codebase-memory/ripgrep
  resources before relying on direct file inspection.
- **VII. Database Schema Migrations — PASS**: Add revision 015 for every new
  table/index/constraint/column, test upgrade/downgrade against local Docker
  PostgreSQL, and apply the migration before dependent runtime code is used.
- **VIII. UX Completeness — N/A/PASS**: No new frontend surface exists; the
  plan explicitly retains the existing authenticated workflow and adds no UI
  states requiring `PRODUCT.md`/`DESIGN.md` implementation work.
- **IX. Optimistic Concurrency — PASS**: Outbox coalescing, dispatcher claims,
  worker claims, lease recovery, retry/dead transitions, manual retry, and
  terminal cleanup use expected-version/lease predicates and safe reloads.
- **X. Strongly-Typed API Boundaries — PASS**: No new HTTP admin API is needed.
  Pydantic payload/operational schemas and typed CLI contracts are defined; any
  future HTTP endpoint must be bounded and sanitized.
- **XI. Frontend State & Component Discipline — N/A**: No React component or
  frontend API client change is planned.
- **XII. Documentation — PASS WITH IMPLEMENTATION FOLLOW-UP**: Add
  `docs/background-jobs.md` after implementation and verification, describing
  actual behavior, configuration, commands, recovery, and extension rules.

**Gate result: PASS.** No constitution violation requires a Complexity
Tracking exception. ARQ's maintenance-only upstream status is recorded as a
risk in research and contained behind an application-owned adapter; it is not
a constitution violation or reason to introduce a second queue.

## Project Structure

### Documentation (this feature)

```text
specs/013-background-jobs-foundation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── background-jobs.md
└── tasks.md                 # created later by /speckit-tasks
```

### Source Code

```text
backend/
├── Dockerfile                         # local API/worker runtime image
├── pyproject.toml                     # add exact arq dependency/rationale
├── uv.lock                            # lock ARQ and transitive Redis client
├── scripts/
│   ├── background_jobs.py             # bounded status/dispatch/recovery triggers
│   ├── background_worker.py           # dedicated ARQ WorkerSettings entrypoint
│   └── rag_index.py                   # existing independent RAG recovery CLI
├── src/
│   ├── config.py                      # Redis/worker/retry/retention settings
│   ├── database.py                    # startup-safe worker session resource factory
│   ├── models/
│   │   ├── __init__.py                # register BackgroundWorkItem
│   │   └── background_work_item.py    # durable outbox/job state model
│   ├── schemas/
│   │   └── background_jobs.py         # typed payload/status/command schemas
│   ├── services/
│   │   ├── background_jobs/
│   │   │   ├── __init__.py
│   │   │   ├── contracts.py           # generic job/envelope/failure types
│   │   │   ├── registry.py             # explicit execution allowlist
│   │   │   ├── outbox.py               # stage/coalesce/reload transitions
│   │   │   ├── dispatcher.py           # bounded PostgreSQL -> Redis handoff
│   │   │   ├── retry.py                # classification/backoff/jitter
│   │   │   ├── runtime.py              # worker startup/shutdown resource factory
│   │   │   ├── logging.py              # safe structured fields/redaction
│   │   │   └── handlers/
│   │   │       ├── __init__.py
│   │   │       └── rag_reconciliation.py
│   │   ├── rag/
│   │   │   ├── contracts.py           # extend target/impact dependency contract
│   │   │   ├── registry.py             # retain source/dependency authority
│   │   │   ├── indexing.py             # add targeted key reconciliation
│   │   │   └── ...                     # existing loaders/builders/provider seam
│   │   ├── player_service.py           # stage eligible Player impacts
│   │   ├── team_service.py             # stage Team/roster impacts
│   │   ├── coach_service.py            # stage semantic assignment impacts
│   │   ├── match_service.py            # stage Match impacts
│   │   ├── performance_service.py      # stage performance/stat impacts
│   │   └── calendar_service.py         # stage projected occurrence impacts
│   └── migrations/versions/
│       └── 015_background_processing_foundation.py
├── tests/
│   ├── unit/
│   │   ├── test_background_jobs_contracts.py
│   │   ├── test_background_jobs_registry.py
│   │   ├── test_background_jobs_retry.py
│   │   ├── test_background_jobs_outbox.py
│   │   ├── test_background_jobs_dispatcher.py
│   │   ├── test_background_jobs_worker.py
│   │   └── test_background_jobs_redaction.py
│   └── integration/
│       ├── test_background_job_migration.py
│       ├── test_background_outbox.py
│       ├── test_background_dispatch.py
│       ├── test_background_worker.py
│       ├── test_background_rag_reconciliation.py
│       ├── test_background_failure_recovery.py
│       └── quickstart/
│           └── test_013_quickstart_flow.py
frontend/
└── e2e/
    └── background-jobs-foundation-flow.spec.ts  # existing API workflow boundary
docker-compose.yml                       # add Redis and dedicated worker service
.env.example                             # local Redis/job settings
.env.test.example                        # deterministic test Redis/job settings
docs/background-jobs.md                  # written after implementation/verification
```

**Structure Decision**: Keep the existing single backend web-service project
and add background infrastructure under `backend/src/services/background_jobs`
plus one dedicated worker entrypoint. Domain services remain the mutation
boundaries. RAG extensions remain under `backend/src/services/rag`. The worker
does not create parallel domain services or a second RAG implementation. A
small backend image is added only so Compose can run a worker process with the
same locked environment; PostgreSQL/pgvector remains unchanged.

## Phase 0 Research Output

Phase 0 is complete in [research.md](./research.md). Decisions carried into
design are:

1. Pin ARQ 0.28.0, isolate it behind a generic worker adapter, and configure
   bounded concurrency, timeout, startup/shutdown, and retry/defer behavior.
2. Override ARQ's default pickle serializer with a bounded JSON envelope that
   contains only a PostgreSQL work ID; do not retain ARQ results as durable
   state.
3. Use one versioned PostgreSQL work-item row with coalescing keys, dispatch and
   execution leases, finite retry state, sanitized failure, retention, and OCC.
4. Stage/coalesce intents inside existing mutation-service transactions; never
   make external calls before domain commit.
5. Extend the RAG registry/indexing service with stable target/impact resolution
   and dependency closure; the worker only delegates.
6. Persist delayed eligibility in PostgreSQL and expose a manual safety trigger
   without adding a general scheduler.
7. Add Redis/worker local infrastructure, an isolated cross-connection
   quickstart, bounded operator commands, and no new frontend UI.

## Phase 1 Design Output

- [data-model.md](./data-model.md) defines the durable work row, in-memory
  registry/payload entities, indexes, privacy limits, and OCC state machine.
- [contracts/background-jobs.md](./contracts/background-jobs.md) defines the
  mutation staging, JSON/ARQ envelope, registry, dispatcher, worker, failure,
  CLI, configuration, audit, and authorization contracts.
- [quickstart.md](./quickstart.md) defines the runnable local setup, migration,
  20-step durable RAG flow, failure/restart checks, CLI checks, quality gates,
  and Playwright boundary.

## Design and Implementation Sequence

1. **Lock the runtime boundary and configuration.** Add `arq==0.28.0` with the
   required rationale using `uv add`, update `uv.lock`, add validated Redis,
   worker, retry, dispatch, lease, and retention settings to `config.py` and
   both environment examples, and add a worker-only startup resource factory.
   The factory must create database sessions, Redis pool, fake/Gemini provider
   seam, registry, and logger during worker startup and close them during
   shutdown; importing settings or handler modules must not create clients.

2. **Define generic typed contracts and registry.** Add Pydantic models and
   immutable contracts for job envelopes, payload versions, failure categories,
   retry policy, safe operational projections, and `BackgroundJobDefinition`.
   Implement registry validation, explicit handler allowlisting, JSON codec
   bounds, redaction, deterministic backoff with injectable time/randomness,
   and safe unknown-version/type rejection. Keep ARQ types behind the runtime
   adapter and disable unneeded result retention/logging.

3. **Add durable persistence and migration 015.** Implement
   `BackgroundWorkItem` and register it in `models/__init__.py`. Add the table,
   check constraints, unique idempotency index, partial active coalescing index,
   eligible/recovery/retention indexes, timestamps, counters, leases,
   sanitized failure fields, and `version_number` through a reversible Alembic
   revision. Test upgrade/downgrade before dependent runtime code. Do not add
   foreign keys to polymorphic source IDs or overload existing audit/DataSync/RAG
   tables.

4. **Implement transaction-local staging and coalescing.** Add the shared
   outbox service that validates a registered payload, computes safe
   idempotency/coalescing identities, merges bounded pending payloads with OCC,
   creates a successor when a source is already running, and never commits or
   contacts a network. Preserve each existing service's Business Audit and
   rollback behavior. Add unit tests for rollback semantics, coalescing,
   payload limits, duplicate identities, and no-audit behavior.

5. **Wire existing domain mutation boundaries.** Add impact staging immediately
   before the existing commits in `PlayerService` create/update/activation
   paths, `TeamService` create/update/roster paths, semantic `CoachService`
   assignment paths, `MatchService` create/update and supported delete paths,
   `PerformanceService` batch writes/stat recalculation, and all applicable
   `CalendarService` event/series/occurrence/exception create/update/delete
   paths. Use a shared RAG impact/dependency resolver so these services submit
   stable IDs/instructions rather than copying RAG dependency rules. Keep
   `PlayerAccountService`/authentication changes out unless registry metadata
   declares a semantic source impact; live retrieval authorization remains
   request-time. Verify Data Quality remediation still delegates through these
   services and does not create technical audit events.

6. **Implement the PostgreSQL-to-Redis dispatcher.** Add bounded candidate
   selection, expired-lease recovery, short claim transactions, stable ARQ job
   IDs, custom JSON envelope enqueue, successful dispatch transition, and
   sanitized temporary-failure retry. Use expected `version_number`, state,
   lease-owner, and lease-expiry predicates for every transition. Add a bounded
   dispatcher report and tests for Redis outage, competing dispatchers, crash
   after enqueue, duplicate enqueue, and no lost committed work.

7. **Implement the dedicated ARQ worker.** Add `WorkerSettings` with one generic
   registered function, custom JSON codec, configured `max_jobs`, timeout,
   finite retry behavior, startup/shutdown hooks, and safe structured logs.
   Claim the PostgreSQL row before handler execution, validate the registry
   payload, invoke the handler with startup-owned dependencies, persist
   completion/retry/dead transitions, and allow expired leases to recover
   after cancellation, timeout, process restart, or database/Redis failure.
   Ensure stale workers cannot win a later OCC transition.

8. **Extend the existing RAG service and add the handler.** Add the smallest
   target/impact/dependency contract under `services/rag`, then extend
   `RagIndexingService` to reconcile stable target keys and declared dependency
   closure without turning targeted work into a full corpus run. The registered
   `rag_reconciliation` handler must call that service directly, preserve
   source fingerprints/content hashes/active versions/provider limits, and
   reload current state. Wire Player, Team, TeamPlayer, TeamCoach, Match,
   performance, statistics, and Calendar impacts. Calendar must continue to use
   effective projected occurrences, existing timezone/scope/exception rules,
   stable occurrence keys, and the 45-day horizon. Add an incremental/repair
   safety trigger without an automatic user scheduler.

9. **Add operational commands and local deployment.** Implement the worker,
   status, dispatch, recover, bounded manual retry, targeted RAG trigger, and
   safety trigger commands from the contracts. Add safe summaries only. Add a
   minimal backend runtime image, Redis and worker Compose services, health/
   dependency wiring, and local environment defaults. Keep
   `scripts/rag_index.py` unchanged as an independent full/targeted/
   incremental/repair/status recovery tool.

10. **Add tests in constitution order.** Cover all public contracts and helpers
    with unit tests using `pytest-mock`. Add migration, transaction/outbox,
    dispatcher/OCC, Redis outage, worker crash/restart, retry/dead/manual
    recovery, coalescing, JSON/payload rejection, redaction, and RAG delegation
    integration tests. Add the isolated 20-step quickstart with committed
    cross-connection state and local Redis. Add the request-level authenticated
    Playwright mutation/retrieval test under the existing frontend runner; do
    not add UI solely for the test.

11. **Run final verification and documentation.** Run Ruff, mypy, mandatory
    unit/integration/quickstart/migration/RAG tests, and the Spec 013
    Playwright journey. Inspect SQL/index/query behavior, no-audit pollution,
    sensitive-data redaction, lease/OCC conflicts, and dead/redundant code.
    Only after behavior is verified, write `docs/background-jobs.md` describing
    the implemented architecture, configuration, commands, RAG triggers,
    Redis outage semantics, retry/dead recovery, and future job extension path.

## Risks and Mitigations

- **ARQ maintenance-only status or future API drift**: pin the exact version,
  use one generic entry point and local adapter, keep application contracts
  independent of ARQ, and document the replacement seam.
- **ARQ default pickle or result leakage**: inject JSON serializer/deserializer,
  enqueue only a work ID, disable result retention/logging, and test raw Redis
  and log output for forbidden content.
- **Dispatcher crash after enqueue**: use deterministic queue IDs, preserve the
  PostgreSQL row, assume duplicate delivery, and rely on idempotent RAG hashes
  and active-version constraints.
- **Worker crash after claim**: use versioned leases and expiry recovery;
  stale completion updates fail safely and do not overwrite a newer state.
- **Coalescing drops the latest mutation**: merge only bounded non-running rows;
  create a successor for running work and always reload current source truth.
- **Deleted relationship or Calendar source cannot be found in current state**:
  stage old/new stable source references or bounded projection targets through
  the shared impact resolver; let the existing deletion policy remove obsolete
  derived rows.
- **Mutation services have many direct commits**: wire one staging helper at
  each existing commit path and add rollback/Business Audit integration tests;
  do not introduce a parallel unit-of-work service.
- **Redis outage or free-tier pressure**: small PostgreSQL-referenced payloads,
  bounded polling/batches/concurrency, no permanent Redis history, and an
  inspectable PostgreSQL backlog.
- **Provider timeout during RAG**: retain existing last usable derived state,
  classify/sanitize the failure, and retry through the shared policy without
  holding an academy transaction.
- **Calendar semantic drift**: invoke `CalendarService` projection and add
  recurring/moved/deleted/timezone/scope/exception tests against the existing
  45-day horizon; never implement recurrence logic in the worker.
- **Operational leakage**: allowlist status fields, cap messages/payloads,
  redact structured logs, and test passwords/tokens/vectors/full documents are
  absent from queues, status, logs, and retrieval responses.

## Post-Design Constitution Re-check

After Phase 1 artifacts are generated, re-evaluate the gates against the final
contracts and data model:

- No UI is introduced, so responsive/frontend principles remain N/A.
- The only new production dependency remains the justified exact ARQ pin.
- Migration 015 covers every persistence change and is tested before runtime
  use.
- All persistent competing transitions have version/lease predicates.
- No HTTP admin API or untyped frontend contract is introduced.
- Unit, integration, quickstart, and Playwright requirements are explicit.
- Documentation is deferred until implementation verification, as required by
  the constitution.

**Post-design gate result: PASS.** No Complexity Tracking entries are
required.
