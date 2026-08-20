# Background Jobs and Reliable Processing Foundation Research

**Feature**: `013-background-jobs-foundation`
**Date**: 2026-08-14

This research resolves the planning decisions for the durable background-work
foundation. It uses the current repository as the source of truth and records
the externally mandated ARQ/Redis choice without allowing either system to
become authoritative academy state.

## Decision Summary

| Area | Decision | Consequence |
|---|---|---|
| Worker framework | Pin `arq==0.28.0` through `uv add` | The worker uses the existing Python 3.12 async stack and keeps the ARQ integration behind one runtime adapter. |
| Broker | Use the ARQ-compatible Redis connection configured by `REDIS_URL` | Redis carries executable queue messages and coordination only; PostgreSQL remains the recovery record. |
| Durable handoff | Add one dedicated PostgreSQL `background_work_items` table | The same bounded record represents outbox intent and the durable processing state needed for dispatch/recovery. |
| Queue payload | Use a custom bounded JSON serializer and enqueue only a work ID envelope | ARQ's default pickle serializer is not used; the full validated payload is read from PostgreSQL. |
| Delivery | Assume at-least-once delivery | A deterministic ARQ job ID, PostgreSQL OCC/leases, source hashes, and reconciliatory handlers make replay safe. |
| Dispatch | Claim committed eligible rows in short PostgreSQL transactions, enqueue outside the transaction, then record the result with OCC | Redis downtime delays freshness but cannot roll back or erase a committed academy mutation. |
| Worker state | Claim the PostgreSQL work row before invoking a handler and renew/release a lease explicitly | Worker crashes and API restarts leave work recoverable without treating Redis memory as durable state. |
| Retry | Persist bounded retry state in PostgreSQL and use ARQ's retry/defer primitive as the execution mechanism | Retry classification, backoff, terminal failure, and manual recovery remain inspectable independent of Redis. |
| Job extensibility | Registry of typed job definitions with one generic ARQ entry point | Future jobs add a payload, handler, policy, registration, and tests rather than a new queue path. |
| First workload | `rag_reconciliation` handler delegates to `RagIndexingService` | RAG source/dependency rules, current-state reloads, provider bounds, and Calendar projection remain in existing RAG services. |
| Targeting | Carry bounded stable source references and let the RAG registry/service resolve current dependency closure | Mutation payloads never contain ORM snapshots; one mutation does not trigger an unrelated corpus rebuild. |
| Scheduling | Persist validated `run_after`; do not add a user scheduler or recurring scheduler in this release | A future safety sweep or maintenance job can be scheduled through the same outbox/dispatcher contract. |
| Operator surface | Bounded CLI commands, no jobs dashboard or admin HTTP API | Status and recovery are available without creating a new user-facing workflow or leaking raw payloads. |

## Repository Findings

- The backend is Python 3.12+, FastAPI, Pydantic Settings, async SQLAlchemy 2,
  asyncpg, Alembic, and PostgreSQL 16 with pgvector. Runtime code is under
  `backend/src`; operator scripts are under `backend/scripts`.
- The current migration head is `014_rag_indexing_foundation.py`. The new
  background-processing schema must be revision 015 and must be applied before
  dependent application code is deployed.
- `backend/src/database.py` exposes the existing `AsyncSessionFactory`, while
  application services own their commits and rollbacks. New outbox staging must
  be added before those existing commits; it must not introduce a second domain
  transaction boundary.
- `VersionMixin` and `services/occ.py` provide the repository's optimistic
  concurrency pattern. RAG source claims in `services/rag/indexing.py` provide
  an additional version-plus-lease pattern for competing workers.
- `BusinessAuditService` stages normal domain audit events but does not commit;
  `AuditService` writes a separate authentication/security log. Technical
  outbox, dispatch, worker, retry, and RAG operations must call neither writer.
- `RagSourceRegistry` is the explicit source allowlist. It currently registers
  Player, Team, Match, three performance families, two statistics families, and
  projected Calendar occurrences. `RagIndexingService` currently exposes full,
  source-type targeted, incremental, repair, and status operations.
- Calendar RAG preparation delegates to `CalendarService` effective-occurrence
  projection, `America/Los_Angeles`, scope rules, exceptions, and the bounded
  45-day horizon. The background layer must call that boundary instead of
  implementing recurrence arithmetic.
- Existing integration fixtures use a rollback-only outer transaction. A
  cross-process quickstart cannot depend on that fixture because an external
  dispatcher/worker must observe committed rows. The feature quickstart needs a
  dedicated isolated database/schema setup with explicit cleanup or a burst
  worker boundary sharing committed test state.
- Docker Compose currently provides PostgreSQL only and there is no backend
  Dockerfile. Adding a small backend runtime image is the least surprising way
  to provide a dedicated local worker service without changing the PostgreSQL
  authority.
- The existing `backend/scripts/rag_index.py` is an operator recovery tool and
  must remain independent. The background worker will import services directly,
  never shell out to this script.

## Technology and Integration Research

### ARQ version, lifecycle, and bounded execution

**Decision**: Pin `arq==0.28.0` exactly in the production dependency set and
use only the documented worker/connection interfaces behind a small local
adapter.

**Rationale**:

- The user explicitly selected ARQ and Redis for the first implementation.
- The official package release history lists 0.28.0 as the current release on
  the planning date, and its recent releases support modern Python versions.
- ARQ exposes the controls required by this feature: worker `max_jobs`, default
  `job_timeout`, `max_tries`, startup/shutdown hooks, cancellation handling,
  and `Retry(defer=...)` for deferred execution.
- The repository already uses asynchronous Python services, so ARQ can invoke
  those services without introducing a synchronous worker framework.

**Risk and containment**: The upstream repository describes ARQ as being in
maintenance-only mode. That is a reason to keep the integration narrow, not a
reason to add a second queue. The application-facing contracts will not expose
ARQ types; the dispatcher, worker lifecycle, retry adapter, and serializer will
be replaceable behind the same registry and PostgreSQL state model later.

**Alternatives considered**:

- **FastAPI `BackgroundTasks`**: rejected because work is tied to the request
  process and does not provide durable handoff, independent workers, or restart
  recovery.
- **Celery/RabbitMQ/Kafka/workflow engine**: rejected by the feature scope and
  dependency discipline; they add broker/workflow infrastructure not justified
  by the current academy workload.
- **A custom asyncio worker**: rejected because it would recreate queue
  claiming, retry, shutdown, and broker integration that ARQ already provides.

Primary references: [ARQ documentation](https://arq-docs.helpmanual.io/),
[ARQ package release history](https://pypi.org/project/arq/), and the
[ARQ source repository](https://github.com/python-arq/arq).

### JSON serialization and Redis responsibility

**Decision**: Supply ARQ with an application-owned JSON serializer/deserializer
and keep ARQ result retention disabled for this worker. Enqueue one generic
function with a UUID work ID and a small contract version; load the validated
job type and payload from PostgreSQL before execution.

**Rationale**:

- ARQ documents `pickle.dumps`/`pickle.loads` as its default job serializer;
  that default conflicts with the explicit no-pickle application contract.
- A JSON-only envelope is bounded, inspectable, compatible across worker
  versions, and safe to reject before handler execution.
- The durable payload belongs in PostgreSQL. Redis contains only the minimum
  execution reference and transient ARQ state, which is compatible with a
  small/free Redis tier.
- A deterministic ARQ `_job_id` derived from the PostgreSQL work ID reduces
  duplicate queue entries after a dispatcher crash. It is only an optimization;
  the handler still assumes duplicate execution.

**Alternatives considered**:

- **ARQ's default pickle**: rejected because it permits arbitrary Python object
  deserialization and is not an inspectable application contract.
- **Embedding the full payload in Redis**: rejected because it duplicates
  durable state, increases exposure and payload size, and lets stale queue data
  look authoritative.
- **Redis Streams or a second queue implementation**: rejected because ARQ is
  the selected execution framework. Redis's queue primitives remain an
  implementation detail behind ARQ, not a second application contract.

Redis queue behavior is consistent with the official [Redis list
documentation](https://redis.io/docs/latest/develop/data-types/lists/): Redis
is suitable for queue operations, but this design deliberately keeps the
durable work record in PostgreSQL.

### Transactional outbox and optimistic concurrency

**Decision**: Use a single dedicated PostgreSQL row per logical background work
intent. Existing mutation services stage or coalesce that row in their current
session before their existing `commit()`. A dispatcher and worker use short
lease claims with `version_number` predicates and `RETURNING` updates.

**Rationale**:

- One table is sufficient for durable intent, dispatch state, retry state,
  leases, safe failure data, and retention; a second generic job history table
  would add storage and transitions without a required use case.
- The current services already own transaction boundaries. A shared staging
  service can preserve Business Audit behavior and guarantee that rollback
  removes the work intent.
- `SELECT ... FOR UPDATE SKIP LOCKED` can bound candidate selection, while the
  final state changes still require expected-version/lease predicates. This
  follows the repository's explicit OCC requirement instead of relying only on
  row locks.
- A crash after Redis enqueue and before the PostgreSQL dispatch update is
  handled as a duplicate-delivery case: stable queue IDs, an expired claim, and
  idempotent/reconciliatory handlers preserve correctness.

**Alternatives considered**:

- **Commit domain data, then enqueue synchronously**: rejected because a Redis
  failure between those steps loses required work.
- **Publish before commit**: rejected because a later domain rollback leaves
  executable work for data that never committed.
- **Use Redis as the outbox**: rejected because Redis is not the authoritative
  durable handoff required by the feature.
- **Only use a row lock without a version field**: rejected because the
  constitution requires safe competing transitions and stale writers must not
  silently overwrite newer state.

### Retry, crash recovery, and terminal failures

**Decision**: PostgreSQL stores authoritative attempt counts, `run_after`,
lease ownership/expiry, state, and sanitized last failure. The generic ARQ
handler maps retry-safe failures to a bounded `Retry(defer=...)` after persisting
the next state; terminal failures are persisted as `dead` and return without
exposing raw exceptions.

**Rationale**:

- ARQ supplies execution retry and cancellation behavior, while PostgreSQL
  supplies inspectable recovery even when Redis is unavailable.
- A separate application retry policy can classify provider, timeout, broker,
  database, payload, and source failures consistently across future jobs.
- Exponential backoff with bounded jitter avoids synchronized provider retries
  without creating indefinite work.
- A worker crash before completion leaves a lease that the dispatcher/recovery
  path can reclaim; a stale worker cannot complete the row after another worker
  wins because the version/lease predicate fails.

**Alternatives considered**:

- **Only ARQ retry counters**: rejected because they are not sufficient for
  PostgreSQL backlog inspection or Redis outage recovery.
- **Infinite retry**: rejected because permanent payload/source errors would
  consume resources forever and never become operator-visible.
- **Persist raw exceptions**: rejected because provider, database, and internal
  exception text may contain secrets or sensitive implementation details.

### RAG impact and targeted reconciliation

**Decision**: Add a shared RAG mutation-impact contract and a targeted
reconciliation entry point to the existing RAG registry/indexing service. Domain
services submit bounded stable source references; the worker asks the RAG service
to resolve current source rows and declared dependency closure.

**Rationale**:

- The current source registry already owns source identities, loaders, builders,
  eligibility, deletion policy, and dependency metadata. The background layer
  must not copy those rules.
- Stable IDs are enough for ordinary updates. Relationship/deletion paths can
  include old and new stable source references or a bounded projection selector,
  without embedding domain snapshots.
- The RAG service already owns source claims, content/dependency fingerprints,
  provider batching, current-state reloads, active-version activation, and
  Calendar effective-occurrence semantics. Extending it preserves those
  guarantees.
- When several mutations coalesce, the newest committed state is reloaded at
  execution time. If a source is already being processed, a successor work row
  may be retained rather than dropping a later mutation.

**Alternatives considered**:

- **Run the existing full/incremental CLI after every mutation**: rejected
  because it shells out, couples request code to a process, and can rebuild
  unrelated sources.
- **Call Gemini from the worker directly**: rejected because provider profile,
  batching, error mapping, and source activation belong to `RagIndexingService`.
- **Store mutation snapshots in the outbox**: rejected because snapshots become
  stale, enlarge sensitive payloads, and compete with PostgreSQL source truth.

### Scheduling and safety reconciliation

**Decision**: Make `run_after` a first-class durable field and have the
dispatcher select only due rows. Do not implement a general scheduler. Expose a
registered/manual RAG incremental-safety trigger that can later be scheduled by
staging the same job type with a future `run_after`.

**Rationale**: This supports delayed work and future periodic maintenance while
keeping the release bounded. Mutation-triggered targeted reconciliation remains
the normal path; the safety trigger reuses `RagIndexingService.run_incremental`
or `run_repair` and does not introduce a second Calendar or RAG implementation.

### Local development, dependency, and test decisions

**Decision**: Add Redis and a worker service to Compose, add a small backend
runtime image because the repository has no existing Dockerfile, add Redis/job
settings to both environment examples, and keep unit tests provider/broker
isolated with `pytest-mock`.

The feature-specific quickstart will use committed state visible across
connections and an actual local Redis instance. It will not reuse the generic
rollback-only integration fixture for the cross-process portion. Migration
tests will exercise upgrade/downgrade; unit tests will never require Docker,
Internet, Redis, or Gemini.

The only new direct production dependency is exact `arq==0.28.0`; its rationale
will be recorded beside the dependency in `backend/pyproject.toml`. Redis is
provided through ARQ's supported client dependency rather than introducing a
second queue client unless the lockfile requires an explicit direct import.

## Resolved Technical Unknowns

- Worker concurrency: configurable `BACKGROUND_WORKER_MAX_JOBS`, default 4.
- Generic job timeout: configurable `BACKGROUND_JOB_TIMEOUT_SECONDS`, default
  300 seconds; RAG provider timeout remains controlled by existing RAG settings.
- Maximum attempts: configurable `BACKGROUND_MAX_ATTEMPTS`, default 5.
- Backoff: configurable base 5 seconds, maximum 300 seconds, and bounded jitter
  of 5 seconds.
- Dispatcher batch: configurable default 50 rows and 5-second polling interval.
- Claim lease: configurable default 120 seconds; it must exceed the normal
  dispatch/claim round trip and be shorter than the maximum recovery window.
- Retention: completed records default to 7 days; dead records default to 30
  days. Both remain configurable and are never applied to active work.
- Payload limits: validate a maximum serialized application payload size of
  16 KiB and a maximum of 128 coalesced target references for the initial RAG
  contract; reject or partition larger requests rather than growing Redis or
  PostgreSQL JSON without bound.
- No HTTP administration endpoint is needed in this release. CLI commands are
  the approved operational boundary; any future endpoint must use typed,
  sanitized schemas.

All technical unknowns in the plan are resolved by these decisions. The plan
does not create a new frontend surface.
