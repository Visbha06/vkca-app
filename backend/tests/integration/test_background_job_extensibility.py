"""Integration coverage for onboarding a typed job on the shared runtime path."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.models.background_work_item import BackgroundWorkItem
from src.services.background_jobs.contracts import BackgroundWorkState
from src.services.background_jobs.dispatcher import BackgroundJobDispatcher
from src.services.background_jobs.outbox import BackgroundJobOutbox
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    ResourceBounds,
)
from src.services.background_jobs.retry import RetryPolicy
from src.services.background_jobs.runtime import BackgroundWorkerRuntime


class SyntheticPayload(BaseModel):
    record_id: str = Field(min_length=1, max_length=80)

    model_config = ConfigDict(extra="forbid", frozen=True)


class RecordingBroker:
    def __init__(self) -> None:
        self.envelopes: list[dict[str, object]] = []

    async def enqueue_job(
        self, function: str, *args: object, **kwargs: object
    ) -> object:
        del function, kwargs
        self.envelopes.append(args[0])
        return object()


def _policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        base_delay_seconds=1,
        max_delay_seconds=30,
        jitter_seconds=0,
        timeout_seconds=20,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_synthetic_job_uses_existing_dispatcher_and_worker_after_delay(
    background_session_factory,
) -> None:
    handled: list[str] = []

    async def synthetic_handler(context: object, payload: BaseModel) -> None:
        del context
        handled.append(SyntheticPayload.model_validate(payload).record_id)

    registry = BackgroundJobRegistry(allowed_handlers={synthetic_handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="synthetic_maintenance",
            payload_version=1,
            payload_model=SyntheticPayload,
            handler=synthetic_handler,
            retry_policy=_policy(),
            idempotency_strategy="Reload the current record before applying repair.",
            resource_bounds=ResourceBounds(max_concurrency=1, max_batch_size=10),
            manual_retry_allowed=True,
            manual_trigger="trigger-synthetic-maintenance",
        )
    )
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    due_at = now + timedelta(minutes=5)
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    async with background_session_factory() as session:
        staged = await outbox.stage_manual_trigger(
            session,
            "trigger-synthetic-maintenance",
            {"record_id": "record-1"},
            run_after=due_at,
        )
        await session.commit()
        work_id = staged.id

    broker = RecordingBroker()
    dispatcher = BackgroundJobDispatcher(
        session_factory=background_session_factory,
        broker=broker,
        outbox=outbox,
        retry_policy=_policy(),
        queue_name="vkca-background",
        dispatcher_id="extensibility-dispatcher",
        batch_size=10,
        lease_seconds=30,
        clock=lambda: now,
        random_uniform=lambda _lower, _upper: 0,
    )
    early = await dispatcher.dispatch_once(now=now)
    assert early.claimed == 0
    assert broker.envelopes == []

    due_dispatcher = BackgroundJobDispatcher(
        session_factory=background_session_factory,
        broker=broker,
        outbox=outbox,
        retry_policy=_policy(),
        queue_name="vkca-background",
        dispatcher_id="extensibility-due-dispatcher",
        batch_size=10,
        lease_seconds=30,
        clock=lambda: due_at,
        random_uniform=lambda _lower, _upper: 0,
    )
    dispatched = await due_dispatcher.dispatch_once(now=due_at)
    assert dispatched.enqueued == 1
    assert len(broker.envelopes) == 1

    runtime = BackgroundWorkerRuntime(
        session_factory=background_session_factory,
        registry=registry,
        outbox=outbox,
        handler_context=object(),
        worker_id="extensibility-worker",
        lease_seconds=30,
        clock=lambda: due_at,
        random_uniform=lambda _lower, _upper: 0,
    )
    completed = await runtime.execute(broker.envelopes[0])

    assert completed.state is BackgroundWorkState.COMPLETED
    assert handled == ["record-1"]
    async with background_session_factory() as session:
        persisted = await session.scalar(
            select(BackgroundWorkItem).where(BackgroundWorkItem.id == work_id)
        )
    assert persisted is not None
    assert BackgroundWorkState(persisted.state) is BackgroundWorkState.COMPLETED
