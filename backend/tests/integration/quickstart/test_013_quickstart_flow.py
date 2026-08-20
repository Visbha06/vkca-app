"""Executable quickstart for durable background RAG processing."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.config import get_settings
from src.database import AsyncSessionFactory
from src.enums import BattingStyle, BowlingStyle, PlayerType, UserRole
from src.models.auth_audit_log import AuthAuditLog
from src.models.background_work_item import BackgroundWorkItem
from src.models.business_audit_event import BusinessAuditEvent
from src.models.player import Player
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.user import User
from src.schemas.player import PlayerCreate, PlayerUpdate
from src.schemas.rag import RagRetrievalRequest
from src.services.background_jobs.contracts import BackgroundWorkState
from src.services.background_jobs.dispatcher import BackgroundJobDispatcher
from src.services.background_jobs.outbox import BackgroundJobOutbox
from src.services.background_jobs.registry import build_background_job_registry
from src.services.background_jobs.retry import RetryPolicy
from src.services.background_jobs.runtime import (
    BackgroundHandlerContext,
    BackgroundWorkerRuntime,
)
from src.services.player_service import PlayerService
from src.services.rag.contracts import (
    RagMutationImpact,
    RagMutationOperation,
    RagMutationRef,
    RagMutationSource,
)
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.registry import get_rag_mutation_stager
from src.services.rag.retrieval import RagRetrievalService


class RecordingBroker:
    """Small ARQ-compatible boundary with deterministic outage injection."""

    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.envelopes: list[dict[str, object]] = []

    async def enqueue_job(self, function, *args, **kwargs):
        del function, kwargs
        if self.failures:
            self.failures -= 1
            raise ConnectionError("redis://user:secret@localhost")
        self.envelopes.append(args[0])
        return object()


class FailingProvider(FakeEmbeddingProvider):
    """Fail with text that must never cross the sanitization boundary."""

    async def embed_documents(self, inputs, profile=None):
        del inputs, profile
        raise ConnectionError("provider token=quickstart-secret")


def _player_payload(first_name: str) -> PlayerCreate:
    return PlayerCreate(
        first_name=first_name,
        last_name="Quickstart",
        date_of_birth=date(2012, 4, 3),
        bio="Durable processing quickstart",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
    )


def _dispatcher(
    *,
    outbox: BackgroundJobOutbox,
    broker: RecordingBroker,
    now: datetime,
    policy: RetryPolicy,
) -> BackgroundJobDispatcher:
    return BackgroundJobDispatcher(
        session_factory=AsyncSessionFactory,
        broker=broker,
        outbox=outbox,
        retry_policy=policy,
        queue_name="vkca-background",
        dispatcher_id=f"quickstart-dispatcher:{uuid4()}",
        batch_size=50,
        lease_seconds=120,
        clock=lambda: now,
        random_uniform=lambda _lower, _upper: 0,
    )


def _runtime(
    *,
    outbox: BackgroundJobOutbox,
    registry,
    settings,
    provider: FakeEmbeddingProvider,
    now: datetime,
) -> BackgroundWorkerRuntime:
    context = BackgroundHandlerContext(
        settings=settings,
        session_factory=AsyncSessionFactory,
        redis=None,
        provider=provider,
        registry=registry,
    )
    return BackgroundWorkerRuntime(
        session_factory=AsyncSessionFactory,
        registry=registry,
        outbox=outbox,
        handler_context=context,
        worker_id=f"quickstart-worker:{uuid4()}",
        lease_seconds=120,
        clock=lambda: now,
        random_uniform=lambda _lower, _upper: 0,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_background_jobs_foundation_quickstart_flow(caplog) -> None:
    """Validate the documented 20-step durable processing and recovery flow."""

    settings = get_settings().model_copy(
        update={
            "background_max_attempts": 2,
            "background_retry_base_seconds": 1.0,
            "background_retry_max_seconds": 2.0,
            "background_retry_jitter_seconds": 0.0,
        }
    )
    registry = build_background_job_registry(settings=settings)
    policy = registry.get("rag_reconciliation").retry_policy
    outbox = BackgroundJobOutbox(
        registry,
        completed_retention_days=settings.background_completed_retention_days,
        dead_retention_days=settings.background_dead_retention_days,
    )
    operator = User(
        id=uuid4(),
        first_name="Quickstart",
        last_name="Operator",
        email=f"quickstart-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )
    healthy_provider = FakeEmbeddingProvider()

    # Steps 1-4: isolated PostgreSQL fixtures are migrated by the integration
    # harness; the broker/worker seams and representative source are initialized.
    async with AsyncSessionFactory() as session:
        session.add(operator)
        await session.commit()
        before_business = int(
            await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0
        )
        before_auth = int(
            await session.scalar(select(func.count(AuthAuditLog.id))) or 0
        )

    # Steps 5-8: a normal service mutation commits with one durable intent and
    # never invokes the embedding provider on the request path.
    async with AsyncSessionFactory() as session:
        player = await PlayerService(session).create_player(_player_payload("Initial"))
        player_id = player.id
    assert healthy_provider.document_call_count == 0
    async with AsyncSessionFactory() as session:
        committed = await session.get(Player, player_id)
        work = await session.scalar(
            select(BackgroundWorkItem).where(
                BackgroundWorkItem.source_key == str(player_id)
            )
        )
        assert committed is not None and work is not None
        assert work.state == BackgroundWorkState.PENDING
        work_id = work.id
        now = work.run_after

    # A separate rolled-back transaction leaves neither its source nor intent.
    rolled_back_id = uuid4()
    async with AsyncSessionFactory() as session:
        rolled_back = Player(
            id=rolled_back_id,
            **_player_payload("RolledBack").model_dump(),
            is_active=True,
        )
        session.add(rolled_back)
        await session.flush()
        reference = RagMutationRef(
            source=RagMutationSource.PLAYER,
            source_key=str(rolled_back_id),
        )
        await get_rag_mutation_stager().stage(
            session,
            RagMutationImpact(
                operation=RagMutationOperation.UPSERT,
                current_refs=(reference,),
                coalescing_ref=reference,
            ),
        )
        await session.rollback()
    async with AsyncSessionFactory() as session:
        assert await session.get(Player, rolled_back_id) is None
        assert (
            await session.scalar(
                select(func.count(BackgroundWorkItem.id)).where(
                    BackgroundWorkItem.source_key == str(rolled_back_id)
                )
            )
            == 0
        )

    # Redis outage: the committed source survives and the row becomes retryable
    # with only a sanitized failure category/message.
    unavailable = RecordingBroker(failures=1)
    outage = await _dispatcher(
        outbox=outbox,
        broker=unavailable,
        now=now,
        policy=policy,
    ).dispatch_once(now=now)
    assert outage.retrying == 1
    async with AsyncSessionFactory() as session:
        retrying = await session.get(BackgroundWorkItem, work_id)
        assert retrying is not None and retrying.state == BackgroundWorkState.RETRYING
        assert retrying.last_failure_category == "redis_unavailable"
        assert "secret" not in (retrying.last_failure_message or "")
        now = retrying.run_after

    # Steps 9-12: dispatch the PostgreSQL reference, run the registered generic
    # worker, reconcile current truth, and retrieve it through authorization.
    broker = RecordingBroker()
    dispatched = await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now,
        policy=policy,
    ).dispatch_once(now=now)
    assert dispatched.enqueued == 1 and len(broker.envelopes) == 1
    completed = await _runtime(
        outbox=outbox,
        registry=registry,
        settings=settings,
        provider=healthy_provider,
        now=now,
    ).execute(broker.envelopes[-1])
    assert completed.state == BackgroundWorkState.COMPLETED
    async with AsyncSessionFactory() as session:
        retrieval = await RagRetrievalService(
            session,
            provider=healthy_provider,
            query_max_characters=200,
            result_limit_default=20,
            result_limit_max=20,
            timeout_seconds=5,
        ).retrieve(
            operator,
            RagRetrievalRequest(query="Initial Quickstart", limit=20),
        )
        assert any(item.source_key == str(player_id) for item in retrieval.results)

    # Step 13: rapid updates stage one bounded successor carrying current IDs,
    # and processing reloads the newest committed source rather than a snapshot.
    async with AsyncSessionFactory() as session:
        current = await session.get(Player, player_id)
        assert current is not None
        await PlayerService(session).update_player(
            player_id,
            PlayerUpdate(
                first_name="Intermediate", version_number=current.version_number
            ),
        )
        await PlayerService(session).update_player(
            player_id,
            PlayerUpdate(first_name="Current", version_number=current.version_number),
        )
    async with AsyncSessionFactory() as session:
        pending = tuple(
            (
                await session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.source_key == str(player_id),
                        BackgroundWorkItem.state == BackgroundWorkState.PENDING,
                    )
                )
            ).all()
        )
        assert len(pending) == 1
        successor_id = pending[0].id
        now = pending[0].run_after

    # Steps 14-16: provider failure is retryable, a reconstructed worker after
    # the retry window succeeds, and the committed domain value is unchanged.
    await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now,
        policy=policy,
    ).dispatch_once(now=now)
    failed = await _runtime(
        outbox=outbox,
        registry=registry,
        settings=settings,
        provider=FailingProvider(),
        now=now,
    ).execute(broker.envelopes[-1])
    assert failed.state == BackgroundWorkState.RETRYING
    async with AsyncSessionFactory() as session:
        retrying = await session.get(BackgroundWorkItem, successor_id)
        assert retrying is not None
        assert "quickstart-secret" not in (retrying.last_failure_message or "")
        now = retrying.run_after
    await _dispatcher(
        outbox=outbox,
        broker=broker,
        now=now,
        policy=policy,
    ).dispatch_once(now=now)
    recovered = await _runtime(
        outbox=outbox,
        registry=registry,
        settings=settings,
        provider=healthy_provider,
        now=now,
    ).execute(broker.envelopes[-1])
    assert recovered.state == BackgroundWorkState.COMPLETED

    # Steps 17-20: active RAG identities remain unique, technical processing
    # creates no audit records, and status/log projections expose no payloads.
    async with AsyncSessionFactory() as session:
        player_document = await session.scalar(
            select(RagDocument).where(
                RagDocument.source_key == str(player_id),
                RagDocument.is_searchable.is_(True),
            )
        )
        assert player_document is not None
        assert "Current" in player_document.semantic_text
        active_duplicates = (
            await session.execute(
                select(RagDocument.source_type, RagDocument.source_key)
                .where(RagDocument.is_searchable.is_(True))
                .group_by(RagDocument.source_type, RagDocument.source_key)
                .having(func.count(RagDocument.id) > 1)
            )
        ).all()
        assert active_duplicates == []
        assert int(await session.scalar(select(func.count(RagChunk.id))) or 0) > 0
        assert (
            int(await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0)
            == before_business
        )
        assert (
            int(await session.scalar(select(func.count(AuthAuditLog.id))) or 0)
            == before_auth
        )
        status = await outbox.inspect_status(session, limit=10)

    serialized_status = status.model_dump_json()
    rendered_logs = caplog.text
    for item in status.items:
        assert {"payload", "lease_owner", "safe_metadata"}.isdisjoint(item.model_dump())
    assert "quickstart-secret" not in serialized_status
    assert "quickstart-secret" not in rendered_logs
    assert str(settings.redis_url) not in rendered_logs
