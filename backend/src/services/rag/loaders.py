"""Bounded set-based source-loading seams shared by registered adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.rag.canonical import normalize_text, stable_component_hash
from src.services.rag.contracts import SourceDependency, SourceLoadBatch

DEFAULT_SOURCE_BATCH_SIZE = 100
MAX_SOURCE_BATCH_SIZE = 1_000
MAX_LOADER_CURSOR_CHARACTERS = 512


class LoaderContractError(ValueError):
    """A registered loader violated its bounded/set-based contract."""


@dataclass(frozen=True, slots=True)
class FetchedSourcePage[RecordT]:
    """Authoritative page returned by one set-based source query."""

    records: tuple[RecordT, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class LoadedSourceRecord[RecordT]:
    """One source plus the declared relationship inputs loaded for its builder."""

    record: RecordT
    source_key: str
    source_version: str | None
    source_fingerprint: str
    dependency_fingerprint: str | None
    relationships: Mapping[str, object]


class SourcePageFetcher[RecordT](Protocol):
    """Execute one ordered page query, not one query per source record."""

    async def __call__(
        self,
        session: AsyncSession,
        *,
        cursor: str | None,
        limit: int,
    ) -> FetchedSourcePage[RecordT]: ...


class RelationshipDependencyLoader[RecordT](Protocol):
    """Load all declared relationships for the whole page in bounded queries."""

    async def __call__(
        self,
        session: AsyncSession,
        records: Sequence[RecordT],
        dependencies: tuple[SourceDependency, ...],
    ) -> Mapping[str, Mapping[str, object]]: ...


class SourceFingerprintHook[RecordT](Protocol):
    """Compute the authoritative source/version fingerprint for one loaded row."""

    def __call__(
        self,
        record: RecordT,
        relationships: Mapping[str, object],
    ) -> str: ...


class DependencyFingerprintHook[RecordT](Protocol):
    """Hash only the declared relationship/projection inputs for invalidation."""

    def __call__(
        self,
        record: RecordT,
        relationships: Mapping[str, object],
    ) -> str | None: ...


class BoundedSetBasedLoader[RecordT]:
    """Validate bounds and combine a page query with one relationship-load seam."""

    def __init__(
        self,
        *,
        fetch_page: SourcePageFetcher[RecordT],
        source_key: Callable[[RecordT], object],
        source_version: Callable[[RecordT], object | None],
        source_fingerprint: SourceFingerprintHook[RecordT],
        dependencies: tuple[SourceDependency, ...] = (),
        load_relationships: RelationshipDependencyLoader[RecordT] | None = None,
        dependency_fingerprint: DependencyFingerprintHook[RecordT] | None = None,
        max_batch_size: int = DEFAULT_SOURCE_BATCH_SIZE,
    ) -> None:
        if not 1 <= max_batch_size <= MAX_SOURCE_BATCH_SIZE:
            raise LoaderContractError(
                f"loader max_batch_size must be between 1 and {MAX_SOURCE_BATCH_SIZE}"
            )
        dependency_names = [dependency.name for dependency in dependencies]
        if len(dependency_names) != len(set(dependency_names)):
            raise LoaderContractError("declared loader dependencies must be unique")
        if dependencies and load_relationships is None:
            raise LoaderContractError(
                "declared relationships require one set-based dependency loader"
            )
        self.fetch_page = fetch_page
        self.source_key = source_key
        self.source_version = source_version
        self.source_fingerprint = source_fingerprint
        self.dependencies = dependencies
        self.load_relationships = load_relationships
        self.dependency_fingerprint = dependency_fingerprint
        self.max_batch_size = max_batch_size

    @staticmethod
    def _validate_cursor(cursor: str | None) -> None:
        if cursor is not None and (
            not cursor.strip() or len(cursor) > MAX_LOADER_CURSOR_CHARACTERS
        ):
            raise LoaderContractError("loader cursor is blank or exceeds its bound")

    async def load_batch(
        self,
        session: object,
        *,
        cursor: str | None,
        limit: int,
    ) -> SourceLoadBatch[LoadedSourceRecord[RecordT]]:
        """Load one capped page and all its relationships without N+1 dispatch."""

        self._validate_cursor(cursor)
        if limit <= 0:
            raise LoaderContractError("loader batch limit must be positive")
        typed_session = cast(AsyncSession, session)
        bounded_limit = min(limit, self.max_batch_size)
        page = await self.fetch_page(
            typed_session,
            cursor=cursor,
            limit=bounded_limit,
        )
        if len(page.records) > bounded_limit:
            raise LoaderContractError(
                "source fetcher returned more than its batch limit"
            )
        self._validate_cursor(page.next_cursor)

        relationships_by_key: Mapping[str, Mapping[str, object]] = {}
        if self.load_relationships is not None and page.records:
            relationships_by_key = await self.load_relationships(
                typed_session,
                page.records,
                self.dependencies,
            )

        loaded: list[LoadedSourceRecord[RecordT]] = []
        seen_keys: set[str] = set()
        for record in page.records:
            key = normalize_text(str(self.source_key(record)))
            if not key:
                raise LoaderContractError("loaded source key must not be blank")
            if key in seen_keys:
                raise LoaderContractError("source page contains duplicate source keys")
            seen_keys.add(key)
            relationships = dict(relationships_by_key.get(key, {}))
            fingerprint = normalize_text(self.source_fingerprint(record, relationships))
            if not fingerprint:
                raise LoaderContractError("source fingerprint must not be blank")
            dependency_hash = (
                self.dependency_fingerprint(record, relationships)
                if self.dependency_fingerprint is not None
                else None
            )
            version = self.source_version(record)
            loaded.append(
                LoadedSourceRecord(
                    record=record,
                    source_key=key,
                    source_version=(
                        normalize_text(str(version)) if version is not None else None
                    ),
                    source_fingerprint=fingerprint,
                    dependency_fingerprint=(
                        normalize_text(dependency_hash)
                        if dependency_hash is not None
                        else None
                    ),
                    relationships=relationships,
                )
            )

        aggregate_fingerprint = (
            stable_component_hash(
                tuple((item.source_key, item.source_fingerprint) for item in loaded)
            )
            if loaded
            else None
        )
        return SourceLoadBatch(
            items=tuple(loaded),
            next_cursor=page.next_cursor,
            source_fingerprint=aggregate_fingerprint,
        )


async def iter_loader_batches[RecordT](
    loader: BoundedSetBasedLoader[RecordT],
    session: AsyncSession,
    *,
    batch_size: int | None = None,
) -> AsyncIterator[SourceLoadBatch[LoadedSourceRecord[RecordT]]]:
    """Traverse a loader through bounded cursors and reject cursor cycles."""

    cursor: str | None = None
    seen_cursors: set[str] = set()
    selected_size = batch_size or loader.max_batch_size
    while True:
        batch = await loader.load_batch(
            session,
            cursor=cursor,
            limit=selected_size,
        )
        yield batch
        if batch.next_cursor is None:
            return
        if batch.next_cursor in seen_cursors:
            raise LoaderContractError("source loader produced a cursor cycle")
        seen_cursors.add(batch.next_cursor)
        cursor = batch.next_cursor


SetBasedLoader = BoundedSetBasedLoader
