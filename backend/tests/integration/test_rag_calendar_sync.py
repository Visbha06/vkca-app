"""Incremental reconciliation coverage for projected Calendar occurrences."""

from datetime import date, time
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.database import AsyncSessionFactory
from src.enums import AgeGroup, EventType, ScopeKind
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.schemas.calendar import CalendarEventInstance
from src.services.rag.builders.calendar import (
    CALENDAR_OCCURRENCE_BUILDER_VERSION,
    build_calendar_occurrence_document,
)
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import (
    RagSourceDefinition,
    SourceDependency,
    SourceLoadBatch,
)
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from src.services.rag.loaders import LoadedSourceRecord
from src.services.rag.registry import MarkMissingDeletedPolicy, RagSourceRegistry


class MutableOccurrenceLoader:
    """Expose a mutable, already-projected Calendar horizon to the indexer."""

    dependencies = (SourceDependency("calendar_projection"),)

    def __init__(self, occurrences: tuple[CalendarEventInstance, ...]) -> None:
        self.occurrences = occurrences

    async def load_batch(self, session, *, cursor: str | None, limit: int):
        del session
        ordered = tuple(sorted(self.occurrences, key=lambda item: item.occurrence_id))
        page = tuple(
            item for item in ordered if cursor is None or item.occurrence_id > cursor
        )[:limit]
        loaded = tuple(
            LoadedSourceRecord(
                record=item,
                source_key=item.occurrence_id,
                source_version=(
                    f"event:{item.event_version_number}:"
                    f"exception:{item.exception_version_number or 0}"
                ),
                source_fingerprint=stable_component_hash(
                    item.occurrence_id,
                    item.event_version_number,
                    item.exception_version_number,
                    item.event_date,
                    item.start_time,
                ),
                dependency_fingerprint=stable_component_hash(
                    item.original_date,
                    item.event_date,
                    item.scope_kind,
                    tuple(item.age_groups),
                ),
                relationships={},
            )
            for item in page
        )
        return SourceLoadBatch(
            items=loaded,
            next_cursor=page[-1].occurrence_id if len(page) == limit else None,
        )


def _occurrence(
    *,
    occurrence_id: str,
    event_id,
    series_id,
    original_date: date,
    event_date: date,
    name: str = "U13 practice",
    start: time = time(17, 0),
    age_groups=(AgeGroup.U13,),
    event_version: int = 1,
    exception_id=None,
    exception_version=None,
) -> CalendarEventInstance:
    return CalendarEventInstance(
        occurrence_id=occurrence_id,
        event_id=event_id,
        series_id=series_id,
        original_date=original_date,
        event_date=event_date,
        event_type=EventType.PRACTICE,
        name=name,
        is_all_day=False,
        start_time=start,
        end_time=time(start.hour + 1, start.minute),
        scope_kind=ScopeKind.AGE_GROUP,
        age_groups=list(age_groups),
        is_recurring=True,
        recurrence_summary="Weekly",
        event_version_number=event_version,
        exception_id=exception_id,
        exception_version_number=exception_version,
    )


def _registry(loader: MutableOccurrenceLoader) -> RagSourceRegistry:
    definition = RagSourceDefinition(
        source_type="calendar_occurrence",
        builder_version=CALENDAR_OCCURRENCE_BUILDER_VERSION,
        loader=loader,
        build=lambda loaded: build_calendar_occurrence_document(loaded.record),
        source_key=lambda loaded: loaded.source_key,
        source_version=lambda loaded: loaded.source_version,
        dependency_fingerprint=lambda loaded: loaded.dependency_fingerprint,
        scope_metadata=lambda loaded: (
            build_calendar_occurrence_document(loaded.record).scope
        ),
        eligible=lambda loaded: True,
        dependencies=loader.dependencies,
        deletion_policy=MarkMissingDeletedPolicy(),
    )
    return RagSourceRegistry((definition,))


@pytest.mark.asyncio(loop_scope="session")
async def test_calendar_projection_reconciles_effective_changes_and_missing_keys():
    event_id, series_id = uuid4(), uuid4()
    original_date = date(2026, 8, 14)
    occurrence_id = f"series:{series_id}:{original_date.isoformat()}"
    initial = _occurrence(
        occurrence_id=occurrence_id,
        event_id=event_id,
        series_id=series_id,
        original_date=original_date,
        event_date=original_date,
    )
    loader = MutableOccurrenceLoader((initial,))
    provider = FakeEmbeddingProvider()

    async with AsyncSessionFactory() as session:
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=8,
            timeout_seconds=30,
            registry=_registry(loader),
        )
        first = await service.run_targeted("calendar_occurrence")
        document = await session.scalar(
            select(RagDocument).where(RagDocument.source_key == occurrence_id)
        )
        assert first.status.value == "completed"
        assert document is not None
        document_id = document.id

        # A moved exception keeps the stable occurrence key but changes effective data.
        exception_id = uuid4()
        loader.occurrences = (
            _occurrence(
                occurrence_id=occurrence_id,
                event_id=event_id,
                series_id=series_id,
                original_date=original_date,
                event_date=date(2026, 8, 15),
                event_version=2,
                exception_id=exception_id,
                exception_version=1,
            ),
        )
        moved = await service.run_incremental()
        await session.refresh(document)
        assert moved.counters.embeddings_created == 1
        assert document.id == document_id
        assert "2026-08-15" in document.semantic_text

        # Replacement, academy-local time, and scope projection changes reconcile.
        loader.occurrences = (
            _occurrence(
                occurrence_id=occurrence_id,
                event_id=event_id,
                series_id=series_id,
                original_date=original_date,
                event_date=date(2026, 8, 15),
                name="Replacement practice",
                start=time(18, 0),
                age_groups=(AgeGroup.U15,),
                event_version=3,
                exception_id=exception_id,
                exception_version=2,
            ),
        )
        replaced = await service.run_incremental()
        await session.refresh(document)
        assert replaced.counters.embeddings_created == 1
        assert "Replacement practice" in document.semantic_text
        assert "18:00:00" in document.semantic_text
        assert document.age_groups == ["U15"]

        # A deleted or out-of-horizon projected key is reconciled without a provider.
        calls_before_removal = provider.document_call_count
        loader.occurrences = ()
        removed = await service.run_incremental()
        state = await session.scalar(
            select(RagSourceState).where(
                RagSourceState.source_type == "calendar_occurrence",
                RagSourceState.source_key == occurrence_id,
            )
        )
        searchable = (
            await session.scalars(
                select(RagChunk).where(
                    RagChunk.document_id == document_id,
                    RagChunk.is_searchable.is_(True),
                )
            )
        ).all()

        assert removed.counters.deleted_or_ineligible == 1
        assert state is not None and state.status == "deleted"
        assert not searchable
        assert provider.document_call_count == calls_before_removal
