"""Committed mutation, durable outbox, dispatch, and isolation coverage."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType, UserRole
from src.models.auth_audit_log import AuthAuditLog
from src.models.background_work_item import BackgroundWorkItem
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.schemas.player import PlayerCreate, PlayerUpdate
from src.services.background_jobs.contracts import (
    BackgroundWorkConflictError,
    BackgroundWorkState,
)
from src.services.background_jobs.dispatcher import BackgroundJobDispatcher
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    ResourceBounds,
)
from src.services.background_jobs.retry import RetryPolicy
from src.services.background_jobs.runtime import BackgroundWorkerRuntime
from src.services.business_audit_service import AuditActorContext
from src.services.player_service import PlayerService
from src.services.rag.contracts import (
    RagMutationImpact,
    RagMutationOperation,
    RagMutationRef,
    RagMutationSource,
    RagReconciliationPayloadV1,
)
from src.services.rag.registry import get_rag_mutation_stager


class RecordingBroker:
    def __init__(self, *, failure: BaseException | None = None) -> None:
        self.failure = failure
        self.envelopes: list[dict[str, object]] = []

    async def enqueue_job(self, function, *args, **kwargs):
        del function, kwargs
        if self.failure is not None:
            raise self.failure
        self.envelopes.append(args[0])
        return object()


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=5,
        base_delay_seconds=5,
        max_delay_seconds=300,
        jitter_seconds=0,
        timeout_seconds=300,
    )


def _dispatcher(broker: RecordingBroker) -> BackgroundJobDispatcher:
    return BackgroundJobDispatcher(
        session_factory=AsyncSessionFactory,
        broker=broker,
        outbox=get_rag_mutation_stager().outbox,
        retry_policy=_retry_policy(),
        queue_name="vkca-background",
        dispatcher_id="integration-dispatcher",
        batch_size=50,
        lease_seconds=120,
        random_uniform=lambda _lower, _upper: 0,
    )


def _player_payload(first_name: str) -> PlayerCreate:
    return PlayerCreate(
        first_name=first_name,
        last_name="Background",
        date_of_birth=date(2012, 4, 3),
        bio="Durable mutation test",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_committed_mutation_dispatches_and_executes_without_audit_pollution(
    background_session_factory,
    mocker,
) -> None:
    provider = mocker.AsyncMock()
    actor = AuditActorContext(
        user_id=uuid4(),
        display_name="Integration Coach",
        role=UserRole.HEAD_COACH,
        request_id="background-outbox-integration",
    )
    async with background_session_factory() as mutation_session:
        before_business = int(
            await mutation_session.scalar(select(func.count(BusinessAuditEvent.id)))
            or 0
        )
        before_auth = int(
            await mutation_session.scalar(select(func.count(AuthAuditLog.id))) or 0
        )
        player = await PlayerService(mutation_session).create_player(
            _player_payload("Committed"),
            actor=actor,
        )
        player_id = player.id

    async with background_session_factory() as observer_session:
        work = await observer_session.scalar(
            select(BackgroundWorkItem).where(
                BackgroundWorkItem.source_type == "player_profile",
                BackgroundWorkItem.source_key == str(player_id),
            )
        )

    assert work is not None
    work_id = work.id
    assert work.state == BackgroundWorkState.PENDING
    assert work.payload == {
        "mode": "targets",
        "reason": "mutation",
        "targets": [{"source_type": "player_profile", "source_key": str(player_id)}],
    }
    provider.assert_not_awaited()

    broker = RecordingBroker()
    dispatch_report = await _dispatcher(broker).dispatch_once()
    assert dispatch_report.enqueued == 1
    assert broker.envelopes == [{"contract_version": 1, "work_id": str(work_id)}]

    handled: list[RagReconciliationPayloadV1] = []

    async def handler(context: object, payload: BaseModel) -> None:
        del context
        handled.append(RagReconciliationPayloadV1.model_validate(payload))

    registry = BackgroundJobRegistry(allowed_handlers={handler})
    registry.register(
        BackgroundJobDefinition(
            job_type="rag_reconciliation",
            payload_version=1,
            payload_model=RagReconciliationPayloadV1,
            handler=handler,
            retry_policy=_retry_policy(),
            idempotency_strategy="Reload current registered source truth.",
            resource_bounds=ResourceBounds(max_concurrency=1, max_batch_size=128),
            manual_retry_allowed=True,
        )
    )
    runtime = BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=get_rag_mutation_stager().outbox,
        handler_context={"provider": provider},
        worker_id="integration-worker",
        lease_seconds=120,
        random_uniform=lambda _lower, _upper: 0,
    )
    execution = await runtime.execute(broker.envelopes[0])

    assert execution.state is BackgroundWorkState.COMPLETED
    assert handled == [RagReconciliationPayloadV1.model_validate(work.payload)]
    provider.assert_not_awaited()
    async with background_session_factory() as observer_session:
        completed = await observer_session.get(BackgroundWorkItem, work_id)
        assert completed is not None
        assert completed.state == BackgroundWorkState.COMPLETED
        with pytest.raises(BackgroundWorkConflictError):
            await get_rag_mutation_stager().outbox.mark_completed(
                observer_session,
                completed.id,
                expected_version=completed.version_number - 1,
                lease_owner="stale-worker",
                now=datetime.now(UTC),
            )

        after_business = int(
            await observer_session.scalar(select(func.count(BusinessAuditEvent.id)))
            or 0
        )
        after_auth = int(
            await observer_session.scalar(select(func.count(AuthAuditLog.id))) or 0
        )
    assert after_business - before_business == 1
    assert after_auth == before_auth


@pytest.mark.asyncio(loop_scope="session")
async def test_rollback_removes_staged_work(background_session_factory) -> None:
    player_id = uuid4()
    async with background_session_factory() as mutation_session:
        player = Player(
            id=player_id,
            **_player_payload("RolledBack").model_dump(),
            is_active=True,
        )
        mutation_session.add(player)
        await mutation_session.flush()
        reference = RagMutationRef(
            source=RagMutationSource.PLAYER,
            source_key=str(player.id),
        )
        await get_rag_mutation_stager().stage(
            mutation_session,
            RagMutationImpact(
                operation=RagMutationOperation.UPSERT,
                current_refs=(reference,),
                coalescing_ref=reference,
            ),
        )
        await mutation_session.rollback()

    async with background_session_factory() as observer_session:
        work_count = int(
            await observer_session.scalar(
                select(func.count(BackgroundWorkItem.id)).where(
                    BackgroundWorkItem.source_key == str(player_id)
                )
            )
            or 0
        )
        assert work_count == 0
        assert await observer_session.get(Player, player_id) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_redis_unavailability_preserves_domain_commit_and_retryable_work(
    background_session_factory,
) -> None:
    async with background_session_factory() as mutation_session:
        player = await PlayerService(mutation_session).create_player(
            _player_payload("RedisDown")
        )
        player_id = player.id

    report = await _dispatcher(
        RecordingBroker(failure=ConnectionError("redis unavailable"))
    ).dispatch_once()

    assert report.claimed == 1
    assert report.retrying == 1
    async with background_session_factory() as observer_session:
        committed_player = await observer_session.get(Player, player_id)
        work = await observer_session.scalar(
            select(BackgroundWorkItem).where(
                BackgroundWorkItem.source_key == str(player_id)
            )
        )
        assert committed_player is not None
        assert work is not None
        assert work.state == BackgroundWorkState.RETRYING
        assert work.last_failure_category == "redis_unavailable"
        assert "redis unavailable" not in (work.last_failure_message or "").lower()


@pytest.mark.asyncio(loop_scope="session")
async def test_rapid_player_mutations_coalesce_without_losing_final_commit(
    background_session_factory,
) -> None:
    async with background_session_factory() as mutation_session:
        player = await PlayerService(mutation_session).create_player(
            _player_payload("RapidOne")
        )
        await PlayerService(mutation_session).update_player(
            player.id,
            PlayerUpdate(first_name="RapidTwo", version_number=1),
        )
        final = await PlayerService(mutation_session).update_player(
            player.id,
            PlayerUpdate(first_name="RapidFinal", version_number=2),
        )
        player_id = player.id

    async with background_session_factory() as observer_session:
        work_items = list(
            (
                await observer_session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.source_key == str(player_id)
                    )
                )
            ).all()
        )
        committed = await observer_session.get(Player, player_id)

    assert final.first_name == "RapidFinal"
    assert committed is not None and committed.first_name == "RapidFinal"
    assert len(work_items) == 1
    assert work_items[0].state == BackgroundWorkState.PENDING
    assert work_items[0].version_number == 3
