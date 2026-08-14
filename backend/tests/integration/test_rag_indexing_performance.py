"""Set-based synchronization and bounded provider-batch regression coverage."""

from datetime import date
from uuid import uuid4

import pytest

from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from src.services.rag.registry import RagSourceRegistry, source_registry


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

        first = await service.run_targeted("player_profile")

        assert first.counters.embeddings_created == len(players)
        assert len(provider.document_batch_keys) == 3
        assert all(len(batch) <= 4 for batch in provider.document_batch_keys)

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
