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

from sqlalchemy import or_, update
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
