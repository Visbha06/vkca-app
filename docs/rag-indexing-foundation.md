# Authorization-Aware RAG Indexing Foundation

This feature provides a rebuildable PostgreSQL/pgvector index over an explicit
allowlist of academy data. The relational database remains authoritative. RAG
tables are derived operational state: they never correct academy records, and
they can be reconstructed through full, targeted, incremental, or repair runs.

It does not provide a chatbot, answer generation, conversation storage, a
frontend search experience, or external-document ingestion.

## Architecture

The implementation has six boundaries:

1. A source registry opts a domain source into indexing and supplies its
   bounded loader, builder version, eligibility, dependency fingerprint, scope
   metadata, and deletion policy.
2. Source builders convert allowlisted authoritative fields into deterministic
   canonical documents. Builders have no provider, persistence, User ACL, or
   LLM access.
3. The versioned chunker preserves small structured documents and splits larger
   documents at semantic boundaries with stable ordinals, IDs, and hashes.
4. One `EmbeddingProvider` protocol owns document/query embedding, batching,
   timeout handling, validation, compatibility, and sanitized failures.
5. `RagIndexingService` reconciles source state, documents, chunks, vectors,
   leases, failures, and deletion/ineligibility without writing Business Audit
   or authentication audit events.
6. `RagRetrievalService` resolves current database authorization and applies
   the active source registry plus relational scope predicates inside the
   pgvector candidate query before cosine ordering and result limiting.

## Registered Sources

The initial registry contains exactly nine source identifiers:

- `player_profile`
- `team`
- `match`
- `match_batting_performance`
- `match_bowling_performance`
- `match_fielding_performance`
- `player_batting_stats`
- `player_bowling_stats`
- `calendar_occurrence`

`TeamPlayer` and `TeamCoach` are relationship inputs, not documents. `User`,
Calendar event definitions, recurrence rows, exceptions, authentication data,
security audit data, and Business Audit records are not registered sources.

Calendar indexing calls the existing `CalendarService` projection over its
existing 45-day maximum range. One document represents one effective
occurrence. Moved/replaced occurrences retain a stable occurrence key, deleted
or out-of-horizon occurrences are reconciled, academy timezone and scope rules
come from Calendar, and raw definitions never become standalone RAG documents.

## Canonical Documents and Chunks

A canonical document carries stable source/document identity, source and
dependency versions, normalized semantic text, structured provenance,
intrinsic Player/Team/age-group/all-academy facets, content hash, builder
version, and preparation time. Normalization fixes Unicode, whitespace,
date/time/decimal/list formatting, null omission, labels, and ordering.

The initial chunk policy is `rag-chunk-v1`. It is deterministic and bounded;
small structured documents stay intact, while continuations repeat only the
minimum identity context. A chunk stores its stable parent/ordinal identity,
safe text/hash/provenance/scope, builder/chunk versions, and compatible vector.
Unchanged compatible vectors are reused. Obsolete child chunks are replaced
atomically after a complete candidate batch validates.

## Embedding Configuration

Development uses the official Google GenAI adapter through the provider
protocol:

```dotenv
RAG_EMBEDDING_PROVIDER=gemini
RAG_EMBEDDING_MODEL=gemini-embedding-001
RAG_EMBEDDING_DIMENSION=1536
GEMINI_API_KEY=<private value>
```

Documents use `RETRIEVAL_DOCUMENT`; queries use `RETRIEVAL_QUERY`. Reduced
1536-dimensional Gemini output is manually L2-normalized for cosine search.
The adapter rejects wrong counts, dimensions, non-finite values, malformed
ordering, and partial batches. Tests and quickstart use the deterministic fake
provider and never read a real Gemini key.

Provider/model/dimension changes are explicit compatibility transitions.
Incompatible vectors are never mixed into one searchable index; use a targeted
or full rebuild, plus a migration if the stored vector dimension changes.

## PostgreSQL Persistence

Alembic revision `014_rag_indexing_foundation` enables the vector extension and
creates separate run, source-state, document, and chunk tables. Constraints
prevent duplicate source/document/chunk identities. B-tree and GIN indexes
support synchronization and relational scope facets; the `vector(1536)` cosine
HNSW index supports candidate ordering. The migration has a tested downgrade to
revision 013 and re-upgrade path.

Run/source status contains bounded counters, versions, timestamps, model
metadata, state, and sanitized failures only. It never selects or prints
canonical bodies, full chunks, vectors, credentials, or provider requests.

## Authorization Matrix

Scope is derived per request from the authenticated database `User`, current
role/activation, linked active `Player`, `TeamCoach` assignments, `TeamPlayer`
memberships, Team IDs, active assigned-Team Player IDs, and age groups. Clients
cannot submit User, Player, role, Team, age-group, or scope expansion fields.

| Viewer | Visibility |
|---|---|
| Head Coach | All eligible registered sources; inactive Player-scoped and excluded security/audit sources remain unavailable. |
| Assistant Coach | Assigned Teams, every active Player in those Teams, related permitted Match/performance/statistics context, and all-academy or assigned-age-group Calendar occurrences. |
| Linked Player | Own profile/performance/statistics plus current-team Match/Team and applicable Calendar context. |
| Unlinked Player | Empty protected result set for Player/team-specific knowledge. |
| Inactive User or linked inactive Player | No authorized retrieval result boundary. |

The SQL candidate query intersects these predicates with the active registry
before cosine ordering and `LIMIT`. Relationship, role, activation, or link
changes affect the next request without re-embedding unchanged text. Results
contain safe chunk text, source/document references, provenance, and scores—no
vectors or LLM answer.

The verification route is:

```text
GET /api/v1/rag/retrieval?query=<bounded-text>&limit=<1..20>
```

It uses the existing bearer/session authentication dependency and returns 401,
422, or a sanitized 503 as appropriate.

## Indexing, Recovery, and Status Commands

Run commands from `backend/`:

```bash
uv run python -m scripts.rag_index --mode full
uv run python -m scripts.rag_index --mode incremental
uv run python -m scripts.rag_index --mode targeted --source-type player_profile
uv run python -m scripts.rag_index --mode repair
uv run python -m scripts.rag_index --status <run-id>
```

Full traverses every registered source; targeted selects exactly one registered
type; incremental skips compatible unchanged sources and reconciles changes or
deletions; repair retries stale, failed, interrupted, or incomplete work from
committed source truth.

Claims use optimistic versions and expiring leases. Provider calls are outside
normal academy mutation transactions. If an eligible refresh fails, its last
usable document/chunks remain searchable and status records a sanitized failure.
Deletion or ineligibility deactivates derived content without needing the
provider. Re-running safely reconciles state and does not duplicate rows.

## Adding a Future Source

Create an adapter that provides:

- a lowercase source identifier and builder version;
- a bounded/set-based loader with declared dependencies;
- stable source version and dependency fingerprints;
- an allowlisted deterministic canonical builder;
- intrinsic scope metadata without User-ID ACLs;
- eligibility and missing/deletion behavior.

Register it through `RagSourceRegistry`. Registry validation rejects reserved
security/auth source names, unsafe metadata, mismatched builder output, and
obvious provider/vector/session captures. The synthetic fixture in
`backend/tests/fixtures/rag_synthetic.py` demonstrates full, targeted,
incremental, deletion, embedding, persistence, and protected retrieval without
editing the core pipeline. An unregistered SQLAlchemy model produces nothing.

## Security and Exclusions

Builders use explicit allowlists. Passwords/hashes, emails, dates of birth,
arbitrary Player JSON, tokens, sessions, CSRF data, credentials, provider
requests, raw errors, vectors, free-text performance notes, security audits,
and Business Audit payloads are excluded from provider inputs and normal
logs/status/responses. Indexing and retrieval create no Business Audit or
authentication audit events.

The feature also excludes chat UI/routes, conversations, answer generation,
streaming, prompts, external PDF/web/file ingestion, AI data correction,
user-configurable RAG permissions, hosted vector services, audit summarization,
reranking, notifications, analytics, administration UI, and automatic indexing
of future models.

## Local Verification

Start and migrate the isolated database from the repository root/backend:

```bash
docker compose --env-file .env.test up -d db
cd backend
VKCA_ENV=test uv run alembic upgrade head
VKCA_ENV=test uv run pytest tests/integration/quickstart/test_012_quickstart_flow.py -q
VKCA_ENV=test uv run pytest tests/integration/test_rag_*.py -q
uv run ruff format --check src scripts tests
uv run ruff check src scripts tests
uv run mypy src
VKCA_ENV=test uv run pytest -q
```

Run the request-level contract check from `frontend/`:

```bash
npm run lint
npm run build
npm run test:e2e -- rag-indexing-foundation-flow.spec.ts
```

Set `RAG_E2E_API_URL` and `RAG_E2E_AUTH_TOKEN` to exercise an already-seeded
live backend. Without them, the Playwright test uses its deterministic
request-contract fixture and still verifies the bearer header, bounded query,
forbidden scope absence, bounded safe response, and forbidden-result absence.

The representative performance tests record query counts, batch bounds, and a
single authorization-filtered vector candidate query as regression signals;
they intentionally do not claim a production latency SLA.
