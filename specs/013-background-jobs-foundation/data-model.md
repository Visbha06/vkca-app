# Background Jobs and Reliable Processing Foundation Data Model

**Feature**: `013-background-jobs-foundation`
**Migration**: `015_background_processing_foundation.py` (planned)

This model adds technical processing state only. It does not add a second
academy-data record, user-owned job, authorization snapshot, or RAG source
model.

## Persistent Entity: `BackgroundWorkItem`

`BackgroundWorkItem` is the PostgreSQL transactional-outbox row and the
durable application-level job state. It is intentionally separate from
`DataSyncLog`, `BusinessAuditEvent`, `AuthAuditLog`, `RagIndexRun`, and
`RagSourceState`.

| Field | Type/shape | Rules and purpose |
|---|---|---|
| `id` | UUID | Stable work identity and ARQ deduplication identity. Primary key. |
| `job_type` | bounded lowercase string | Must be registered before dispatch or execution. Initial value is `rag_reconciliation`. |
| `payload_version` | positive small integer | Selects the typed JSON payload schema. Unknown versions are terminal failures without handler execution. |
| `payload` | bounded JSON object | Validated by the registered job definition. Contains IDs/instructions, never snapshots, secrets, documents, vectors, or client scope. |
| `state` | `BackgroundWorkState` | One of `pending`, `scheduled`, `dispatching`, `dispatched`, `running`, `retrying`, `completed`, or `dead`. |
| `idempotency_key` | bounded string, nullable | Stable identity for a duplicate logical request. Unique per job type when present. |
| `coalescing_key` | bounded string, nullable | Logical reconciliation identity, such as one registered source target. At most one non-running active row owns a key. |
| `correlation_id` | UUID, nullable | Safe request/operation correlation only; never a session, token, or authorization snapshot. |
| `source_type` | bounded string, nullable | Safe registered source family for operator filtering. It is not trusted as a handler allowlist. |
| `source_key` | bounded string, nullable | Safe stable source identity for operator filtering. It is not a domain snapshot. |
| `safe_metadata` | bounded JSON object | Allowlisted operational metadata only; no arbitrary client data. |
| `run_after` | timezone-aware timestamp | Earliest durable eligibility time. Future work is `scheduled`; due work may be `pending` or `retrying`. |
| `dispatch_attempt_count` | non-negative integer | Number of dispatcher attempts, including broker failures. |
| `execution_attempt_count` | non-negative integer | Number of worker handler claims/attempts. Used with the shared finite retry policy. |
| `manual_retry_count` | non-negative integer | Number of operator requeues; bounded by the recovery command/policy. |
| `arq_job_id` | bounded string, nullable | Last deterministic ARQ queue identity. This is coordination metadata, not the durable work identity. |
| `lease_owner` | bounded string, nullable | Opaque dispatcher/worker instance identity. Must not contain credentials or host secrets. |
| `lease_expires_at` | timezone-aware timestamp, nullable | Recovery boundary for a dispatch or worker claim. Expired leases are reclaimable. |
| `last_attempt_at` | timezone-aware timestamp, nullable | Last dispatch or execution attempt timestamp. |
| `dispatched_at` | timezone-aware timestamp, nullable | Time a dispatcher recorded successful enqueue. |
| `started_at` | timezone-aware timestamp, nullable | Time a worker recorded a running claim. |
| `completed_at` | timezone-aware timestamp, nullable | Time successful completion was recorded. |
| `terminal_at` | timezone-aware timestamp, nullable | Time a non-retryable or exhausted failure became `dead`. |
| `last_failure_category` | bounded string, nullable | Sanitized category from the shared failure taxonomy. |
| `last_failure_message` | bounded string, nullable | Short sanitized operator message; no raw exception or provider response. |
| `manual_retry_allowed` | boolean | Explicitly records whether the registered job permits bounded manual recovery. |
| `retention_until` | timezone-aware timestamp, nullable | Cleanup eligibility. Active work has no cleanup eligibility. |
| `version_number` | positive integer | OCC state version. Every competing state/payload/lease transition increments it. Reuses `VersionMixin` semantics. |
| `created_at`, `updated_at` | timezone-aware timestamps | Standard repository timestamp behavior. |

### Persistence constraints and indexes

- `idempotency_key` is unique within `job_type` when non-null. A duplicate
  request resolves the existing logical row rather than creating a second
  executable identity.
- `coalescing_key` has a partial unique index for non-null keys in
  `pending`, `scheduled`, `dispatching`, `dispatched`, and `retrying` states.
  `running` is deliberately excluded so a later mutation can create a
  successor row when the current execution has already claimed its payload.
- An eligible-work index covers `(state, run_after, created_at)` for the
  dispatcher's bounded batch query.
- A recovery index covers `(state, lease_expires_at)` for expired dispatch and
  worker claims.
- A retention index covers `(state, retention_until)` for bounded cleanup.
- Check constraints enforce positive versions, non-negative counters, bounded
  state values, non-blank registered identifiers, and valid timestamp ordering
  where practical. Application validation enforces the 16 KiB serialized JSON
  limit and safe metadata allowlist before insert/update.
- No polymorphic foreign key points at Player, Team, Match, Calendar, RAG, or
  audit rows. The safe source identifiers are instructions for re-resolution;
  they do not own or preserve authoritative rows.
- No JSONB index is required for payload inspection. Operators filter on typed
  columns and bounded safe metadata rather than querying arbitrary payload
  content.

## In-memory Entity: `BackgroundJobDefinition`

The registry stores one typed definition per executable job type. It is not a
database row and is loaded explicitly by the worker/dispatcher runtime.

| Member | Contract |
|---|---|
| `job_type` | Lowercase stable identifier; duplicate registration is an error. |
| `payload_version` / `payload_model` | Pydantic model/version pair used for JSON validation. |
| `handler` | Async application handler receiving a startup-owned runtime context and validated payload. |
| `retry_classifier` | Maps known exceptions/outcomes to retryable, terminal, or safe-no-op behavior. |
| `retry_policy` | Maximum attempts, backoff bounds, jitter, and timeout. |
| `idempotency_strategy` | Explains how the handler treats repeated delivery. |
| `coalescer` | Optional bounded merge strategy for logical work that is not yet running. |
| `concurrency_key` / `resource_limits` | Optional stricter semaphore or provider/batch bound. |
| `timeout_seconds` | Positive finite execution limit. |
| `manual_trigger` | Optional allowlisted operator trigger; absent means no manual arbitrary payload trigger. |

The runtime executes only definitions in this registry. It never imports a
handler based on a client-supplied module path or arbitrary function name.

## In-memory Entity: `BackgroundJobEnvelopeV1`

The Redis/ARQ message contains only a bounded JSON-compatible reference:

```json
{
  "contract_version": 1,
  "work_id": "00000000-0000-4000-8000-000000000000"
}
```

The dispatcher uses the work ID as the deterministic ARQ `_job_id`. The generic
registered ARQ function loads the row, validates the state/version/lease, and
then validates the PostgreSQL payload against the registry. No Python pickle,
ORM object, provider credential, raw vector, or full RAG document crosses the
queue boundary.

## In-memory Entity: `RagReconciliationPayloadV1`

The first registered job's durable payload is a bounded JSON object:

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
- `targets`: zero to 128 `RagTargetRef` values for `incremental_safety`, and
  one or more registered stable references for `targets`.
- `RagTargetRef.source_type`: must resolve through `RagSourceRegistry`.
- `RagTargetRef.source_key`: non-blank bounded identity, not a serialized row.

The RAG handler delegates to a targeted/reconciliation method on
`RagIndexingService`. That method reloads current rows, resolves declared
dependency closure, honors eligibility/deletion policy, and uses existing
fingerprints, claims, provider limits, and active-version behavior. The
payload never asserts the final content.

## In-memory Entity: `RagMutationImpact`

Existing mutation services construct a small impact description before their
existing commit:

- operation reason;
- one or more registered source references or relationship-derived stable IDs;
- old/new stable references when a deletion or relationship replacement makes
  both sides necessary;
- safe correlation ID if already available.

The shared RAG impact/dependency resolver, not the background worker, maps the
impact to registered source/dependency targets. A relationship row such as
`TeamPlayer` or `TeamCoach` is not itself a RAG document. Account/auth changes
only create RAG work when the registry explicitly declares a semantic source
impact; live retrieval authorization remains relational and request-time.

## State Machine

| From | Event/guard | To | Required protection |
|---|---|---|---|
| none | Valid service mutation stages work in the same DB transaction | `pending` or `scheduled` | Same transaction as domain mutation; rollback removes both. |
| `pending`/`retrying`/`scheduled` | `run_after <= now` and dispatcher claims a row | `dispatching` | Short lease, expected `version_number`, bounded batch. |
| `dispatching` | Redis enqueue succeeds | `dispatched` | Expected version and matching lease; store deterministic ARQ ID. |
| `dispatching` | Redis unavailable or enqueue fails | `retrying` | Sanitized failure, bounded backoff, version check; durable row remains. |
| `dispatching` | Lease expires | `pending`/`retrying` | Recovery transition only if lease/version still matches. |
| `dispatched` | Generic worker claims due row | `running` | Expected version, state, and lease predicate. |
| `running` | Handler reconciles successfully | `completed` | Expected version and worker lease; set retention. |
| `running` | Retryable failure and attempts remain | `retrying` | Persist category/backoff before ARQ retry/defer. |
| `running` | Non-retryable or exhausted failure | `dead` | Persist sanitized terminal state; no silent disappearance. |
| `running` | Worker crashes/timeouts | `dispatched`/`retrying` after lease recovery | Expired lease makes the work claimable; stale worker cannot complete it. |
| `dead` | Approved bounded manual retry | `pending` | Operator command validates job definition and increments manual retry count with OCC. |
| `completed`/`dead` | Retention cleanup becomes eligible | removed/archived by bounded cleanup | Never remove active work; dead retention exceeds completed retention. |

There is no separate generic `cancelled` state in this release. Cancellation
would need an explicit safe use case and a state transition that cannot strand
an in-flight handler.

## Transaction and Ownership Rules

1. Domain application services validate and mutate authoritative rows, stage
   normal Business Audit work where their current rules require it, stage a
   background intent, and commit once.
2. The staging service performs no Redis, ARQ, Gemini, or other network call and
   emits no audit event.
3. The dispatcher claims and commits a short PostgreSQL lease, performs Redis
   enqueue outside that transaction, then records success/failure with OCC.
4. The worker claims and commits a short PostgreSQL execution lease, invokes
   the registered handler, and records completion/retry/dead state with OCC.
5. The RAG handler may use its existing short derived-state transactions and
   provider calls, but never mutates authoritative academy rows.
6. Any failed OCC update reloads the row and chooses a safe no-op/retry/recovery
   path. It never overwrites a newer payload, lease, or terminal state.

## Retention and Privacy

- Completed rows are eligible for cleanup after the configured completed
  retention period; dead rows use the longer dead retention period.
- Retention cleanup is bounded, state-filtered, and itself must use OCC or a
  safe terminal predicate. It is not required to be scheduled automatically in
  this feature.
- Status/log projections expose IDs, job types, states, attempts, timestamps,
  failure categories, and safe source/correlation fields only.
- Payloads and logs exclude passwords, hashes, tokens, sessions, CSRF values,
  provider/database credentials, audit records, unrestricted role/team scope,
  full RAG documents, and raw vectors.
