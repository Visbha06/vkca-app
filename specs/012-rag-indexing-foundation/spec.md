# Feature Specification: Authorization-Aware RAG Indexing Foundation

**Feature Branch**: `012-rag-indexing-foundation`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "Part 12: RAG Data Preparation and Authorization-Aware Indexing Foundation"

The feature establishes a reusable backend foundation that prepares selected
VK Cricket Academy records for future retrieval-augmented features. The
relational academy database remains authoritative. The RAG index is derived,
disposable state that can be rebuilt from the authoritative records at any
time. This feature ends before chatbot conversations, answer generation, or
frontend chat experiences.

## Repository-Derived Baseline

The specification is grounded in the current repository rather than a new
parallel domain model:

- The backend uses asynchronous application services, SQLAlchemy models,
  Pydantic schemas, FastAPI routes, and versioned Alembic migrations. There is
  no existing backend repository package to preserve as a separate convention.
- The current database is PostgreSQL 16 using the `pgvector/pgvector:pg16`
  container image. The backend already depends on `pgvector` (locked at
  `0.4.2`), so this feature extends the existing database capability rather
  than adding a hosted vector database.
- The current database-loaded roles are Head Coach, Assistant Coach, and
  Player. Authentication checks the current `User` row and active
  `AuthSession`; it does not trust the role claim in a JWT. A linked inactive
  Player profile also blocks authentication, while an unlinked Player account
  may authenticate.
- Current role-aware scope derives Head Coach access from the academy, Assistant
  Coach access from active `TeamCoach` rows, and Player access from the explicit
  `User -> Player -> TeamPlayer -> Team` relationship. Existing dashboard scope
  resolution is the starting point for a shared RAG access-scope resolver.
- Match participant semantics are explicit: a Match is external with one
  academy Team and an outside opponent, or internal with two academy Teams.
  Performance rows reference a Player and Match; aggregate batting and bowling
  statistics are stored per Player and Match format.
- Calendar uses persisted event scopes, bounded recurrence expansion, occurrence
  exceptions, and the academy timezone `America/Los_Angeles`. Calendar RAG
  preparation must index projected effective occurrences, consuming the
  existing Calendar service semantics instead of introducing another recurrence
  implementation or indexing only raw event definitions.
- Data Quality evaluates current Player, Team, roster, coach-assignment, and
  Calendar state without silently correcting it. Business Audit is an
  append-only record of successful domain mutations, while `AuthAuditLog` is a
  separate authentication/security log. Neither is an automatic RAG source.
- `DataSyncLog` currently stores only a source, status, target table, one error
  message, and timestamps. It does not represent a RAG run, per-source
  versions, embedding model compatibility, counts, or preserved previous
  embeddings. The feature therefore uses a RAG-specific operational state
  boundary unless planning proves that every required field can be represented
  without changing `DataSyncLog` semantics.
- Existing `Base`, timestamp, version, migration, environment-file, isolated
  PostgreSQL test-database, and quickstart conventions remain applicable.

## Clarifications

### Session 2026-08-13

- Q: What initial development embedding provider/model should the RAG foundation use, and how must future provider replacement work? → A: Use Gemini `gemini-embedding-001` as the initial development embedding provider/model; keep the shared embedding-provider abstraction so a later provider/model replacement does not change document preparation, authorization, persistence, or retrieval architecture.
- Q: What Calendar representation must enter the RAG corpus? → A: Index projected effective Calendar occurrences, reusing the existing recurrence, exception, timezone, and scope semantics; do not index only raw event definitions.
- Q: What Player content may an Assistant Coach retrieve? → A: All active Players in the Assistant Coach's currently assigned Teams, plus the related permitted Player, performance, statistics, Match, Team, and Calendar context defined by the authorization matrix; exclude inactive Players and unrelated Teams.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a trustworthy academy knowledge index (Priority: P1)

As an academy operator, I want to run a complete index build from current
academy records, so that future retrieval features can use consistent,
provenanced, searchable academy knowledge without changing source records.

**Why this priority**: A deterministic, rebuildable corpus is the foundation
for every later AI capability. It must be correct before retrieval or answers
are useful.

**Independent Test**: Seed one representative record for every registered
source family, run a full build, inspect only counts/status/provenance, and
verify that canonical documents, chunks, and embeddings exist without any
Business Audit or security-audit mutation.

**Acceptance Scenarios**:

1. **Given** valid Player, Team, roster, coach assignment, Match, performance,
   statistics, and Calendar records, **When** an operator runs a full build,
   **Then** each eligible registered source, including projected effective
   Calendar occurrences, produces deterministic canonical content, chunks,
   provenance, and authorization metadata, and the run reports inspected,
   prepared, chunked, embedded, skipped, and failed counts.
2. **Given** the same authoritative database state and builder/chunking/model
   versions, **When** the operator reruns the build, **Then** document IDs,
   chunk IDs, content hashes, and semantic text are unchanged, no duplicate
   derived rows are created, and unchanged embeddings are skipped.
3. **Given** a backend model that is not registered as a RAG source, **When** a
   full build runs, **Then** no document, chunk, or embedding is created for
   that model.
4. **Given** a source record containing authentication fields, arbitrary JSON,
   or an unapproved personal field, **When** its builder prepares a document,
   **Then** those values are absent from semantic text, stored provenance,
   provider requests, and normal operational logs.

### User Story 2 - Synchronize only changed academy knowledge (Priority: P1)

As an academy operator, I want incremental synchronization to recognize source
changes, deletions, eligibility changes, and builder changes, so that the index
stays current without re-embedding unrelated data or rolling back valid
academy mutations.

**Why this priority**: The index is derived state. Efficient, recoverable
synchronization prevents stale information from becoming an operational burden
and keeps provider usage bounded.

**Independent Test**: Build a seeded corpus, change one Player or Match, alter
one current relationship or effective Calendar occurrence, remove one eligible
source, and run incremental synchronization after each change. Compare
source-state, document, chunk, and embedding changes by source type.

**Acceptance Scenarios**:

1. **Given** a source whose version, relevant relationship fingerprint, builder
   version, and semantic content are unchanged, **When** incremental sync runs,
   **Then** it marks the source current or leaves it current without a new
   provider call or duplicate chunk.
2. **Given** one changed registered source, **When** incremental sync runs,
   **Then** only that source and explicitly dependent canonical documents are
   regenerated; unchanged source types retain their current derived state.
3. **Given** a source deletion, inactive transition, or loss of required
   eligibility, **When** synchronization observes it, **Then** its derived
   document and chunks are removed or invalidated according to the source
   policy and cannot remain searchable indefinitely.
4. **Given** an embedding provider timeout, malformed response, incompatible
   dimension, or partial batch failure, **When** synchronization handles the
   error, **Then** the previous usable embedding remains available for an
   eligible source, the source/run is marked stale or failed with a sanitized
   reason, and the source database transaction remains unaffected.
5. **Given** a builder version changes for one source type, **When** a targeted
   rebuild is requested, **Then** that source type can be regenerated without
   rebuilding unrelated source types.

### User Story 3 - Retrieve only knowledge the current user may see (Priority: P1)

As a Head Coach, Assistant Coach, or linked Player, I want future retrieval to
respect my current account, role, team assignments, memberships, and account
status, so that semantic relevance never expands my authorization.

**Why this priority**: A semantically useful result is still a security defect
if it discloses another team, Player, or restricted operational record.

**Independent Test**: Seed overlapping academy data, authenticate as each role,
run the retrieval service with the same query embedding, and verify the result
set against the scope matrix. Change an Assistant Coach assignment, a Player
membership, a User role, and a Player/User link without re-embedding, then
repeat retrieval.

**Acceptance Scenarios**:

1. **Given** a Head Coach, **When** retrieval runs, **Then** it may return all
   eligible registered academy content, subject to the source allowlist and
   current account status, but never authentication, security, secret, or
   Business Audit content.
2. **Given** an Assistant Coach assigned to Team A but not Team B, **When**
   retrieval runs, **Then** all active Players in Team A and the related
   permitted Team, Match, performance, statistics, and applicable Calendar
   context may be returned, while inactive Players, Team B content, and
   unrelated age-group content are excluded.
3. **Given** a linked Player with current Team A membership, **When** retrieval
   runs, **Then** the Player may receive their own profile, performance, and
   statistics plus permitted Team A, Match, and Calendar context, but not
   another Player's private profile or unrelated Team B context.
4. **Given** a Player-role User with no linked Player profile, **When** retrieval
   runs, **Then** it returns zero Player/team-specific RAG results rather than
   falling back to academy-wide content.
5. **Given** a TeamCoach assignment, TeamPlayer membership, User role, User
   activation state, or Player/User link changes, **When** retrieval runs on
   the next authenticated request, **Then** its scope reflects current
   relational state without requiring an embedding refresh.
6. **Given** a client supplies a User ID, Player ID, role, Team ID, age group,
   or requested scope intended to widen access, **When** the retrieval boundary
   receives the request, **Then** the server ignores or rejects the client
   scope input and derives authorization only from the authenticated database
   User and current relationships.

### User Story 4 - Add a future registered source safely (Priority: P2)

As a backend developer, I want a new domain model to opt into RAG through the
same preparation, chunking, embedding, persistence, and authorization path, so
that adding one source does not require redesigning or bypassing the core
pipeline.

**Why this priority**: The current corpus is intentionally limited, but future
academy models should be able to participate through a clear extension point.

**Independent Test**: Add a synthetic registered source fixture with an
allowlisted builder, source version, provenance, authorization metadata, and
deletion policy. Run the existing core pipeline and protected retrieval tests
without modifying core indexing or retrieval logic.

**Acceptance Scenarios**:

1. **Given** a synthetic source adapter registered with a builder, version,
   loader, eligibility policy, scope strategy, and deletion strategy, **When** a
   full or incremental build runs, **Then** it flows through the shared
   document, chunk, embedding, persistence, and retrieval boundaries.
2. **Given** a new SQLAlchemy model that has no registry entry, **When** any
   indexing mode runs, **Then** the model remains excluded by default.
3. **Given** a future builder that attempts direct vector persistence, direct
   provider access, arbitrary User-ID scope, or unapproved fields, **When** its
   contract tests run, **Then** the extension is rejected or fails at the
   shared boundary rather than silently bypassing controls.

### User Story 5 - Inspect index health without exposing indexed content (Priority: P2)

As an operator, I want bounded run and source status information, so that I can
diagnose stale or failed indexing without reading document bodies, vectors, or
secrets from logs or normal application responses.

**Why this priority**: A derived index that cannot be repaired or inspected is
not dependable operational infrastructure.

**Independent Test**: Run successful, skipped, partial-failure, model-mismatch,
and deletion scenarios, then verify status summaries, sanitized errors,
retained prior chunks, and the absence of source bodies/vectors/secrets in
captured logs and responses.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** an operator requests status, **Then** the
   response contains mode, source filter, timestamps, counts, and state/error
   summaries but not full semantic text, full chunks, vectors, provider request
   bodies, or credentials.
2. **Given** a run is interrupted and restarted, **When** the same run mode is
   rerun, **Then** already-current source state is safely skipped and incomplete
   work is recoverable without duplicate derived rows.

### Edge Cases

- An inactive Player, an inactive linked Player profile, a deleted Team, an
  orphaned relationship, or an invalid source relation must not be made to look
  complete by guessed identity or fabricated membership.
- An Assistant Coach with no active `TeamCoach` assignments receives no
  team-specific retrieval results and no academy-wide fallback except sources
  explicitly allowed as all-academy content by the matrix.
- An Assistant Coach assigned to a Team may retrieve all active Players in that
  Team and the related permitted Player, performance, statistics, Match, Team,
  and Calendar context; inactive Players and unrelated Teams remain excluded.
- A linked Player with no current `TeamPlayer` memberships receives only
  explicitly permitted self-scoped content and no team-wide content.
- A Match relevant through both internal sides appears once, not once per Team.
- Calendar RAG indexes projected effective occurrences rather than only raw
  event definitions. An occurrence moved into a requested range, deleted, or
  replaced is reconciled according to the existing recurrence, exception,
  timezone, and scope projection; the RAG builder must not invent a second
  recurrence interpretation.
- A source has the same semantic text but a changed authorization relationship:
  scope metadata may be updated without re-embedding, while retrieval still
  applies current relational authorization.
- A source has a changed version but the same canonical text: preparation and
  provenance state are refreshed, but the provider call is skipped when the
  model, dimension, chunking version, and chunk hashes remain compatible.
- A long semantic field crosses a chunk boundary: the builder preserves source
  identity and the chunker repeats only the minimum context needed to interpret
  the continuation.
- A provider returns too few, too many, non-finite, or wrongly dimensioned
  vectors, or fails part of a batch: no malformed vector is persisted and the
  last successful eligible state remains usable.
- The configured embedding model changes with the same dimension, or the
  dimension changes: the system detects incompatibility before mixing vectors
  and identifies the targeted or full re-index required.
- A source contains a password hash, token, CSRF value, account email, date of
  birth, arbitrary `player_metadata`, audit payload, or secret: no builder may
  include it merely because it is present in a SQLAlchemy model.
- A retrieval query has no authorized candidates, a bounded result limit of
  zero/too large, or a missing query embedding: the service returns a safe
  empty/validation result without running an unrestricted fallback search.
- A domain mutation completes while a provider is unavailable: the domain
  mutation remains committed; the index is marked stale or failed for later
  repair.
- A registered source is temporarily malformed or fails Data Quality/domain
  eligibility checks: it is skipped or failed with an inspectable reason and
  does not cause unrelated source types to fail.

## Requirements *(mandatory)*

### Functional Requirements

#### Authoritative data and registered corpus

- **FR-001**: The RAG system MUST treat the current relational academy
  database as the only authoritative source for indexed academy knowledge.
  RAG-derived records MUST be disposable and rebuildable, and MUST NOT correct,
  overwrite, invent, or infer academy data.
- **FR-002**: The initial source registry MUST explicitly allow only these
  source types: `player_profile`, `team`, `match`,
  `match_batting_performance`, `match_bowling_performance`,
  `match_fielding_performance`, `player_batting_stats`,
  `player_bowling_stats`, and `calendar_occurrence`.
- **FR-003**: `TeamPlayer` and `TeamCoach` MUST be treated as relationship
  inputs to the registered builders that need current roster or coaching
  context, not as automatically indexed standalone documents. Calendar event
  definitions, recurrence series, and occurrence exceptions MUST be treated as
  inputs to the `calendar_occurrence` projection rather than automatically
  indexed raw definitions. `User` MUST NOT be an independent RAG source.
- **FR-004**: A backend model MUST remain excluded until a source registry entry
  supplies its source identifier, safe loader, builder, builder/schema version,
  eligibility policy, authorization metadata strategy, incremental version
  strategy, and deletion handling.
- **FR-005**: Source loading MUST be bounded and set-based for representative
  full and incremental builds. It MUST avoid one query per source record and
  MUST declare relationship dependencies needed to detect affected parent
  documents. The `calendar_occurrence` loader MUST use a documented bounded
  effective-occurrence horizon and set-based projection inputs.
- **FR-006**: A source MUST be considered indexable only when its required
  authoritative records and relationships are present and valid under current
  domain constraints and applicable Data Quality/eligibility rules. Missing or
  invalid data MUST be omitted or marked ineligible, never completed by guess.

#### Source-specific preparation and safe fields

- **FR-007**: Each registered source type MUST have a dedicated builder or
  adapter that converts authoritative rows and declared relationship inputs to
  the shared canonical document contract. Builders MUST NOT know about vector
  storage, provider SDKs, or retrieval authorization queries.
- **FR-008**: The Player builder MUST allow only stable Player identity and
  cricket profile fields needed for academy retrieval, including display name,
  Player type, batting style, and bowling style. It MUST exclude date of birth,
  email, linked User ID from semantic text, account metadata, arbitrary
  `player_metadata`, and unapproved biography/free-text fields in the initial
  version.
- **FR-009**: The Team builder MUST allow team name, age group, and useful
  current roster/coaching context from active `TeamPlayer` and `TeamCoach`
  relationships. It MUST use safe display names and bounded summaries only;
  account emails, credentials, inactive account details, and internal account
  metadata MUST be excluded.
- **FR-010**: The Match builder MUST allow match date, format, explicit external
  or internal participant semantics, academy Team names/age groups, external
  opponent where applicable, home/away meaning, venue where appropriate, and
  recorded result/context. It MUST preserve the Match identity and MUST NOT
  derive participants from an opponent string or unrelated names.
- **FR-011**: Each performance builder MUST allow the linked Player identity,
  Match context, and its recorded batting, bowling, or fielding figures. Free
  text performance notes MUST remain excluded from the initial allowlist unless
  a later version explicitly defines a bounded safe-note policy.
- **FR-012**: The batting-statistics and bowling-statistics builders MUST allow
  the linked Player context, Match format, and recorded aggregate numeric
  fields. They MUST not serialize an entire ORM row or arbitrary related JSON.
- **FR-013**: The registered `calendar_occurrence` builder MUST create one
  canonical document per projected effective Calendar occurrence within the
  configured bounded indexing horizon. It MUST allow event name/type, effective
  academy-local date/time, all-academy or age-group scope, recurrence context,
  and useful schedule details. It MUST reuse the existing Calendar service's
  projected occurrence, recurrence, exception, timezone, and scope semantics,
  including its bounded range behavior, and MUST NOT introduce a second
  recurrence model. The stable source identity and provenance MUST retain the
  event/series/occurrence identity needed to reconcile moved, replaced, or
  deleted occurrences. Raw event definitions, recurrence series, or exception
  rows alone MUST NOT produce RAG documents.
- **FR-014**: Every builder MUST use explicit field allowlists, stable labels,
  stable ordering, bounded text lengths, and safe normalization. Arbitrary
  JSON, `BusinessAuditEvent` metadata, security records, and fields not named
  by the builder contract MUST never be serialized into canonical text or sent
  to an embedding provider.

#### Canonical document contract

- **FR-015**: The shared canonical document representation MUST contain a stable
  document ID; source type; source entity ID or stable composite key (including
  a stable effective-occurrence key for `calendar_occurrence`); source version
  or equivalent modification fingerprint; normalized semantic text;
  structured provenance; authorization-relevant scope metadata; deterministic
  content hash; builder/schema version; and preparation/index timestamps.
- **FR-016**: Canonical normalization MUST be deterministic. It MUST apply the
  same Unicode/whitespace normalization, field labels, date/time formatting,
  decimal formatting, null omission, relationship ordering, and list ordering
  for the same source state and builder version.
- **FR-017**: A canonical content hash MUST be computed from the normalized
  semantic content using a stable digest. The same source state and builder
  version MUST yield the same text and hash, independent of query order,
  process, or machine.
- **FR-018**: Provenance MUST identify the registered source type and source
  entity without exposing unnecessary personal data. For
  `calendar_occurrence`, it MUST identify the authoritative event/series and
  projected occurrence identity needed to reproduce the effective occurrence.
  It MAY retain internal relationship identifiers required for reproducibility,
  but it MUST remain a structured allowlist rather than a raw model dump.
- **FR-019**: Canonical document preparation MUST be deterministic and rule
  based. It MUST NOT call an LLM or ask an LLM to rewrite, summarize, correct,
  or complete a source record.

#### Deterministic chunks

- **FR-020**: The system MUST chunk canonical documents between preparation and
  embedding using semantic/section boundaries first, retaining a small
  structured document intact when it fits the configured bound.
- **FR-021**: Chunking MUST use a fixed, versioned, bounded policy with stable
  ordering and no uncontrolled overlap or arbitrary fragmentation. The initial
  policy MUST use a documented maximum text size and repeat only the minimum
  source identity/context needed for a continuation chunk.
- **FR-022**: Every chunk MUST contain a stable chunk ID, parent document ID,
  ordinal, normalized semantic text, content hash, source type, source entity
  ID, provenance metadata, authorization metadata, and builder/chunking version.
- **FR-023**: Reprocessing unchanged canonical content MUST produce the same
  chunk sequence and IDs and MUST NOT create duplicate chunks. Changed chunk
  content, ordering, or chunking version MUST remove or replace obsolete child
  chunks as one derived-state reconciliation.

#### Embedding provider boundary

- **FR-024**: All embedding calls MUST pass through one centralized provider
  abstraction. Builders, domain services, retrieval authorization code, and
  persistence models MUST NOT call a provider SDK or HTTP API directly.
- **FR-025**: The provider abstraction MUST support bounded batches, configured
  timeouts, sanitized provider failures, fake/test implementations, model and
  version reporting, and response dimensionality validation.
- **FR-026**: The initial development embedding provider/model MUST be Gemini
  `gemini-embedding-001`. The implementation plan MUST verify and record the
  model's configured output dimension before the vector migration is finalized.
  All embedding calls MUST still pass through the shared provider abstraction,
  so replacing the provider or model later MUST NOT require changes to document
  preparation, authorization, persistence, or retrieval architecture. Tests and
  the isolated quickstart MUST use a deterministic fake or local implementation
  of that provider contract and MUST NOT require real Gemini credentials.
- **FR-027**: A provider response MUST be rejected if it has the wrong number of
  vectors, an incorrect dimension, non-finite values, or a response that cannot
  be mapped unambiguously to the submitted batch. No malformed vector may be
  persisted.
- **FR-028**: Provider credentials, request bodies, vectors, and raw provider
  errors MUST never be logged or returned to callers. Errors exposed through
  status or API boundaries MUST use sanitized categories/messages.
- **FR-029**: A provider, model, or dimension incompatibility MUST be detected
  before new vectors are mixed with the current index. The system MUST identify
  the affected source types and required targeted/full rebuild, rather than
  silently storing incompatible vectors under one searchable model. Replacing
  Gemini `gemini-embedding-001` MUST be an explicit provider/model transition
  through the shared abstraction, with targeted or full re-index handling as
  required by the compatibility change.

#### Persistence and PostgreSQL/pgvector setup

- **FR-030**: The feature MUST add versioned Alembic migration(s) for all RAG
  tables, constraints, indexes, and vector-extension setup. The migration MUST
  ensure the existing PostgreSQL vector extension is available through the
  normal project migration path; developers MUST NOT need a manual extension
  command.
- **FR-031**: The persistence design MUST distinguish run-level operational
  state, per-source/document indexing state, canonical documents, and embedded
  chunks. It MUST be possible to identify current, pending/stale, indexing,
  failed, and no-longer-eligible state without inspecting logs.
- **FR-032**: Per-source state MUST identify the source type/entity, source
  version or fingerprint, builder version, latest canonical content hash,
  authorization/scope fingerprint where relevant, indexing status, embedding
  model/version/dimension, last successful indexing time, failure state, and
  the current derived document/chunk identity.
- **FR-033**: Canonical document persistence MUST store only the safe normalized
  representation and structured provenance/scope metadata required for
  reproducibility and retrieval. Embedded chunk persistence MUST store stable
  chunk identity, parent/source identity, safe semantic text, vector embedding,
  scope metadata, content hash, and model/version metadata. Raw vectors MUST
  not be exposed through normal application responses.
- **FR-034**: Derived records MUST have uniqueness and referential constraints
  that prevent duplicate source states, documents, or chunks. Obsolete chunks
  MUST be deleted or invalidated when a source is deleted or no longer eligible.
- **FR-035**: Persistence MUST provide indexes for source lookup and
  synchronization, status/model compatibility, parent-child reconciliation,
  and authorization-relevant Player, Team, age-group, and all-academy scope
  predicates. The vector index/operator MUST match the selected embedding
  model and similarity metric.
- **FR-036**: The vector column definition, provider model, reported dimension,
  and migration configuration MUST remain consistent. Changing to an
  incompatible dimension MUST require an explicit migration/rebuild path and
  MUST fail safely before normal retrieval can mix models.

#### Full build and incremental synchronization

- **FR-037**: The backend MUST provide an explicit, reusable application-service
  command for full indexing with modes for the entire corpus and one
  registered source type. The command MUST be safe to rerun, deterministic,
  idempotent, bounded, batched, and observable.
- **FR-038**: Full and targeted runs MUST report at least source records
  inspected, documents prepared, chunks generated, embeddings created,
  unchanged documents/chunks skipped, deleted/ineligible sources handled, and
  failed sources. Reports MUST be aggregate operational data and MUST NOT
  contain full bodies, chunks, vectors, or secrets.
- **FR-039**: Incremental synchronization MUST use source versions/timestamps
  and deterministic content/scope hashes to skip unchanged content, regenerate
  changed canonical documents, re-embed only changed chunks, reconcile obsolete
  chunks, and handle deleted/no-longer-indexable records. For
  `calendar_occurrence`, it MUST reconcile the prior and newly projected
  effective occurrence sets so moved, replaced, or deleted occurrences do not
  leave stale searchable chunks.
- **FR-040**: Relationship-dependent builders MUST detect changes to relevant
  `TeamPlayer`, `TeamCoach`, Match participant, Calendar recurrence,
  scope/exception/timezone projection, and other declared dependencies. A pure
  authorization change MUST be reflected by retrieval-time relational checks
  and MUST NOT require re-embedding semantically unchanged content.
- **FR-041**: The synchronization boundary MUST not call an external provider
  inside the database transaction that commits a normal Player, Team, Match,
  performance, statistics, Calendar, User, assignment, or membership mutation.
  Provider failure MAY make the derived index stale, but MUST NOT roll back an
  otherwise valid academy-domain mutation.
- **FR-042**: Provider calls and derived-state writes MUST be recoverable in
  bounded batches. A failed refresh MUST preserve the previous usable
  embedding for an eligible source until a replacement succeeds. Eligibility
  removal or source deletion MUST remove access to the old derived content
  even when a provider is unavailable.
- **FR-043**: Rerunning an interrupted or failed run MUST reconcile from source
  truth rather than depend on an in-memory queue, and MUST not duplicate or
  silently lose usable derived records.
- **FR-044**: RAG indexing runs and source-state failures MUST use technical
  operational telemetry separate from Business Audit and authentication/
  security audit records. Document preparation, embedding, indexing,
  retrieval, repair, and rebuild MUST NOT create normal Business Audit events.

#### Current-user authorization and retrieval

- **FR-045**: The system MUST provide a shared RAG access-scope resolver that
  accepts the authenticated database `User` context and derives current role,
  active status, linked Player, current `TeamPlayer` memberships, current
  `TeamCoach` assignments, Team IDs, and age groups from authoritative
  relationships. It MUST reuse or extract the existing role-aware dashboard
  scope behavior wherever the current behavior is equivalent, and any
  intentional difference MUST be documented and tested rather than copied as
  an undocumented second role system.
- **FR-046**: The source-type visibility matrix MUST be enforced as follows:

  | Registered source | Head Coach | Assistant Coach | Linked Player | Unlinked Player |
  |---|---|---|---|---|
  | Player profile | All eligible active Player profiles | All active Players in currently assigned Teams | The linked Player's own profile only | None |
  | Team | All eligible Teams and allowed context | Currently assigned Teams and their active Player roster context | Teams in current memberships only | None |
  | Match | All eligible Matches | Matches involving currently assigned Teams and their related active Player context | Matches involving a current Team membership | None |
  | Batting/bowling/fielding performance | All eligible records | Records for active Players in currently assigned Teams and their permitted Match/Team scope | The linked Player's own permitted records only | None |
  | Player batting/bowling statistics | All eligible records | Statistics for active Players currently in assigned Teams | The linked Player's own statistics only | None |
  | Calendar occurrence | All projected effective eligible Calendar occurrences | All-academy occurrences plus age-group occurrences intersecting assigned Teams | All-academy occurrences plus age-group occurrences intersecting current Teams | None |

  Administrative, authentication, security, secret, and Business Audit data
  remains excluded for every role even when the viewer is a Head Coach.
  For Assistant Coaches, the assigned-Team Player scope includes every active
  Player in each currently assigned Team and the related permitted Player,
  performance, statistics, Match, Team, and Calendar context represented above;
  it excludes inactive Players and unrelated Teams.
- **FR-047**: Every indexed document/chunk MUST carry intrinsic, queryable
  scope metadata sufficient for the matrix, including source type and the
  relevant Player IDs, Team IDs, age groups, and all-academy indicator where
  applicable. The index MUST NOT persist currently authorized User-ID lists.
- **FR-048**: The retrieval service MUST accept a query embedding or a safe
  query abstraction, resolve the current user's scope, perform a bounded
  similarity search, apply source/membership/role filters in the
  database/service candidate query, and return only authorized safe text,
  provenance references, and scores. It MUST never expose vector values.
- **FR-049**: Authorization predicates MUST constrain candidates before the
  retrieval result set is released to the caller. An unrestricted vector search
  followed by application-side removal of forbidden results is prohibited.
- **FR-050**: Retrieval MUST use the current database role, User activation,
  Player/User link, `Player.is_active`, `TeamCoach`, and `TeamPlayer` state for
  every request. A role, assignment, membership, account-status, or link
  change MUST take effect on the next retrieval request without re-embedding
  unchanged semantic content.
- **FR-051**: The retrieval service MUST enforce a configured maximum result
  count and bounded query input. It MUST return deterministic tie-breaking for
  equal similarity where practical and preserve source/chunk provenance needed
  by a future chatbot without exposing unrelated fields.
- **FR-052**: If an authenticated HTTP retrieval boundary is provided for
  development or integration testing, it MUST require the existing
  authentication dependency, derive scope server-side, reject client-selected
  authorization scope, enforce bounded results, expose only necessary
  source/chunk metadata, and never generate an LLM answer or expose an
  unrestricted vector-search API. An internal service boundary remains the
  primary reusable contract.

#### Configuration, security, tests, and documentation

- **FR-053**: Configuration MUST follow the existing Pydantic Settings and
  environment-file conventions. It MUST configure Gemini
  `gemini-embedding-001` as the initial development provider/model and add only
  settings required for its provider credential, reported dimension, provider
  timeout, embedding batch bound, chunking version/bounds, and retrieval result
  bound. `.env.example` and `.env.test.example` MUST contain safe placeholders;
  tests MUST use a fake or local provider and MUST not require real credentials.
- **FR-054**: The system MUST never log or send to a provider password hashes,
  plaintext passwords, access tokens, refresh tokens, authentication sessions,
  CSRF values, authentication/security audit records, rate-limit internals,
  secret configuration, provider credentials, database credentials, raw
  vectors, full canonical bodies, or full chunks.
- **FR-055**: Unit and integration tests MUST cover every registered initial
  builder, allowlisted-field behavior, deterministic text/hashes/provenance,
  scope metadata, sensitive-field exclusion, chunk IDs/order/boundaries,
  Gemini-compatible provider configuration and model reporting through a
  deterministic fake transport, batching/timeouts/failures/malformed
  dimensions/partial batches, replacement-provider contract compatibility,
  migration and vector storage, similarity retrieval, relational
  authorization filters, full rebuild idempotency, incremental change and
  deletion handling, builder-version targeting, failure preservation, and
  absence of Business Audit events.
- **FR-056**: Authorization tests MUST cover Head Coach, relevant and
  irrelevant Assistant Coach assignments, all active Players in assigned Teams,
  linked Player, and unlinked Player, including inactive Player exclusion and
  assignment/membership/link/role/account-status changes without regenerating
  embeddings. They MUST assert zero unauthorized retrieval results and verify
  the related permitted Player, performance, statistics, Match, Team, and
  Calendar context for Assistant Coaches.
- **FR-057**: PostgreSQL/pgvector integration tests MUST verify extension setup,
  migration and downgrade behavior where supported, vector dimensionality,
  similarity ordering, scope-filtered retrieval, relational indexes, and
  duplicate prevention against the isolated test database.
- **FR-058**: The test suite MUST include a synthetic registered source fixture
  that passes through builder, canonical document, chunk, fake embedding,
  persistence, incremental synchronization, deletion, and protected retrieval
  without changes to core pipeline logic.
- **FR-059**: The backend quickstart MUST use the project's isolated test
  PostgreSQL conventions and cover: starting the database, applying the RAG
  migration, seeding representative data, full indexing, expected counts,
  idempotent rerun, one-source mutation, incremental indexing, protected
  retrieval as Head Coach, Assistant Coach, linked Player, and unlinked Player,
  forbidden-record absence, provider failure recovery, and stale/failure status
  inspection. The corresponding test MUST follow the repository naming
  convention as `backend/tests/integration/quickstart/test_012_quickstart_flow.py`.
- **FR-060**: After implementation and verification, documentation MUST
  describe the implemented architecture, registered sources, canonical
  contract, builder extension process, chunking, provider configuration,
  PostgreSQL/pgvector persistence, authorization matrix, rebuild and
  incremental commands, failure recovery, future-model onboarding, exclusion
  rules, and local verification commands. It MUST be written as
  `docs/rag-indexing-foundation.md` and describe implemented behavior rather
  than a plan.

### Operational Quickstart Acceptance Flow

The implementation quickstart and its feature-012 integration test MUST make
the following sequence executable against the isolated test database:

1. Start the project's test PostgreSQL/pgvector database.
2. Apply the RAG Alembic migration and verify the vector extension path.
3. Seed representative academy records for every initial source family and
   every authorization role/state, with the initial Gemini
   `gemini-embedding-001` model configured through the provider abstraction and
   a deterministic test transport.
4. Run a full index for the complete registered corpus.
5. Inspect expected document, chunk, source-state, and run counts without
   printing full indexed content.
6. Rerun the full index and verify unchanged sources are skipped with no
   duplicate derived records.
7. Mutate exactly one registered source record.
8. Run incremental synchronization.
9. Verify that only the changed source and declared dependents changed,
   including replacement/removal of any affected projected Calendar occurrence.
10. Retrieve as a Head Coach and verify academy-wide eligible results.
11. Retrieve as an Assistant Coach and verify all active Players in assigned
    Teams plus the related permitted Player, performance, statistics, Match,
    Team, and assigned-age-group/all-academy Calendar scope only.
12. Retrieve as a linked Player and verify own/current-membership scope only.
13. Retrieve as an unlinked Player and verify zero Player/team-specific
    results.
14. Assert that forbidden records never appear for any non-Head-Coach scope and
    that excluded security/audit data never appears for any role.
15. Simulate provider timeout/failure and verify previous usable results,
    sanitized failure state, and committed academy-domain data.
16. Inspect stale/failed/current status and verify the run can be repaired by
    rerunning the appropriate full, incremental, or source-targeted mode.

### Authorization Authority and Visibility Matrix

The following rules are normative for the retrieval boundary:

| Viewer state | Scope authority | Allowed RAG visibility | Required denial behavior |
|---|---|---|---|
| Active Head Coach | Current active `User` role | All registered eligible source content under the source allowlist | Never include excluded security, secret, or Business Audit data |
| Active Assistant Coach | Current `TeamCoach` rows for that User, plus age groups of those Teams | All active Players in currently assigned Teams, plus related permitted Player/performance/statistics, Match, Team, and all-academy/assigned-age-group Calendar content | Exclude inactive Players and unrelated Team, Player, Match, performance, statistics, and age-group content |
| Active linked Player | Current `Player.user_id`, active Player profile, and current `TeamPlayer` rows | Own Player/performance/statistics content plus current-team/match/calendar context allowed by the source matrix | Never infer another profile or widen to all academy data |
| Active unlinked Player | No Player profile relationship | No Player/team-specific RAG content | Return an empty protected result set or typed unlinked state |
| Inactive User or inactive linked Player profile | Existing authentication/session authority | No retrieval request reaches an authorized result boundary | Preserve existing authentication failure behavior |

The client cannot choose any part of this scope. Indexed authorization metadata
describes source relationships, not a snapshot of User permissions. Current
relationships are joined at retrieval time so assignment, membership, link,
role, and account changes take effect immediately.

### Operational State and Recovery

The run/status contract must expose enough information to distinguish:

- `current`: the source state, canonical content, chunk set, and configured
  embedding model are compatible and the last indexing attempt succeeded;
- `pending`/`stale`: source state changed or an earlier result is known to be
  older than current source truth;
- `indexing`: a bounded run currently owns the source reconciliation;
- `failed`: the most recent attempt failed, with a sanitized reason and the
  previous usable state retained when the source remains eligible; and
- `ineligible`/`deleted`: the source is no longer allowed in the corpus and its
  derived content is not searchable.

Run status is technical telemetry. It is not a Business Audit event, not an
authentication event, and not a user-facing academy activity item.

### Explicit Exclusions and Feature Boundary

The indexing system MUST NOT include password hashes, plaintext passwords,
access tokens, refresh tokens, authentication sessions, CSRF values,
authentication/security audit records, rate-limit/security internals, secret
configuration, provider credentials, database credentials, arbitrary JSON
metadata, or Business Audit records unless a future feature explicitly
registers a narrowly defined safe source and authorization policy. No current
feature registers any of them.

The feature does not include chatbot UI, chat routes/pages, conversation
history, LLM answer generation, prompt/system-prompt work, response streaming,
frontend citation rendering, query rewriting, autonomous or tool-calling
agents, AI mutations/corrections to academy data, user-configurable RAG
permissions, external PDF/web/file ingestion, Business Audit summarization,
a separate hosted vector database, advanced reranking, scheduled
notifications, analytics or RAG administration UI, or automatic indexing of
future SQLAlchemy models.

There is no user-facing frontend surface in this feature. Any developer or
integration retrieval boundary is authenticated, bounded, keyboard/UI
requirements do not apply, and no frontend route or chat experience is added.

## Key Entities *(include if feature involves data)*

- **RAG source registration**: The explicit opt-in definition for a source
  type, including its loader, builder, version, eligibility, authorization
  metadata, incremental dependency strategy, and deletion behavior.
- **Projected Calendar occurrence**: The bounded, effective Calendar instance
  produced from authoritative event definitions, recurrence, exceptions,
  timezone, and scope semantics. It is the registered Calendar source entity;
  raw definitions are projection inputs rather than standalone RAG documents.
- **Canonical RAG document**: The deterministic, safe semantic representation
  of one registered source entity, including identity, version, provenance,
  scope metadata, content hash, builder version, and normalized text.
- **RAG chunk**: A deterministic bounded child of a canonical document with a
  stable ordinal/ID, chunk hash, safe semantic text, provenance, scope
  metadata, and one embedding for the selected model/version.
- **RAG source index state**: The current synchronization/status record for one
  registered source entity, including source fingerprint, content hash,
  builder/model compatibility, last success, and failure/stale state.
- **RAG indexing run**: Technical operational state and aggregate counters for
  a full, incremental, targeted, or repair operation.
- **RAG access scope**: A request-time projection of the authenticated User's
  current role, active state, linked Player, TeamCoach assignments,
  TeamPlayer memberships, Team IDs, and age groups. It is derived at read time
  and is never persisted as a User-ID allowlist in vector records.
- **Source provenance and authorization metadata**: Structured safe metadata
  that identifies where a result came from and which current relational
  predicates may make it visible, without storing current authorized User IDs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every initial registered source fixture, repeated preparation
  from unchanged authoritative state produces identical canonical text,
  document IDs, content hashes, provenance, scope metadata, chunk IDs, chunk
  order, and chunk hashes 100% of the time.
- **SC-002**: Running a full build twice against unchanged seeded data creates
  zero duplicate documents or chunks and makes zero new embedding requests for
  unchanged chunks on the second run.
- **SC-003**: An incremental run after one source mutation changes only the
  mutated source and declared dependent documents/chunks; unrelated source
  types produce zero new embeddings and retain their current state.
- **SC-004**: Deleting or making a source ineligible leaves zero searchable
  chunks for that source after the corresponding reconciliation completes.
- **SC-005**: Across Head Coach, assigned/unassigned Assistant Coach, linked
  Player, and unlinked Player test accounts, protected retrieval returns zero
  unauthorized chunks in every authorization scenario. An assigned Assistant
  Coach can retrieve all active Players in assigned Teams and their related
  permitted context, while inactive Players and unrelated Teams remain absent,
  including after relationship and role changes without re-embedding.
- **SC-006**: A successful academy-domain mutation remains committed in 100% of
  simulated provider timeout/failure cases, while the affected eligible index
  state is marked stale/failed and its last usable result remains available.
- **SC-007**: Every normal retrieval call returns no more than the configured
  maximum result count, and every indexing run emits all required aggregate
  counters without full document/chunk/vector/secret payloads.
- **SC-008**: The isolated quickstart completes all 16 verification stages,
  including migration, deterministic rerun, targeted incremental change,
  protected retrieval for all four account states, forbidden-result checks,
  provider-failure recovery, and status inspection.
- **SC-009**: A synthetic registered source completes the same shared pipeline
  and protected retrieval path without any change to core indexing,
  embedding, persistence, or authorization logic; an unregistered synthetic
  model produces zero derived records.
- **SC-010**: The representative seeded integration suite demonstrates bounded
  source loading, batch embedding, indexed authorization predicates, and no
  N+1 source-preparation pattern. Observed full-build and retrieval latency is
  recorded as a regression signal; this foundation does not promise a strict
  production SLA.
- **SC-011**: Captured provider requests, application logs, status responses,
  and normal retrieval responses contain zero password hashes, tokens, CSRF
  values, security-audit data, credentials, raw vectors, or unapproved source
  fields.
- **SC-012**: The initial development build uses Gemini
  `gemini-embedding-001` through the shared provider contract, and a provider
  replacement contract test demonstrates that document preparation,
  authorization metadata, persistence, and retrieval interfaces remain
  unchanged.
- **SC-013**: For seeded recurring Calendar data with recurrence, exception,
  timezone, and scope changes, the indexed Calendar documents match the
  existing effective-occurrence projection for the configured horizon, while
  raw event definitions alone produce zero standalone RAG documents.

## Assumptions

- The current migration head is revision `013`; the RAG migration is added
  after it and is tested against the isolated Docker PostgreSQL/pgvector
  database before implementation is considered complete.
- Initial development uses Gemini `gemini-embedding-001` through the shared
  embedding-provider abstraction. The implementation plan verifies and records
  its output dimension before creating the vector column. A later provider or
  model may replace it through that abstraction without changing document
  preparation, authorization, persistence, or retrieval architecture; any
  incompatible dimension or model transition requires explicit rebuild
  handling. Tests and the local quickstart use a deterministic fake/local
  implementation, never a real secret.
- The existing `pgvector` dependency and container image are sufficient for
  the first persistence implementation. No new hosted vector service is
  needed unless a concrete repository-tested limitation is documented.
- `Player.is_active` and current relational integrity are the eligibility
  authority for Player-specific content. Existing authentication behavior
  remains authoritative for inactive Users and linked inactive Player
  profiles.
- A Team has no separate active flag in the current model. Team eligibility
  therefore follows current persisted Team validity and declared source/
  relationship checks; the indexer does not invent a Team lifecycle field.
- Calendar RAG indexing uses projected effective occurrences within a bounded,
  documented horizon compatible with the existing 45-day Calendar range. It
  reuses authoritative recurrence, exception, timezone, and scope semantics and
  records the definition/scope context needed to reproduce the projection; it
  does not index only raw event definitions or materialize an unlimited
  recurrence lifetime.
- No automatic post-commit worker, queue, scheduler, notification, or
  dashboard is required for this foundation. Full/incremental/repair commands
  and the run-status boundary are sufficient to recover stale state.
- Indexing commands are operator/developer operations and do not create normal
  Business Audit events. Any optional authenticated retrieval route is a
  protected foundation boundary, not a chatbot API.
- Existing project testing conventions require unit coverage for new backend
  logic, PostgreSQL integration coverage for this cross-module feature, an
  isolated quickstart test named for feature `012`, and an authenticated
  Playwright request-level end-to-end check if the project’s standard E2E gate
  requires one for this backend-only feature.
- Documentation is written after implementation and verification so it reports
  the actual selected provider/model, configuration names, commands, schema,
  and recovery behavior rather than unresolved planning choices.
