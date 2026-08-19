"""Dedicated generic worker lifecycle and execution adapter."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import random
from collections.abc import Callable, MutableMapping
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any, Final, Protocol, cast
from uuid import UUID, uuid4

from arq import Retry
from pydantic import ValidationError

from src.config import Settings, get_settings
from src.database import create_database_resources
from src.models.background_work_item import BackgroundWorkItem
from src.schemas.background_jobs import WorkerExecutionReport
from src.services.background_jobs.contracts import (
    BackgroundJobEnvelopeV1,
    BackgroundPayloadValidationError,
    BackgroundWorkConflictError,
    BackgroundWorkState,
    IncompatiblePayloadVersionError,
    UnregisteredBackgroundJobError,
    decode_job_envelope,
)
from src.services.background_jobs.logging import redact_structured_fields
from src.services.background_jobs.outbox import (
    BackgroundJobOutbox,
    BackgroundWorkNotFoundError,
    BackgroundWorkTransitionError,
    utc_now,
)
from src.services.background_jobs.registry import (
    BackgroundJobRegistry,
    build_background_job_registry,
)
from src.services.background_jobs.retry import (
    FailureCategory,
    FailureClassification,
    RandomUniform,
    RetryDisposition,
    RetryPolicy,
    build_retry_decision,
)

BACKGROUND_RESOURCES_KEY: Final = "background_resources"
_EXECUTION_STARTED: ContextVar[float | None] = ContextVar(
    "background_execution_started",
    default=None,
)
logger = logging.getLogger(__name__)


class WorkerDatabaseResources(Protocol):
    """Database resource shape accepted by the worker lifecycle."""

    session_factory: Callable[[], Any]

    async def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class BackgroundHandlerContext:
    """Startup-owned dependencies supplied to registered application handlers."""

    settings: Settings
    session_factory: object
    redis: object | None
    provider: object | None
    registry: BackgroundJobRegistry


@dataclass(frozen=True, slots=True)
class BackgroundWorkerResources:
    """Resources created and released by the dedicated worker lifecycle."""

    settings: Settings
    database: WorkerDatabaseResources
    registry: BackgroundJobRegistry
    outbox: BackgroundJobOutbox
    redis: object | None
    provider: object | None
    runtime: BackgroundWorkerRuntime


class BackgroundWorkerRuntime:
    """Claim durable work and execute only its registered typed handler."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        registry: BackgroundJobRegistry,
        outbox: BackgroundJobOutbox,
        handler_context: object,
        worker_id: str,
        lease_seconds: int,
        clock: Callable[[], datetime] = utc_now,
        random_uniform: RandomUniform,
    ) -> None:
        normalized_worker_id = worker_id.strip()
        if not 1 <= len(normalized_worker_id) <= 128:
            raise ValueError("worker_id must be non-blank and at most 128 characters")
        if not 1 <= lease_seconds <= 3_600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        self.session_factory = session_factory
        self.registry = registry
        self.outbox = outbox
        self.handler_context = handler_context
        self.worker_id = normalized_worker_id
        self.lease_seconds = lease_seconds
        self.clock = clock
        self.random_uniform = random_uniform

    async def execute(
        self,
        envelope: BackgroundJobEnvelopeV1 | dict[str, object] | bytes | str,
        *,
        defer_retry: bool = False,
    ) -> WorkerExecutionReport:
        """Execute one work item while measuring its bounded worker outcome."""

        token = _EXECUTION_STARTED.set(perf_counter())
        try:
            return await self._execute(envelope, defer_retry=defer_retry)
        finally:
            _EXECUTION_STARTED.reset(token)

    async def _execute(
        self,
        envelope: BackgroundJobEnvelopeV1 | dict[str, object] | bytes | str,
        *,
        defer_retry: bool = False,
    ) -> WorkerExecutionReport:
        """Execute one queue reference through durable claim and terminal state."""

        parsed = self._parse_envelope(envelope)
        now = self._now()
        async with self.session_factory() as session:
            async with session.begin():
                current = await self.outbox.reload(session, parsed.work_id)
                if current is None:
                    raise BackgroundWorkNotFoundError(
                        f"Background work {parsed.work_id} was not found."
                    )
                current_state = self._state(current.state)
                if current_state not in {
                    BackgroundWorkState.DISPATCHED,
                    BackgroundWorkState.RETRYING,
                }:
                    return self._report(current)
                try:
                    running = await self.outbox.claim_for_execution(
                        session,
                        parsed.work_id,
                        expected_version=current.version_number,
                        lease_owner=self.worker_id,
                        lease_seconds=self.lease_seconds,
                        now=now,
                    )
                except (
                    BackgroundWorkConflictError,
                    BackgroundWorkTransitionError,
                ) as exc:
                    winner = (
                        exc.current
                        if isinstance(exc, BackgroundWorkConflictError)
                        else current
                    )
                    if isinstance(winner, BackgroundWorkItem):
                        return self._report(winner)
                    return self._report(current)

        try:
            definition = self.registry.get(
                running.job_type,
                payload_version=running.payload_version,
            )
            typed_payload = definition.payload_adapter.validate(running.payload)
        except UnregisteredBackgroundJobError:
            return await self._mark_terminal(
                running,
                FailureCategory.UNREGISTERED_JOB,
                now=now,
            )
        except IncompatiblePayloadVersionError:
            return await self._mark_terminal(
                running,
                FailureCategory.INCOMPATIBLE_PAYLOAD_VERSION,
                now=now,
            )
        except BackgroundPayloadValidationError:
            return await self._mark_terminal(
                running,
                FailureCategory.INVALID_PAYLOAD,
                now=now,
            )

        required_lease_seconds = max(
            self.lease_seconds,
            math.ceil(definition.timeout_seconds) + 30,
        )
        if required_lease_seconds > self.lease_seconds:
            renewal_now = self._now()
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        running = await self.outbox.renew_execution_lease(
                            session,
                            running.id,
                            expected_version=running.version_number,
                            lease_owner=self.worker_id,
                            lease_seconds=required_lease_seconds,
                            now=renewal_now,
                        )
            except BackgroundWorkConflictError as conflict:
                if isinstance(conflict.current, BackgroundWorkItem):
                    return self._report(conflict.current, work_id=parsed.work_id)
                return self._report(running, work_id=parsed.work_id)

        try:
            async with asyncio.timeout(definition.timeout_seconds):
                await definition.handler(self.handler_context, typed_payload)
        except asyncio.CancelledError:
            await self._persist_cancellation(
                running,
                definition.retry_policy,
                now=self._now(),
            )
            self._log_outcome(
                running,
                outcome="cancelled",
                failure_category=FailureCategory.TIMEOUT.value,
                retry_status="recovery_persisted",
            )
            raise
        except Exception as error:
            failure_now = self._now()
            report, delay = await self._persist_failure(
                running,
                error,
                definition.retry_policy,
                now=failure_now,
                classifier=definition.retry_classifier,
            )
            if defer_retry and report.state is BackgroundWorkState.RETRYING:
                raise Retry(defer=delay) from None
            return report

        completion_now = self._now()
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    completed = await self.outbox.mark_completed(
                        session,
                        running.id,
                        expected_version=running.version_number,
                        lease_owner=self.worker_id,
                        now=completion_now,
                    )
            return self._report(completed, work_id=parsed.work_id)
        except BackgroundWorkConflictError as conflict:
            if isinstance(conflict.current, BackgroundWorkItem):
                return self._report(conflict.current, work_id=parsed.work_id)
            return self._report(running, work_id=parsed.work_id)

    async def _mark_terminal(
        self,
        running: BackgroundWorkItem,
        category: FailureCategory,
        *,
        now: datetime,
    ) -> WorkerExecutionReport:
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    dead = await self.outbox.mark_dead(
                        session,
                        running.id,
                        expected_version=running.version_number,
                        lease_owner=self.worker_id,
                        category=category,
                        now=now,
                    )
            return self._report(
                dead, failure_category=category.value, work_id=running.id
            )
        except BackgroundWorkConflictError as conflict:
            if isinstance(conflict.current, BackgroundWorkItem):
                return self._report(conflict.current, work_id=running.id)
            return self._report(running, work_id=running.id)

    async def _persist_failure(
        self,
        running: BackgroundWorkItem,
        error: BaseException,
        policy: RetryPolicy,
        *,
        now: datetime,
        classifier: Callable[[BaseException], FailureClassification],
    ) -> tuple[WorkerExecutionReport, float | None]:
        decision = build_retry_decision(
            error,
            attempt_count=max(running.execution_attempt_count, 1),
            policy=policy,
            now=now,
            random_uniform=self.random_uniform,
            classifier=classifier,
        )
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    if decision.disposition is RetryDisposition.RETRY:
                        assert decision.run_after is not None
                        item = await self.outbox.mark_retrying(
                            session,
                            running.id,
                            expected_version=running.version_number,
                            lease_owner=self.worker_id,
                            category=decision.category,
                            run_after=decision.run_after,
                            now=now,
                        )
                    elif decision.disposition is RetryDisposition.SAFE_NOOP:
                        item = await self.outbox.mark_completed(
                            session,
                            running.id,
                            expected_version=running.version_number,
                            lease_owner=self.worker_id,
                            now=now,
                        )
                    else:
                        item = await self.outbox.mark_dead(
                            session,
                            running.id,
                            expected_version=running.version_number,
                            lease_owner=self.worker_id,
                            category=decision.category,
                            now=now,
                        )
            return (
                self._report(
                    item,
                    failure_category=decision.category.value,
                    work_id=running.id,
                ),
                decision.delay_seconds,
            )
        except BackgroundWorkConflictError as conflict:
            winner = conflict.current
            if isinstance(winner, BackgroundWorkItem):
                return self._report(winner, work_id=running.id), None
            return self._report(running, work_id=running.id), None

    async def _persist_cancellation(
        self,
        running: BackgroundWorkItem,
        policy: RetryPolicy,
        *,
        now: datetime,
    ) -> None:
        decision = build_retry_decision(
            TimeoutError(),
            attempt_count=max(running.execution_attempt_count, 1),
            policy=policy,
            now=now,
            random_uniform=self.random_uniform,
        )
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    if decision.disposition is RetryDisposition.RETRY:
                        assert decision.run_after is not None
                        await self.outbox.mark_retrying(
                            session,
                            running.id,
                            expected_version=running.version_number,
                            lease_owner=self.worker_id,
                            category=FailureCategory.TIMEOUT,
                            run_after=decision.run_after,
                            now=now,
                        )
                    else:
                        await self.outbox.mark_dead(
                            session,
                            running.id,
                            expected_version=running.version_number,
                            lease_owner=self.worker_id,
                            category=FailureCategory.RETRY_LIMIT_EXHAUSTED,
                            now=now,
                        )
        except BackgroundWorkConflictError:
            return

    @staticmethod
    def _parse_envelope(
        envelope: BackgroundJobEnvelopeV1 | dict[str, object] | bytes | str,
    ) -> BackgroundJobEnvelopeV1:
        if isinstance(envelope, BackgroundJobEnvelopeV1):
            return envelope
        if isinstance(envelope, (bytes, str)):
            return decode_job_envelope(envelope)
        if isinstance(envelope, dict):
            try:
                return BackgroundJobEnvelopeV1.model_validate(envelope)
            except ValidationError as exc:
                raise BackgroundPayloadValidationError(
                    "Queue envelope does not match contract version 1."
                ) from exc
        raise BackgroundPayloadValidationError("Queue envelope has an invalid type.")

    @staticmethod
    def _state(value: BackgroundWorkState | str) -> BackgroundWorkState:
        return (
            value
            if isinstance(value, BackgroundWorkState)
            else BackgroundWorkState(value)
        )

    def _now(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Worker clocks must be timezone-aware")
        return now

    def _report(
        self,
        item: BackgroundWorkItem,
        *,
        failure_category: str | None = None,
        work_id: UUID | None = None,
    ) -> WorkerExecutionReport:
        report = WorkerExecutionReport(
            work_id=item.id if work_id is None else work_id,
            state=self._state(item.state),
            failure_category=failure_category or item.last_failure_category,
        )
        self._log_outcome(
            item,
            outcome=report.state.value,
            failure_category=report.failure_category,
        )
        return report

    @staticmethod
    def _log_outcome(
        item: BackgroundWorkItem,
        *,
        outcome: str,
        failure_category: str | None,
        retry_status: str | None = None,
    ) -> None:
        """Emit one safe execution outcome with no payload or exception text."""

        state = BackgroundWorkState(item.state)
        started = _EXECUTION_STARTED.get()
        duration_ms = (
            round((perf_counter() - started) * 1_000, 3) if started is not None else 0.0
        )
        fields = redact_structured_fields(
            {
                "event": "background_job_execution",
                "work_id": str(item.id),
                "job_type": item.job_type,
                "attempt": item.execution_attempt_count,
                "duration_ms": duration_ms,
                "outcome": outcome,
                "retry_status": retry_status
                or (
                    "scheduled"
                    if state is BackgroundWorkState.RETRYING
                    else "terminal"
                    if state is BackgroundWorkState.DEAD
                    else "not_retrying"
                ),
                "failure_category": failure_category,
                "correlation_id": (
                    str(item.correlation_id)
                    if item.correlation_id is not None
                    else None
                ),
                "source_type": item.source_type,
                "source_key": item.source_key,
            }
        )
        logger.info("background_job_execution", extra={"background_job": fields})


async def _maybe_await(value: object) -> object:
    return await value if inspect.isawaitable(value) else value


async def worker_startup(ctx: MutableMapping[object, object]) -> None:
    """Create worker-owned database, provider, registry, and execution resources."""

    if BACKGROUND_RESOURCES_KEY in ctx:
        return
    settings = cast(Settings, ctx.get("settings") or get_settings())
    database_factory = cast(
        Callable[[object], object],
        ctx.get("database_factory") or create_database_resources,
    )
    registry_factory = cast(Callable[[], object] | None, ctx.get("registry_factory"))
    provider_factory = cast(Callable[[], object] | None, ctx.get("provider_factory"))

    database = cast(
        WorkerDatabaseResources,
        await _maybe_await(database_factory(str(settings.database_url))),
    )
    registry = await _maybe_await(
        registry_factory()
        if registry_factory is not None
        else build_background_job_registry(settings=settings)
    )
    if provider_factory is not None:
        provider = await _maybe_await(provider_factory())
    else:
        from src.services.rag.embedding import create_embedding_provider

        provider = create_embedding_provider(settings)
    if not isinstance(registry, BackgroundJobRegistry):
        raise TypeError("registry_factory must return BackgroundJobRegistry")
    worker_id = str(ctx.get("worker_id") or f"worker:{uuid4()}")
    outbox = BackgroundJobOutbox(
        registry,
        completed_retention_days=settings.background_completed_retention_days,
        dead_retention_days=settings.background_dead_retention_days,
    )
    handler_context = ctx.get("handler_context") or BackgroundHandlerContext(
        settings=settings,
        session_factory=database.session_factory,
        redis=ctx.get("redis"),
        provider=provider,
        registry=registry,
    )
    runtime = BackgroundWorkerRuntime(
        session_factory=database.session_factory,
        registry=registry,
        outbox=outbox,
        handler_context=handler_context,
        worker_id=worker_id,
        lease_seconds=settings.background_claim_lease_seconds,
        random_uniform=random.uniform,
    )
    ctx[BACKGROUND_RESOURCES_KEY] = BackgroundWorkerResources(
        settings=settings,
        database=database,
        registry=registry,
        outbox=outbox,
        redis=ctx.get("redis"),
        provider=provider,
        runtime=runtime,
    )


async def worker_shutdown(ctx: MutableMapping[object, object]) -> None:
    """Close worker-owned resources while leaving ARQ's Redis pool to ARQ."""

    resources = ctx.pop(BACKGROUND_RESOURCES_KEY, None)
    if not isinstance(resources, BackgroundWorkerResources):
        return
    try:
        provider = resources.provider
        if provider is not None:
            close = getattr(provider, "aclose", None) or getattr(
                provider, "close", None
            )
            if close is not None:
                await _maybe_await(close())
    finally:
        close_database = getattr(resources.database, "close", None)
        if close_database is not None:
            await _maybe_await(close_database())


async def run_background_work(
    ctx: MutableMapping[object, object],
    envelope: dict[str, object],
) -> None:
    """ARQ's sole registered function for all application job definitions."""

    resources = ctx.get(BACKGROUND_RESOURCES_KEY)
    if not isinstance(resources, BackgroundWorkerResources):
        raise RuntimeError("Background worker resources were not initialized")
    await resources.runtime.execute(envelope, defer_retry=True)
