"""RAG-only run/source claims, leases, status, and safe telemetry helpers.

This foundational module intentionally does not traverse domain sources or call
an embedding provider. Story-specific reconciliation is layered on these
short derived-state transactions in later phases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_index_run import RagIndexRun
from src.models.rag_source_state import RagSourceState
from src.services.rag.canonical import derive_source_id, normalize_text
from src.services.rag.contracts import (
    EmbeddingProfile,
    RagIndexRunReport,
    RagRunCounters,
    RagRunMode,
    RagRunStatus,
    RagSourceStatus,
)
from src.services.rag.embedding import RAG_VECTOR_DIMENSION, EmbeddingProviderError

DEFAULT_SOURCE_LEASE_SECONDS = 300
MAX_FAILURE_MESSAGE_LENGTH = 500
_FAILURE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|database[_-]?url|password|secret|token)"
    r"\s*[:=]\s*[^\s,;]+"
)
_URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+:[^/@\s]+@", re.I)


class RagClaimConflictError(RuntimeError):
    """A source claim lost an optimistic-version or active-lease race."""


@dataclass(frozen=True, slots=True)
class TechnicalFailure:
    """Bounded error telemetry safe to persist or print."""

    code: str
    message: str


def sanitize_technical_message(message: str) -> str:
    """Normalize, redact common credentials, and bound an approved safe message."""

    redacted = _SENSITIVE_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}=[redacted]", message
    )
    redacted = _URL_CREDENTIALS.sub(r"\1[redacted]@", redacted)
    return normalize_text(redacted)[:MAX_FAILURE_MESSAGE_LENGTH]


def technical_failure(code: str, safe_message: str) -> TechnicalFailure:
    """Construct telemetry only from an explicit category and bounded message."""

    normalized_code = code.strip().casefold()
    if not _FAILURE_CODE_PATTERN.fullmatch(normalized_code):
        raise ValueError("technical failure code must be lowercase snake_case")
    sanitized = sanitize_technical_message(safe_message)
    if not sanitized:
        raise ValueError("technical failure message must not be blank")
    return TechnicalFailure(normalized_code, sanitized)


def failure_from_exception(error: BaseException) -> TechnicalFailure:
    """Map exceptions without copying raw provider/application exception text."""

    if isinstance(error, EmbeddingProviderError):
        return technical_failure(error.category.value, error.safe_message)
    return technical_failure(
        "indexing_failed",
        "RAG indexing failed; retry with incremental or repair mode.",
    )


def lease_is_available(
    state: RagSourceState,
    *,
    run_id: UUID,
    now: datetime,
) -> bool:
    """Return whether a run may acquire/renew a source without stealing a lease."""

    return (
        state.claim_run_id is None
        or state.claim_run_id == run_id
        or state.lease_expires_at is None
        or state.lease_expires_at <= now
    )


class RagIndexingStateService:
    """Stage short RAG operational writes without committing or auditing."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_run(
        self,
        mode: RagRunMode,
        *,
        source_type: str | None = None,
        now: datetime | None = None,
    ) -> RagIndexRun:
        """Stage one indexing run; the caller owns commit/rollback."""

        if mode is RagRunMode.TARGETED and not source_type:
            raise ValueError("targeted RAG runs require source_type")
        if source_type is not None:
            source_type = normalize_text(source_type).casefold()
            if not source_type:
                raise ValueError("RAG run source_type must not be blank")
        run = RagIndexRun(
            mode=mode,
            source_type=source_type,
            status=RagRunStatus.INDEXING,
            started_at=now or datetime.now(UTC),
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def create_source_state(
        self,
        *,
        source_type: str,
        source_key: str,
        source_entity_id: UUID | None,
        builder_version: str,
        chunking_version: str,
        profile: EmbeddingProfile,
        status: RagSourceStatus = RagSourceStatus.PENDING,
    ) -> RagSourceState:
        """Stage a deterministic per-source state before its first claim."""

        normalized_type = normalize_text(source_type).casefold()
        normalized_key = normalize_text(source_key)
        if not normalized_type or not normalized_key:
            raise ValueError("RAG source identity must not be blank")
        normalized_builder = normalize_text(builder_version)
        normalized_chunking = normalize_text(chunking_version)
        if not normalized_builder or not normalized_chunking:
            raise ValueError("RAG builder and chunking versions must not be blank")
        if profile.dimension != RAG_VECTOR_DIMENSION:
            raise ValueError("RAG source profile must match vector(1536)")
        state = RagSourceState(
            id=derive_source_id(normalized_type, normalized_key),
            source_type=normalized_type,
            source_key=normalized_key,
            source_entity_id=source_entity_id,
            builder_version=normalized_builder,
            chunking_version=normalized_chunking,
            provider_name=profile.provider_name,
            model_name=profile.model_name,
            embedding_dimension=profile.dimension,
            status=status,
        )
        self.session.add(state)
        await self.session.flush()
        return state

    async def claim_source(
        self,
        state_id: UUID,
        *,
        expected_version: int,
        run_id: UUID,
        now: datetime | None = None,
        lease_seconds: int = DEFAULT_SOURCE_LEASE_SECONDS,
    ) -> RagSourceState:
        """Atomically acquire a source using version and lease predicates."""

        if expected_version < 1:
            raise ValueError("expected source version must be positive")
        if lease_seconds <= 0:
            raise ValueError("source lease must be positive")
        claimed_at = now or datetime.now(UTC)
        statement = (
            update(RagSourceState)
            .where(
                RagSourceState.id == state_id,
                RagSourceState.version_number == expected_version,
                or_(
                    RagSourceState.claim_run_id.is_(None),
                    RagSourceState.claim_run_id == run_id,
                    RagSourceState.lease_expires_at.is_(None),
                    RagSourceState.lease_expires_at <= claimed_at,
                ),
            )
            .values(
                status=RagSourceStatus.INDEXING,
                claim_run_id=run_id,
                lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
                last_attempt_at=claimed_at,
                version_number=expected_version + 1,
            )
            .returning(RagSourceState)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        state = (await self.session.execute(statement)).scalar_one_or_none()
        if state is None:
            raise RagClaimConflictError(
                "RAG source claim conflicted with a newer version or active lease."
            )
        return state

    async def renew_claim(
        self,
        state_id: UUID,
        *,
        expected_version: int,
        run_id: UUID,
        now: datetime | None = None,
        lease_seconds: int = DEFAULT_SOURCE_LEASE_SECONDS,
    ) -> RagSourceState:
        """Renew only the same run's active optimistic claim."""

        if expected_version < 1:
            raise ValueError("expected source version must be positive")
        if lease_seconds <= 0:
            raise ValueError("source lease must be positive")
        renewed_at = now or datetime.now(UTC)
        statement = (
            update(RagSourceState)
            .where(
                RagSourceState.id == state_id,
                RagSourceState.version_number == expected_version,
                RagSourceState.status == RagSourceStatus.INDEXING,
                RagSourceState.claim_run_id == run_id,
            )
            .values(
                lease_expires_at=renewed_at + timedelta(seconds=lease_seconds),
                version_number=expected_version + 1,
            )
            .returning(RagSourceState)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        state = (await self.session.execute(statement)).scalar_one_or_none()
        if state is None:
            raise RagClaimConflictError("RAG source lease could not be renewed.")
        return state

    async def mark_source_current(
        self,
        state_id: UUID,
        *,
        expected_version: int,
        run_id: UUID,
        active_document_id: UUID,
        source_version: str | None,
        dependency_hash: str | None,
        content_hash: str,
        now: datetime | None = None,
    ) -> RagSourceState:
        """Activate success only when the same claim/version still owns the source."""

        completed_at = now or datetime.now(UTC)
        statement = (
            update(RagSourceState)
            .where(
                RagSourceState.id == state_id,
                RagSourceState.version_number == expected_version,
                RagSourceState.claim_run_id == run_id,
                RagSourceState.status == RagSourceStatus.INDEXING,
            )
            .values(
                status=RagSourceStatus.CURRENT,
                active_document_id=active_document_id,
                observed_source_version=source_version,
                observed_dependency_hash=dependency_hash,
                observed_content_hash=content_hash,
                last_successful_content_hash=content_hash,
                last_success_at=completed_at,
                failure_code=None,
                failure_message=None,
                claim_run_id=None,
                lease_expires_at=None,
                version_number=expected_version + 1,
            )
            .returning(RagSourceState)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        state = (await self.session.execute(statement)).scalar_one_or_none()
        if state is None:
            raise RagClaimConflictError(
                "RAG source activation conflicted with newer source state."
            )
        return state

    async def mark_source_failed(
        self,
        state_id: UUID,
        *,
        expected_version: int,
        run_id: UUID,
        failure: TechnicalFailure,
    ) -> RagSourceState:
        """Record a sanitized failed attempt while retaining active document state."""

        statement = (
            update(RagSourceState)
            .where(
                RagSourceState.id == state_id,
                RagSourceState.version_number == expected_version,
                RagSourceState.claim_run_id == run_id,
            )
            .values(
                status=RagSourceStatus.FAILED,
                failure_code=failure.code,
                failure_message=failure.message,
                claim_run_id=None,
                lease_expires_at=None,
                version_number=expected_version + 1,
            )
            .returning(RagSourceState)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        state = (await self.session.execute(statement)).scalar_one_or_none()
        if state is None:
            raise RagClaimConflictError(
                "RAG source failure update conflicted with newer state."
            )
        return state

    async def mark_source_unsearchable(
        self,
        state_id: UUID,
        *,
        expected_version: int,
        status: RagSourceStatus,
    ) -> RagSourceState:
        """Deactivate deleted/ineligible content without requiring a provider call."""

        if status not in {RagSourceStatus.DELETED, RagSourceStatus.INELIGIBLE}:
            raise ValueError("unsearchable sources must be deleted or ineligible")
        statement = (
            update(RagSourceState)
            .where(
                RagSourceState.id == state_id,
                RagSourceState.version_number == expected_version,
            )
            .values(
                status=status,
                active_document_id=None,
                claim_run_id=None,
                lease_expires_at=None,
                version_number=expected_version + 1,
            )
            .returning(RagSourceState)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        state = (await self.session.execute(statement)).scalar_one_or_none()
        if state is None:
            raise RagClaimConflictError(
                "RAG source invalidation conflicted with newer state."
            )
        document_ids = (
            RagDocument.__table__.select()
            .with_only_columns(RagDocument.id)
            .where(RagDocument.source_state_id == state_id)
        )
        await self.session.execute(
            update(RagChunk)
            .where(RagChunk.document_id.in_(document_ids))
            .values(is_searchable=False)
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(
            update(RagDocument)
            .where(RagDocument.source_state_id == state_id)
            .values(is_searchable=False)
            .execution_options(synchronize_session=False)
        )
        return state

    async def finish_run(
        self,
        run: RagIndexRun,
        *,
        status: RagRunStatus,
        counters: RagRunCounters,
        failure: TechnicalFailure | None = None,
        now: datetime | None = None,
    ) -> RagIndexRun:
        """Stage final aggregate counters and sanitized status; never commit."""

        if status is RagRunStatus.INDEXING:
            raise ValueError("finished RAG run cannot retain indexing status")
        for name, value in counters.as_dict().items():
            setattr(run, name, value)
        run.status = status
        run.finished_at = now or datetime.now(UTC)
        run.failure_code = failure.code if failure is not None else None
        run.failure_message = failure.message if failure is not None else None
        run.version_number += 1
        await self.session.flush()
        return run


def report_from_run(run: RagIndexRun) -> RagIndexRunReport:
    """Project an ORM run into the provider/content-free typed report."""

    return RagIndexRunReport(
        run_id=run.id,
        mode=RagRunMode(run.mode),
        status=RagRunStatus(run.status),
        source_type=run.source_type,
        started_at=run.started_at,
        finished_at=run.finished_at,
        counters=RagRunCounters(
            source_records_inspected=run.source_records_inspected,
            documents_prepared=run.documents_prepared,
            chunks_generated=run.chunks_generated,
            embeddings_created=run.embeddings_created,
            unchanged_skipped=run.unchanged_skipped,
            deleted_or_ineligible=run.deleted_or_ineligible,
            failed_sources=run.failed_sources,
        ),
        failure_code=run.failure_code,
        failure_message=run.failure_message,
    )


IndexingStateService = RagIndexingStateService


class RagIndexingService:
    """Run deterministic full or targeted builds over explicitly registered sources."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        provider: object,
        batch_size: int,
        timeout_seconds: float,
        registry: object | None = None,
        chunker: object | None = None,
    ) -> None:
        from src.services.rag.chunking import RagChunker
        from src.services.rag.embedding import EmbeddingBatcher
        from src.services.rag.registry import source_registry

        if not all(
            hasattr(provider, attribute) for attribute in ("profile", "embed_documents")
        ):
            raise TypeError("provider must implement the embedding provider contract")
        self.session = session
        self.provider = provider
        self.registry = registry or source_registry
        self.chunker = chunker or RagChunker()
        self.batcher = EmbeddingBatcher(
            batch_size=batch_size, timeout_seconds=timeout_seconds
        )
        self.state = RagIndexingStateService(session)

    async def run_full(self) -> RagIndexRunReport:
        """Build every registered source family from committed authoritative rows."""

        return await self.run(RagRunMode.FULL)

    async def run_targeted(self, source_type: str) -> RagIndexRunReport:
        """Build one explicit registry source type without dynamic model discovery."""

        return await self.run(RagRunMode.TARGETED, source_type=source_type)

    async def run(
        self,
        mode: RagRunMode,
        *,
        source_type: str | None = None,
    ) -> RagIndexRunReport:
        """Execute the Phase 3 full/targeted traversal and safely persist aggregates."""

        if mode not in {RagRunMode.FULL, RagRunMode.TARGETED}:
            raise ValueError("Phase 3 indexing supports full and targeted modes only")
        if mode is RagRunMode.TARGETED:
            if source_type is None:
                raise ValueError("targeted RAG runs require source_type")
            definitions = self.registry.select((source_type,))
        else:
            definitions = self.registry.select()
            source_type = None

        run = await self.state.start_run(mode, source_type=source_type)
        counters = RagRunCounters()
        try:
            for definition in definitions:
                await self._traverse_definition(run, definition, counters)
            status = (
                RagRunStatus.PARTIAL
                if counters.failed_sources
                else RagRunStatus.COMPLETED
            )
            await self.state.finish_run(run, status=status, counters=counters)
            await self.session.commit()
            return report_from_run(run)
        except Exception as error:
            await self.session.rollback()
            # Preserve no semantic/error body and do not attempt to continue
            # after a global registry/database configuration failure.
            failure = failure_from_exception(error)
            retry_run = await self.state.start_run(mode, source_type=source_type)
            await self.state.finish_run(
                retry_run,
                status=RagRunStatus.FAILED,
                counters=counters,
                failure=failure,
            )
            await self.session.commit()
            return report_from_run(retry_run)

    async def _traverse_definition(
        self,
        run: RagIndexRun,
        definition: object,
        counters: RagRunCounters,
    ) -> None:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page = await definition.loader.load_batch(  # type: ignore[union-attr]
                self.session, cursor=cursor, limit=100
            )
            for loaded in page.items:
                await self._process_record(run, definition, loaded, counters)
            if page.next_cursor is None:
                return
            if page.next_cursor in seen_cursors:
                raise RuntimeError(
                    "registered RAG source loader produced a cursor cycle"
                )
            seen_cursors.add(page.next_cursor)
            cursor = page.next_cursor

    async def _process_record(
        self,
        run: RagIndexRun,
        definition: object,
        loaded: object,
        counters: RagRunCounters,
    ) -> None:
        counters.add(source_records_inspected=1)
        source_type = definition.source_type  # type: ignore[union-attr]
        source_key = definition.source_key(loaded)  # type: ignore[union-attr]
        source_id = derive_source_id(source_type, source_key)
        source_version = definition.source_version(loaded)  # type: ignore[union-attr]
        dependency_hash = definition.dependency_fingerprint(loaded)  # type: ignore[union-attr]
        if not definition.eligible(loaded):  # type: ignore[union-attr]
            existing = await self.session.get(RagSourceState, source_id)
            if existing is not None:
                await self.state.mark_source_unsearchable(
                    existing.id,
                    expected_version=existing.version_number,
                    status=RagSourceStatus.INELIGIBLE,
                )
            counters.add(deleted_or_ineligible=1)
            return

        document = definition.build(loaded)  # type: ignore[union-attr]
        existing_state = await self.session.get(RagSourceState, source_id)
        profile = self.provider.profile
        if self._is_current(existing_state, document, profile):
            counters.add(unchanged_skipped=1)
            return
        state = existing_state or await self.state.create_source_state(
            source_type=source_type,
            source_key=source_key,
            source_entity_id=document.source_entity_id,
            builder_version=document.builder_version,
            chunking_version=self.chunker.policy.version,
            profile=profile,
        )
        try:
            claimed = await self.state.claim_source(
                state.id,
                expected_version=state.version_number,
                run_id=run.id,
            )
            chunks = self.chunker.chunk(document)
            from src.services.rag.contracts import as_embedding_inputs

            batch = await self.batcher.embed_documents(
                self.provider, as_embedding_inputs(chunks), profile=profile
            )
            vectors = {vector.item_key: vector.values for vector in batch.vectors}
            if len(vectors) != len(chunks):
                raise ValueError("validated embedding response did not map every chunk")
            await self._activate_document(
                state=claimed,
                document=document,
                chunks=chunks,
                vectors=vectors,
                profile=profile,
            )
            await self.state.mark_source_current(
                claimed.id,
                expected_version=claimed.version_number,
                run_id=run.id,
                active_document_id=document.document_id,
                source_version=source_version,
                dependency_hash=dependency_hash,
                content_hash=document.content_hash,
            )
            counters.add(
                documents_prepared=1,
                chunks_generated=len(chunks),
                embeddings_created=len(chunks),
            )
        except Exception as error:
            counters.add(failed_sources=1)
            if "claimed" in locals():
                try:
                    await self.state.mark_source_failed(
                        claimed.id,
                        expected_version=claimed.version_number,
                        run_id=run.id,
                        failure=failure_from_exception(error),
                    )
                except RagClaimConflictError:
                    pass

    @staticmethod
    def _is_current(
        state: RagSourceState | None,
        document: object,
        profile: EmbeddingProfile,
    ) -> bool:
        return bool(
            state is not None
            and state.status == RagSourceStatus.CURRENT
            and state.active_document_id == document.document_id  # type: ignore[union-attr]
            and state.last_successful_content_hash == document.content_hash  # type: ignore[union-attr]
            and state.builder_version == document.builder_version  # type: ignore[union-attr]
            and state.chunking_version
            and state.provider_name == profile.provider_name
            and state.model_name == profile.model_name
            and state.embedding_dimension == profile.dimension
        )

    async def _activate_document(
        self,
        *,
        state: RagSourceState,
        document: object,
        chunks: object,
        vectors: dict[str, tuple[float, ...]],
        profile: EmbeddingProfile,
    ) -> None:
        """Replace one derived document atomically after all vectors validate."""

        persisted = await self.session.scalar(
            select(RagDocument).where(RagDocument.source_state_id == state.id)
        )
        values = {
            "source_type": document.source_type,
            "source_key": document.source_key,
            "source_entity_id": document.source_entity_id,
            "source_version": document.source_version,
            "semantic_text": document.semantic_text,
            "provenance_metadata": dict(document.provenance),
            "scope_metadata": document.scope.as_json(),
            "player_ids": list(document.scope.player_ids),
            "team_ids": list(document.scope.team_ids),
            "age_groups": list(document.scope.age_groups),
            "is_all_academy": document.scope.is_all_academy,
            "content_hash": document.content_hash,
            "builder_version": document.builder_version,
            "chunking_version": self.chunker.policy.version,
            "prepared_at": document.prepared_at,
            "is_searchable": True,
        }
        if persisted is None:
            persisted = RagDocument(
                id=document.document_id,
                source_state_id=state.id,
                **values,
            )
            self.session.add(persisted)
        else:
            for key, value in values.items():
                setattr(persisted, key, value)
        await self.session.flush()
        await self.session.execute(
            delete(RagChunk).where(RagChunk.document_id == persisted.id)
        )
        for chunk in chunks:
            self.session.add(
                RagChunk(
                    id=chunk.chunk_id,
                    document_id=persisted.id,
                    source_type=chunk.source_type,
                    source_key=chunk.source_key,
                    ordinal=chunk.ordinal,
                    semantic_text=chunk.semantic_text,
                    content_hash=chunk.content_hash,
                    provenance_metadata=dict(chunk.provenance),
                    scope_metadata=chunk.scope.as_json(),
                    player_ids=list(chunk.scope.player_ids),
                    team_ids=list(chunk.scope.team_ids),
                    age_groups=list(chunk.scope.age_groups),
                    is_all_academy=chunk.scope.is_all_academy,
                    embedding=list(vectors[str(chunk.chunk_id)]),
                    provider_name=profile.provider_name,
                    model_name=profile.model_name,
                    embedding_dimension=profile.dimension,
                    builder_version=chunk.builder_version,
                    chunking_version=chunk.chunking_version,
                    is_searchable=True,
                )
            )
        await self.session.flush()
