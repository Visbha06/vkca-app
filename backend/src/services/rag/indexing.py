"""RAG-only run/source claims, leases, status, and safe telemetry helpers.

This foundational module intentionally does not traverse domain sources or call
an embedding provider. Story-specific reconciliation is layered on these
short derived-state transactions in later phases.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_index_run import RagIndexRun
from src.models.rag_source_state import RagSourceState
from src.services.rag.canonical import (
    derive_source_id,
    normalize_text,
    stable_component_hash,
)
from src.services.rag.contracts import (
    CanonicalRagDocument,
    EmbeddingProfile,
    RagChunkCandidate,
    RagIndexRunReport,
    RagOperationalStatusReport,
    RagRunCounters,
    RagRunMode,
    RagRunStatus,
    RagSourceDefinition,
    RagSourceStatus,
    RagSourceStatusSummary,
)
from src.services.rag.embedding import (
    RAG_VECTOR_DIMENSION,
    EmbeddingCompatibilityError,
    EmbeddingProvider,
    EmbeddingProviderError,
)
from src.services.rag.registry import validate_built_document

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


class _ChunkingPolicy(Protocol):
    version: str


class _Chunker(Protocol):
    @property
    def policy(self) -> _ChunkingPolicy: ...

    def chunk(
        self, document: CanonicalRagDocument
    ) -> tuple[RagChunkCandidate, ...]: ...


class _SourceRegistry(Protocol):
    def select(
        self, source_types: Sequence[str] | None = None
    ) -> tuple[RagSourceDefinition[object], ...]: ...


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
        builder_version: str | None = None,
        chunking_version: str | None = None,
        profile: EmbeddingProfile | None = None,
        now: datetime | None = None,
    ) -> RagSourceState:
        """Activate success only when the same claim/version still owns the source."""

        completed_at = now or datetime.now(UTC)
        values: dict[str, object] = {
            "status": RagSourceStatus.CURRENT,
            "active_document_id": active_document_id,
            "observed_source_version": source_version,
            "observed_dependency_hash": dependency_hash,
            "observed_content_hash": content_hash,
            "last_successful_content_hash": content_hash,
            "last_success_at": completed_at,
            "failure_code": None,
            "failure_message": None,
            "claim_run_id": None,
            "lease_expires_at": None,
            "version_number": expected_version + 1,
        }
        if builder_version is not None:
            values["builder_version"] = normalize_text(builder_version)
        if chunking_version is not None:
            values["chunking_version"] = normalize_text(chunking_version)
        if profile is not None:
            values.update(
                provider_name=profile.provider_name,
                model_name=profile.model_name,
                embedding_dimension=profile.dimension,
            )
        statement = (
            update(RagSourceState)
            .where(
                RagSourceState.id == state_id,
                RagSourceState.version_number == expected_version,
                RagSourceState.claim_run_id == run_id,
                RagSourceState.status == RagSourceStatus.INDEXING,
            )
            .values(**values)
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
        source_version: str | None = None,
        dependency_hash: str | None = None,
        content_hash: str | None = None,
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
                observed_source_version=source_version,
                observed_dependency_hash=dependency_hash,
                observed_content_hash=content_hash,
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

    async def mark_source_stale(
        self,
        state_id: UUID,
        *,
        expected_version: int,
        failure: TechnicalFailure,
        run_id: UUID | None = None,
        source_version: str | None = None,
        dependency_hash: str | None = None,
        content_hash: str | None = None,
    ) -> RagSourceState:
        """Release a stale claim or flag a compatibility change safely."""

        predicates = [
            RagSourceState.id == state_id,
            RagSourceState.version_number == expected_version,
        ]
        if run_id is not None:
            predicates.append(RagSourceState.claim_run_id == run_id)
        statement = (
            update(RagSourceState)
            .where(*predicates)
            .values(
                status=RagSourceStatus.STALE,
                observed_source_version=source_version,
                observed_dependency_hash=dependency_hash,
                observed_content_hash=content_hash,
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
                "RAG source stale update conflicted with newer state."
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
            source_records_inspected=run.source_records_inspected or 0,
            documents_prepared=run.documents_prepared or 0,
            chunks_generated=run.chunks_generated or 0,
            embeddings_created=run.embeddings_created or 0,
            unchanged_skipped=run.unchanged_skipped or 0,
            deleted_or_ineligible=run.deleted_or_ineligible or 0,
            failed_sources=run.failed_sources or 0,
        ),
        failure_code=run.failure_code,
        failure_message=(
            sanitize_technical_message(run.failure_message)
            if run.failure_message
            else None
        ),
    )


IndexingStateService = RagIndexingStateService


class ReconciliationAction(StrEnum):
    """The bounded action selected after comparing source and derived state."""

    SKIP = "skip"
    REFRESH_METADATA = "refresh_metadata"
    RECONCILE = "reconcile"
    REQUIRE_EXPLICIT_REBUILD = "require_explicit_rebuild"


@dataclass(frozen=True, slots=True)
class SourceReconciliationDecision:
    """Explain why one source is skipped, refreshed, or rebuilt."""

    action: ReconciliationAction
    reasons: frozenset[str]
    requires_embedding: bool


def _scope_payload(value: object) -> Mapping[str, object]:
    scope = getattr(value, "scope", None)
    if scope is not None and callable(getattr(scope, "as_json", None)):
        return scope.as_json()
    persisted = getattr(value, "scope_metadata", None)
    return persisted if isinstance(persisted, Mapping) else {}


def scope_fingerprint(value: object) -> str:
    """Hash only safe intrinsic scope metadata in deterministic key order."""

    return stable_component_hash(_scope_payload(value))


def compare_source_candidate(
    state: RagSourceState | None,
    candidate: CanonicalRagDocument,
    *,
    active_document: RagDocument | None,
    profile: EmbeddingProfile,
    chunking_version: str,
    mode: RagRunMode,
) -> SourceReconciliationDecision:
    """Compare source, dependency, content, scope, and vector compatibility."""

    if state is None:
        return SourceReconciliationDecision(
            action=ReconciliationAction.RECONCILE,
            reasons=frozenset({"missing_source_state", "missing_active_document"}),
            requires_embedding=True,
        )

    reasons: set[str] = set()
    if RagSourceStatus(state.status) is not RagSourceStatus.CURRENT:
        reasons.add("source_status")
    if state.observed_source_version != candidate.source_version:
        reasons.add("source_version")
    if state.observed_dependency_hash != candidate.dependency_fingerprint:
        reasons.add("dependency_fingerprint")
    if state.last_successful_content_hash != candidate.content_hash:
        reasons.add("content_hash")
    if state.builder_version != candidate.builder_version:
        reasons.add("builder_version")
    if state.chunking_version != chunking_version:
        reasons.add("chunking_version")
    if (
        state.provider_name != profile.provider_name
        or state.model_name != profile.model_name
        or state.embedding_dimension != profile.dimension
    ):
        reasons.add("embedding_profile")

    if active_document is None:
        reasons.add("missing_active_document")
    else:
        if state.active_document_id not in {None, active_document.id}:
            reasons.add("active_document_identity")
        if not active_document.is_searchable:
            reasons.add("searchability")
        if scope_fingerprint(active_document) != scope_fingerprint(candidate):
            reasons.add("scope_fingerprint")

    frozen_reasons = frozenset(reasons)
    if not frozen_reasons:
        return SourceReconciliationDecision(
            action=ReconciliationAction.SKIP,
            reasons=frozen_reasons,
            requires_embedding=False,
        )
    if "embedding_profile" in reasons and mode in {
        RagRunMode.INCREMENTAL,
        RagRunMode.REPAIR,
    }:
        return SourceReconciliationDecision(
            action=ReconciliationAction.REQUIRE_EXPLICIT_REBUILD,
            reasons=frozen_reasons,
            requires_embedding=False,
        )

    embedding_reasons = {
        "content_hash",
        "chunking_version",
        "embedding_profile",
        "missing_active_document",
        "active_document_identity",
    }
    requires_embedding = bool(reasons.intersection(embedding_reasons))
    return SourceReconciliationDecision(
        action=(
            ReconciliationAction.RECONCILE
            if requires_embedding
            else ReconciliationAction.REFRESH_METADATA
        ),
        reasons=frozen_reasons,
        requires_embedding=requires_embedding,
    )


def reusable_chunk_vectors(
    candidates: Sequence[RagChunkCandidate],
    existing_chunks: Sequence[RagChunk],
    *,
    profile: EmbeddingProfile,
) -> dict[str, tuple[float, ...]]:
    """Return only compatible unchanged vectors, keyed by deterministic chunk ID."""

    existing_by_id = {chunk.id: chunk for chunk in existing_chunks}
    reusable: dict[str, tuple[float, ...]] = {}
    for candidate in candidates:
        persisted = existing_by_id.get(candidate.chunk_id)
        if persisted is None:
            continue
        if (
            persisted.content_hash != candidate.content_hash
            or persisted.chunking_version != candidate.chunking_version
            or persisted.provider_name != profile.provider_name
            or persisted.model_name != profile.model_name
            or persisted.embedding_dimension != profile.dimension
        ):
            continue
        try:
            vector = tuple(float(item) for item in persisted.embedding)
        except (TypeError, ValueError):
            continue
        if len(vector) != profile.dimension or not all(
            math.isfinite(item) for item in vector
        ):
            continue
        magnitude = math.sqrt(sum(item * item for item in vector))
        if not math.isclose(magnitude, 1.0, rel_tol=1e-4, abs_tol=1e-4):
            continue
        reusable[str(candidate.chunk_id)] = vector
    return reusable


@dataclass(slots=True)
class _SourcePlan:
    definition: RagSourceDefinition[object]
    loaded: object
    state_id: UUID
    state_version: int
    active_document: RagDocument | None
    existing_chunks: tuple[RagChunk, ...]
    document: CanonicalRagDocument
    chunks: tuple[RagChunkCandidate, ...]
    reused_vectors: dict[str, tuple[float, ...]]
    source_fingerprint: str


class RagIndexingService:
    """Reconcile registered sources with bounded provider and derived transactions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        provider: EmbeddingProvider,
        batch_size: int,
        timeout_seconds: float,
        registry: _SourceRegistry | None = None,
        chunker: _Chunker | None = None,
    ) -> None:
        from src.services.rag.chunking import RagChunker
        from src.services.rag.embedding import EmbeddingBatcher
        from src.services.rag.registry import source_registry

        if not all(
            hasattr(provider, attribute)
            for attribute in ("profile", "embed_documents", "embed_query")
        ):
            raise TypeError("provider must implement the embedding provider contract")
        if provider.profile.dimension != RAG_VECTOR_DIMENSION:
            raise EmbeddingCompatibilityError(
                "Embedding dimension is incompatible with vector(1536); a migration "
                "and full rebuild are required."
            )
        self.session = session
        self.provider = provider
        self.registry: _SourceRegistry = registry or source_registry
        self.chunker = cast(_Chunker, chunker or RagChunker())
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

    async def run_incremental(self) -> RagIndexRunReport:
        """Reconcile changed, missing, stale, and ineligible registered sources."""

        return await self.run(RagRunMode.INCREMENTAL)

    async def run_repair(self) -> RagIndexRunReport:
        """Retry recoverable source state while skipping compatible current rows."""

        return await self.run(RagRunMode.REPAIR)

    async def inspect_status(
        self,
        *,
        run_id: UUID | None = None,
        source_type: str | None = None,
        limit: int = 100,
        now: datetime | None = None,
    ) -> RagOperationalStatusReport:
        """Read bounded operational rows without selecting documents or chunks.

        This is intentionally a projection over ``RagIndexRun`` and
        ``RagSourceState`` only.  Keeping document/chunk tables out of this
        method prevents accidental exposure of canonical text or vectors in
        normal operator diagnostics.
        """

        if not 1 <= limit <= 100:
            raise ValueError("RAG status limit must be between 1 and 100")
        selected_type = (
            normalize_text(source_type).casefold() if source_type is not None else None
        )
        if source_type is not None and not selected_type:
            raise ValueError("RAG status source_type must not be blank")

        run_statement = select(RagIndexRun).order_by(
            RagIndexRun.started_at.desc(), RagIndexRun.id
        ).limit(limit)
        if run_id is not None:
            run_statement = run_statement.where(RagIndexRun.id == run_id)
        if selected_type is not None:
            run_statement = run_statement.where(
                RagIndexRun.source_type == selected_type
            )
        runs = tuple((await self.session.scalars(run_statement)).all())

        state_statement = select(RagSourceState).order_by(
            RagSourceState.source_type, RagSourceState.source_key
        ).limit(limit)
        if selected_type is not None:
            state_statement = state_statement.where(
                RagSourceState.source_type == selected_type
            )
        states = tuple((await self.session.scalars(state_statement)).all())
        inspected_at = now or datetime.now(UTC)
        counts: dict[str, int] = {}
        summaries: list[RagSourceStatusSummary] = []
        for state in states:
            status = RagSourceStatus(state.status)
            counts[status.value] = counts.get(status.value, 0) + 1
            recoverable = status in {
                RagSourceStatus.PENDING,
                RagSourceStatus.STALE,
                RagSourceStatus.FAILED,
            }
            if status is RagSourceStatus.INDEXING and (
                state.lease_expires_at is None or state.lease_expires_at <= inspected_at
            ):
                recoverable = True
            summaries.append(
                RagSourceStatusSummary(
                    source_type=state.source_type,
                    source_key=state.source_key,
                    status=status,
                    observed_source_version=state.observed_source_version,
                    builder_version=state.builder_version,
                    provider_name=state.provider_name,
                    model_name=state.model_name,
                    embedding_dimension=state.embedding_dimension,
                    last_attempt_at=state.last_attempt_at,
                    last_success_at=state.last_success_at,
                    failure_code=state.failure_code,
                    failure_message=(
                        sanitize_technical_message(state.failure_message)
                        if state.failure_message
                        else None
                    ),
                    recoverable=recoverable,
                )
            )
        return RagOperationalStatusReport(
            runs=tuple(report_from_run(run) for run in runs),
            sources=tuple(summaries),
            source_filter=selected_type,
            status_counts=dict(sorted(counts.items())),
            recoverable_source_count=sum(item.recoverable for item in summaries),
        )

    async def run(
        self,
        mode: RagRunMode,
        *,
        source_type: str | None = None,
    ) -> RagIndexRunReport:
        """Execute one bounded mode and persist only aggregate, sanitized telemetry."""

        if mode not in set(RagRunMode):
            raise ValueError("unsupported RAG indexing mode")
        if mode is RagRunMode.TARGETED:
            if source_type is None:
                raise ValueError("targeted RAG runs require source_type")
            definitions = self.registry.select((source_type,))
        else:
            definitions = self.registry.select()
            source_type = None

        run = await self.state.start_run(mode, source_type=source_type)
        run_id = run.id
        await self.session.commit()
        counters = RagRunCounters()
        try:
            for definition in definitions:
                await self._traverse_definition(
                    run,
                    definition,
                    counters,
                    mode=mode,
                )
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
            failure = failure_from_exception(error)
            persisted_run = await self.session.get(RagIndexRun, run_id)
            if persisted_run is None:
                persisted_run = await self.state.start_run(
                    mode, source_type=source_type
                )
            await self.state.finish_run(
                persisted_run,
                status=RagRunStatus.FAILED,
                counters=counters,
                failure=failure,
            )
            await self.session.commit()
            return report_from_run(persisted_run)

    async def _traverse_definition(
        self,
        run: RagIndexRun,
        definition: RagSourceDefinition[object],
        counters: RagRunCounters,
        *,
        mode: RagRunMode,
    ) -> None:
        cursor: str | None = None
        seen_cursors: set[str] = set()
        seen_keys: set[str] = set()
        while True:
            page = await definition.loader.load_batch(  # type: ignore[union-attr]
                self.session, cursor=cursor, limit=100
            )
            for loaded in page.items:
                seen_keys.add(definition.source_key(loaded))  # type: ignore[union-attr]
            await self._process_page(
                run,
                definition,
                page.items,
                counters,
                mode=mode,
                cursor=cursor,
                limit=100,
            )
            if page.next_cursor is None:
                break
            if page.next_cursor in seen_cursors:
                raise RuntimeError(
                    "registered RAG source loader produced a cursor cycle"
                )
            seen_cursors.add(page.next_cursor)
            cursor = page.next_cursor
        await self._reconcile_missing(definition, seen_keys, counters)

    async def _load_existing_graph(
        self,
        source_type: str,
        source_keys: Sequence[str],
    ) -> tuple[
        dict[str, RagSourceState],
        dict[UUID, RagDocument],
        dict[UUID, tuple[RagChunk, ...]],
    ]:
        if not source_keys:
            return {}, {}, {}
        states = tuple(
            (
                await self.session.scalars(
                    select(RagSourceState).where(
                        RagSourceState.source_type == source_type,
                        RagSourceState.source_key.in_(source_keys),
                    )
                )
            ).all()
        )
        states_by_key = {state.source_key: state for state in states}
        if not states:
            return states_by_key, {}, {}
        state_ids = tuple(state.id for state in states)
        documents = tuple(
            (
                await self.session.scalars(
                    select(RagDocument).where(
                        RagDocument.source_state_id.in_(state_ids)
                    )
                )
            ).all()
        )
        documents_by_state = {
            document.source_state_id: document for document in documents
        }
        if not documents:
            return states_by_key, documents_by_state, {}
        chunks = tuple(
            (
                await self.session.scalars(
                    select(RagChunk)
                    .where(
                        RagChunk.document_id.in_(
                            tuple(document.id for document in documents)
                        )
                    )
                    .order_by(RagChunk.document_id, RagChunk.ordinal)
                )
            ).all()
        )
        chunks_by_document: defaultdict[UUID, list[RagChunk]] = defaultdict(list)
        for chunk in chunks:
            chunks_by_document[chunk.document_id].append(chunk)
        return (
            states_by_key,
            documents_by_state,
            {
                document_id: tuple(items)
                for document_id, items in chunks_by_document.items()
            },
        )

    @staticmethod
    def _loaded_fingerprint(loaded: object, document: CanonicalRagDocument) -> str:
        value = getattr(loaded, "source_fingerprint", None)
        if value is not None:
            return normalize_text(str(value))
        return stable_component_hash(
            document.source_version,
            document.dependency_fingerprint,
            document.content_hash,
            document.scope.as_json(),
        )

    async def _process_page(
        self,
        run: RagIndexRun,
        definition: RagSourceDefinition[object],
        loaded_items: Sequence[object],
        counters: RagRunCounters,
        *,
        mode: RagRunMode,
        cursor: str | None,
        limit: int,
    ) -> None:
        source_type = definition.source_type  # type: ignore[union-attr]
        source_keys = tuple(
            definition.source_key(loaded)
            for loaded in loaded_items  # type: ignore[union-attr]
        )
        states, documents, chunks_by_document = await self._load_existing_graph(
            source_type, source_keys
        )
        plans: list[_SourcePlan] = []
        for loaded, source_key in zip(loaded_items, source_keys, strict=True):
            counters.add(source_records_inspected=1)
            existing_state = states.get(source_key)
            active_document = (
                documents.get(existing_state.id) if existing_state is not None else None
            )
            if not definition.eligible(loaded):  # type: ignore[union-attr]
                if existing_state is not None and (
                    RagSourceStatus(existing_state.status)
                    is not RagSourceStatus.INELIGIBLE
                    or (active_document is not None and active_document.is_searchable)
                ):
                    await self.state.mark_source_unsearchable(
                        existing_state.id,
                        expected_version=existing_state.version_number,
                        status=RagSourceStatus.INELIGIBLE,
                    )
                    counters.add(deleted_or_ineligible=1)
                continue

            document = definition.build(loaded)  # type: ignore[union-attr]
            validate_built_document(definition, loaded, document)  # type: ignore[arg-type]
            profile = self.provider.profile
            state = existing_state or await self.state.create_source_state(
                source_type=source_type,
                source_key=source_key,
                source_entity_id=document.source_entity_id,
                builder_version=document.builder_version,
                chunking_version=self.chunker.policy.version,
                profile=profile,
            )
            decision = compare_source_candidate(
                existing_state,
                document,
                active_document=active_document,
                profile=profile,
                chunking_version=self.chunker.policy.version,
                mode=mode,
            )
            if decision.action is ReconciliationAction.SKIP:
                counters.add(unchanged_skipped=1)
                continue
            if decision.action is ReconciliationAction.REQUIRE_EXPLICIT_REBUILD:
                await self.state.mark_source_stale(
                    state.id,
                    expected_version=state.version_number,
                    failure=technical_failure(
                        "incompatible_profile",
                        "Embedding profile changed; run a targeted or full rebuild.",
                    ),
                    source_version=document.source_version,
                    dependency_hash=document.dependency_fingerprint,
                    content_hash=document.content_hash,
                )
                counters.add(failed_sources=1)
                continue
            try:
                claimed = await self.state.claim_source(
                    state.id,
                    expected_version=state.version_number,
                    run_id=run.id,
                )
            except RagClaimConflictError:
                counters.add(failed_sources=1)
                continue
            chunks = self.chunker.chunk(document)
            existing_chunks = (
                chunks_by_document.get(active_document.id, ())
                if active_document is not None
                else ()
            )
            plans.append(
                _SourcePlan(
                    definition=definition,
                    loaded=loaded,
                    state_id=claimed.id,
                    state_version=claimed.version_number,
                    active_document=active_document,
                    existing_chunks=existing_chunks,
                    document=document,
                    chunks=chunks,
                    reused_vectors=reusable_chunk_vectors(
                        chunks, existing_chunks, profile=profile
                    ),
                    source_fingerprint=self._loaded_fingerprint(loaded, document),
                )
            )

        # Persist claims/invalidation before any external provider call.
        await self.session.commit()
        if not plans:
            return

        missing_chunks = tuple(
            chunk
            for plan in plans
            for chunk in plan.chunks
            if str(chunk.chunk_id) not in plan.reused_vectors
        )
        embedded_vectors: dict[str, tuple[float, ...]] = {}
        if missing_chunks:
            from src.services.rag.contracts import as_embedding_inputs

            try:
                batch = await self.batcher.embed_documents(
                    self.provider,
                    as_embedding_inputs(missing_chunks),
                    profile=self.provider.profile,
                )
                embedded_vectors = {
                    vector.item_key: vector.values for vector in batch.vectors
                }
            except Exception as error:
                await self._fail_plans(plans, run, failure_from_exception(error))
                counters.add(failed_sources=len(plans))
                return

        try:
            fresh_page = await definition.loader.load_batch(  # type: ignore[union-attr]
                self.session,
                cursor=cursor,
                limit=limit,
            )
        except Exception as error:
            await self.session.rollback()
            await self._fail_plans(plans, run, failure_from_exception(error))
            counters.add(failed_sources=len(plans))
            return
        fresh_by_key = {
            definition.source_key(item): item  # type: ignore[union-attr]
            for item in fresh_page.items
        }
        for plan in plans:
            source_key = plan.document.source_key
            fresh = fresh_by_key.get(source_key)
            if fresh is None or not definition.eligible(fresh):  # type: ignore[union-attr]
                status = (
                    RagSourceStatus.DELETED
                    if fresh is None
                    else RagSourceStatus.INELIGIBLE
                )
                try:
                    await self.state.mark_source_unsearchable(
                        plan.state_id,
                        expected_version=plan.state_version,
                        status=status,
                    )
                    await self.session.commit()
                    counters.add(deleted_or_ineligible=1)
                except RagClaimConflictError:
                    await self.session.rollback()
                    counters.add(failed_sources=1)
                continue
            fresh_document = definition.build(fresh)  # type: ignore[union-attr]
            fresh_fingerprint = self._loaded_fingerprint(fresh, fresh_document)
            if (
                fresh_fingerprint != plan.source_fingerprint
                or fresh_document.content_hash != plan.document.content_hash
                or scope_fingerprint(fresh_document) != scope_fingerprint(plan.document)
            ):
                try:
                    await self.state.mark_source_stale(
                        plan.state_id,
                        expected_version=plan.state_version,
                        run_id=run.id,
                        failure=technical_failure(
                            "source_changed",
                            "Authoritative source changed during embedding; retry.",
                        ),
                        source_version=fresh_document.source_version,
                        dependency_hash=fresh_document.dependency_fingerprint,
                        content_hash=fresh_document.content_hash,
                    )
                    await self.session.commit()
                except RagClaimConflictError:
                    await self.session.rollback()
                counters.add(failed_sources=1)
                continue

            vectors = dict(plan.reused_vectors)
            vectors.update(
                {
                    str(chunk.chunk_id): embedded_vectors[str(chunk.chunk_id)]
                    for chunk in plan.chunks
                    if str(chunk.chunk_id) not in plan.reused_vectors
                }
            )
            try:
                await self._activate_document(
                    state_id=plan.state_id,
                    document=plan.document,
                    chunks=plan.chunks,
                    vectors=vectors,
                    profile=self.provider.profile,
                    persisted=plan.active_document,
                    existing_chunks=plan.existing_chunks,
                )
                await self.state.mark_source_current(
                    plan.state_id,
                    expected_version=plan.state_version,
                    run_id=run.id,
                    active_document_id=plan.document.document_id,
                    source_version=plan.document.source_version,
                    dependency_hash=plan.document.dependency_fingerprint,
                    content_hash=plan.document.content_hash,
                    builder_version=plan.document.builder_version,
                    chunking_version=self.chunker.policy.version,
                    profile=self.provider.profile,
                )
                await self.session.commit()
                counters.add(
                    documents_prepared=1,
                    chunks_generated=len(plan.chunks),
                    embeddings_created=(len(plan.chunks) - len(plan.reused_vectors)),
                    unchanged_skipped=len(plan.reused_vectors),
                )
            except Exception as error:
                await self.session.rollback()
                current = await self.session.get(RagSourceState, plan.state_id)
                if (
                    current is not None
                    and current.claim_run_id == run.id
                    and RagSourceStatus(current.status) is RagSourceStatus.INDEXING
                ):
                    try:
                        await self.state.mark_source_failed(
                            current.id,
                            expected_version=current.version_number,
                            run_id=run.id,
                            failure=failure_from_exception(error),
                            source_version=plan.document.source_version,
                            dependency_hash=plan.document.dependency_fingerprint,
                            content_hash=plan.document.content_hash,
                        )
                        await self.session.commit()
                    except RagClaimConflictError:
                        await self.session.rollback()
                counters.add(failed_sources=1)

    async def _fail_plans(
        self,
        plans: Sequence[_SourcePlan],
        run: RagIndexRun,
        failure: TechnicalFailure,
    ) -> None:
        """Persist one sanitized failure for every claimed all-or-nothing candidate."""

        for plan in plans:
            try:
                await self.state.mark_source_failed(
                    plan.state_id,
                    expected_version=plan.state_version,
                    run_id=run.id,
                    failure=failure,
                    source_version=plan.document.source_version,
                    dependency_hash=plan.document.dependency_fingerprint,
                    content_hash=plan.document.content_hash,
                )
            except RagClaimConflictError:
                continue
        await self.session.commit()

    async def _reconcile_missing(
        self,
        definition: RagSourceDefinition[object],
        seen_keys: set[str],
        counters: RagRunCounters,
    ) -> None:
        states = tuple(
            (
                await self.session.scalars(
                    select(RagSourceState).where(
                        RagSourceState.source_type == definition.source_type  # type: ignore[union-attr]
                    )
                )
            ).all()
        )
        previous_keys = {state.source_key for state in states}
        deleted_keys = definition.deletion_policy.reconcile_deleted(  # type: ignore[union-attr]
            seen_keys=seen_keys,
            previous_keys=previous_keys,
        )
        states_by_key = {state.source_key: state for state in states}
        for source_key in deleted_keys:
            state = states_by_key[source_key]
            if RagSourceStatus(state.status) is RagSourceStatus.DELETED:
                continue
            try:
                await self.state.mark_source_unsearchable(
                    state.id,
                    expected_version=state.version_number,
                    status=RagSourceStatus.DELETED,
                )
                counters.add(deleted_or_ineligible=1)
            except RagClaimConflictError:
                counters.add(failed_sources=1)
        await self.session.commit()

    async def _activate_document(
        self,
        *,
        state_id: UUID,
        document: CanonicalRagDocument,
        chunks: Sequence[RagChunkCandidate],
        vectors: dict[str, tuple[float, ...]],
        profile: EmbeddingProfile,
        persisted: RagDocument | None,
        existing_chunks: Sequence[RagChunk],
    ) -> None:
        """Reconcile one complete candidate atomically after all vectors validate."""

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
            "indexed_at": datetime.now(UTC),
            "is_searchable": True,
        }
        if persisted is None:
            persisted = RagDocument(
                id=document.document_id,
                source_state_id=state_id,
                **values,
            )
            self.session.add(persisted)
        else:
            for key, value in values.items():
                setattr(persisted, key, value)
        await self.session.flush()
        desired_ids = {chunk.chunk_id for chunk in chunks}
        obsolete_ids = {
            chunk.id for chunk in existing_chunks if chunk.id not in desired_ids
        }
        if obsolete_ids:
            await self.session.execute(
                delete(RagChunk).where(RagChunk.id.in_(obsolete_ids))
            )
        existing_by_id = {chunk.id: chunk for chunk in existing_chunks}
        for chunk in chunks:
            chunk_values: dict[str, Any] = {
                "document_id": persisted.id,
                "source_type": chunk.source_type,
                "source_key": chunk.source_key,
                "ordinal": chunk.ordinal,
                "semantic_text": chunk.semantic_text,
                "content_hash": chunk.content_hash,
                "provenance_metadata": dict(chunk.provenance),
                "scope_metadata": chunk.scope.as_json(),
                "player_ids": list(chunk.scope.player_ids),
                "team_ids": list(chunk.scope.team_ids),
                "age_groups": list(chunk.scope.age_groups),
                "is_all_academy": chunk.scope.is_all_academy,
                "embedding": list(vectors[str(chunk.chunk_id)]),
                "provider_name": profile.provider_name,
                "model_name": profile.model_name,
                "embedding_dimension": profile.dimension,
                "builder_version": chunk.builder_version,
                "chunking_version": chunk.chunking_version,
                "is_searchable": True,
            }
            persisted_chunk = existing_by_id.get(chunk.chunk_id)
            if persisted_chunk is None:
                self.session.add(RagChunk(id=chunk.chunk_id, **chunk_values))
            else:
                for key, value in chunk_values.items():
                    setattr(persisted_chunk, key, value)
        await self.session.flush()
