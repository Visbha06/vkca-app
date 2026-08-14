"""Unit coverage for deterministic canonical RAG document preparation."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

from src.services.rag.canonical import (
    canonical_content_hash,
    canonicalize_fields,
    create_canonical_document,
    derive_chunk_id,
    derive_document_id,
    derive_source_id,
    format_decimal,
    format_list,
    format_value,
    normalize_semantic_text,
    normalize_text,
    stable_component_hash,
)
from src.services.rag.contracts import RagScopeMetadata


def test_normalization_and_stable_value_formatting_are_machine_independent() -> None:
    assert normalize_text("  A\u0301sha\t  Patel  ") == "Ásha Patel"
    assert normalize_semantic_text(" Title  \r\n\r\n\r\n Value\t one \n") == (
        "Title\n\nValue one"
    )
    assert format_value(date(2026, 8, 13)) == "2026-08-13"
    assert format_value(time(9, 5, 0)) == "09:05:00"
    assert format_value(datetime(2026, 8, 13, 16, 30, tzinfo=UTC)) == (
        "2026-08-13T16:30:00Z"
    )
    assert format_decimal(Decimal("12.3400")) == "12.34"
    assert format_decimal(Decimal("-0.000")) == "0"
    assert format_list([" U15 ", "U13", "U15"]) == "U13, U15"


def test_ids_and_hashes_are_stable_and_namespaced() -> None:
    source_id = derive_source_id("player_profile", "player-1")
    document_id = derive_document_id("player_profile", "player-1")

    assert source_id == derive_source_id("player_profile", "player-1")
    assert document_id == derive_document_id("player_profile", "player-1")
    assert source_id != document_id
    assert derive_chunk_id(document_id, 0) == derive_chunk_id(document_id, 0)
    assert derive_chunk_id(document_id, 0) != derive_chunk_id(document_id, 1)
    assert canonical_content_hash("Name:  Asha\n") == canonical_content_hash(
        "Name: Asha"
    )
    assert stable_component_hash({"b": 2, "a": 1}) == stable_component_hash(
        {"a": 1, "b": 2}
    )
    assert stable_component_hash((("a", "b"), ("c", "d"))) != (
        stable_component_hash((("a", "c"), ("b", "d")))
    )


def test_canonical_document_contains_only_the_shared_typed_boundary() -> None:
    player_id = uuid4()
    team_ids = (uuid4(), uuid4())
    text = canonicalize_fields(
        [
            ("Player", "  Asha  Patel "),
            ("Teams", [str(team_ids[1]), str(team_ids[0])]),
            ("Optional", None),
        ]
    )
    scope = RagScopeMetadata(
        source_type="player_profile",
        player_ids=(player_id,),
        team_ids=team_ids,
        age_groups=("U15", "U13", "U15"),
    )

    document = create_canonical_document(
        source_type="player_profile",
        source_key=str(player_id),
        source_entity_id=player_id,
        source_version="7",
        dependency_fingerprint="relationships-v2",
        semantic_text=text,
        provenance={
            "source_type": "player_profile",
            "source_entity_id": str(player_id),
        },
        scope=scope,
        builder_version="player-v1",
        prepared_at=datetime(2026, 8, 13, tzinfo=UTC),
    )

    assert document.document_id == derive_document_id("player_profile", str(player_id))
    assert document.content_hash == canonical_content_hash(text)
    assert document.scope.age_groups == ("U13", "U15")
    assert document.scope.team_ids == tuple(sorted(team_ids, key=str))
    assert document.semantic_text == text
    assert not hasattr(document, "embedding")
    assert not hasattr(document, "provider_client")
    assert not hasattr(document, "session")
