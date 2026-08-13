# RAG Indexing Command Contract

Commands are operator/developer boundaries over the shared indexing service.
They are safe to rerun, do not mutate academy source records, and emit
aggregate operational data only.

Run from the backend directory.

## Full corpus

    uv run python -m scripts.rag_index --mode full

Processes every registered source type.

## Incremental synchronization

    uv run python -m scripts.rag_index --mode incremental

Processes source identities whose authoritative version, dependency hash,
builder/chunking version, model profile, or eligibility state requires work.

## Targeted source type

    uv run python -m scripts.rag_index --mode targeted --source-type player_profile

The source type must be one of the explicit registry identifiers. The same
option can target Calendar projected occurrences or any future registered
source.

## Repair

    uv run python -m scripts.rag_index --mode repair

Retries stale, failed, model-incompatible, and incomplete source states without
rebuilding unrelated current sources.

## Status output

    uv run python -m scripts.rag_index --status <run-id>

Status output contains run mode, selected source filter, timestamps, counters,
source states, and sanitized error categories. It never prints semantic
documents, chunks, vectors, provider request bodies, credentials, or secrets.

## Output contract

The command reports:

- run ID, mode, source filter, status;
- source records inspected;
- documents prepared;
- chunks generated;
- embeddings created;
- unchanged documents/chunks skipped;
- deleted/ineligible sources reconciled;
- failed sources;
- sanitized failure categories and next repair mode.

Exit status is zero for a completed run, non-zero for failed setup/global
compatibility errors, and a documented partial status for source-level failures.
A partial/failed run remains recoverable through incremental or repair mode.

## Provider configuration

Local development uses the Gemini adapter with:

    RAG_EMBEDDING_PROVIDER=gemini
    RAG_EMBEDDING_MODEL=gemini-embedding-001
    RAG_EMBEDDING_DIMENSION=1536

Tests and the isolated quickstart select the deterministic fake provider through
the same provider protocol and never require a real Gemini key. The configured
model/dimension profile must still match the migration and fake-provider
contract.
