"""Unit coverage for the versioned deterministic RAG chunking policy."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.services.rag.canonical import create_canonical_document
from src.services.rag.chunking import ChunkingPolicy, chunk_document
from src.services.rag.contracts import RagScopeMetadata


def _document(text: str):
    source_id = uuid4()
    return create_canonical_document(
        source_type="team",
        source_key=str(source_id),
        source_entity_id=source_id,
        source_version="1",
        dependency_fingerprint="dependency-v1",
        semantic_text=text,
        provenance={"source_type": "team", "source_entity_id": str(source_id)},
        scope=RagScopeMetadata(source_type="team", team_ids=(source_id,)),
        builder_version="team-v1",
        prepared_at=datetime(2026, 8, 13, tzinfo=UTC),
    )


def test_small_structured_document_remains_intact() -> None:
    document = _document("Team: U15 Falcons\n\nAge group: U15")

    chunks = chunk_document(
        document,
        ChunkingPolicy(version="chunk-v1", max_characters=256, context_characters=60),
    )

    assert len(chunks) == 1
    assert chunks[0].semantic_text == document.semantic_text
    assert chunks[0].ordinal == 0
    assert chunks[0].document_id == document.document_id


def test_long_document_splits_on_boundaries_with_stable_minimal_context() -> None:
    document = _document(
        "Team: U15 Falcons\n\n"
        + "Roster: "
        + " ".join(f"Player-{index}" for index in range(70))
        + "\n\nCoaches: Coach One. Coach Two."
    )
    policy = ChunkingPolicy(
        version="chunk-v1",
        max_characters=180,
        context_characters=40,
    )

    first = chunk_document(document, policy)
    second = chunk_document(document, policy)

    assert first == second
    assert len(first) > 1
    assert [chunk.ordinal for chunk in first] == list(range(len(first)))
    assert len({chunk.chunk_id for chunk in first}) == len(first)
    assert all(len(chunk.semantic_text) <= policy.max_characters for chunk in first)
    assert all(chunk.chunking_version == "chunk-v1" for chunk in first)
    assert all(
        chunk.semantic_text.startswith("Context: Team: U15 Falcons")
        for chunk in first[1:]
    )


def test_chunking_rejects_an_impossible_continuation_bound() -> None:
    with pytest.raises(ValueError, match="context"):
        ChunkingPolicy(
            version="chunk-v1",
            max_characters=80,
            context_characters=75,
        )
