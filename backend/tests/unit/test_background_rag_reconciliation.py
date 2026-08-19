"""Unit coverage for registered, current-state RAG reconciliation work."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.services.background_jobs.handlers import rag_reconciliation as handler_module
from src.services.background_jobs.handlers.rag_reconciliation import (
    coalesce_rag_reconciliation_payloads,
    rag_reconciliation_handler,
)
from src.services.background_jobs.registry import build_background_job_registry
from src.services.rag.contracts import (
    MAX_RAG_MUTATION_TARGETS,
    RagReconciliationPayloadV1,
    RagRunStatus,
    RagTargetRef,
    SourceDependency,
)
from src.services.rag.registry import (
    RagSourceRegistry,
    RegistryValidationError,
    source_registry,
)


class _AsyncSessionScope:
    def __init__(self, session: object) -> None:
        self.session = session

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        return None


def _context(mocker, *, provider: object | None = None) -> SimpleNamespace:
    session = mocker.Mock(name="session")
    return SimpleNamespace(
        settings=SimpleNamespace(
            rag_embedding_batch_size=8,
            rag_embedding_timeout_seconds=12.0,
        ),
        session_factory=mocker.Mock(return_value=_AsyncSessionScope(session)),
        provider=provider or mocker.Mock(name="provider"),
    )


def test_payload_supports_targeted_and_incremental_safety_modes() -> None:
    target = RagTargetRef(source_type="player_profile", source_key=str(uuid4()))

    targeted = RagReconciliationPayloadV1(
        mode="targets",
        reason="manual",
        targets=(target,),
    )
    safety = RagReconciliationPayloadV1(
        mode="incremental_safety",
        reason="safety",
    )

    assert targeted.targets == (target,)
    assert safety.targets == ()
    with pytest.raises(ValueError, match="at least one"):
        RagReconciliationPayloadV1(mode="targets", reason="mutation")


@pytest.mark.asyncio
async def test_registered_handler_delegates_stable_targets_to_indexing_service(
    mocker,
) -> None:
    target = RagTargetRef(source_type="player_profile", source_key=str(uuid4()))
    report = SimpleNamespace(status=RagRunStatus.COMPLETED)
    service = mocker.Mock()
    service.reconcile_targets = mocker.AsyncMock(return_value=(report,))
    service_type = mocker.patch.object(
        handler_module,
        "RagIndexingService",
        return_value=service,
    )
    provider = mocker.Mock()
    provider.embed_documents = mocker.AsyncMock()
    context = _context(mocker, provider=provider)

    await rag_reconciliation_handler(
        context,
        RagReconciliationPayloadV1(
            mode="targets",
            reason="mutation",
            targets=(target,),
        ),
    )

    service_type.assert_called_once()
    service.reconcile_targets.assert_awaited_once_with((target,))
    provider.embed_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_handler_delivery_reloads_through_service_each_time(
    mocker,
) -> None:
    target = RagTargetRef(source_type="team", source_key=str(uuid4()))
    report = SimpleNamespace(status=RagRunStatus.COMPLETED)
    service = mocker.Mock()
    service.reconcile_targets = mocker.AsyncMock(return_value=(report,))
    mocker.patch.object(handler_module, "RagIndexingService", return_value=service)
    context = _context(mocker)
    payload = RagReconciliationPayloadV1(targets=(target,))

    await rag_reconciliation_handler(context, payload)
    await rag_reconciliation_handler(context, payload)

    assert service.reconcile_targets.await_count == 2
    assert payload.model_dump(mode="json") == {
        "mode": "targets",
        "reason": "mutation",
        "targets": [
            {"source_type": "team", "source_key": target.source_key},
        ],
    }


@pytest.mark.asyncio
async def test_handler_rejects_unregistered_source_before_service_execution(
    mocker,
) -> None:
    service_type = mocker.patch.object(handler_module, "RagIndexingService")
    payload = RagReconciliationPayloadV1(
        targets=(RagTargetRef(source_type="unknown_source", source_key="safe-key"),)
    )

    with pytest.raises(RegistryValidationError, match="not registered"):
        await rag_reconciliation_handler(_context(mocker), payload)

    service_type.assert_not_called()


@pytest.mark.asyncio
async def test_incremental_safety_uses_existing_incremental_operation(mocker) -> None:
    report = SimpleNamespace(status=RagRunStatus.COMPLETED)
    service = mocker.Mock()
    service.run_incremental = mocker.AsyncMock(return_value=report)
    mocker.patch.object(handler_module, "RagIndexingService", return_value=service)

    await rag_reconciliation_handler(
        _context(mocker),
        RagReconciliationPayloadV1(
            mode="incremental_safety",
            reason="safety",
        ),
    )

    service.run_incremental.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_registry_resolves_declared_dependency_targets_without_second_map(
    mocker,
) -> None:
    upstream = source_registry.get("player_profile")
    dependent = source_registry.get("team")
    resolver = mocker.AsyncMock(return_value=("dependent-1",))
    dependency = SourceDependency(
        "synthetic_dependency",
        trigger_source_types=(upstream.source_type,),
        target_resolver=resolver,
    )
    dependent = replace(dependent, dependencies=(dependency,))
    registry = RagSourceRegistry((upstream, dependent))
    root = RagTargetRef(source_type=upstream.source_type, source_key="root-1")
    session = mocker.Mock()

    closure = await registry.resolve_dependency_closure(session, (root,))

    assert closure == (
        root,
        RagTargetRef(source_type=dependent.source_type, source_key="dependent-1"),
    )
    resolver.assert_awaited_once_with(
        session,
        trigger_source_type=upstream.source_type,
        trigger_source_keys=(root.source_key,),
        limit=127,
    )


def test_rag_payload_coalescing_unions_stable_targets() -> None:
    first = RagTargetRef(source_type="player_profile", source_key=str(uuid4()))
    second = RagTargetRef(source_type="team", source_key=str(uuid4()))

    merged = coalesce_rag_reconciliation_payloads(
        RagReconciliationPayloadV1(targets=(first,)),
        RagReconciliationPayloadV1(targets=(second,)),
    )

    assert set(merged.targets) == {first, second}
    assert merged.mode == "targets"
    assert merged.reason == "mutation"


def test_rag_payload_coalescing_overflow_becomes_bounded_safety_work() -> None:
    full_batch = tuple(
        RagTargetRef(source_type="player_profile", source_key=f"player-{index}")
        for index in range(MAX_RAG_MUTATION_TARGETS)
    )
    overflow = RagTargetRef(
        source_type="player_profile",
        source_key="overflow-player",
    )

    merged = coalesce_rag_reconciliation_payloads(
        RagReconciliationPayloadV1(targets=full_batch),
        RagReconciliationPayloadV1(targets=(overflow,)),
    )

    assert merged.mode == "incremental_safety"
    assert merged.reason == "safety"
    assert merged.targets == ()


def test_application_registry_uses_real_rag_handler_and_retry_policy() -> None:
    registry = build_background_job_registry()

    definition = registry.get("rag_reconciliation", payload_version=1)

    assert definition.handler is rag_reconciliation_handler
    assert definition.manual_retry_allowed
    assert definition.coalescer is coalesce_rag_reconciliation_payloads
    assert definition.retry_policy.max_attempts >= 1
    assert definition.timeout_seconds <= 3_600
