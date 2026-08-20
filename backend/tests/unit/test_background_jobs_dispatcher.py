"""Unit coverage for bounded PostgreSQL-to-Redis dispatch."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from src.models.background_work_item import BackgroundWorkItem
from src.services.background_jobs.contracts import (
    BackgroundWorkConflictError,
    BackgroundWorkState,
)
from src.services.background_jobs.dispatcher import (
    BackgroundJobDispatcher,
    deterministic_arq_job_id,
)
from src.services.background_jobs.retry import FailureCategory, RetryPolicy


class AsyncScope:
    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self) -> object:
        return self.value

    async def __aexit__(self, *args: object) -> None:
        return None


class SessionFactory:
    def __init__(self, session: object) -> None:
        self.session = session
        self.calls = 0

    def __call__(self) -> AsyncScope:
        self.calls += 1
        return AsyncScope(self.session)


def make_item(now: datetime, *, version_number: int = 2) -> BackgroundWorkItem:
    return BackgroundWorkItem(
        id=uuid4(),
        job_type="synthetic_job",
        payload_version=1,
        payload={"value": "current"},
        state=BackgroundWorkState.DISPATCHING,
        idempotency_key=None,
        coalescing_key=None,
        correlation_id=None,
        source_type=None,
        source_key=None,
        safe_metadata={},
        run_after=now,
        dispatch_attempt_count=1,
        execution_attempt_count=0,
        manual_retry_count=0,
        manual_retry_allowed=True,
        lease_owner="dispatcher:test",
        lease_expires_at=now,
        version_number=version_number,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=5,
        base_delay_seconds=5,
        max_delay_seconds=30,
        jitter_seconds=2,
        timeout_seconds=30,
    )


def make_dispatcher(
    mocker: Any,
    *,
    now: datetime,
    retry_policy: RetryPolicy,
    claimed: list[BackgroundWorkItem],
) -> tuple[BackgroundJobDispatcher, Any, Any, SessionFactory]:
    session = mocker.Mock()
    session.begin = mocker.Mock(side_effect=lambda: AsyncScope(None))
    factory = SessionFactory(session)
    outbox = mocker.Mock()
    outbox.recover_expired_leases = mocker.AsyncMock(return_value=[])
    outbox.claim_dispatch_batch = mocker.AsyncMock(return_value=claimed)
    outbox.mark_dispatched = mocker.AsyncMock(side_effect=lambda *_a, **_k: claimed[0])
    outbox.mark_dispatch_failure = mocker.AsyncMock(
        side_effect=lambda *_a, **_k: claimed[0]
    )
    broker = mocker.Mock()
    broker.enqueue_job = mocker.AsyncMock(return_value=object())
    dispatcher = BackgroundJobDispatcher(
        session_factory=factory,
        broker=broker,
        outbox=outbox,
        retry_policy=retry_policy,
        queue_name="vkca-background",
        dispatcher_id="dispatcher:test",
        batch_size=50,
        lease_seconds=120,
        clock=lambda: now,
        random_uniform=lambda _lower, _upper: 0,
    )
    return dispatcher, outbox, broker, factory


@pytest.mark.asyncio
async def test_dispatcher_claims_bounded_batch_and_records_success(
    mocker: Any,
    retry_policy: RetryPolicy,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    item = make_item(now)
    dispatcher, outbox, broker, factory = make_dispatcher(
        mocker,
        now=now,
        retry_policy=retry_policy,
        claimed=[item],
    )

    report = await dispatcher.dispatch_once(limit=10)

    assert report.claimed == 1
    assert report.enqueued == 1
    assert report.retrying == 0
    assert report.conflicts == 0
    assert report.work_ids == [item.id]
    outbox.claim_dispatch_batch.assert_awaited_once_with(
        factory.session,
        lease_owner="dispatcher:test",
        lease_seconds=120,
        limit=10,
        now=now,
    )
    broker.enqueue_job.assert_awaited_once_with(
        "run_background_work",
        {"contract_version": 1, "work_id": str(item.id)},
        _job_id=deterministic_arq_job_id(item.id),
        _queue_name="vkca-background",
    )
    outbox.mark_dispatched.assert_awaited_once_with(
        factory.session,
        item.id,
        expected_version=item.version_number,
        lease_owner="dispatcher:test",
        arq_job_id=deterministic_arq_job_id(item.id),
        now=now,
    )
    assert factory.calls == 2


@pytest.mark.asyncio
async def test_dispatcher_recovers_expired_leases_before_claiming(
    mocker: Any,
    retry_policy: RetryPolicy,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    dispatcher, outbox, _broker, factory = make_dispatcher(
        mocker,
        now=now,
        retry_policy=retry_policy,
        claimed=[],
    )

    report = await dispatcher.dispatch_once(limit=7)

    assert report.claimed == 0
    outbox.recover_expired_leases.assert_awaited_once_with(
        factory.session,
        limit=7,
        now=now,
    )


@pytest.mark.asyncio
async def test_broker_failure_persists_retry_with_sanitized_category(
    mocker: Any,
    retry_policy: RetryPolicy,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    item = make_item(now)
    dispatcher, outbox, broker, factory = make_dispatcher(
        mocker,
        now=now,
        retry_policy=retry_policy,
        claimed=[item],
    )
    broker.enqueue_job.side_effect = ConnectionError(
        "redis://operator:top-secret@localhost:6379/0"
    )

    report = await dispatcher.dispatch_once()

    assert report.claimed == 1
    assert report.enqueued == 0
    assert report.retrying == 1
    outbox.mark_dispatch_failure.assert_awaited_once()
    kwargs = outbox.mark_dispatch_failure.await_args.kwargs
    assert kwargs["category"] is FailureCategory.REDIS_UNAVAILABLE
    assert kwargs["run_after"].timestamp() == now.timestamp() + 5
    assert "top-secret" not in report.model_dump_json()
    assert factory.calls == 2


@pytest.mark.asyncio
async def test_competing_dispatch_transition_is_reported_as_conflict(
    mocker: Any,
    retry_policy: RetryPolicy,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    item = make_item(now)
    dispatcher, outbox, broker, _factory = make_dispatcher(
        mocker,
        now=now,
        retry_policy=retry_policy,
        claimed=[item],
    )
    outbox.mark_dispatched.side_effect = BackgroundWorkConflictError(
        item.id,
        item.version_number,
    )

    report = await dispatcher.dispatch_once()

    assert broker.enqueue_job.await_count == 1
    assert report.claimed == 1
    assert report.enqueued == 0
    assert report.conflicts == 1
    assert report.retrying == 0


def test_deterministic_arq_id_is_stable_and_bounded() -> None:
    work_id = uuid4()

    assert deterministic_arq_job_id(work_id) == deterministic_arq_job_id(work_id)
    assert str(work_id) in deterministic_arq_job_id(work_id)
    assert len(deterministic_arq_job_id(work_id)) <= 64
