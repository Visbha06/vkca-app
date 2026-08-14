"""Provider-failure coverage for the RAG/domain transaction boundary."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.player import Player
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.services.rag.contracts import (
    EmbeddingBatch,
    EmbeddingInput,
    EmbeddingProfile,
    EmbeddingVector,
    RagRunMode,
)
from src.services.rag.embedding import (
    EmbeddingTimeoutError,
    FakeEmbeddingProvider,
)
from src.services.rag.indexing import (
    RagClaimConflictError,
    RagIndexingService,
    RagIndexingStateService,
)
from src.services.rag.registry import RagSourceRegistry, source_registry


class BrokenProvider(FakeEmbeddingProvider):
    """Return one selected sanitized provider-contract failure."""

    def __init__(self, failure: str) -> None:
        super().__init__()
        self.failure = failure

    async def embed_documents(
        self,
        inputs: Sequence[EmbeddingInput],
        profile=None,
    ) -> EmbeddingBatch:
        if self.failure == "timeout":
            raise EmbeddingTimeoutError()
        valid = await super().embed_documents(inputs, profile)
        if self.failure == "wrong_dimension":
            first = valid.vectors[0]
            return EmbeddingBatch(
                profile=valid.profile,
                vectors=(EmbeddingVector(first.item_key, (1.0, 0.0)),),
            )
        if self.failure == "malformed_count":
            return EmbeddingBatch(profile=valid.profile, vectors=())
        return EmbeddingBatch(profile=valid.profile, vectors=valid.vectors[:-1])


class SourceMutatingProvider(FakeEmbeddingProvider):
    """Commit a concurrent source change while the indexer is embedding."""

    def __init__(self, player_id) -> None:
        super().__init__()
        self.player_id = player_id

    async def embed_documents(self, inputs, profile=None):
        async with AsyncSessionFactory() as mutation_session:
            player = await mutation_session.get(Player, self.player_id)
            assert player is not None
            player.first_name = "Raced"
            player.version_number += 1
            await mutation_session.commit()
        return await super().embed_documents(inputs, profile)


def _player(player_id):
    return Player(
        id=player_id,
        first_name="Asha",
        last_name="Khan",
        date_of_birth=date(2012, 3, 2),
        bio="Opening batter",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=True,
    )


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        ("timeout", "timeout"),
        ("malformed_count", "malformed_response"),
        ("wrong_dimension", "malformed_response"),
        ("partial_batch", "malformed_response"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_provider_failure_preserves_prior_chunks_and_committed_mutation(
    failure: str,
    expected_code: str,
) -> None:
    player_id = uuid4()
    registry = RagSourceRegistry((source_registry.get("player_profile"),))
    async with AsyncSessionFactory() as session:
        player = _player(player_id)
        session.add(player)
        await session.commit()

        initial = RagIndexingService(
            session,
            provider=FakeEmbeddingProvider(),
            batch_size=32,
            timeout_seconds=30,
            registry=registry,
        )
        first = await initial.run_targeted("player_profile")
        prior_document = await session.scalar(
            select(RagDocument).where(RagDocument.source_key == str(player_id))
        )
        assert prior_document is not None
        prior_text = prior_document.semantic_text
        prior_chunk_ids = tuple(
            (
                await session.scalars(
                    select(RagChunk.id)
                    .where(RagChunk.document_id == prior_document.id)
                    .order_by(RagChunk.ordinal)
                )
            ).all()
        )

        player.first_name = "Changed"
        player.version_number += 1
        await session.commit()

        failed = await RagIndexingService(
            session,
            provider=BrokenProvider(failure),
            batch_size=32,
            timeout_seconds=0.1,
            registry=registry,
        ).run_incremental()

        await session.refresh(prior_document)
        state = await session.scalar(
            select(RagSourceState).where(
                RagSourceState.source_type == "player_profile",
                RagSourceState.source_key == str(player_id),
            )
        )
        current_chunk_ids = tuple(
            (
                await session.scalars(
                    select(RagChunk.id)
                    .where(
                        RagChunk.document_id == prior_document.id,
                        RagChunk.is_searchable.is_(True),
                    )
                    .order_by(RagChunk.ordinal)
                )
            ).all()
        )

        assert first.status.value == "completed"
        assert failed.status.value == "partial"
        assert failed.counters.failed_sources == 1
        assert state is not None
        assert state.status == "failed"
        assert state.failure_code == expected_code
        assert "Opening batter" not in (state.failure_message or "")
        assert prior_document.semantic_text == prior_text
        assert prior_document.is_searchable
        assert current_chunk_ids == prior_chunk_ids

    async with AsyncSessionFactory() as verification_session:
        committed_player = await verification_session.get(Player, player_id)
        assert committed_player is not None
        assert committed_player.first_name == "Changed"


@pytest.mark.asyncio(loop_scope="session")
async def test_pre_activation_recheck_discards_a_candidate_changed_during_embedding():
    player_id = uuid4()
    registry = RagSourceRegistry((source_registry.get("player_profile"),))
    async with AsyncSessionFactory() as session:
        player = _player(player_id)
        session.add(player)
        await session.commit()
        service = RagIndexingService(
            session,
            provider=FakeEmbeddingProvider(),
            batch_size=8,
            timeout_seconds=30,
            registry=registry,
        )
        await service.run_targeted("player_profile")
        document = await session.scalar(
            select(RagDocument).where(RagDocument.source_key == str(player_id))
        )
        assert document is not None
        prior_text = document.semantic_text

        player.first_name = "Prepared"
        player.version_number += 1
        await session.commit()
        raced = await RagIndexingService(
            session,
            provider=SourceMutatingProvider(player_id),
            batch_size=8,
            timeout_seconds=30,
            registry=registry,
        ).run_incremental()

        await session.refresh(document)
        state = await session.scalar(
            select(RagSourceState).where(
                RagSourceState.source_type == "player_profile",
                RagSourceState.source_key == str(player_id),
            )
        )
        assert raced.status.value == "partial"
        assert state is not None and state.status == "stale"
        assert state.failure_code == "source_changed"
        assert document.semantic_text == prior_text

        repaired = await RagIndexingService(
            session,
            provider=FakeEmbeddingProvider(),
            batch_size=8,
            timeout_seconds=30,
            registry=registry,
        ).run_repair()
        await session.refresh(document)

        assert repaired.status.value == "completed"
        assert "Raced" in document.semantic_text


@pytest.mark.asyncio(loop_scope="session")
async def test_claim_lease_rejects_overlap_and_allows_expired_claim_recovery():
    now = datetime(2026, 8, 13, tzinfo=UTC)
    source_id = uuid4()
    profile = EmbeddingProfile(
        provider_name="fake",
        model_name="gemini-embedding-001",
        dimension=1536,
        adapter_version="fake-v1",
    )
    async with AsyncSessionFactory() as session:
        state_service = RagIndexingStateService(session)
        first_run = await state_service.start_run(RagRunMode.INCREMENTAL, now=now)
        second_run = await state_service.start_run(RagRunMode.REPAIR, now=now)
        state = await state_service.create_source_state(
            source_type="player_profile",
            source_key=str(source_id),
            source_entity_id=source_id,
            builder_version="player-profile-v1",
            chunking_version="rag-chunk-v1",
            profile=profile,
        )
        await session.commit()
        state_id = state.id

        claimed = await state_service.claim_source(
            state_id,
            expected_version=state.version_number,
            run_id=first_run.id,
            now=now,
            lease_seconds=30,
        )
        await session.commit()
        claimed_version = claimed.version_number
        second_run_id = second_run.id

        with pytest.raises(RagClaimConflictError):
            await state_service.claim_source(
                state_id,
                expected_version=claimed_version,
                run_id=second_run_id,
                now=now + timedelta(seconds=10),
            )
        await session.rollback()

        recovered = await state_service.claim_source(
            state_id,
            expected_version=claimed_version,
            run_id=second_run_id,
            now=now + timedelta(seconds=31),
        )

        assert recovered.claim_run_id == second_run_id
        assert recovered.version_number == claimed_version + 1
