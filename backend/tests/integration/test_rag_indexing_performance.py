"""Set-based synchronization and bounded provider-batch regression coverage."""

from datetime import date
from time import perf_counter
from uuid import uuid4

import pytest

from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.schemas.rag import RagRetrievalRequest
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from src.services.rag.registry import RagSourceRegistry, source_registry
from src.services.rag.retrieval import RagRetrievalService
from tests.integration.test_rag_authorization import _seed_scope_corpus


def _player(index: int) -> Player:
    return Player(
        id=uuid4(),
        first_name=f"Player{index:02d}",
        last_name="Batch",
        date_of_birth=date(2012, 1, min(index + 1, 28)),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=True,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_incremental_preparation_is_set_based_and_embedding_batches_are_bounded(
    data_quality_query_counter,
    record_property,
) -> None:
    players = [_player(index) for index in range(12)]
    registry = RagSourceRegistry((source_registry.get("player_profile"),))
    provider = FakeEmbeddingProvider()

    async with AsyncSessionFactory() as session:
        session.add_all(players)
        await session.commit()
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=4,
            timeout_seconds=30,
            registry=registry,
        )

        started_at = perf_counter()
        first = await service.run_targeted("player_profile")
        record_property("rag_targeted_build_seconds", perf_counter() - started_at)

        assert first.counters.embeddings_created == len(players)
        assert len(provider.document_batch_keys) == 3
        assert all(len(batch) <= 4 for batch in provider.document_batch_keys)
        record_property("rag_sources_loaded", len(players))
        record_property("rag_embedding_batches", len(provider.document_batch_keys))

        calls_after_first = provider.document_call_count
        with data_quality_query_counter.count() as counter:
            unchanged = await service.run_incremental()

        assert unchanged.counters.unchanged_skipped == len(players)
        assert provider.document_call_count == calls_after_first
        assert counter.select_count <= 8, counter.statements

        # One declared Team membership changes one Player dependency only.
        team = Team(id=uuid4(), name="U13 Dependency", age_group="U13")
        session.add(team)
        await session.commit()
        session.add(
            TeamPlayer(team_id=team.id, player_id=players[0].id, roster_order=1)
        )
        await session.commit()

        changed = await service.run_incremental()

        assert changed.counters.documents_prepared == 1
        assert changed.counters.embeddings_created == 1
        assert changed.counters.unchanged_skipped == len(players) - 1
        assert provider.document_call_count == calls_after_first + 1


@pytest.mark.asyncio(loop_scope="session")
async def test_authorized_retrieval_is_one_bounded_vector_candidate_query(
    data_quality_query_counter,
    record_property,
) -> None:
    """Measure scope resolution and prove candidates are filtered before LIMIT."""

    async with AsyncSessionFactory() as session:
        seed = await _seed_scope_corpus(session)
        provider = seed["provider"]
        service = RagRetrievalService(
            session,
            provider=provider,
            query_max_characters=100,
            result_limit_default=3,
            result_limit_max=5,
            timeout_seconds=5,
        )

        with data_quality_query_counter.count() as counter:
            started_at = perf_counter()
            response = await service.retrieve(
                seed["assistant_a"],
                RagRetrievalRequest(query="scope query", limit=3),
            )
            record_property(
                "rag_authorized_retrieval_seconds",
                perf_counter() - started_at,
            )

        assert response.returned_count == 3
        assert response.returned_count <= response.limit == 3
        assert all(
            not item.source_key.endswith("-b")
            and not item.source_key.endswith("u15")
            and item.source_key != "player-inactive"
            for item in response.results
        )
        vector_queries = [
            statement for statement in counter.statements if "<=>" in statement
        ]
        assert len(vector_queries) == 1, counter.statements
        candidate_query = vector_queries[0]
        assert "rag_chunks.player_ids &&" in candidate_query
        assert "rag_chunks.team_ids &&" in candidate_query
        assert " LIMIT " in candidate_query
        assert counter.select_count <= 6, counter.statements
        record_property("rag_authorized_retrieval_selects", counter.select_count)
