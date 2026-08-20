"""Unit coverage for the generic dedicated worker runtime."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.models.background_work_item import BackgroundWorkItem
from src.services.background_jobs.contracts import (
    BackgroundPayloadValidationError,
    BackgroundWorkConflictError,
    BackgroundWorkState,
)
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    ResourceBounds,
)
from src.services.background_jobs.retry import (
    FailureCategory,
    FailureClassification,
    RetryDisposition,
    RetryPolicy,
)
from src.services.background_jobs.runtime import (
    BACKGROUND_RESOURCES_KEY,
    BackgroundWorkerResources,
    BackgroundWorkerRuntime,
    run_background_work,
    worker_shutdown,
    worker_startup,
)


class SyntheticPayload(BaseModel):
    value: str


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

    def __call__(self) -> AsyncScope:
        return AsyncScope(self.session)


def make_item(
    now: datetime,
    *,
    state: BackgroundWorkState,
    version_number: int,
    payload_version: int = 1,
    payload: dict[str, object] | None = None,
) -> BackgroundWorkItem:
    return BackgroundWorkItem(
        id=uuid4(),
        job_type="synthetic_job",
        payload_version=payload_version,
        payload=payload or {"value": "current"},
        state=state,
        idempotency_key=None,
        coalescing_key=None,
        correlation_id=None,
        source_type=None,
        source_key=None,
        safe_metadata={},
        run_after=now,
        dispatch_attempt_count=1,
        execution_attempt_count=1 if state is BackgroundWorkState.RUNNING else 0,
        manual_retry_count=0,
        manual_retry_allowed=True,
        lease_owner="worker:test" if state is BackgroundWorkState.RUNNING else None,
        lease_expires_at=(
            now + timedelta(minutes=2) if state is BackgroundWorkState.RUNNING else None
        ),
        version_number=version_number,
        created_at=now,
        updated_at=now,
    )


def make_registry(
    handler: Any,
    *,
    max_attempts: int = 3,
    timeout_seconds: float = 10,
    retry_classifier: Any = None,
) -> BackgroundJobRegistry:
    registry = BackgroundJobRegistry(allowed_handlers={handler})
    definition_values: dict[str, object] = {
        "job_type": "synthetic_job",
        "payload_version": 1,
        "payload_model": SyntheticPayload,
        "handler": handler,
        "retry_policy": RetryPolicy(
            max_attempts=max_attempts,
            base_delay_seconds=5,
            max_delay_seconds=30,
            jitter_seconds=0,
            timeout_seconds=timeout_seconds,
        ),
        "idempotency_strategy": "Reload current state before execution.",
        "resource_bounds": ResourceBounds(max_concurrency=1, max_batch_size=10),
        "manual_retry_allowed": True,
    }
    if retry_classifier is not None:
        definition_values["retry_classifier"] = retry_classifier
    registry.register(BackgroundJobDefinition(**definition_values))
    return registry


def make_runtime(
    mocker: Any,
    *,
    now: datetime,
    registry: BackgroundJobRegistry,
    dispatched: BackgroundWorkItem,
    running: BackgroundWorkItem,
) -> tuple[BackgroundWorkerRuntime, Any]:
    session = mocker.Mock()
    session.begin = mocker.Mock(side_effect=lambda: AsyncScope(None))
    outbox = mocker.Mock()
    outbox.reload = mocker.AsyncMock(return_value=dispatched)
    outbox.claim_for_execution = mocker.AsyncMock(return_value=running)
    outbox.renew_execution_lease = mocker.AsyncMock(return_value=running)
    outbox.mark_completed = mocker.AsyncMock(
        return_value=make_item(
            now,
            state=BackgroundWorkState.COMPLETED,
            version_number=running.version_number + 1,
        )
    )
    outbox.mark_retrying = mocker.AsyncMock(
        return_value=make_item(
            now,
            state=BackgroundWorkState.RETRYING,
            version_number=running.version_number + 1,
        )
    )
    outbox.mark_dead = mocker.AsyncMock(
        return_value=make_item(
            now,
            state=BackgroundWorkState.DEAD,
            version_number=running.version_number + 1,
        )
    )
    runtime = BackgroundWorkerRuntime(
        session_factory=SessionFactory(session),
        registry=registry,
        outbox=outbox,
        handler_context={"provider": "fake"},
        worker_id="worker:test",
        lease_seconds=120,
        clock=lambda: now,
        random_uniform=lambda _lower, _upper: 0,
    )
    return runtime, outbox


@pytest.mark.asyncio
async def test_generic_worker_claims_validates_dispatches_and_completes(
    mocker: Any,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    handled: list[tuple[object, SyntheticPayload]] = []

    async def handler(context: object, payload: BaseModel) -> None:
        handled.append((context, SyntheticPayload.model_validate(payload)))

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler),
        dispatched=dispatched,
        running=running,
    )

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert handled == [({"provider": "fake"}, SyntheticPayload(value="current"))]
    assert report.state is BackgroundWorkState.COMPLETED
    outbox.claim_for_execution.assert_awaited_once()
    outbox.mark_completed.assert_awaited_once_with(
        outbox.mark_completed.await_args.args[0],
        running.id,
        expected_version=running.version_number,
        lease_owner="worker:test",
        now=now,
    )


@pytest.mark.asyncio
async def test_unknown_job_is_terminal_without_handler_execution(mocker: Any) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=BackgroundJobRegistry(),
        dispatched=dispatched,
        running=running,
    )

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert report.state is BackgroundWorkState.DEAD
    assert report.failure_category == FailureCategory.UNREGISTERED_JOB.value
    assert (
        outbox.mark_dead.await_args.kwargs["category"]
        is FailureCategory.UNREGISTERED_JOB
    )
    outbox.mark_completed.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_stored_payload_is_terminal_without_handler(mocker: Any) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    called = False

    async def handler(context: object, payload: BaseModel) -> None:
        nonlocal called
        called = True
        del context, payload

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(
        now,
        state=BackgroundWorkState.RUNNING,
        version_number=3,
        payload={"password": "unsafe"},
    )
    running.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler),
        dispatched=dispatched,
        running=running,
    )

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert not called
    assert report.state is BackgroundWorkState.DEAD
    assert report.failure_category == FailureCategory.INVALID_PAYLOAD.value
    assert (
        outbox.mark_dead.await_args.kwargs["category"]
        is FailureCategory.INVALID_PAYLOAD
    )


@pytest.mark.asyncio
async def test_timeout_persists_bounded_retry(mocker: Any) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload
        raise TimeoutError("provider token=secret")

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler),
        dispatched=dispatched,
        running=running,
    )

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert report.state is BackgroundWorkState.RETRYING
    assert report.failure_category == FailureCategory.TIMEOUT.value
    retry_kwargs = outbox.mark_retrying.await_args.kwargs
    assert retry_kwargs["run_after"] == now + timedelta(seconds=5)
    assert "secret" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_worker_extends_lease_to_cover_registered_timeout(mocker: Any) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    renewed = make_item(now, state=BackgroundWorkState.RUNNING, version_number=4)
    renewed.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler, timeout_seconds=300),
        dispatched=dispatched,
        running=running,
    )
    outbox.renew_execution_lease.return_value = renewed

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert report.state is BackgroundWorkState.COMPLETED
    outbox.renew_execution_lease.assert_awaited_once()
    assert outbox.renew_execution_lease.await_args.kwargs["lease_seconds"] == 330
    assert outbox.mark_completed.await_args.kwargs["expected_version"] == 4


@pytest.mark.asyncio
async def test_registered_safe_noop_classifier_completes_without_retry(
    mocker: Any,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload
        raise RuntimeError("source is already absent")

    def classify_noop(error: BaseException) -> FailureClassification:
        del error
        return FailureClassification(
            category=FailureCategory.PERMANENT_DOMAIN_SOURCE_FAILURE,
            disposition=RetryDisposition.SAFE_NOOP,
            safe_message="The source is already absent.",
        )

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler, retry_classifier=classify_noop),
        dispatched=dispatched,
        running=running,
    )

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert report.state is BackgroundWorkState.COMPLETED
    outbox.mark_completed.assert_awaited_once()
    outbox.mark_retrying.assert_not_awaited()
    outbox.mark_dead.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_persists_retry_then_propagates(mocker: Any) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload
        raise asyncio.CancelledError

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler),
        dispatched=dispatched,
        running=running,
    )

    with pytest.raises(asyncio.CancelledError):
        await runtime.execute({"contract_version": 1, "work_id": str(dispatched.id)})

    outbox.mark_retrying.assert_awaited_once()
    assert outbox.mark_retrying.await_args.kwargs["category"] is FailureCategory.TIMEOUT


@pytest.mark.asyncio
async def test_stale_worker_completion_does_not_overwrite_winner(mocker: Any) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload

    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    running.id = dispatched.id
    winner = make_item(now, state=BackgroundWorkState.RETRYING, version_number=4)
    winner.id = dispatched.id
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler),
        dispatched=dispatched,
        running=running,
    )
    outbox.mark_completed.side_effect = BackgroundWorkConflictError(
        running.id,
        running.version_number,
        current=winner,
    )

    report = await runtime.execute(
        {"contract_version": 1, "work_id": str(dispatched.id)}
    )

    assert report.state is BackgroundWorkState.RETRYING
    outbox.mark_retrying.assert_not_awaited()
    outbox.mark_dead.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_startup_and_shutdown_own_resources(mocker: Any) -> None:
    settings = SimpleNamespace(
        database_url="postgresql+asyncpg://test:test@localhost/background_test",
        background_completed_retention_days=7,
        background_dead_retention_days=30,
        background_claim_lease_seconds=120,
    )
    session_factory = mocker.Mock()
    database = SimpleNamespace(session_factory=session_factory)
    database.close = mocker.AsyncMock()
    provider = SimpleNamespace()
    provider.aclose = mocker.AsyncMock()
    registry = BackgroundJobRegistry()
    context: dict[str, object] = {
        "settings": settings,
        "redis": mocker.Mock(),
        "database_factory": mocker.Mock(return_value=database),
        "registry_factory": mocker.Mock(return_value=registry),
        "provider_factory": mocker.AsyncMock(return_value=provider),
        "worker_id": "worker:test",
    }

    await worker_startup(context)

    resources = context[BACKGROUND_RESOURCES_KEY]
    assert resources.database is database
    assert resources.registry is registry
    assert resources.provider is provider
    assert resources.redis is context["redis"]

    await worker_shutdown(context)

    provider.aclose.assert_awaited_once()
    database.close.assert_awaited_once()
    assert BACKGROUND_RESOURCES_KEY not in context
    with pytest.raises(RuntimeError, match="not initialized"):
        await run_background_work(
            context,
            {"contract_version": 1, "work_id": str(uuid4())},
        )


@pytest.mark.asyncio
async def test_malformed_envelope_is_rejected_before_database_access(
    mocker: Any,
) -> None:
    async def handler(context: object, payload: BaseModel) -> None:
        del context, payload

    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    dispatched = make_item(now, state=BackgroundWorkState.DISPATCHED, version_number=2)
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    runtime, outbox = make_runtime(
        mocker,
        now=now,
        registry=make_registry(handler),
        dispatched=dispatched,
        running=running,
    )

    with pytest.raises(BackgroundPayloadValidationError):
        await runtime.execute({"contract_version": 2, "work_id": str(uuid4())})

    outbox.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_arq_wrapper_returns_no_result_and_delegates_to_runtime(
    mocker: Any,
) -> None:
    runtime = mocker.Mock()
    runtime.execute = mocker.AsyncMock(
        return_value=SimpleNamespace(state=BackgroundWorkState.COMPLETED)
    )
    resources = BackgroundWorkerResources(
        settings=mocker.Mock(),
        database=mocker.Mock(),
        registry=BackgroundJobRegistry(),
        outbox=mocker.Mock(),
        redis=mocker.Mock(),
        provider=None,
        runtime=runtime,
    )
    envelope = {"contract_version": 1, "work_id": str(uuid4())}

    result = await run_background_work(
        {BACKGROUND_RESOURCES_KEY: resources},
        envelope,
    )

    assert result is None
    runtime.execute.assert_awaited_once_with(envelope, defer_retry=True)


def test_worker_settings_are_bounded_and_disable_arq_results() -> None:
    from scripts.background_worker import WorkerSettings
    from src.services.background_jobs.contracts import (
        json_job_deserializer,
        json_job_serializer,
    )

    assert WorkerSettings.functions == [run_background_work]
    assert WorkerSettings.max_jobs >= 1
    assert WorkerSettings.job_timeout > 0
    assert WorkerSettings.keep_result == 0
    assert WorkerSettings.log_results is False
    assert WorkerSettings.job_serializer is json_job_serializer
    assert WorkerSettings.job_deserializer is json_job_deserializer
