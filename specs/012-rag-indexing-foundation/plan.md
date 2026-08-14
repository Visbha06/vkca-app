# Implementation Plan: Authorization-Aware RAG Indexing Foundation

Branch: 012-rag-indexing-foundation  
Date: 2026-08-13  
Spec: [spec.md](./spec.md)

Input: Feature specification from specs/012-rag-indexing-foundation/spec.md

## Summary

Build a reusable backend RAG foundation over the existing PostgreSQL/pgvector
database. The design introduces an explicit source registry, deterministic
canonical document builders, versioned chunking, a centralized embedding
provider boundary, RAG-specific synchronization state, and a retrieval service
that applies current database-derived authorization predicates inside the
candidate query.

The initial development provider is Gemini gemini-embedding-001 through the
official google-genai SDK, configured at 1536 dimensions with cosine similarity.
The provider is replaceable without changing document preparation, persistence,
authorization, or retrieval. Calendar indexing registers projected effective
occurrences from CalendarService rather than raw event definitions. Assistant
Coach scope includes every active Player in currently assigned Teams plus the
permitted related context defined by the specification.

## Technical Context

Language/Version: Python 3.12+; TypeScript/React 19 only for the required
request-level Playwright contract test; no frontend feature surface.

Primary Dependencies: FastAPI, Pydantic 2/Pydantic Settings, SQLAlchemy 2
async, asyncpg, Alembic, existing pgvector 0.4.2, pytest/pytest-asyncio/
pytest-mock, Ruff, mypy, Playwright; add google-genai as the only new runtime
dependency for the Gemini adapter.

Storage: PostgreSQL 16 in pgvector/pgvector:pg16. Add the vector extension and
RAG schema in Alembic revision 014. Store embeddings in vector(1536), use
cosine distance/vector_cosine_ops, and add relational/GIN scope indexes.

Testing: pytest unit tests with pytest-mock, isolated PostgreSQL integration
tests using the existing rollback-only fixture, migration tests, pgvector
similarity/authorization tests, feature-012 quickstart, and one authenticated
request-level Playwright test. Run Ruff, mypy, and the existing frontend E2E
toolchain.

Target Platform: Linux-hosted FastAPI service and Docker-hosted PostgreSQL;
operator commands run from backend with uv.

Project Type: Authenticated backend web service with internal application
services, operator CLI scripts, and one bounded protected retrieval route for
integration verification.

Performance Goals: Bounded/set-based source loading; no N+1 preparation;
configurable embedding batches and timeouts; bounded query text and result
count; cosine HNSW retrieval with authorization filters in the same SQL query.
Record full-build and retrieval timing as a local regression signal without
promising a production SLA.

Constraints: The relational academy database is authoritative and RAG state is
disposable. Provider calls cannot run inside academy mutation transactions.
Current role, active account, Player link, TeamCoach assignment, TeamPlayer
membership, and Player.is_active state are resolved per retrieval request.
Only explicitly registered sources and fields are indexed. Tests never require
a real Gemini key. No chatbot, LLM answer generation, conversation history,
frontend RAG UI, external document ingestion, or hosted vector database.

Scale/Scope: One academy and nine initial source types. Calendar projection
uses `CalendarService.get_range()` and its existing
`MAX_CALENDAR_RANGE_DATES` 45-day effective-occurrence horizon; this feature
does not introduce a separate RAG horizon setting. The first vector profile is
1536 dimensions. Indexing is bounded and batched; exact production corpus sizing
and strict latency SLOs are deferred beyond this foundation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- I. Clean Code — PASS: Keep source-specific preparation in dedicated builder
  adapters, keep indexing/provider/retrieval responsibilities separate, and
  avoid a central source-type conditional chain.
- II. Simple UX — PASS: No user-facing screen or workflow is introduced.
  Operator commands and the protected retrieval contract are bounded and
  explicit.
- III. Responsive Design — N/A: This feature has no frontend surface. The
  Playwright check is request-level and does not add UI.
- IV. Minimal Dependencies — PASS: Add only google-genai, which supplies the
  selected provider SDK unavailable in the repository. Keep it out of test
  credentials and avoid a second vector database or HTTP client.
- V. Testing Discipline — PASS: Add unit coverage for all new public logic,
  required PostgreSQL/pgvector integration coverage, test-012 quickstart
  coverage, and an authenticated Playwright check.
- VI. MCP Server Priority — PASS: Codebase-memory MCP and ripgrep MCP were used
  for architecture, symbol, relationship, and literal repository discovery.
- VII. Database Schema Migrations — PASS: Add revision 014, enable vector in
  the migration path, test upgrade/downgrade, and never rely on manual schema
  edits.
- VIII. UX Completeness — N/A/PASS: No user-facing UI is in scope; the spec and
  contracts explicitly define the authenticated, bounded backend surface.
- IX. Optimistic Concurrency — PASS: Use source version/fingerprint checks,
  versioned source state, run claims/leases, and recheck before activating a
  candidate.
- X. Strongly-Typed API Boundaries — PASS: Define Pydantic request/response
  schemas for the optional retrieval route and keep internal contracts typed.
- XI. Frontend State & Component Discipline — N/A: No React component is added.
- XII. Documentation — PASS WITH IMPLEMENTATION FOLLOW-UP: Add
  docs/rag-indexing-foundation.md after implementation and verification.

Gate result: PASS. No constitution violation requires complexity
justification. All Phase 0 technical unknowns are resolved in research.md.

## Project Structure

### Documentation (this feature)

    specs/012-rag-indexing-foundation/
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── contracts/
    │   ├── rag-internal.md
    │   ├── rag-retrieval-api.md
    │   └── rag-commands.md
    └── tasks.md                 # created later by /speckit-tasks

### Source Code

    backend/
    ├── pyproject.toml           # add google-genai with dependency rationale
    ├── uv.lock                  # lock the provider dependency
    ├── scripts/
    │   └── rag_index.py         # full/incremental/targeted/repair/status CLI
    ├── src/
    │   ├── config.py            # provider, dimension, batch, timeout, bounds
    │   ├── main.py              # include protected RAG retrieval route
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── rag_index_run.py
    │   │   ├── rag_source_state.py
    │   │   ├── rag_document.py
    │   │   └── rag_chunk.py
    │   ├── schemas/
    │   │   └── rag.py
    │   ├── services/
    │   │   └── rag/
    │   │       ├── __init__.py
    │   │       ├── contracts.py
    │   │       ├── registry.py
    │   │       ├── canonical.py
    │   │       ├── chunking.py
    │   │       ├── embedding.py
    │   │       ├── gemini_provider.py
    │   │       ├── loaders.py
    │   │       ├── scope.py
    │   │       ├── indexing.py
    │   │       ├── retrieval.py
    │   │       └── builders/
    │   │           ├── player.py
    │   │           ├── team.py
    │   │           ├── match.py
    │   │           ├── performance.py
    │   │           ├── statistics.py
    │   │           └── calendar.py
    │   ├── routes/
    │   │   └── rag.py
    │   └── migrations/versions/
    │       └── 014_rag_indexing_foundation.py
    └── tests/
        ├── unit/
        │   ├── test_rag_registry.py
        │   ├── test_rag_builders.py
        │   ├── test_rag_calendar_builder.py
        │   ├── test_rag_chunking.py
        │   ├── test_rag_embedding.py
        │   ├── test_rag_scope.py
        │   ├── test_rag_retrieval.py
        │   └── test_rag_route.py
        ├── integration/
        │   ├── test_rag_migration.py
        │   ├── test_rag_pgvector.py
        │   ├── test_rag_authorization.py
        │   ├── test_rag_indexing.py
        │   └── quickstart/
        │       └── test_012_quickstart_flow.py
    frontend/
    └── e2e/
        └── rag-indexing-foundation-flow.spec.ts  # request-level Playwright

    .env.example
    .env.test.example
    docs/rag-indexing-foundation.md  # written after implementation/verification

The request-level Playwright test remains under frontend/e2e because that is
the repository’s existing Playwright runner. It must use a configured backend
API base URL and keep one canonical retrieval assertion without adding a UI.

## Phase 0 Research Output

Phase 0 is complete in [research.md](./research.md). Key decisions are:

1. Use google-genai behind an EmbeddingProvider protocol; do not import the SDK
   from builders or retrieval authorization.
2. Use Gemini gemini-embedding-001 with output dimension 1536, manual
   normalization, RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY purposes, cosine distance,
   and pgvector HNSW.
3. Use a RAG-specific operational schema instead of DataSyncLog.
4. Register calendar_occurrence as a projected CalendarService source with
   stable occurrence IDs and bounded horizon reconciliation.
5. Extract current DashboardScope relationship semantics into RagAccessScope;
   Assistant Coach scope includes all active Players in assigned Teams.
6. Keep provider calls outside source mutation transactions and activate only
   complete validated derived versions.

## Phase 1 Design Output

- [data-model.md](./data-model.md) defines persistent models, in-memory
  contracts, source dependencies, authorization facets, states, constraints,
  indexes, and privacy rules.
- [contracts/rag-internal.md](./contracts/rag-internal.md) defines registry,
  builder, chunker, provider, indexing, scope, retrieval, and status boundaries.
- [contracts/rag-retrieval-api.md](./contracts/rag-retrieval-api.md) defines the
  optional authenticated bounded retrieval route.
- [contracts/rag-commands.md](./contracts/rag-commands.md) defines operator
  full/incremental/targeted/repair/status commands and safe output.
- [quickstart.md](./quickstart.md) defines the isolated migration, build,
  synchronization, failure, authorization, retrieval, and Playwright checks.

## Design and Implementation Sequence

1. Add typed in-memory RAG contracts, source identifiers, deterministic
   normalization/hash helpers, chunking policy, and registry interfaces.
2. Add RAG SQLAlchemy models and migration 014. Enable vector extension,
   create vector(1536), scope/model/status indexes, HNSW cosine index, and
   downgrade behavior. Register models in models/__init__.py.
3. Add provider configuration and the exact `google-genai` 1.45.0 dependency
   using `uv add google-genai==1.45.0`, with its rationale recorded
   in `pyproject.toml`. Implement the Gemini adapter, fake provider, bounded
   batching, timeout/retry policy,
   finite/dimension/order validation, L2 normalization, and sanitized errors.
4. Implement set-based loaders and dedicated builders for Player, Team, Match,
   three performance families, two statistics families, and projected Calendar
   occurrences. Enforce safe field allowlists and no raw JSON/personal leakage.
5. Implement source-state reconciliation and run orchestration. Keep provider
   calls outside domain transactions, preserve last usable eligible rows on
   failure, reconcile obsolete Calendar occurrence keys, and recheck source
   fingerprints before activation.
6. Extract reusable role/team/Player resolution into RagAccessScope. Build
   source-specific SQL authorization predicates over current TeamCoach,
   TeamPlayer, User, Player, and Calendar scope state. Add bounded vector
   similarity retrieval with deterministic tie-breaking.
7. Add Pydantic retrieval schemas, the authenticated GET route, operator CLI,
   status output, and safe environment placeholders. Do not add chat routes or
   answer generation.
8. Add unit, migration, pgvector, authorization, indexing, quickstart, and
   request-level Playwright coverage. Include SQL query-count/N+1 regression
   checks and no-audit assertions.
9. Perform the final security/data-exclusion review and apply fixes, then rerun
   the isolated quickstart, backend quality gates, and Playwright E2E check.
   Complete the acceptance checklist, then write
   docs/rag-indexing-foundation.md describing the verified implemented behavior,
   commands, configuration, source extension, authorization, recovery, and
   exclusions.

## Risks and Mitigations

- Provider SDK/API changes: isolate all Gemini calls in one adapter and persist
  provider/model/dimension/adapter metadata.
- Provider outage during refresh: use complete candidate activation and retain
  last usable eligible chunks.
- Stale authorization facets: derive current scope at retrieval time and never
  persist User IDs.
- Calendar drift: call CalendarService effective projection and test moved,
  replaced, deleted, timezone, and scope cases.
- Concurrent runs: claim source states with version/lease fields and recheck
  fingerprints before activation.
- Sensitive data leakage: explicit field allowlists, typed provenance, bounded
  logs, sanitized errors, and provider-request redaction tests.
- Vector incompatibility: validate configured profile against vector(1536) before
  provider work and require explicit re-index for model changes.

## Post-Design Constitution Check

*GATE: Re-evaluate after Phase 1 design.*

- Clean code: PASS; registry/adapter/builder boundaries preserve single
  responsibility and future-source extension.
- Minimal dependencies: PASS; google-genai is the only new runtime dependency
  and is directly required by the selected provider.
- Testing: PASS; every new service boundary has unit coverage, PostgreSQL and
  pgvector behavior has integration coverage, quickstart is test-012, and the
  constitution-required Playwright request contract is planned.
- Migrations: PASS; all RAG tables/indexes/extension setup are in revision 014
  and tested through the existing migration harness.
- Authorization/security: PASS; current relational scope is applied in SQL
  before result release; vectors/secrets/audit data are excluded.
- Optimistic concurrency: PASS; source state and run claims use versions,
  leases, and pre-activation source-fingerprint checks.
- Documentation: PASS WITH FOLLOW-UP; implementation must write the feature
  document only after verification, per constitution.
- UX: N/A; no user-facing UI is introduced.

Post-design gate result: PASS. No unresolved clarification or unjustified
complexity remains.

## Complexity Tracking

No constitution violations require complexity justification. The new provider
dependency, RAG-specific tables, and protected verification route are directly
required by the specification and are isolated behind reusable boundaries.
