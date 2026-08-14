"""Unit coverage for incremental RAG reconciliation decisions and chunk reuse."""

from datetime import UTC, datetime
from uuid import uuid4

from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.services.rag.canonical import create_canonical_document, derive_source_id
from src.services.rag.chunking import RagChunker
from src.services.rag.contracts import (
    EmbeddingProfile,
    RagRunMode,
    RagScopeMetadata,
    RagSourceStatus,
)
from src.services.rag.indexing import (
    ReconciliationAction,
    compare_source_candidate,
    reusable_chunk_vectors,
)

PROFILE = EmbeddingProfile(
    provider_name="fake",
    model_name="gemini-embedding-001",
    dimension=1536,
    adapter_version="fake-v1",
)


def _candidate(
    *,
    text: str = "Player: Asha Khan",
    source_version: str = "1",
    dependency: str = "dependencies-v1",
    builder_version: str = "player-profile-v1",
    team_ids=(),
):
    return create_canonical_document(
        source_type="player_profile",
        source_key="player-1",
        source_entity_id=None,
        source_version=source_version,
        dependency_fingerprint=dependency,
        semantic_text=text,
        provenance={"source_type": "player_profile"},
        scope=RagScopeMetadata(
            source_type="player_profile",
            team_ids=tuple(team_ids),
        ),
        builder_version=builder_version,
        prepared_at=datetime(2026, 8, 13, tzinfo=UTC),
    )


def _persisted(candidate):
    state = RagSourceState(
        id=derive_source_id(candidate.source_type, candidate.source_key),
        source_type=candidate.source_type,
        source_key=candidate.source_key,
        observed_source_version=candidate.source_version,
        observed_dependency_hash=candidate.dependency_fingerprint,
        observed_content_hash=candidate.content_hash,
        last_successful_content_hash=candidate.content_hash,
        builder_version=candidate.builder_version,
        chunking_version="rag-chunk-v1",
        provider_name=PROFILE.provider_name,
        model_name=PROFILE.model_name,
        embedding_dimension=PROFILE.dimension,
        status=RagSourceStatus.CURRENT,
        active_document_id=candidate.document_id,
    )
    document = RagDocument(
        id=candidate.document_id,
        source_state_id=state.id,
        source_type=candidate.source_type,
        source_key=candidate.source_key,
        semantic_text=candidate.semantic_text,
        provenance_metadata=dict(candidate.provenance),
        scope_metadata=candidate.scope.as_json(),
        player_ids=list(candidate.scope.player_ids),
        team_ids=list(candidate.scope.team_ids),
        age_groups=list(candidate.scope.age_groups),
        is_all_academy=candidate.scope.is_all_academy,
        content_hash=candidate.content_hash,
        builder_version=candidate.builder_version,
        chunking_version="rag-chunk-v1",
        prepared_at=candidate.prepared_at,
        is_searchable=True,
    )
    return state, document


def test_unchanged_source_is_skipped_only_when_every_fingerprint_is_compatible():
    candidate = _candidate()
    state, active = _persisted(candidate)

    decision = compare_source_candidate(
        state,
        candidate,
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v1",
        mode=RagRunMode.INCREMENTAL,
    )

    assert decision.action is ReconciliationAction.SKIP
    assert decision.reasons == frozenset()
    assert not decision.requires_embedding


def test_source_dependency_and_scope_only_changes_refresh_without_embedding():
    original = _candidate()
    state, active = _persisted(original)
    changed_team_id = uuid4()
    candidate = _candidate(
        source_version="2",
        dependency="dependencies-v2",
        team_ids=(changed_team_id,),
    )

    decision = compare_source_candidate(
        state,
        candidate,
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v1",
        mode=RagRunMode.INCREMENTAL,
    )

    assert decision.action is ReconciliationAction.REFRESH_METADATA
    assert decision.reasons == {
        "source_version",
        "dependency_fingerprint",
        "scope_fingerprint",
    }
    assert not decision.requires_embedding


def test_content_or_chunking_change_reconciles_and_builder_change_can_reuse_chunks():
    original = _candidate()
    state, active = _persisted(original)

    content_change = compare_source_candidate(
        state,
        _candidate(text="Player: Asha Khan\nPlayer type: batter"),
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v1",
        mode=RagRunMode.INCREMENTAL,
    )
    chunking_change = compare_source_candidate(
        state,
        original,
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v2",
        mode=RagRunMode.INCREMENTAL,
    )
    builder_change = compare_source_candidate(
        state,
        _candidate(builder_version="player-profile-v2"),
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v1",
        mode=RagRunMode.TARGETED,
    )

    assert content_change.action is ReconciliationAction.RECONCILE
    assert content_change.requires_embedding
    assert chunking_change.action is ReconciliationAction.RECONCILE
    assert chunking_change.requires_embedding
    assert builder_change.action is ReconciliationAction.REFRESH_METADATA
    assert not builder_change.requires_embedding


def test_incremental_refuses_profile_transition_but_targeted_rebuilds_it():
    candidate = _candidate()
    state, active = _persisted(candidate)
    state.model_name = "replacement-model"

    incremental = compare_source_candidate(
        state,
        candidate,
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v1",
        mode=RagRunMode.INCREMENTAL,
    )
    targeted = compare_source_candidate(
        state,
        candidate,
        active_document=active,
        profile=PROFILE,
        chunking_version="rag-chunk-v1",
        mode=RagRunMode.TARGETED,
    )

    assert incremental.action is ReconciliationAction.REQUIRE_EXPLICIT_REBUILD
    assert "embedding_profile" in incremental.reasons
    assert targeted.action is ReconciliationAction.RECONCILE
    assert targeted.requires_embedding


def test_chunk_reuse_is_hash_profile_and_chunking_compatible():
    candidate = _candidate(text="Player: Asha Khan")
    chunks = RagChunker().chunk(candidate)
    first = chunks[0]
    vector = [0.0] * PROFILE.dimension
    vector[0] = 1.0
    persisted = RagChunk(
        id=first.chunk_id,
        document_id=first.document_id,
        source_type=first.source_type,
        source_key=first.source_key,
        ordinal=first.ordinal,
        semantic_text=first.semantic_text,
        content_hash=first.content_hash,
        provenance_metadata=dict(first.provenance),
        scope_metadata=first.scope.as_json(),
        player_ids=[],
        team_ids=[],
        age_groups=[],
        is_all_academy=False,
        embedding=vector,
        provider_name=PROFILE.provider_name,
        model_name=PROFILE.model_name,
        embedding_dimension=PROFILE.dimension,
        builder_version=first.builder_version,
        chunking_version=first.chunking_version,
        is_searchable=True,
    )

    reusable = reusable_chunk_vectors(chunks, (persisted,), profile=PROFILE)
    changed = reusable_chunk_vectors(
        RagChunker().chunk(_candidate(text="Player: Asha Khan changed")),
        (persisted,),
        profile=PROFILE,
    )
    persisted.model_name = "replacement-model"
    incompatible = reusable_chunk_vectors(chunks, (persisted,), profile=PROFILE)

    assert reusable == {str(first.chunk_id): tuple(vector)}
    assert changed == {}
    assert incompatible == {}
