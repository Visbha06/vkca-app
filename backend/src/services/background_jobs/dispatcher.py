"""Bounded PostgreSQL-to-Redis handoff for durable background work."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from time import perf_counter
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.background_work_item import BackgroundWorkItem
from src.schemas.background_jobs import DispatchReport
from src.services.background_jobs.contracts import (
    BackgroundJobEnvelopeV1,
    BackgroundWorkConflictError,
    BackgroundWorkState,
)
from src.services.background_jobs.logging import redact_structured_fields
from src.services.background_jobs.outbox import BackgroundJobOutbox, utc_now
from src.services.background_jobs.retry import (
    FailureCategory,
    RandomUniform,
    RetryPolicy,
    retry_run_after,
)

logger = logging.getLogger(__name__)


class BackgroundJobBroker(Protocol):
    """Small ARQ-compatible enqueue boundary used by the dispatcher."""

    async def enqueue_job(
        self,
        function: str,
        *args: Any,
        _job_id: str | None = None,
        _queue_name: str | None = None,
        **kwargs: Any,
    ) -> object | None: ...


SessionFactory = async_sessionmaker[AsyncSession] | Callable[[], Any]


def deterministic_arq_job_id(work_id: UUID) -> str:
    """Return the stable broker deduplication identity for durable work."""

    return f"bg:{work_id}"


class BackgroundJobDispatcher:
    """Claim committed work, enqueue references, and persist broker outcomes."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        broker: BackgroundJobBroker,
        outbox: BackgroundJobOutbox,
        retry_policy: RetryPolicy,
        queue_name: str,
        dispatcher_id: str,
        batch_size: int,
        lease_seconds: int,
        clock: Callable[[], datetime] = utc_now,
        random_uniform: RandomUniform,
    ) -> None:
        normalized_queue = queue_name.strip()
        normalized_dispatcher = dispatcher_id.strip()
        if not 1 <= len(normalized_queue) <= 64:
            raise ValueError("queue_name must be non-blank and at most 64 characters")
        if not 1 <= len(normalized_dispatcher) <= 128:
            raise ValueError(
                "dispatcher_id must be non-blank and at most 128 characters"
            )
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500")
        if not 1 <= lease_seconds <= 3_600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        self.session_factory = session_factory
        self.broker = broker
        self.outbox = outbox
        self.retry_policy = retry_policy
        self.queue_name = normalized_queue
        self.dispatcher_id = normalized_dispatcher
        self.batch_size = batch_size
        self.lease_seconds = lease_seconds
        self.clock = clock
        self.random_uniform = random_uniform

    async def dispatch_once(
        self,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> DispatchReport:
        """Run one bounded claim/enqueue/update cycle."""

        reference = self._reference(now)
        effective_limit = self._limit(limit)
        async with self.session_factory() as session:
            async with session.begin():
                await self.outbox.recover_expired_leases(
                    session,
                    limit=effective_limit,
                    now=reference,
                )
                claimed = await self.outbox.claim_dispatch_batch(
                    session,
                    lease_owner=self.dispatcher_id,
                    lease_seconds=self.lease_seconds,
                    limit=effective_limit,
                    now=reference,
                )

        enqueued = 0
        retrying = 0
        dead = 0
        conflicts = 0
        for item in claimed:
            item_started = perf_counter()
            arq_job_id = deterministic_arq_job_id(item.id)
            envelope = BackgroundJobEnvelopeV1(work_id=item.id).model_dump(mode="json")
            try:
                await self.broker.enqueue_job(
                    "run_background_work",
                    envelope,
                    _job_id=arq_job_id,
                    _queue_name=self.queue_name,
                )
            except Exception:
                try:
                    async with self.session_factory() as session:
                        async with session.begin():
                            if (
                                item.dispatch_attempt_count
                                >= self.retry_policy.max_attempts
                            ):
                                transitioned = await self.outbox.mark_dead(
                                    session,
                                    item.id,
                                    expected_version=item.version_number,
                                    lease_owner=self.dispatcher_id,
                                    expected_states=(BackgroundWorkState.DISPATCHING,),
                                    category=FailureCategory.RETRY_LIMIT_EXHAUSTED,
                                    now=reference,
                                )
                                dead += 1
                            else:
                                run_after = retry_run_after(
                                    reference,
                                    attempt_count=max(item.dispatch_attempt_count, 1),
                                    policy=self.retry_policy,
                                    random_uniform=self.random_uniform,
                                )
                                transitioned = await self.outbox.mark_dispatch_failure(
                                    session,
                                    item.id,
                                    expected_version=item.version_number,
                                    lease_owner=self.dispatcher_id,
                                    category=FailureCategory.REDIS_UNAVAILABLE,
                                    run_after=run_after,
                                    now=reference,
                                )
                                retrying += 1
                    self._log_outcome(
                        transitioned,
                        outcome=BackgroundWorkState(transitioned.state).value,
                        started=item_started,
                    )
                except BackgroundWorkConflictError:
                    conflicts += 1
                    self._log_outcome(
                        item,
                        outcome="conflict",
                        started=item_started,
                    )
                continue

            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        dispatched = await self.outbox.mark_dispatched(
                            session,
                            item.id,
                            expected_version=item.version_number,
                            lease_owner=self.dispatcher_id,
                            arq_job_id=arq_job_id,
                            now=reference,
                        )
                enqueued += 1
                self._log_outcome(
                    dispatched,
                    outcome=BackgroundWorkState.DISPATCHED.value,
                    started=item_started,
                )
            except BackgroundWorkConflictError:
                # The deterministic queue identity and durable row make the
                # already-enqueued reference safe to encounter again.
                conflicts += 1
                self._log_outcome(
                    item,
                    outcome="conflict",
                    started=item_started,
                )

        return DispatchReport(
            claimed=len(claimed),
            enqueued=enqueued,
            retrying=retrying,
            dead=dead,
            conflicts=conflicts,
            work_ids=[item.id for item in claimed],
        )

    def _reference(self, now: datetime | None) -> datetime:
        reference = now or self.clock()
        if reference.tzinfo is None or reference.utcoffset() is None:
            raise ValueError("Dispatcher clocks must be timezone-aware")
        return reference

    def _limit(self, requested: int | None) -> int:
        if requested is None:
            return self.batch_size
        if not 1 <= requested <= 500:
            raise ValueError("limit must be between 1 and 500")
        return min(requested, self.batch_size)

    @staticmethod
    def _log_outcome(
        item: BackgroundWorkItem,
        *,
        outcome: str,
        started: float,
    ) -> None:
        """Emit one bounded dispatch outcome without payloads or raw exceptions."""

        state = BackgroundWorkState(item.state)
        fields = redact_structured_fields(
            {
                "event": "background_job_dispatch",
                "work_id": str(item.id),
                "job_type": item.job_type,
                "attempt": item.dispatch_attempt_count,
                "duration_ms": round((perf_counter() - started) * 1_000, 3),
                "outcome": outcome,
                "retry_status": (
                    "scheduled"
                    if state is BackgroundWorkState.RETRYING
                    else "terminal"
                    if state is BackgroundWorkState.DEAD
                    else "not_retrying"
                ),
                "correlation_id": (
                    str(item.correlation_id)
                    if item.correlation_id is not None
                    else None
                ),
                "source_type": item.source_type,
                "source_key": item.source_key,
            }
        )
        logger.info("background_job_dispatch", extra={"background_job": fields})
