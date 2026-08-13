# RAG Internal Service Contracts

These contracts describe the reusable application boundary. They are not
provider SDK contracts and do not authorize direct access to vector tables.

## Source Registry

A registered source definition contains:

- source_type: one of the nine initial allowlisted identifiers;
- source_key(record): deterministic source identity;
- load(batch_cursor, session): bounded/set-based authoritative loader;
- build(record): source-specific canonical document builder;
- builder_version: explicit schema version;
- dependency_fingerprint(record): deterministic relevant relationship state;
- scope_metadata(record): intrinsic Player/Team/age-group/all-academy facets;
- eligible(record): current domain/Data Quality eligibility decision;
- reconcile_deleted(seen_keys, previous_keys): deletion/ineligibility policy.

The registry is the only entry point for source participation. Adding a new
backend model without registering a source definition produces no RAG records.

## Canonical Document Builder

Conceptual typed boundary:

    build(source_record) -> CanonicalRagDocument

The builder must:

- select only allowlisted fields;
- normalize values, labels, ordering, dates, and decimals deterministically;
- provide a stable source key and provenance;
- provide intrinsic authorization facets;
- compute a content hash and expose its builder version;
- avoid SQLAlchemy persistence, provider clients, User-ID ACLs, and LLM calls.

The Calendar builder consumes effective CalendarEventInstance values from
CalendarService.get_range(). It produces one document per stable occurrence_id;
raw definitions do not enter this boundary as standalone documents.

## Chunker

Conceptual typed boundary:

    chunk(canonical_document) -> tuple[RagChunkCandidate, ...]

The chunker uses a fixed versioned policy. Small structured documents remain
intact. Larger documents split at semantic/section boundaries, with only
minimal repeated identity/context. Output ordering, ordinals, IDs, and hashes
are deterministic.

## Embedding Provider

Conceptual typed boundary:

    embed_documents(inputs, profile) -> EmbeddingBatch
    embed_query(query, profile) -> QueryEmbedding

Embedding input includes a stable local item key, text, and purpose. The
returned batch preserves input order and includes:

- provider name;
- model name;
- adapter/schema version;
- configured dimension 1536;
- finite normalized float values;
- one vector per input.

The initial adapter is Gemini gemini-embedding-001 through google-genai.
Document inputs use RETRIEVAL_DOCUMENT and query inputs use RETRIEVAL_QUERY.
The provider boundary owns batching, timeout, bounded transient retries,
credential handling, response validation, dimension validation, and sanitized
error mapping. Builders and retrieval authorization code never call the SDK.

## Indexing Service

Conceptual typed boundary:

    run(mode, source_type=None, *, now=None) -> RagIndexRunReport

Modes:

- full: reconcile the entire registered corpus;
- incremental: inspect source/dependency fingerprints and process changed items;
- targeted: process one registered source type;
- repair: retry stale/failed/incomplete source states.

The service:

1. loads committed authoritative records through the registry;
2. prepares deterministic canonical documents;
3. chunks them;
4. skips compatible unchanged chunks;
5. calls the provider outside domain mutation transactions;
6. validates all returned vectors;
7. rechecks source fingerprints/optimistic versions;
8. activates derived rows atomically;
9. reconciles obsolete/deleted/ineligible rows;
10. records only technical counters and sanitized status.

A failed eligible refresh retains its prior active document/chunks. A deleted or
ineligible source is made non-searchable even when embedding is unavailable.

## Access-Scope Resolver

Conceptual typed boundary:

    resolve(authenticated_user) -> RagAccessScope

The resolver loads current database relationships. It must not accept client
scope parameters. It derives:

- Head Coach academy scope;
- Assistant Coach TeamCoach Teams and every active Player in those Teams;
- linked Player identity and current TeamPlayer memberships;
- current age groups and all-academy visibility;
- unlinked/inactive denial state.

Role, account status, Player link, assignment, membership, and active Player
changes affect the next request without re-embedding semantic content.

## Retrieval Service

Conceptual typed boundary:

    retrieve(user, request) -> RagRetrievalResponse

Request accepts either a bounded query text or a validated query embedding and a
bounded result limit. It does not accept User ID, Player ID, role, Team ID,
age-group, or authorization scope fields.

The service:

1. resolves RagAccessScope from the authenticated database User;
2. embeds bounded query text through the shared provider when needed;
3. builds one SQLAlchemy/pgvector candidate query;
4. applies current relational authorization predicates inside that query;
5. orders only authorized searchable chunks by cosine distance;
6. applies the configured result limit and deterministic tie-breaker;
7. returns safe text, source/chunk references, provenance, and scores only.

It never returns vectors, credentials, raw provider errors, or unauthorized
candidate rows.

## Status and Run Report

Status responses contain only:

- run ID, mode, selected source type, state, timestamps;
- aggregate inspected/prepared/chunked/embedded/skipped/deleted/failed counts;
- source state, failure category, and sanitized bounded message.

They do not contain canonical bodies, full chunks, vectors, provider request
bodies, secrets, or unapproved source fields.
