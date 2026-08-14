# Quickstart: Background Jobs and Reliable Processing Foundation

This guide validates the durable outbox, Redis/ARQ worker, retry/recovery
behavior, and automatic RAG reconciliation against the repository's existing
PostgreSQL/pgvector and protected retrieval boundaries. It does not add a jobs
dashboard or chatbot UI.

## Prerequisites

- Docker and Docker Compose.
- Python 3.12+, `uv`, Node.js/npm, and installed project dependencies.
- A test-only `.env.test` copied from `.env.test.example`.
- A test-only PostgreSQL database exposed on the repository's configured port.
- No Gemini credential or Internet access for unit tests; the deterministic
  fake embedding provider is used by the quickstart.
- Redis is local and disposable for integration validation. The worker must
  use `REDIS_URL=redis://127.0.0.1:6379/0` when run on the host, or the Compose
  service hostname when run inside Compose.

## Start local infrastructure

From the repository root, after the feature's Compose changes are present:

```bash
docker compose --env-file .env.test up -d db redis
docker compose --env-file .env.test ps
```

Expected result: the PostgreSQL/pgvector `db` service and Redis service are
healthy. Redis is an execution dependency only; no academy records are stored
there.

To run the dedicated worker as a Compose service instead of a host process:

```bash
docker compose --env-file .env.test up -d db redis worker
```

The API may continue to run from the host during local development:

```bash
cd backend
uv sync --all-groups
VKCA_ENV=test uv run alembic upgrade head
VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
```

In another terminal, when not using the Compose worker:

```bash
cd backend
VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run python -m scripts.background_worker
```

## Migration validation

Run the migration test against an isolated PostgreSQL schema/database:

```bash
cd backend
VKCA_ENV=test uv run pytest tests/integration/test_background_job_migration.py -q
```

The test must upgrade to the background-processing revision, verify tables,
constraints, partial indexes, JSON/payload bounds, OCC columns, and then
downgrade and upgrade again. No manual schema edits are part of the workflow.

## Required feature quickstart test

Run:

```bash
cd backend
VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run pytest tests/integration/quickstart/test_013_quickstart_flow.py -q
```

The test uses committed state visible across independent database sessions and
an isolated cleanup boundary. It must not rely on the generic rollback-only
fixture for the cross-connection dispatch/worker assertions.

The executable flow covers these stages:

1. Start isolated PostgreSQL and Redis.
2. Apply the background-processing migration(s).
3. Start or instantiate the dispatcher/worker test boundary.
4. Seed representative Player, Team, roster, coach-assignment, Match,
   performance, statistics, and Calendar data through existing services.
5. Create or update an eligible RAG-backed source through its normal
   application-service/API flow.
6. Verify the authoritative domain transaction commits.
7. Verify a durable pending or safely coalesced outbox work item exists.
8. Delay/fail the fake provider and verify the request does not wait for
   embedding generation.
9. Dispatch the committed work to Redis using the bounded dispatcher.
10. Execute the work through the registered generic ARQ handler.
11. Verify RAG reconciliation reaches the newest committed source state.
12. Verify protected retrieval reflects the updated source and current
    authorization scope.
13. Perform multiple rapid mutations and verify bounded deduplication/
    coalescing without losing the final reconciliation.
14. Simulate provider failure and verify sanitized bounded retry state.
15. Restart/recreate the worker or expire its lease and verify work remains
    recoverable.
16. Restore the provider and verify eventual successful reconciliation.
17. Verify no duplicate RAG documents, chunks, embeddings, or active versions.
18. Verify no unintended Business Audit or authentication/security audit
    entries were created by technical processing.
19. Inspect safe job/outbox status and exercise an approved bounded retry or
    recovery command.
20. Verify no sensitive payload, result, or structured-log leakage.

The test also covers rollback: a validation/OCC failure or explicit transaction
rollback must leave zero executable work intent. A Redis outage must leave the
domain mutation committed and the PostgreSQL work row eligible for later
dispatch.

## Operator command checks

With the worker stopped or running, validate bounded operational commands:

```bash
cd backend
VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run python -m scripts.background_jobs status --limit 50

VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run python -m scripts.background_jobs dispatch --limit 50

VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run python -m scripts.background_jobs recover --limit 50
```

For a seeded registered source, use only the approved trigger shape:

```bash
VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run python -m scripts.background_jobs trigger-rag \
  --source-type player_profile --source-key <stable-source-key>

VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run python -m scripts.background_jobs trigger-rag --safety
```

Verify that output contains bounded counts, IDs, states, attempts, timestamps,
and sanitized failure categories only. It must not contain payload JSON,
semantic document text, vectors, credentials, tokens, or user scope.

The existing RAG recovery CLI remains independent and must still work:

```bash
VKCA_ENV=test RAG_EMBEDDING_PROVIDER=fake \
  uv run python -m scripts.rag_index --mode incremental
VKCA_ENV=test RAG_EMBEDDING_PROVIDER=fake \
  uv run python -m scripts.rag_index --mode repair
```

## Focused quality checks

```bash
cd backend
uv run pytest tests/unit/test_background_jobs_contracts.py \
  tests/unit/test_background_jobs_registry.py \
  tests/unit/test_background_jobs_retry.py \
  tests/unit/test_background_jobs_outbox.py \
  tests/unit/test_background_jobs_redaction.py -q

VKCA_ENV=test REDIS_URL=redis://127.0.0.1:6379/0 \
  uv run pytest tests/integration/test_background_outbox.py \
  tests/integration/test_background_dispatch.py \
  tests/integration/test_background_worker.py \
  tests/integration/test_background_rag_reconciliation.py -q

uv run ruff check src tests
uv run mypy src
```

Run the required request-level Playwright journey from `frontend/` after the
API and worker are available:

```bash
BACKGROUND_JOBS_E2E_API_URL=http://127.0.0.1:8000 \
  npm run test:e2e -- background-jobs-foundation-flow.spec.ts
```

The test uses the existing authenticated Player/team mutation boundary and then
the protected RAG retrieval boundary. It does not add a frontend jobs page. A
deterministic mocked boundary may be used when no API URL is configured, while
the configured integration run must verify the real committed mutation and
eventual retrieval result.

## Expected completion signals

- Migration 015 upgrades/downgrades safely and all required indexes/constraints
  exist.
- Valid domain commits always leave durable or safely coalesced work; rollbacks
  leave none.
- Redis downtime delays background freshness but does not roll back academy
  data.
- Duplicate delivery and worker restart produce no duplicate active RAG state.
- Current source truth, RAG dependency closure, and Calendar effective
  occurrences are reconciled without a full unrelated corpus rebuild.
- Provider failure produces bounded retry/dead state with a safe prior RAG
  version where the existing service supports it.
- Technical processing creates no Business/Auth Audit records.
- Status, logs, payloads, and retrieval responses exclude sensitive data.
- Unit tests run offline; integration/quickstart and the configured Playwright
  journey pass with the local services and deterministic provider.
