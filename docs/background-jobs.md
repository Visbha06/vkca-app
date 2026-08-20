# Background Jobs and Reliable Processing

VKCA App uses a PostgreSQL transactional outbox, Redis, and a dedicated ARQ
worker to keep slow, retryable work outside academy mutation requests. The
initial registered workload reconciles RAG content after eligible Player, Team,
roster, coach-assignment, Match, performance, statistics, and Calendar changes.

## Architecture and durability

```text
domain service + outbox row (one PostgreSQL transaction)
    -> bounded dispatcher after commit
    -> JSON work-ID envelope in Redis/ARQ
    -> generic worker + registered handler
    -> existing RagIndexingService
```

PostgreSQL is authoritative for both academy data and durable work intent.
Redis only transports a JSON envelope containing the work ID; it does not hold
authoritative state or serialized domain snapshots. ARQ 0.28.0 is pinned because
it supplies the async Redis worker lifecycle, bounded concurrency, and enqueue
protocol without introducing another queue system. Application code owns the
outbox, validation, retries, recovery, and execution registry.

Eligible domain services stage a minimal, versioned payload before their
existing commit. Staging never commits, calls Redis, creates provider clients,
or emits technical Business/Auth Audit events. A rollback removes the intent.
Idempotency keys resolve repeated logical submissions, while coalescing merges
bounded stable source references. Work already running is not mutated; a
successor is created so the final reconciliation cannot be lost.

The dispatcher claims due rows in bounded batches with a version predicate and
short lease, commits that claim, and only then enqueues a deterministic ARQ job
ID. A broker failure leaves the row retryable in PostgreSQL. The generic worker
claims the durable row with optimistic concurrency, validates its registered
type and payload version, invokes the allowlisted handler, and persists a
completed, retrying, or dead outcome. Delivery is at least once, so handlers
must reload current source truth and be replay-safe.

## Retries, recovery, and retention

Retryable dependency, timeout, Redis, database, and bounded internal failures
use exponential backoff plus bounded jitter. Invalid payloads, unknown jobs,
incompatible versions, and permanent source failures become terminal instead
of retrying indefinitely. When the finite attempt limit is exhausted, the item
becomes `dead` and remains inspectable. Approved job definitions may be
manually requeued through the bounded operator command.

Dispatch and execution leases make claimed work recoverable after a dispatcher
or worker exits. Recovery moves expired work back to a safe retry/dead state
using its expected version. Redis downtime delays freshness but does not undo a
committed academy mutation. Completed rows default to seven days of retention;
dead rows default to 30 days. Cleanup eligibility never deletes active work.

Status projections and structured logs expose only bounded work IDs, type,
state, attempts, timestamps, safe source/correlation metadata, and sanitized
failure categories/messages. They exclude payloads, documents, vectors,
credentials, connection strings, provider responses, stack traces, leases, and
authorization scope. Technical processing creates no Business Audit or
authentication/security audit records.

## RAG synchronization

The `rag_reconciliation` definition is registered explicitly. Its payload holds
stable source type/key references or an incremental safety instruction. The
handler calls `RagIndexingService` directly; it never shells out to the RAG CLI,
calls an embedding provider directly, or maintains another dependency map.
The existing RAG registry resolves dependency closure and Calendar projected
occurrences. Execution reloads current relational rows, so an old delivery
cannot restore a stale snapshot. Existing hashes, claims, stable identities,
active-version uniqueness, provider bounds, and retrieval authorization remain
in force.

## Configuration

The environment examples contain all supported settings:

| Variable | Default | Purpose |
|---|---:|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker endpoint; never logged |
| `BACKGROUND_QUEUE_NAME` | `vkca-background` | Stable ARQ queue name |
| `BACKGROUND_WORKER_MAX_JOBS` | `4` | Worker concurrency bound |
| `BACKGROUND_JOB_TIMEOUT_SECONDS` | `300` | Per-handler timeout |
| `BACKGROUND_MAX_ATTEMPTS` | `5` | Finite dispatch/execution attempts |
| `BACKGROUND_RETRY_BASE_SECONDS` | `5` | Initial backoff |
| `BACKGROUND_RETRY_MAX_SECONDS` | `300` | Maximum backoff |
| `BACKGROUND_RETRY_JITTER_SECONDS` | `5` | Maximum jitter |
| `BACKGROUND_DISPATCH_BATCH_SIZE` | `50` | Claim batch bound |
| `BACKGROUND_DISPATCH_POLL_SECONDS` | `5` | Worker dispatcher interval |
| `BACKGROUND_CLAIM_LEASE_SECONDS` | `120` | Recovery lease |
| `BACKGROUND_COMPLETED_RETENTION_DAYS` | `7` | Completed-row retention |
| `BACKGROUND_DEAD_RETENTION_DAYS` | `30` | Dead-row retention |

Validation rejects blank identifiers, non-positive or unbounded values, and a
maximum retry delay below its base. Importing settings creates no network
client.

## Local workflow

From the repository root, start PostgreSQL and Redis, apply migrations, then
run FastAPI and the dedicated worker in separate terminals:

```bash
docker compose up -d db redis
cd backend
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

```bash
cd backend
uv run python -m scripts.background_worker
```

Alternatively, `docker compose up -d db redis worker` runs the worker in
Compose. Migration 015 must be deployed before an API or worker version that
uses `background_work_items`. Stop services with `docker compose down`; Redis
is disposable, while the PostgreSQL volume is retained unless `-v` is used.

## Operator commands

Run these from `backend/`. All limits and trigger shapes are validated.

```bash
uv run python -m scripts.background_jobs status --limit 50
uv run python -m scripts.background_jobs dispatch --limit 50
uv run python -m scripts.background_jobs recover --limit 50
uv run python -m scripts.background_jobs retry --work-id <uuid>
uv run python -m scripts.background_jobs trigger-rag \
  --source-type player_profile --source-key <stable-source-key>
uv run python -m scripts.background_jobs trigger-rag --safety
```

The existing `scripts.rag_index` full, targeted, incremental, repair, and
status commands remain independent recovery tools.

## Adding a future job

A future workload adds a strict versioned Pydantic payload, an async handler,
retry/idempotency/resource declarations, an explicit registry entry, and unit
plus integration tests. If useful, it may declare a synchronous bounded
coalescer and an allowlisted manual trigger. Core dispatcher, worker,
persistence, serialization, and recovery code should not change, and arbitrary
job names or raw JSON payloads must never become an execution path.

Run the complete executable acceptance flow with:

```bash
cd backend
VKCA_ENV=test uv run pytest \
  tests/integration/quickstart/test_013_quickstart_flow.py -q
```
