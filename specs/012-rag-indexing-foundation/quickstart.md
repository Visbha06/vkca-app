# Quickstart: Authorization-Aware RAG Indexing Foundation

This guide validates the backend foundation against the repository’s isolated
PostgreSQL/pgvector conventions. It does not create a chatbot or an LLM answer.

## Prerequisites

- Docker and the repository PostgreSQL/pgvector image.
- Python 3.12+, uv, and installed backend dependencies.
- A project-root .env.test created from .env.test.example and pointing at a
  test-only database name.
- No Gemini credential is needed for tests; the deterministic fake provider is
  used. Real local development indexing may set GEMINI_API_KEY privately.

## Start the isolated database and migration

From the repository root:

    docker compose --env-file .env.test up -d db

From backend:

    cd backend
    VKCA_ENV=test uv run alembic upgrade head

Expected result: revision 014 is applied, the vector extension is available,
and no manual CREATE EXTENSION command was needed. The migration integration
test must also exercise downgrade to 013 and upgrade back to 014 against an
isolated PostgreSQL schema.

## Execute the feature quickstart test

    cd backend
    VKCA_ENV=test uv run pytest \
      tests/integration/quickstart/test_012_quickstart_flow.py -q

The test seeds unique representative records inside the existing rollback-only
integration transaction. It must cover these stages:

1. Seed Head Coach, relevant and irrelevant Assistant Coaches, linked Player,
   unlinked Player, Teams, active/inactive Players, TeamCoach assignments,
   TeamPlayer memberships, external/internal Matches, all performance families,
   aggregate statistics, and recurring Calendar data.
2. Configure the fake provider with the Gemini provider contract and dimension
   1536; assert no real provider credential is read.
3. Project recurring Calendar data through CalendarService and verify that
   effective occurrences, moved occurrences, deleted occurrences, timezone, and
   scope match the authoritative projection. Raw event definitions produce no
   standalone RAG source.
4. Run a full build and assert source/document/chunk/embedding counts and
   current status without printing indexed bodies or vectors.
5. Rerun the full build and assert stable IDs/hashes, zero duplicate rows, and
   zero new embedding calls for unchanged chunks.
6. Mutate one Player or Match and one Calendar exception; run incremental sync.
7. Assert that only the changed source/dependents and affected effective
   occurrence rows change; unrelated source types remain untouched.
8. Mark a source deleted, inactive, or otherwise ineligible and assert its
   searchable chunks are removed or invalidated.
9. Simulate timeout, malformed dimensions, partial batch failure, and provider
   unavailability. Assert the previous eligible embedding remains usable,
   failure status is sanitized, and the source transaction remains committed.
10. Retrieve with the same query as Head Coach, assigned Assistant Coach,
    unassigned Assistant Coach, linked Player, and unlinked Player.
11. Assert the Assistant Coach sees every active Player in assigned Teams plus
    permitted Player, performance, statistics, Match, Team, and Calendar context.
12. Change TeamCoach assignment, TeamPlayer membership, Player/User link, role,
    and active state without re-embedding; assert next-request authorization
    changes immediately.
13. Attempt client-selected User, Player, role, Team, age-group, and scope
    expansion fields; assert they are ignored or rejected and cannot widen data.
14. Assert retrieval authorization predicates are part of the SQL candidate
    query, no forbidden result reaches the service response, and no vector is
    returned.
15. Assert indexing, retrieval, repair, and status reads create no Business
    Audit or authentication/security audit event.
16. Verify run/source status inspection and successful repair using incremental,
    targeted, and full modes.

## Manual operator command checks

After representative data is available in the test database, run from backend:

    VKCA_ENV=test RAG_EMBEDDING_PROVIDER=fake \
      uv run python -m scripts.rag_index --mode full

    VKCA_ENV=test RAG_EMBEDDING_PROVIDER=fake \
      uv run python -m scripts.rag_index --mode incremental

    VKCA_ENV=test RAG_EMBEDDING_PROVIDER=fake \
      uv run python -m scripts.rag_index \
      --mode targeted --source-type calendar_occurrence

    VKCA_ENV=test RAG_EMBEDDING_PROVIDER=fake \
      uv run python -m scripts.rag_index --mode repair

The commands must report only aggregate counts and sanitized status. Verify that
the targeted Calendar command reconciles projected occurrences rather than
indexing CalendarEvent rows directly.

For real local development, set the private Gemini key and use:

    VKCA_ENV=development RAG_EMBEDDING_PROVIDER=gemini \
      RAG_EMBEDDING_MODEL=gemini-embedding-001 \
      RAG_EMBEDDING_DIMENSION=1536 \
      uv run python -m scripts.rag_index --mode full

Never place a real key in .env.example, .env.test.example, test fixtures, logs,
or command output.

## Protected retrieval verification

Start the backend against the isolated test environment in a separate terminal:

    cd backend
    VKCA_ENV=test uv run uvicorn main:app --host 127.0.0.1 --port 8000

Use an authenticated test account to call:

    GET http://127.0.0.1:8000/api/v1/rag/retrieval?query=recent%20practice&limit=5

Verify:

- Head Coach receives eligible academy-wide source results.
- Assistant Coach receives assigned-Team/all-academy Calendar results and all
  active Players in assigned Teams with related permitted context.
- Linked Player receives only self/current-membership context.
- Unlinked Player receives an empty protected result set.
- Unrelated Teams, inactive Players, excluded security/audit data, vectors,
  credentials, and client-selected scope never appear.

Run the request-level Playwright contract check required by the project
constitution:

    cd frontend
    RAG_E2E_API_URL=http://127.0.0.1:8000 \
      npm run test:e2e -- rag-indexing-foundation-flow.spec.ts

This test exercises the authenticated retrieval boundary; it does not add a
chat page or frontend RAG UI.

## Focused quality checks

    cd backend
    uv run pytest tests/unit/test_rag_documents.py \
      tests/unit/test_rag_chunking.py \
      tests/unit/test_rag_embedding.py \
      tests/unit/test_rag_scope.py \
      tests/unit/test_rag_retrieval.py -q
    uv run pytest tests/integration/test_rag_migration.py \
      tests/integration/test_rag_pgvector.py \
      tests/integration/test_rag_authorization.py \
      tests/integration/test_rag_indexing.py -q
    uv run ruff check src tests
    uv run mypy src

Expected completion signals:

- migration 014 upgrades/downgrades safely;
- repeated full builds are idempotent;
- incremental work is source-targeted;
- projected Calendar occurrences reconcile correctly;
- Gemini-compatible fake batches validate dimensions and failures;
- provider failure preserves the last usable eligible index;
- Assistant Coach and Player authorization returns zero forbidden chunks;
- no RAG operation creates Business Audit or security-audit records;
- all output is bounded and excludes semantic bodies, vectors, secrets, and
  unapproved personal data.
