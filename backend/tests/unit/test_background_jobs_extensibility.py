"""Focused unit coverage for future typed background-job onboarding."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from scripts.background_jobs import parse_args
from src.services.background_jobs.contracts import (
    BackgroundPayloadValidationError,
    BackgroundWorkState,
    IncompatiblePayloadVersionError,
    UnregisteredBackgroundJobError,
)
from src.services.background_jobs.handlers.rag_reconciliation import (
    build_rag_manual_trigger,
    rag_reconciliation_handler,
)
from src.services.background_jobs.outbox import BackgroundJobOutbox
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    DuplicateBackgroundJobError,
    ResourceBounds,
)
from src.services.background_jobs.retry import RetryPolicy
from src.services.rag.contracts import RagRunStatus


class SyntheticPayload(BaseModel):
    """A deliberately small future-job payload with no free-form fields."""

    record_id: str = Field(min_length=1, max_length=80)

    model_config = ConfigDict(extra="forbid", frozen=True)


async def synthetic_handler(context: object, payload: BaseModel) -> None:
    del context, payload


class _ScalarResult:
    def scalar_one_or_none(self) -> None:
        return None


def _policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        base_delay_seconds=1,
        max_delay_seconds=30,
        jitter_seconds=0,
        timeout_seconds=20,
    )


def _definition(**overrides: Any) -> BackgroundJobDefinition:
    values: dict[str, Any] = {
        "job_type": "synthetic_maintenance",
        "payload_version": 1,
        "payload_model": SyntheticPayload,
        "handler": synthetic_handler,
        "retry_policy": _policy(),
        "idempotency_strategy": "Reload the current record before applying repair.",
        "resource_bounds": ResourceBounds(max_concurrency=2, max_batch_size=25),
        "manual_retry_allowed": True,
        "manual_trigger": "trigger-synthetic-maintenance",
    }
    values.update(overrides)
    return BackgroundJobDefinition(**values)


def _registry() -> BackgroundJobRegistry:
    registry = BackgroundJobRegistry(allowed_handlers={synthetic_handler})
    registry.register(_definition())
    return registry


def _session(mocker: Any) -> Any:
    session = mocker.Mock()
    session.execute = mocker.AsyncMock(return_value=_ScalarResult())
    session.flush = mocker.AsyncMock()
    return session


def test_registered_future_job_declares_typed_policy_and_resource_bounds() -> None:
    registry = _registry()

    definition = registry.get_manual_trigger("trigger-synthetic-maintenance")

    assert definition.job_type == "synthetic_maintenance"
    assert definition.payload_version == 1
    assert definition.retry_policy.max_attempts == 3
    assert definition.idempotency_strategy.startswith("Reload")
    assert definition.resource_bounds == ResourceBounds(
        max_concurrency=2, max_batch_size=25
    )
    assert (
        registry.validate_payload(
            definition.job_type,
            definition.payload_version,
            {"record_id": "record-1"},
        ).record_id
        == "record-1"
    )


def test_future_job_registration_rejects_duplicate_manual_trigger() -> None:
    registry = _registry()

    with pytest.raises(DuplicateBackgroundJobError, match="manual trigger"):
        registry.register(_definition(job_type="another_maintenance"))


def test_registry_rejects_unknown_type_version_and_payload_shape() -> None:
    registry = _registry()

    with pytest.raises(UnregisteredBackgroundJobError):
        registry.get_manual_trigger("trigger-not-registered")
    with pytest.raises(UnregisteredBackgroundJobError):
        registry.validate_payload("unknown_job", 1, {"record_id": "record-1"})
    with pytest.raises(IncompatiblePayloadVersionError):
        registry.validate_payload("synthetic_maintenance", 2, {"record_id": "record-1"})
    with pytest.raises(BackgroundPayloadValidationError):
        registry.validate_payload(
            "synthetic_maintenance",
            1,
            {"record_id": "record-1", "module": "unsafe"},
        )


@pytest.mark.asyncio
async def test_manual_trigger_uses_typed_staging_and_future_eligibility(
    mocker: Any,
) -> None:
    now = datetime(2026, 8, 19, 12, tzinfo=UTC)
    outbox = BackgroundJobOutbox(_registry(), clock=lambda: now)
    session = _session(mocker)

    staged = await outbox.stage_manual_trigger(
        session,
        "trigger-synthetic-maintenance",
        {"record_id": "record-1"},
        run_after=now + timedelta(minutes=5),
    )

    assert staged.state is BackgroundWorkState.SCHEDULED
    assert staged.run_after == now + timedelta(minutes=5)
    assert staged.job_type == "synthetic_maintenance"
    assert staged.payload == {"record_id": "record-1"}
    session.add.assert_called_once_with(staged)
    session.flush.assert_awaited_once()


def test_rag_operator_trigger_supports_only_fixed_safety_or_targeted_shapes() -> None:
    safety = parse_args(
        ["trigger-rag", "--safety", "--run-after", "2026-08-19T12:05:00+00:00"]
    )
    target = parse_args(
        [
            "trigger-rag",
            "--source-type",
            "player_profile",
            "--source-key",
            "player-1",
        ]
    )

    assert safety.safety is True
    assert safety.run_after == datetime(2026, 8, 19, 12, 5, tzinfo=UTC)
    assert target.safety is False
    assert target.source_type == "player_profile"
    with pytest.raises(SystemExit):
        parse_args(["trigger-rag", "--safety", "--source-key", "player-1"])
    with pytest.raises(SystemExit):
        parse_args(["trigger-rag", "--source-type", "player_profile"])


def test_rag_safety_trigger_is_a_minimal_repair_extension_point() -> None:
    request = build_rag_manual_trigger(safety=True)

    assert request.payload.mode == "incremental_safety"
    assert request.payload.reason == "repair"
    assert request.payload.targets == ()
    assert request.coalescing_key == "rag:incremental-safety"
    assert request.safe_metadata["trigger_kind"] == "incremental_safety"


@pytest.mark.asyncio
async def test_repair_safety_handler_reuses_existing_repair_operation(
    mocker: Any,
) -> None:
    from src.services.background_jobs.handlers import rag_reconciliation

    class SessionScope:
        async def __aenter__(self) -> object:
            return mocker.Mock()

        async def __aexit__(self, *args: object) -> None:
            return None

    report = SimpleNamespace(status=RagRunStatus.COMPLETED)
    service = mocker.Mock()
    service.run_repair = mocker.AsyncMock(return_value=report)
    mocker.patch.object(rag_reconciliation, "RagIndexingService", return_value=service)
    context = SimpleNamespace(
        settings=SimpleNamespace(
            rag_embedding_batch_size=8,
            rag_embedding_timeout_seconds=12.0,
        ),
        session_factory=mocker.Mock(return_value=SessionScope()),
        provider=mocker.Mock(),
    )

    await rag_reconciliation_handler(
        context, build_rag_manual_trigger(safety=True).payload
    )

    service.run_repair.assert_awaited_once_with()
