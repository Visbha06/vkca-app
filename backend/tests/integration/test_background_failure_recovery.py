"""Failure, restart, terminal inspection, and manual recovery integration tests."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select

from src.config import get_settings
from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.auth_audit_log import AuthAuditLog
from src.models.background_work_item import BackgroundWorkItem
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.models.rag_document import RagDocument
from src.schemas.player import PlayerCreate
from src.services.background_jobs.contracts import BackgroundWorkState
from src.services.background_jobs.dispatcher import BackgroundJobDispatcher
from src.services.background_jobs.outbox import BackgroundJobOutbox
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    ResourceBounds,
    build_background_job_registry,
)
from src.services.background_jobs.retry import RetryPolicy
from src.services.background_jobs.runtime import (
    BackgroundHandlerContext,
    BackgroundWorkerRuntime,
)
from src.services.player_service import PlayerService
from src.services.rag.embedding import FakeEmbeddingProvider


class _Payload(BaseModel):
    value: str


class _Broker:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.envelopes: list[dict[str, object]] = []

    async def enqueue_job(self, function, *args, **kwargs):
        del function, kwargs
        if self.failures:
            self.failures -= 1
            raise ConnectionError("redis_url=redis://secret:password@localhost")
        self.envelopes.append(args[0])
        return object()


def _policy(*, attempts: int = 2) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=attempts,
        base_delay_seconds=1,
        max_delay_seconds=2,
        jitter_seconds=0,
        timeout_seconds=2,
    )


def _dispatcher(
    *,
    outbox: BackgroundJobOutbox,
    broker: _Broker,
    now: datetime,
    attempts: int = 2,
    dispatcher_id: str = "recovery-dispatcher",
) -> BackgroundJobDispatcher:
    return BackgroundJobDispatcher(
        session_factory=AsyncSessionFactory,
        broker=broker,
        outbox=outbox,
        retry_policy=_policy(attempts=attempts),
        queue_name="vkca-background",
        dispatcher_id=dispatcher_id,
        batch_size=50,
        lease_seconds=10,
        clock=lambda: now,
        random_uniform=lambda _lower, _upper: 0,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_redis_outage_recovers_without_competing_overwrite(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="src.services.background_jobs.dispatcher",
    )

    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload

    registry = BackgroundJobRegistry(allowed_handlers={handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="recovery_job",
            payload_version=1,
            payload_model=_Payload,
            handler=handler,
            retry_policy=_policy(attempts=3),
            idempotency_strategy="Reload current state.",
            resource_bounds=ResourceBounds(max_concurrency=1, max_batch_size=10),
            manual_retry_allowed=True,
        )
    )
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    async with AsyncSessionFactory() as session:
        work = await outbox.stage(session, "recovery_job", {"value": "safe"})
        await session.commit()
        work_id = work.id

    unavailable = _Broker(failures=1)
    failed = await _dispatcher(
        outbox=outbox,
        broker=unavailable,
        now=now,
        attempts=3,
    ).dispatch_once(now=now)
    assert failed.retrying == 1

    recovered_at = now + timedelta(seconds=1)
    broker = _Broker()
    winner = await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=recovered_at,
        attempts=3,
        dispatcher_id="winner",
    ).dispatch_once(now=recovered_at)
    loser = await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=recovered_at,
        attempts=3,
        dispatcher_id="loser",
    ).dispatch_once(now=recovered_at)

    assert winner.enqueued == 1
    assert loser.claimed == 0
    assert len(broker.envelopes) == 1
    async with AsyncSessionFactory() as session:
        current = await session.get(BackgroundWorkItem, work_id)
        assert current is not None
        assert current.state == BackgroundWorkState.DISPATCHED
        assert current.last_failure_message is None

    dispatch_events = [
        record.background_job
        for record in caplog.records
        if hasattr(record, "background_job")
    ]
    assert {event["outcome"] for event in dispatch_events} >= {
        "retrying",
        "dispatched",
    }
    required = {
        "work_id",
        "job_type",
        "attempt",
        "duration_ms",
        "outcome",
        "retry_status",
        "correlation_id",
        "source_type",
        "source_key",
    }
    assert dispatch_events and all(
        required <= event.keys() for event in dispatch_events
    )
    rendered_events = repr(dispatch_events)
    assert "secret:password" not in rendered_events
    assert "redis://" not in rendered_events


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_crash_lease_is_reclaimed_and_new_worker_completes() -> None:
    handled: list[str] = []

    async def handler(context: object, payload: BaseModel) -> None:
        del context
        handled.append(_Payload.model_validate(payload).value)

    registry = BackgroundJobRegistry(allowed_handlers={handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="restart_job",
            payload_version=1,
            payload_model=_Payload,
            handler=handler,
            retry_policy=_policy(attempts=3),
            idempotency_strategy="Replay reloads current state.",
            resource_bounds=ResourceBounds(max_concurrency=1, max_batch_size=10),
            manual_retry_allowed=True,
        )
    )
    now = datetime(2026, 8, 19, 13, tzinfo=UTC)
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    async with AsyncSessionFactory() as session:
        work = await outbox.stage(session, "restart_job", {"value": "eventual"})
        await session.commit()
        claimed = await outbox.claim_dispatch_batch(
            session,
            lease_owner="dispatcher",
            lease_seconds=10,
            limit=1,
            now=now,
        )
        await session.commit()
        dispatched = await outbox.mark_dispatched(
            session,
            work.id,
            expected_version=claimed[0].version_number,
            lease_owner="dispatcher",
            arq_job_id=f"bg:{work.id}",
            now=now,
        )
        await session.commit()
        running = await outbox.claim_for_execution(
            session,
            work.id,
            expected_version=dispatched.version_number,
            lease_owner="crashed-worker",
            lease_seconds=5,
            now=now,
        )
        await session.commit()
        assert running.state == BackgroundWorkState.RUNNING

    restarted_at = now + timedelta(seconds=6)
    async with AsyncSessionFactory() as session:
        recovery = await outbox.recover_expired_leases(
            session,
            limit=10,
            now=restarted_at,
        )
        await session.commit()
    assert recovery.retrying == 1

    runtime = BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=outbox,
        handler_context=object(),
        worker_id="replacement-worker",
        lease_seconds=10,
        clock=lambda: restarted_at,
        random_uniform=lambda _lower, _upper: 0,
    )
    result = await runtime.execute({"contract_version": 1, "work_id": str(work.id)})

    assert result.state is BackgroundWorkState.COMPLETED
    assert handled == ["eventual"]


@pytest.mark.asyncio(loop_scope="session")
async def test_cancelled_worker_persists_retry_and_replacement_completes() -> None:
    entered = asyncio.Event()
    blocker = asyncio.Event()
    should_block = [True]
    handled: list[str] = []

    async def handler(context: object, payload: BaseModel) -> None:
        del context
        value = _Payload.model_validate(payload).value
        if should_block[0]:
            entered.set()
            await blocker.wait()
        handled.append(value)

    registry = BackgroundJobRegistry(allowed_handlers={handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="cancelled_job",
            payload_version=1,
            payload_model=_Payload,
            handler=handler,
            retry_policy=_policy(attempts=3),
            idempotency_strategy="Cancellation reloads current durable work.",
            resource_bounds=ResourceBounds(max_concurrency=1, max_batch_size=10),
            manual_retry_allowed=True,
        )
    )
    now_ref = [datetime(2026, 8, 19, 13, 30, tzinfo=UTC)]
    outbox = BackgroundJobOutbox(registry, clock=lambda: now_ref[0])
    async with AsyncSessionFactory() as session:
        work = await outbox.stage(session, "cancelled_job", {"value": "resumed"})
        await session.commit()
        work_id = work.id

    broker = _Broker()
    dispatched = await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now_ref[0],
        attempts=3,
    ).dispatch_once(now=now_ref[0])
    assert dispatched.enqueued == 1

    cancelled_runtime = BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=outbox,
        handler_context=object(),
        worker_id="cancelled-worker",
        lease_seconds=10,
        clock=lambda: now_ref[0],
        random_uniform=lambda _lower, _upper: 0,
    )
    execution = asyncio.create_task(cancelled_runtime.execute(broker.envelopes[-1]))
    await asyncio.wait_for(entered.wait(), timeout=2)
    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await execution

    async with AsyncSessionFactory() as session:
        retrying = await session.get(BackgroundWorkItem, work_id)
        assert retrying is not None
        assert retrying.state == BackgroundWorkState.RETRYING
        assert retrying.lease_owner is None
        assert retrying.lease_expires_at is None

    should_block[0] = False
    now_ref[0] += timedelta(seconds=2)
    replacement = BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=outbox,
        handler_context=object(),
        worker_id="replacement-after-cancellation",
        lease_seconds=10,
        clock=lambda: now_ref[0],
        random_uniform=lambda _lower, _upper: 0,
    )
    completed = await replacement.execute(broker.envelopes[-1])

    assert completed.state is BackgroundWorkState.COMPLETED
    assert handled == ["resumed"]


@pytest.mark.asyncio(loop_scope="session")
async def test_provider_failure_preserves_data_and_manual_retry_succeeds(
    caplog,
) -> None:
    caplog.set_level(
        logging.INFO,
        logger="src.services.background_jobs.runtime",
    )

    class LeakyUnavailableProvider(FakeEmbeddingProvider):
        async def embed_documents(self, inputs, profile=None):
            del inputs, profile
            raise ConnectionError(
                "provider token=super-secret database_url=postgres://private"
            )

    settings = get_settings().model_copy(
        update={
            "background_max_attempts": 2,
            "background_retry_base_seconds": 1.0,
            "background_retry_max_seconds": 2.0,
            "background_retry_jitter_seconds": 0.0,
        }
    )
    registry = build_background_job_registry(settings=settings)
    outbox = BackgroundJobOutbox(
        registry,
        completed_retention_days=settings.background_completed_retention_days,
        dead_retention_days=settings.background_dead_retention_days,
    )
    now_ref = [datetime(2026, 8, 19, 14, tzinfo=UTC)]
    payload = PlayerCreate(
        first_name="Recoverable",
        last_name="Player",
        date_of_birth=date(2012, 5, 1),
        bio="Committed before provider execution",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
    )
    async with AsyncSessionFactory() as session:
        before_business = int(
            await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0
        )
        before_auth = int(
            await session.scalar(select(func.count(AuthAuditLog.id))) or 0
        )
        created = await PlayerService(session).create_player(payload)
        player_id = created.id
        work = await session.scalar(
            select(BackgroundWorkItem).where(
                BackgroundWorkItem.source_key == str(player_id)
            )
        )
        assert work is not None
        work_id = work.id
        now_ref[0] = work.run_after

    broker = _Broker()
    await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now_ref[0],
        attempts=2,
    ).dispatch_once(now=now_ref[0])
    failing_context = BackgroundHandlerContext(
        settings=settings,
        session_factory=AsyncSessionFactory,
        redis=None,
        provider=LeakyUnavailableProvider(),
        registry=registry,
    )
    failing_runtime = BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=outbox,
        handler_context=failing_context,
        worker_id="provider-failure-worker",
        lease_seconds=120,
        clock=lambda: now_ref[0],
        random_uniform=lambda _lower, _upper: 0,
    )
    first = await failing_runtime.execute(broker.envelopes[-1])
    assert first.state is BackgroundWorkState.RETRYING

    now_ref[0] += timedelta(seconds=5)
    await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now_ref[0],
        attempts=2,
    ).dispatch_once(now=now_ref[0])
    second = await failing_runtime.execute(broker.envelopes[-1])
    assert second.state is BackgroundWorkState.DEAD

    async with AsyncSessionFactory() as session:
        dead = await session.get(BackgroundWorkItem, work_id)
        committed = await session.get(Player, player_id)
        assert dead is not None and committed is not None
        assert dead.last_failure_category == "retry_limit_exhausted"
        serialized = f"{dead.last_failure_message} {dead.last_failure_category}"
        assert "super-secret" not in serialized
        assert "postgres://private" not in serialized
        requeued = await outbox.manual_requeue(
            session,
            dead.id,
            expected_version=dead.version_number,
            max_manual_retries=2,
            now=now_ref[0] + timedelta(seconds=1),
        )
        await session.commit()
        assert requeued.state == BackgroundWorkState.PENDING

    now_ref[0] += timedelta(seconds=2)
    await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now_ref[0],
        attempts=2,
    ).dispatch_once(now=now_ref[0])
    healthy_context = BackgroundHandlerContext(
        settings=settings,
        session_factory=AsyncSessionFactory,
        redis=None,
        provider=FakeEmbeddingProvider(),
        registry=registry,
    )
    healthy_runtime = BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=outbox,
        handler_context=healthy_context,
        worker_id="provider-recovery-worker",
        lease_seconds=120,
        clock=lambda: now_ref[0],
        random_uniform=lambda _lower, _upper: 0,
    )
    final = await healthy_runtime.execute(broker.envelopes[-1])

    assert final.state is BackgroundWorkState.COMPLETED
    async with AsyncSessionFactory() as session:
        assert await session.get(Player, player_id) is not None
        assert (
            await session.scalar(
                select(RagDocument).where(RagDocument.source_key == str(player_id))
            )
            is not None
        )
        assert (
            int(await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0)
            == before_business
        )
        assert (
            int(await session.scalar(select(func.count(AuthAuditLog.id))) or 0)
            == before_auth
        )

    worker_events = [
        record.background_job
        for record in caplog.records
        if hasattr(record, "background_job")
    ]
    assert {event["outcome"] for event in worker_events} >= {
        "retrying",
        "dead",
        "completed",
    }
    rendered_events = repr(worker_events)
    assert "super-secret" not in rendered_events
    assert "postgres://private" not in rendered_events
    assert "database_url" not in rendered_events
