"""Unit coverage for bounded background-work inspection and recovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from scripts.background_jobs import parse_args
from src.models.background_work_item import BackgroundWorkItem
from src.services.background_jobs.contracts import (
    BackgroundWorkConflictError,
    BackgroundWorkState,
)
from src.services.background_jobs.outbox import BackgroundJobOutbox
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    ResourceBounds,
)
from src.services.background_jobs.retry import FailureCategory, RetryPolicy


class _Payload(BaseModel):
    value: str


async def _handler(context: object, payload: BaseModel) -> None:
    del context, payload


class _ScalarCollection:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class _Result:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def scalars(self) -> _ScalarCollection:
        return _ScalarCollection(self.values)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 8, 19, 12, tzinfo=UTC)


@pytest.fixture
def registry() -> BackgroundJobRegistry:
    registry = BackgroundJobRegistry(allowed_handlers={_handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="recoverable_job",
            payload_version=1,
            payload_model=_Payload,
            handler=_handler,
            retry_policy=RetryPolicy(
                max_attempts=3,
                base_delay_seconds=2,
                max_delay_seconds=30,
                jitter_seconds=0,
                timeout_seconds=20,
            ),
            idempotency_strategy="Reload current state before each attempt.",
            resource_bounds=ResourceBounds(max_concurrency=1, max_batch_size=10),
            manual_retry_allowed=True,
        )
    )
    return registry


def _item(
    now: datetime,
    *,
    state: BackgroundWorkState,
    execution_attempt_count: int = 0,
    dispatch_attempt_count: int = 0,
    version_number: int = 1,
) -> BackgroundWorkItem:
    return BackgroundWorkItem(
        id=uuid4(),
        job_type="recoverable_job",
        payload_version=1,
        payload={"value": "safe"},
        state=state,
        safe_metadata={},
        run_after=now,
        dispatch_attempt_count=dispatch_attempt_count,
        execution_attempt_count=execution_attempt_count,
        manual_retry_count=0,
        manual_retry_allowed=True,
        lease_owner="worker:test",
        lease_expires_at=now - timedelta(seconds=1),
        version_number=version_number,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_expired_running_lease_retries_before_attempt_exhaustion(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    candidate = _item(
        now,
        state=BackgroundWorkState.RUNNING,
        execution_attempt_count=2,
        version_number=4,
    )
    recovered = _item(
        now,
        state=BackgroundWorkState.RETRYING,
        execution_attempt_count=2,
        version_number=5,
    )
    recovered.id = candidate.id
    session = mocker.Mock()
    session.execute = mocker.AsyncMock(return_value=_Result([candidate]))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    transition = mocker.patch.object(
        outbox,
        "_transition",
        new=mocker.AsyncMock(return_value=recovered),
    )

    report = await outbox.recover_expired_leases(session, limit=10, now=now)

    assert report.recovered == 1
    assert report.retrying == 1
    assert report.dead == 0
    assert report.work_ids == [candidate.id]
    values = transition.await_args.kwargs["values"]
    assert values["state"] is BackgroundWorkState.RETRYING
    assert values["last_failure_category"] == FailureCategory.TIMEOUT.value


@pytest.mark.asyncio
async def test_expired_running_lease_becomes_dead_after_retry_exhaustion(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    candidate = _item(
        now,
        state=BackgroundWorkState.RUNNING,
        execution_attempt_count=3,
        version_number=7,
    )
    dead = _item(
        now,
        state=BackgroundWorkState.DEAD,
        execution_attempt_count=3,
        version_number=8,
    )
    dead.id = candidate.id
    session = mocker.Mock()
    session.execute = mocker.AsyncMock(return_value=_Result([candidate]))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    transition = mocker.patch.object(
        outbox,
        "_transition",
        new=mocker.AsyncMock(return_value=dead),
    )

    report = await outbox.recover_expired_leases(session, limit=10, now=now)

    assert report.recovered == 1
    assert report.dead == 1
    assert report.retrying == 0
    values = transition.await_args.kwargs["values"]
    assert values["state"] is BackgroundWorkState.DEAD
    assert (
        values["last_failure_category"] == FailureCategory.RETRY_LIMIT_EXHAUSTED.value
    )
    assert values["retention_until"] == now + timedelta(days=30)


@pytest.mark.asyncio
async def test_recovery_occ_conflict_is_reported_without_overwrite(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    candidate = _item(now, state=BackgroundWorkState.DISPATCHING)
    session = mocker.Mock()
    session.execute = mocker.AsyncMock(return_value=_Result([candidate]))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    mocker.patch.object(
        outbox,
        "_transition",
        new=mocker.AsyncMock(
            side_effect=BackgroundWorkConflictError(
                candidate.id,
                candidate.version_number,
                current=candidate,
            )
        ),
    )

    report = await outbox.recover_expired_leases(session, limit=10, now=now)

    assert report.recovered == 0
    assert report.conflicts == 1
    assert report.work_ids == []


@pytest.mark.asyncio
async def test_manual_retry_resets_attempt_cycle_but_preserves_manual_bound(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    dead = _item(
        now,
        state=BackgroundWorkState.DEAD,
        execution_attempt_count=3,
        dispatch_attempt_count=3,
        version_number=9,
    )
    dead.lease_owner = None
    dead.lease_expires_at = None
    dead.manual_retry_count = 1
    session = mocker.Mock()
    session.execute = mocker.AsyncMock()
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)
    mocker.patch.object(
        outbox,
        "reload",
        new=mocker.AsyncMock(return_value=dead),
    )
    requeued = _item(now, state=BackgroundWorkState.PENDING, version_number=10)
    requeued.id = dead.id
    transition = mocker.patch.object(
        outbox,
        "_transition",
        new=mocker.AsyncMock(return_value=requeued),
    )

    await outbox.manual_requeue(
        session,
        dead.id,
        expected_version=9,
        max_manual_retries=2,
        now=now,
    )

    values = transition.await_args.kwargs["values"]
    assert values["manual_retry_count"] == 2
    assert values["dispatch_attempt_count"] == 0
    assert values["execution_attempt_count"] == 0
    assert values["last_failure_message"] is None


def test_status_projection_excludes_payload_and_lease_owner(
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    item = _item(now, state=BackgroundWorkState.RETRYING)
    item.last_failure_category = FailureCategory.TIMEOUT.value
    item.last_failure_message = "The job exceeded its bounded execution time."
    status = BackgroundJobOutbox(registry).project_status(item)

    projected = status.model_dump(mode="json")
    assert projected["id"] == str(item.id)
    assert projected["last_failure_category"] == "timeout"
    assert "payload" not in projected
    assert "lease_owner" not in projected
    assert "safe_metadata" not in projected


def test_operator_argument_parser_enforces_bounded_shapes() -> None:
    status = parse_args(["status", "--state", "dead", "--limit", "25"])
    retry = parse_args(["retry", "--work-id", str(uuid4())])
    trigger = parse_args(
        [
            "trigger-rag",
            "--source-type",
            "player_profile",
            "--source-key",
            "safe-source",
        ]
    )

    assert status.command == "status" and status.limit == 25
    assert status.state == "dead"
    assert retry.command == "retry"
    assert trigger.command == "trigger-rag"
    with pytest.raises(SystemExit):
        parse_args(["status", "--limit", "501"])
    with pytest.raises(SystemExit):
        parse_args(["trigger-rag", "--safety"])
