"""Unit coverage for transaction-local durable work staging and OCC."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

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
from src.services.background_jobs.retry import RetryPolicy


class TargetPayload(BaseModel):
    targets: list[str]


async def synthetic_handler(context: object, payload: BaseModel) -> None:
    del context, payload


def merge_targets(existing: BaseModel, incoming: BaseModel) -> object:
    old = TargetPayload.model_validate(existing)
    new = TargetPayload.model_validate(incoming)
    return {"targets": sorted(set(old.targets) | set(new.targets))}


class ScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class AsyncScope:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class DuplicateIdentityError(Exception):
    constraint_name = "uq_background_work_items_job_idempotency"


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 8, 14, 12, tzinfo=UTC)


@pytest.fixture
def registry() -> BackgroundJobRegistry:
    registry = BackgroundJobRegistry(allowed_handlers={synthetic_handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="synthetic_job",
            payload_version=1,
            payload_model=TargetPayload,
            handler=synthetic_handler,
            retry_policy=RetryPolicy(
                max_attempts=3,
                base_delay_seconds=2,
                max_delay_seconds=30,
                jitter_seconds=0,
                timeout_seconds=20,
            ),
            idempotency_strategy="Reload current state and reconcile targets.",
            resource_bounds=ResourceBounds(max_concurrency=2, max_batch_size=128),
            manual_retry_allowed=True,
            coalescer=merge_targets,
        )
    )
    return registry


def make_session(mocker: Any, *results: object) -> Any:
    session = mocker.Mock()
    session.execute = mocker.AsyncMock(side_effect=results)
    session.flush = mocker.AsyncMock()
    session.begin_nested = mocker.Mock(side_effect=AsyncScope)
    session.commit = mocker.AsyncMock()
    session.rollback = mocker.AsyncMock()
    return session


def make_item(
    now: datetime,
    *,
    state: BackgroundWorkState = BackgroundWorkState.PENDING,
    payload: dict[str, object] | None = None,
    version_number: int = 1,
) -> BackgroundWorkItem:
    return BackgroundWorkItem(
        id=uuid4(),
        job_type="synthetic_job",
        payload_version=1,
        payload=payload or {"targets": ["player:1"]},
        state=state,
        idempotency_key=None,
        coalescing_key="player:1",
        correlation_id=None,
        source_type="player_profile",
        source_key="player:1",
        safe_metadata={},
        run_after=now,
        dispatch_attempt_count=0,
        execution_attempt_count=0,
        manual_retry_count=0,
        manual_retry_allowed=True,
        version_number=version_number,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_stage_adds_work_to_caller_transaction_without_commit(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    session = make_session(mocker, ScalarResult(None), ScalarResult(None))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    item = await outbox.stage(
        session,
        "synthetic_job",
        {"targets": ["player:1"]},
        idempotency_key="mutation:1",
        coalescing_key="player:1",
        source_type="player_profile",
        source_key="player:1",
    )

    assert item.state is BackgroundWorkState.PENDING
    assert item.payload == {"targets": ["player:1"]}
    session.add.assert_called_once_with(item)
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_resolves_existing_work(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    existing = make_item(now)
    existing.idempotency_key = "mutation:1"
    session = make_session(mocker, ScalarResult(existing))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    resolved = await outbox.stage(
        session,
        "synthetic_job",
        {"targets": ["player:2"]},
        idempotency_key="mutation:1",
        coalescing_key="player:2",
    )

    assert resolved is existing
    session.add.assert_not_called()
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_idempotency_insert_resolves_savepoint_winner(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    winner = make_item(now)
    winner.idempotency_key = "mutation:1"
    session = make_session(
        mocker,
        ScalarResult(None),
        ScalarResult(winner),
    )
    session.flush.side_effect = IntegrityError(
        "INSERT INTO background_work_items",
        {},
        DuplicateIdentityError("duplicate"),
    )
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    resolved = await outbox.stage(
        session,
        "synthetic_job",
        {"targets": ["player:1"]},
        idempotency_key="mutation:1",
    )

    assert resolved is winner
    session.begin_nested.assert_called_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_work_coalesces_bounded_targets_with_occ(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    existing = make_item(now, version_number=4)
    merged = make_item(
        now,
        payload={"targets": ["player:1", "player:2"]},
        version_number=5,
    )
    merged.id = existing.id
    session = make_session(
        mocker,
        ScalarResult(existing),
        ScalarResult(merged),
    )
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    resolved = await outbox.stage(
        session,
        "synthetic_job",
        {"targets": ["player:2"]},
        coalescing_key="player:1",
    )

    assert resolved is merged
    assert resolved.payload == {"targets": ["player:1", "player:2"]}
    assert session.execute.await_count == 2
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_running_work_gets_successor_instead_of_payload_mutation(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    running = make_item(now, state=BackgroundWorkState.RUNNING, version_number=3)
    session = make_session(mocker, ScalarResult(running))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    successor = await outbox.stage(
        session,
        "synthetic_job",
        {"targets": ["player:2"]},
        coalescing_key="player:1",
    )

    assert successor is not running
    assert successor.state is BackgroundWorkState.PENDING
    assert successor.coalescing_key == running.coalescing_key
    assert running.payload == {"targets": ["player:1"]}
    session.add.assert_called_once_with(successor)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_coalescing_occ_conflict_reloads_winner_and_raises(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    stale = make_item(now, version_number=2)
    winner = make_item(
        now,
        payload={"targets": ["player:1", "player:3"]},
        version_number=3,
    )
    winner.id = stale.id
    session = make_session(
        mocker,
        ScalarResult(stale),
        ScalarResult(None),
        ScalarResult(winner),
    )
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    with pytest.raises(BackgroundWorkConflictError) as rejected:
        await outbox.stage(
            session,
            "synthetic_job",
            {"targets": ["player:2"]},
            coalescing_key="player:1",
        )

    assert rejected.value.current is winner
    assert rejected.value.expected_version == 2
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delayed_work_is_scheduled_and_caller_rollback_remains_authoritative(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    session = make_session(mocker, ScalarResult(None))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    item = await outbox.stage(
        session,
        "synthetic_job",
        {"targets": ["player:1"]},
        coalescing_key=None,
        run_after=now + timedelta(minutes=5),
    )
    await session.rollback()

    assert item.state is BackgroundWorkState.SCHEDULED
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_manual_requeue_requires_dead_allowed_work_and_expected_version(
    mocker: Any,
    registry: BackgroundJobRegistry,
    now: datetime,
) -> None:
    dead = make_item(now, state=BackgroundWorkState.DEAD, version_number=7)
    dead.terminal_at = now
    requeued = make_item(now, state=BackgroundWorkState.PENDING, version_number=8)
    requeued.id = dead.id
    requeued.manual_retry_count = 1
    session = make_session(mocker, ScalarResult(dead), ScalarResult(requeued))
    outbox = BackgroundJobOutbox(registry, clock=lambda: now)

    result = await outbox.manual_requeue(
        session,
        dead.id,
        expected_version=7,
        max_manual_retries=2,
    )

    assert result is requeued
    assert result.state is BackgroundWorkState.PENDING
    assert result.manual_retry_count == 1
    session.commit.assert_not_awaited()
