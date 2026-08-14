# RAG Indexing Foundation Research

**Feature**: \`012-rag-indexing-foundation\`  
**Date**: 2026-08-13

This research resolves the provider, persistence, authorization, Calendar, and
operational integration decisions required by the implementation plan. It is
based on the clarified specification and the current repository.

## Decision Summary

| Area | Decision | Consequence |
|---|---|---|
| Initial embedding provider | Google GenAI SDK with Gemini \`gemini-embedding-001\` | Provider-specific code is isolated behind \`EmbeddingProvider\`; tests use a fake provider. |
| Vector dimension | 1536 | The migration creates \`vector(1536)\` and rejects any configured mismatch before indexing. |
| Similarity | Cosine distance with normalized vectors | Use pgvector cosine operators and an HNSW index. |
| Source extension | Explicit registry of source definitions and adapters | Unregistered SQLAlchemy models remain excluded. |
| Calendar source | \`calendar_occurrence\` | Raw event definitions are projection inputs; effective occurrences are the indexed entities. |
| Authorization | Request-time \`RagAccessScope\` derived from the authenticated database \`User\` and current relationships | No User-ID allowlists are stored in vector records. |
| Operational state | RAG-specific run/source-state tables | \`DataSyncLog\` remains unchanged because it cannot represent model compatibility, counters, leases, or preserved prior results. |
| Retrieval boundary | Shared service plus a small authenticated retrieval route for integration verification | No unrestricted vector-search endpoint and no LLM answer generation. |
| Provider transaction boundary | Provider calls occur outside academy mutation transactions and outside the short derived-state activation transaction | Provider outages produce recoverable stale/failed index state without rolling back domain writes. |

## Repository Findings

- The backend is Python 3.12+, FastAPI, async SQLAlchemy 2, asyncpg, Pydantic
  Settings, and Alembic. Runtime code is under \`backend/src\`; operator scripts
  are under \`backend/scripts\`.
- The current Alembic head is revision \`013\`, with migrations under
  \`backend/src/migrations/versions\`. The next migration is
  \`014_rag_indexing_foundation.py\` and must be reversible where practical.
- PostgreSQL is provided by \`pgvector/pgvector:pg16\`; \`pgvector\` is already a
  locked backend dependency. The new migration should enable the \`vector\`
  extension through the normal migration path.
- \`Settings\` currently reads the project-root \`.env\` or \`.env.test\`, selected by
  \`VKCA_ENV\`. New Gemini and RAG settings must follow that mechanism and must
  use a safe placeholder in both example files.
- \`get_current_user\` authenticates against the current \`User\` and active
  \`AuthSession\`, checks \`User.is_active\`, and applies the existing linked
  Player-profile authentication rule. \`require_role\` reads the current
  database role rather than trusting a JWT role claim.
- \`DashboardService._resolve_scope\` is the existing role-scope seam. It derives
  Head Coach academy scope, Assistant Coach \`TeamCoach\` scope, and linked
  Player \`TeamPlayer\` scope. RAG should extract the relationship logic into a
  reusable scope resolver rather than copy a dashboard-only implementation.
- \`CalendarService.get_range()\` projects bounded effective occurrences and
  returns stable occurrence identities. \`calendar_recurrence.py\` owns the
  \`America/Los_Angeles\` timezone and 45-day maximum; the RAG Calendar adapter
  must call that service rather than duplicate recurrence arithmetic.
- \`DataSyncLog\` stores only a source, status, target table, one error message,
  and timestamps. It cannot safely represent source fingerprints, provider
  model/dimension, run counters, leases, or last-usable-derived-state
  semantics.
- \`BusinessAuditService\` is reserved for successful academy-domain mutations;
  \`AuditService\` writes the separate authentication/security log. RAG
  preparation, embedding, synchronization, retrieval, and repair must use
  neither writer.
- Integration tests use the rollback-only PostgreSQL fixture in
  \`backend/tests/integration/conftest.py\`; feature quickstart tests follow the
  \`test_<number>_quickstart_flow.py\` convention. Existing Calendar and
  role-aware dashboard tests provide fixtures for effective occurrences,
  assignments, memberships, query bounds, and no-audit read behavior.

## Provider and Embedding Decisions

### Gemini SDK and provider boundary

Use the official \`google-genai\` package and its \`google.genai\` namespace for
the initial adapter. Google’s current migration guidance identifies this SDK as
the replacement for the deprecated \`google-generativeai\` package and shows
\`client.models.embed_content\` for \`gemini-embedding-001\`.

Only the adapter knows Gemini request formats, credentials, task types, SDK
exceptions, and timeout options. The shared provider protocol reports provider,
model, dimension, and adapter version. Builders, persistence models, retrieval
scope logic, and domain mutation services never import the SDK.

**Alternatives considered**:

- \`google-generativeai\`: rejected because Google’s migration documentation
  directs new Python integrations to \`google-genai\`.
- Raw REST with the existing HTTP stack: viable, but deferred because it would
  duplicate request/response and retry handling in the first implementation.
- Vertex AI/ADC: deferred because the repository has no Google Cloud project or
  ADC configuration.
- Gemini Batch API: deferred until corpus scale justifies asynchronous batch
  jobs; the foundation uses bounded inline batches with recoverable state.

### Vector profile

Configure \`gemini-embedding-001\` with \`output_dimensionality=1536\`. Google’s
model documentation lists 1536 as a recommended output size. The selected size
also remains within pgvector’s ordinary indexed \`vector\` dimension support. For
\`gemini-embedding-001\`, reduced dimensions require manual L2 normalization, so
the adapter normalizes finite vectors before returning them.

\`\`\`text
provider: gemini
model: gemini-embedding-001
dimension: 1536
document task: RETRIEVAL_DOCUMENT
query task: RETRIEVAL_QUERY
similarity: cosine
\`\`\`

The vector column, provider response validation, and persisted model profile
must all agree on 1536. Changing provider/model at the same dimension still
requires a full or targeted re-embedding because vectors are not semantically
interchangeable. Changing dimension requires a migration/rebuild path and must
fail before mixed vectors become searchable.

**Alternatives considered**:

- 3072: rejected for the initial standard \`vector\` HNSW index because the
  selected pgvector index type has a 2,000-dimension limit.
- 768: compatible and recommended, but 1536 is the chosen quality/storage
  compromise for this foundation.

### Batching and failures

Define a typed provider protocol with bounded batch embedding, query embedding,
timeouts, sanitized exceptions, model/version reporting, finite-value checks,
and response count/dimension validation. Use \`RETRIEVAL_DOCUMENT\` for indexed
chunks and \`RETRIEVAL_QUERY\` for search queries. A deterministic fake provider
returns stable 1536-dimensional vectors for tests.

The adapter preserves input order, retries only bounded transient failures, and
persists no partial malformed batch. Provider calls never occur inside the
transaction that commits a Player, Team, Match, performance, statistics,
Calendar, User, roster, or assignment mutation.

## Persistence and Synchronization Decisions

### Complete derived-version activation

Source preparation and provider calls produce an in-memory candidate. The
indexer activates a document/chunk set only after every required embedding in
the candidate batch has passed validation. \`RagSourceState\` records the latest
observed source fingerprint and failure, while the previous active document and
chunks remain searchable if an eligible refresh fails.

Deletion or loss of eligibility is different: old derived rows become
non-searchable even when a provider is unavailable.

### RAG-specific operational tables

Create separate run, per-source state, canonical document, and embedded chunk
models. Store technical counters as typed columns and sanitized failure
categories/messages rather than overloading \`DataSyncLog\` or Business Audit.
Use optimistic version/claim fields so two indexing commands cannot activate a
stale candidate over a newer source state.

### pgvector cosine HNSW

Use \`pgvector.sqlalchemy.Vector(1536)\` and a cosine HNSW index with
\`vector_cosine_ops\`. Add B-tree indexes for source/state/model lookups and GIN
indexes for denormalized \`player_ids\`, \`team_ids\`, and \`age_groups\` scope
arrays. The retrieval SQL must include the current user’s authorization
predicate in the same candidate query as the vector ordering.

## Source Registry and Calendar Decisions

The initial registry contains exactly:

\`\`\`text
player_profile
team
match
match_batting_performance
match_bowling_performance
match_fielding_performance
player_batting_stats
player_bowling_stats
calendar_occurrence
\`\`\`

Each entry declares its source key strategy, set-based loader, builder/schema
version, eligibility rule, relationship dependencies, authorization facet
builder, and deletion reconciliation. A future model must register an entry;
SQLAlchemy model discovery is never used as an implicit allowlist.

The Calendar entry calls \`CalendarService.get_range()\` over the existing
bounded horizon, converts each returned \`CalendarEventInstance\` into one
canonical document, and uses its stable \`occurrence_id\` as the source key.
Event definitions, recurrence rows, and exception rows are dependencies, not
independent documents. A moved occurrence retains its original occurrence
identity while its effective date/content is reconciled; deleted and
out-of-horizon occurrences are removed from the active derived set.

## Authorization Decisions

\`RagAccessScope\` is resolved from the authenticated database \`User\` on every
retrieval request:

- Head Coach: all eligible registered source content.
- Assistant Coach: current \`TeamCoach\` Teams, every active Player currently in
  those Teams, and the source-specific Match, performance, statistics, Team,
  and Calendar context allowed by the matrix.
- Linked Player: the linked active Player, current \`TeamPlayer\` Teams, and only
  the permitted self/team context.
- Unlinked Player: no Player/team-specific results and no academy-wide fallback.

User IDs are never copied into index rows. Chunks carry intrinsic source facets
(\`player_ids\`, \`team_ids\`, \`age_groups\`, \`is_all_academy\`), while current
membership, assignment, role, link, and active-state joins are resolved at
request time. The retrieval query is constructed with those predicates before
the vector result set is returned.

## Transaction and Concurrency Decisions

Normal domain mutations do not invoke the provider. Index commands operate from
committed source state and use short derived-state transactions for claims and
activation. A source fingerprint/version is rechecked before activation; if it
changed during embedding, the candidate is discarded or marked stale for the
next run. This satisfies the project’s optimistic-concurrency principle while
preserving the last usable embedding during provider failure.

## Research Sources

- [Gemini Embedding model](https://ai.google.dev/gemini-api/docs/models/gemini-embedding-001)
  — model limits and recommended output dimensions.
- [Gemini Embeddings API](https://ai.google.dev/api/embeddings) — Python SDK
  usage, task configuration, and \`output_dimensionality\`.
- [Gemini Embeddings guide](https://ai.google.dev/gemini-api/docs/embeddings)
  — batch embeddings and manual normalization requirements for truncated
  \`gemini-embedding-001\` vectors.
- [Migrate to the Google GenAI SDK](https://ai.google.dev/gemini-api/docs/migrate)
  — current \`google-genai\` Python namespace and replacement guidance.
- [pgvector README](https://github.com/pgvector/pgvector#hnsw) — cosine HNSW
  syntax and indexed vector dimension support.

All repository-specific findings above were verified against the current
\`backend/src\`, \`backend/tests\`, migration, environment, and existing feature
artifacts. All technical decisions required for Phase 1 design are resolved.
