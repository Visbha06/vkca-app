# Background Processing Contracts

**Feature**: `013-background-jobs-foundation`

These are application and operator contracts for the durable processing
foundation. The feature adds no public job-management HTTP API. Any future HTTP
administration surface must use the same bounded, sanitized projections.

## Processing Boundary

```text
existing domain service
  -> stage(typed impact, same DB session)
  -> PostgreSQL commit
  -> dispatch_once()
  -> ARQ generic function(work_id)
  -> registry lookup + PostgreSQL claim
  -> registered handler(payload)
  -> existing application/RAG service
```

The only authoritative handoff is the committed PostgreSQL work row. Redis and
ARQ carry an execution reference and may deliver it more than once.

## Domain-to-Outbox Contract

Conceptual internal operation:

```text
stage_background_work(
    session,
    job_type,
    payload,
    *,
    idempotency_key,
    coalescing_key,
    correlation_id=None,
    source_type=None,
    source_key=None,
    run_after=None,
) -> BackgroundWorkItem
```

Preconditions:

- `job_type` is registered and the payload model/version validates.
- The caller owns the existing academy-domain transaction.
- IDs and safe metadata are bounded; no snapshots, secrets, client scope, or
  raw derived content are accepted.

Effects:

- Adds or safely coalesces one PostgreSQL work row in the caller's transaction.
- Does not commit, contact Redis, contact an embedding provider, or create
  Business/Auth Audit records.
- A duplicate idempotency key returns the existing logical row.
- A pending/scheduled/retrying/dispatched row with the same coalescing key may
  receive a bounded union of stable targets using an OCC update. If the work is
  already running, the caller creates a successor intent rather than changing
  the in-flight payload.
- The caller's rollback removes the staged work intent with the domain change.

## Generic Job Definition Contract

Each registry entry supplies:

| Field | Meaning |
|---|---|
| `job_type` | Stable lowercase identifier. |
| `payload_version` and schema | Explicit Pydantic validation contract. |
| `handler` | Async function that receives startup-owned resources and validated payload. |
| `retry_policy` | Retry categories, maximum attempts, backoff, jitter, and timeout. |
| `idempotency_strategy` | Why replay is safe and what current state is reloaded. |
| `coalescer` | Optional bounded merge rule and logical key. |
| `resource_limits` | Worker concurrency/provider/batch constraints. |
| `manual_trigger` | Optional allowlisted operator entry point; no arbitrary payload execution. |

Unknown job types are never dynamically imported or executed.

## ARQ Envelope Contract

The dispatcher enqueues one registered ARQ function with a JSON-compatible
envelope equivalent to:

```json
{
  "contract_version": 1,
  "work_id": "00000000-0000-4000-8000-000000000000"
}
```

The worker configures a custom JSON serializer/deserializer. The default ARQ
pickle serializer is prohibited. The queue envelope contains no domain object,
ORM snapshot, provider credential, RAG document, vector, role, or team scope.

The deterministic ARQ job ID is derived from `work_id`. This reduces duplicate
queue entries after dispatcher retries but does not weaken the at-least-once
handler contract.

## Initial `rag_reconciliation` Payload Contract

Payload version 1:

```json
{
  "mode": "targets",
  "reason": "mutation",
  "targets": [
    {
      "source_type": "player_profile",
      "source_key": "00000000-0000-4000-8000-000000000000"
    }
  ]
}
```

Allowed values:

- `mode`: `targets` or `incremental_safety`.
- `reason`: `mutation`, `manual`, `repair`, or `safety`.
- `targets`: bounded stable references to registered RAG source identities.
  `incremental_safety` may use an empty target list.
- Each source type and key is validated; current rows are reloaded at handler
  execution time.

The shared RAG impact/dependency resolver may expand a target to Team, Player,
Match, performance, statistics, or Calendar dependents. The background layer
does not store or calculate the dependency graph itself.

Calendar target resolution uses the existing `CalendarService` projected
effective occurrences, exception rules, timezone, scope, stable occurrence
identity, and bounded horizon.

## Dispatcher Contract

Conceptual operation:

```text
dispatch_once(now=None, limit=50) -> DispatchReport
```

Behavior:

1. Select only committed due rows in `pending`, `scheduled`, or `retrying`
   state, plus expired recoverable claims, in a bounded batch.
2. Claim with a short lease and expected `version_number`.
3. Commit the claim before contacting Redis.
4. Enqueue the generic ARQ envelope with deterministic `_job_id`.
5. Mark `dispatched` with the expected version and lease.
6. On temporary broker failure, persist sanitized failure and `retrying` with
   bounded `run_after`; leave the domain rows untouched.
7. On a claim conflict, skip/reload; never write over the winner.

`DispatchReport` contains counts and safe IDs/categories only:

```json
{
  "claimed": 2,
  "enqueued": 1,
  "retrying": 1,
  "conflicts": 0,
  "work_ids": ["00000000-0000-4000-8000-000000000000"]
}
```

## Worker Contract

The worker registers only the generic function `run_background_work`. Its
startup context contains explicitly created settings, database session
factory, Redis pool, embedding provider seam, registry, retry policy, and safe
logger. Resources are closed by the worker shutdown hook.

Conceptual operation:

```text
run_background_work(ctx, work_id) -> None
```

Behavior:

1. Load the PostgreSQL row by ID and reject an unknown/malformed envelope.
2. Claim only an eligible `dispatched` or recovered row with OCC and a lease.
3. Validate the stored job type/version/payload against the registry.
4. Mark `running`, invoke the registered handler, and never call HTTP routes.
5. Record `completed`, `retrying`, or `dead` with a matching version/lease.
6. On timeout/cancellation/crash, let the lease/retry path reclaim the work.
7. Return no sensitive result to ARQ; job results are not an operational source
   of truth and are not retained by the worker.

## Failure Categories and Retry Contract

| Category | Default classification | Behavior |
|---|---|---|
| `transient_dependency_failure` | Retryable | Persist next `run_after`; bounded exponential backoff with jitter. |
| `timeout` | Retryable when handler is replay-safe | Persist retry/dead according to attempt limit. |
| `redis_unavailable` | Retryable | Keep PostgreSQL work eligible; dispatcher retries later. |
| `database_unavailable` | Retryable if no authoritative mutation is in progress | Let the work lease expire or retry after connection recovery. |
| `invalid_payload` | Terminal | Mark `dead`; no handler execution. |
| `unregistered_job` | Terminal | Mark `dead`; no dynamic dispatch. |
| `incompatible_payload_version` | Terminal until code/operator repair | Mark `dead` with upgrade/repair guidance. |
| `permanent_domain_source_failure` | Terminal or safe no-op | Never retry indefinitely; preserve safe source status. |
| `unexpected_internal_error` | Bounded retry | Dead after the configured limit with sanitized message. |
| `retry_limit_exhausted` | Terminal | Keep inspectable and manually retryable only when the job definition allows it. |

Raw exception text, stack traces, provider responses, connection strings, and
serialized payloads are excluded from status and structured logs.

## Operator Command Contract

Commands run from `backend/` and return bounded JSON/text summaries:

| Command | Purpose |
|---|---|
| `uv run python -m scripts.background_worker` | Start the dedicated ARQ worker. |
| `uv run python -m scripts.background_jobs status --limit 50` | Inspect pending, dispatched, running, retrying, completed, or dead counts and safe rows. |
| `uv run python -m scripts.background_jobs dispatch --limit 50` | Run one bounded dispatcher batch. |
| `uv run python -m scripts.background_jobs recover --limit 50` | Reclaim expired dispatcher/worker leases. |
| `uv run python -m scripts.background_jobs retry --work-id <uuid>` | Requeue one eligible dead work item with OCC and manual-retry bounds. |
| `uv run python -m scripts.background_jobs trigger-rag --source-type <registered> --source-key <key>` | Create an approved targeted RAG reconciliation intent. |
| `uv run python -m scripts.background_jobs trigger-rag --safety` | Create the approved incremental/repair safety intent. |

The commands reject unknown job/source types, arbitrary user scope, raw JSON
payload injection, and unbounded limits. Existing `scripts.rag_index` commands
remain available for full, targeted, incremental, repair, and status RAG
recovery.

## Configuration Contract

| Environment variable | Default/constraint |
|---|---|
| `REDIS_URL` | Local Redis URL; required by dispatcher/worker, never logged. |
| `BACKGROUND_QUEUE_NAME` | Stable bounded queue name. |
| `BACKGROUND_WORKER_MAX_JOBS` | Positive bounded concurrency; local default 4. |
| `BACKGROUND_JOB_TIMEOUT_SECONDS` | Positive bounded default 300. |
| `BACKGROUND_MAX_ATTEMPTS` | Finite default 5. |
| `BACKGROUND_RETRY_BASE_SECONDS` | Positive default 5. |
| `BACKGROUND_RETRY_MAX_SECONDS` | Bounded default 300. |
| `BACKGROUND_RETRY_JITTER_SECONDS` | Bounded default 5. |
| `BACKGROUND_DISPATCH_BATCH_SIZE` | Positive bounded default 50. |
| `BACKGROUND_DISPATCH_POLL_SECONDS` | Positive bounded default 5. |
| `BACKGROUND_CLAIM_LEASE_SECONDS` | Positive bounded default 120. |
| `BACKGROUND_COMPLETED_RETENTION_DAYS` | Positive default 7. |
| `BACKGROUND_DEAD_RETENTION_DAYS` | Positive default 30. |

Settings validation rejects blank URLs, non-positive values, a retry maximum
below its base delay, and unbounded limits. Settings import does not create
Redis, provider, or worker clients.

## Audit and Authorization Contract

- Technical staging, dispatch, enqueue, worker claim, retry, completion, dead
  transition, requeue, and RAG reconciliation create no Business Audit or
  authentication/security audit event.
- User authorization is enforced before a user-triggered mutation stages work.
  Background work never impersonates that user or trusts client-provided scope.
- System/operator commands have explicit trusted-system semantics and can only
  trigger allowlisted registered jobs.
- RAG retrieval continues to derive authorization from current relational state;
  work payloads never contain authorization ACLs.
