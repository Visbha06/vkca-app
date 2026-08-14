# Feature 012 Acceptance Checklist

Validated against `spec.md`, `plan.md`, `data-model.md`, `contracts/`, and
`quickstart.md` after the backend and request-level Playwright gates passed.

## Functional Requirements

- [x] FR-001 — Full/repair reconciliation reads authoritative SQLAlchemy sources; `test_rag_indexing.py` and the 012 quickstart prove rebuildability without domain mutation.
- [x] FR-002 — `test_initial_registry_uses_the_specified_nine_source_identifiers` verifies the exact nine-source allowlist.
- [x] FR-003 — Registry loaders use roster/coaching/Calendar rows only as dependencies; builder and quickstart tests prove no standalone relationship/raw Calendar documents.
- [x] FR-004 — Registry and exclusion tests prove explicit opt-in metadata and default exclusion.
- [x] FR-005 — Loader and performance tests prove bounded batches, set-based dependency loading, and bounded Calendar projection.
- [x] FR-006 — Builder, Data Quality, inactive-Player, relationship, and deletion tests prove fail-closed eligibility.
- [x] FR-007 — Builder modules are source-specific and extension-boundary tests prohibit provider/persistence access.
- [x] FR-008 — Player builder/privacy tests cover the explicit profile allowlist and sensitive-field exclusion.
- [x] FR-009 — Team builder tests cover bounded active roster/coaching context and account-data exclusion.
- [x] FR-010 — Match builder tests cover explicit internal/external participants without opponent inference.
- [x] FR-011 — Performance builder tests cover numeric figures/context and note exclusion.
- [x] FR-012 — Statistics builder tests cover linked Player/format/numeric allowlists without row dumps.
- [x] FR-013 — Calendar builder/sync/quickstart tests cover effective occurrences, moves, replacements, deletions, scope, timezone semantics, and raw-definition exclusion.
- [x] FR-014 — Builder and privacy tests cover deterministic field allowlists, arbitrary JSON, audit, and security exclusions.
- [x] FR-015 — Typed contract and canonical-document tests cover identity, version, text, provenance, scope, hash, builder version, and timestamps.
- [x] FR-016 — Canonical normalization tests cover Unicode, whitespace, dates/times, decimals, nulls, lists, and ordering.
- [x] FR-017 — Canonical hash/ID tests prove stable digest behavior.
- [x] FR-018 — Builder/Calendar provenance tests verify structured, reproducible allowlists.
- [x] FR-019 — Registry extension tests and module boundaries prove deterministic rule-based builders with no LLM dependency.
- [x] FR-020 — Chunking tests prove semantic boundaries and intact small documents.
- [x] FR-021 — Chunk policy tests prove fixed version, bounds, stable order, and minimal continuation context.
- [x] FR-022 — Chunk contract tests cover stable IDs, parent, ordinal, text/hash, provenance/scope, and versions.
- [x] FR-023 — Indexing sync and idempotency tests prove stable sequences and atomic obsolete-child reconciliation.
- [x] FR-024 — Provider boundary tests and extension guards prove all embedding calls are centralized.
- [x] FR-025 — Embedding tests cover bounds, timeouts, fake provider, profile reporting, and validation.
- [x] FR-026 — Gemini adapter/config tests verify `gemini-embedding-001`, 1536 dimensions, task types, and credential-free fake quickstart use.
- [x] FR-027 — Provider tests reject malformed counts, dimensions, non-finite vectors, and partial batches.
- [x] FR-028 — Privacy, route, status, and CLI tests verify sanitized errors and no credential/body/vector exposure.
- [x] FR-029 — Provider transition and indexing-sync tests verify fail-safe compatibility and targeted/full rebuild handling.
- [x] FR-030 — Migration 014 and migration integration tests cover vector extension, schema/index creation, downgrade, and re-upgrade.
- [x] FR-031 — RAG run/source/document/chunk models and status tests cover distinct operational states.
- [x] FR-032 — Source-state model/status tests cover fingerprints, versions, model profile, success/failure, and active document identity.
- [x] FR-033 — Persistence/route tests verify safe documents/chunks and vector-free normal responses.
- [x] FR-034 — Migration/pgvector/indexing tests verify uniqueness, references, and obsolete/ineligible invalidation.
- [x] FR-035 — Migration and pgvector tests verify source, status, scope, relational, GIN, B-tree, and HNSW indexes.
- [x] FR-036 — Config, migration, provider, pgvector, and retrieval compatibility tests enforce vector/model/dimension consistency.
- [x] FR-037 — Indexing service and CLI tests cover full and targeted deterministic, bounded, rerunnable modes.
- [x] FR-038 — Report/status/CLI tests cover required aggregate counters and redaction.
- [x] FR-039 — Sync, Calendar sync, and quickstart tests cover fingerprint skipping, selective embedding, and deletion reconciliation.
- [x] FR-040 — Dependency/performance/authorization tests cover relationship changes and retrieval-time authorization changes without re-embedding.
- [x] FR-041 — Mutation-boundary tests prove provider failure cannot roll back committed academy mutations.
- [x] FR-042 — Failure, chunk-reuse, deletion, repair, and quickstart tests prove recoverable batches and prior-result preservation.
- [x] FR-043 — Claim/recovery/status tests prove source-truth restart and duplicate prevention.
- [x] FR-044 — Indexing/retrieval/quickstart tests verify separate technical telemetry and zero Business/Auth Audit writes.
- [x] FR-045 — Scope resolver tests cover current database User, role, activation, Player link, memberships, assignments, Teams, and age groups.
- [x] FR-046 — Authorization integration and quickstart tests cover the full role/source visibility matrix.
- [x] FR-047 — Contracts, builders, persistence, and extension-boundary tests verify intrinsic scope facets with no User-ID ACLs.
- [x] FR-048 — Retrieval tests cover safe query embedding, database filtering, bounded similarity, provenance, scores, and vector exclusion.
- [x] FR-049 — SQL compilation, pgvector, performance, and registry-intersection tests prove filtering precedes cosine order and limit.
- [x] FR-050 — Relationship-change tests cover role, User/Player active state, link, assignment, and membership changes without re-embedding.
- [x] FR-051 — Schema/retrieval tests cover query/result bounds and deterministic chunk-ID tie-breaking.
- [x] FR-052 — Route, API, and Playwright tests cover existing authentication, server scope, forbidden client scope, bounded metadata, and no answer generation.
- [x] FR-053 — Settings/env/provider tests cover safe placeholders, Gemini defaults, fake tests, and all required bounds.
- [x] FR-054 — Builder/provider/privacy/status/route/quickstart tests cover every named secret, audit, metadata, body, and vector exclusion.
- [x] FR-055 — Unit and integration suites cover builders, canonical/chunk/provider/persistence/sync/auth/failure/audit requirements.
- [x] FR-056 — Authorization and quickstart tests cover every required role/state and live relationship change with zero forbidden chunks.
- [x] FR-057 — Migration/pgvector tests cover extension, downgrade/re-upgrade, dimensions, ordering, scope predicates, indexes, and duplicates.
- [x] FR-058 — Synthetic fixture/extensibility tests cover the full shared pipeline, deletion, targeting, retrieval, and unregistered exclusion.
- [x] FR-059 — `test_012_quickstart_flow.py` executes the isolated migration/vector, build, sync, auth, failure, repair, and status flow.
- [x] FR-060 — `docs/rag-indexing-foundation.md` documents the verified implementation and local commands.

## Success Criteria

- [x] SC-001 — Deterministic builder/canonical/chunk tests verify unchanged output identities and hashes.
- [x] SC-002 — Full-build and quickstart tests verify no duplicates or new unchanged embeddings on rerun.
- [x] SC-003 — Sync/performance/quickstart tests verify only changed sources/dependencies embed.
- [x] SC-004 — Deletion/ineligibility tests verify zero searchable chunks.
- [x] SC-005 — Authorization tests verify zero forbidden chunks for all account states and live relationship changes.
- [x] SC-006 — Mutation-boundary tests verify committed domain changes and retained usable derived state for every simulated failure class.
- [x] SC-007 — Retrieval/report tests verify configured limits and redacted aggregate counters.
- [x] SC-008 — The isolated 012 quickstart executes all 16 acceptance stages.
- [x] SC-009 — Synthetic-source tests pass without core-pipeline changes; unregistered models remain excluded.
- [x] SC-010 — Performance tests record bounded loader/provider batches, one filtered vector candidate query, and bounded query counts.
- [x] SC-011 — Privacy, API, status, provider, indexing, and quickstart tests verify zero sensitive payload leakage.
- [x] SC-012 — Gemini and replacement-provider tests preserve shared document/auth/persistence/retrieval interfaces.
- [x] SC-013 — Calendar builder/sync/quickstart tests match effective projection and exclude raw definitions.

## Explicit Exclusions

- [x] No chatbot UI/routes, conversations, answer generation, prompt work, streaming, citation UI, query rewriting, agents, or reranking.
- [x] No AI mutation/correction of academy data or user-configurable RAG permissions.
- [x] No external PDF/web/file ingestion, hosted vector service, audit summarization, notifications, analytics, or RAG administration UI.
- [x] No automatic indexing of future SQLAlchemy models and no security/authentication/secret/audit source registration.
- [x] No user-facing frontend surface; the only frontend addition is the request-level Playwright contract test.
