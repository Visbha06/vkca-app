"""End-to-end proof that registered source adapters need no core-pipeline edits."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.database import AsyncSessionFactory
from src.enums import UserRole
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.models.user import User
from src.schemas.rag import RagRetrievalRequest
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from src.services.rag.retrieval import RagRetrievalService
from src.services.rag.scope import RagAccessScope
from tests.fixtures.rag_synthetic import (
    SYNTHETIC_BUILDER_VERSION,
    SYNTHETIC_SOURCE_TYPE,
    SyntheticNote,
    synthetic_registry,
)


def _head_scope() -> RagAccessScope:
    return RagAccessScope(
        user_id=uuid4(),
        role=UserRole.HEAD_COACH,
        is_active=True,
        linked_player_id=None,
        team_ids=(),
        age_groups=(),
        active_player_ids=(),
        is_unlinked_player=False,
        can_read_all_registered_sources=True,
    )


def _head_user() -> User:
    return User(
        id=uuid4(),
        first_name="Head",
        last_name="Coach",
        email=f"synthetic-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )


async def _resolve_head_scope(user: User) -> RagAccessScope:
    del user
    return _head_scope()


@pytest.mark.asyncio(loop_scope="session")
async def test_registered_synthetic_source_builds_changes_deletes_and_retrieves():
    note = SyntheticNote(id=uuid4(), title="Training plan", summary="Safe drills")
    registry, loader = synthetic_registry((note,))
    provider = FakeEmbeddingProvider()

    async with AsyncSessionFactory() as session:
        indexing = RagIndexingService(
            session,
            provider=provider,
            batch_size=8,
            timeout_seconds=30,
            registry=registry,
        )
        built = await indexing.run_full()
        state = await session.scalar(
            select(RagSourceState).where(
                RagSourceState.source_type == SYNTHETIC_SOURCE_TYPE,
                RagSourceState.source_key == str(note.id),
            )
        )
        assert built.status.value == "completed"
        assert state is not None and state.builder_version == SYNTHETIC_BUILDER_VERSION
        assert (await session.scalars(select(RagDocument))).one().source_type == (
            SYNTHETIC_SOURCE_TYPE
        )

        # A changed authoritative version is handled by incremental mode only.
        loader.notes = (
            SyntheticNote(
                id=note.id,
                title=note.title,
                summary="Updated safe drills",
                version=2,
            ),
        )
        changed = await indexing.run_incremental()
        assert changed.counters.embeddings_created == 1

        retrieval = RagRetrievalService(
            session,
            provider=provider,
            query_max_characters=100,
            result_limit_default=5,
            result_limit_max=20,
            timeout_seconds=30,
            registry=registry,
            scope_resolver=SimpleNamespace(resolve=_resolve_head_scope),
        )
        response = await retrieval.retrieve(
            _head_user(), RagRetrievalRequest(query="updated drills")
        )
        assert [item.source_type for item in response.results] == [
            SYNTHETIC_SOURCE_TYPE
        ]

        # Missing records are deactivated by the registered deletion policy.
        loader.notes = ()
        deleted = await indexing.run_incremental()
        assert deleted.counters.deleted_or_ineligible == 1
        searchable = (
            await session.scalars(
                select(RagChunk).where(RagChunk.is_searchable.is_(True))
            )
        ).all()
        assert not searchable
        await session.rollback()


@pytest.mark.asyncio(loop_scope="session")
async def test_builder_version_change_targets_only_the_registered_source_type():
    note = SyntheticNote(id=uuid4(), title="Plan", summary="Drills")
    registry, loader = synthetic_registry((note,))
    provider = FakeEmbeddingProvider()

    async with AsyncSessionFactory() as session:
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=8,
            timeout_seconds=30,
            registry=registry,
        )
        await service.run_targeted(SYNTHETIC_SOURCE_TYPE)
        calls_before_builder_change = provider.document_call_count
        replacement_registry, _ = synthetic_registry(
            loader.notes,
            builder_version="synthetic-note-v2",
        )
        replacement = RagIndexingService(
            session,
            provider=provider,
            batch_size=8,
            timeout_seconds=30,
            registry=replacement_registry,
        )
        rerun = await replacement.run_targeted(SYNTHETIC_SOURCE_TYPE)
        state = await session.scalar(
            select(RagSourceState).where(
                RagSourceState.source_type == SYNTHETIC_SOURCE_TYPE,
                RagSourceState.source_key == str(note.id),
            )
        )
        assert rerun.counters.embeddings_created == 0
        assert provider.document_call_count == calls_before_builder_change
        assert state is not None and state.builder_version == "synthetic-note-v2"
        await session.rollback()
