"""Unit coverage for the explicit background-job execution registry."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from src.services.background_jobs.contracts import (
    BackgroundPayloadValidationError,
    IncompatiblePayloadVersionError,
    UnregisteredBackgroundJobError,
)
from src.services.background_jobs.registry import (
    BackgroundJobDefinition,
    BackgroundJobRegistry,
    DuplicateBackgroundJobError,
    HandlerNotAllowedError,
    InvalidBackgroundJobDefinitionError,
    ResourceBounds,
)
from src.services.background_jobs.retry import RetryPolicy


class SyntheticPayload(BaseModel):
    value: str


async def allowed_handler(context: object, payload: BaseModel) -> None:
    del context, payload


async def second_handler(context: object, payload: BaseModel) -> None:
    del context, payload


def sync_handler(context: object, payload: BaseModel) -> None:
    del context, payload


def make_definition(**overrides: Any) -> BackgroundJobDefinition:
    values: dict[str, Any] = {
        "job_type": "synthetic_job",
        "payload_version": 1,
        "payload_model": SyntheticPayload,
        "handler": allowed_handler,
        "retry_policy": RetryPolicy(
            max_attempts=3,
            base_delay_seconds=1,
            max_delay_seconds=30,
            jitter_seconds=2,
            timeout_seconds=20,
        ),
        "idempotency_strategy": "Reload current state before applying work.",
        "resource_bounds": ResourceBounds(max_concurrency=2, max_batch_size=25),
        "manual_retry_allowed": True,
    }
    values.update(overrides)
    return BackgroundJobDefinition(**values)


def test_registry_registers_and_validates_allowlisted_definition() -> None:
    registry = BackgroundJobRegistry(allowed_handlers={allowed_handler})
    definition = registry.register(make_definition())

    assert registry.get("synthetic_job", payload_version=1) is definition
    payload = registry.validate_payload("synthetic_job", 1, {"value": "current"})
    assert isinstance(payload, SyntheticPayload)


def test_registry_rejects_duplicate_job_type_registration() -> None:
    registry = BackgroundJobRegistry(allowed_handlers={allowed_handler})
    registry.register(make_definition())

    with pytest.raises(DuplicateBackgroundJobError):
        registry.register(make_definition(payload_version=2))


def test_registry_rejects_unregistered_job_and_payload_version() -> None:
    registry = BackgroundJobRegistry(allowed_handlers={allowed_handler})
    registry.register(make_definition())

    with pytest.raises(UnregisteredBackgroundJobError):
        registry.get("missing_job", payload_version=1)
    with pytest.raises(IncompatiblePayloadVersionError):
        registry.get("synthetic_job", payload_version=2)


def test_registry_rejects_handler_outside_explicit_allowlist() -> None:
    registry = BackgroundJobRegistry(allowed_handlers={allowed_handler})

    with pytest.raises(HandlerNotAllowedError):
        registry.register(make_definition(handler=second_handler))


@pytest.mark.parametrize(
    "overrides",
    [
        {"job_type": "Synthetic Job"},
        {"job_type": ""},
        {"payload_version": 0},
        {"handler": sync_handler},
        {"idempotency_strategy": "   "},
        {"retry_classifier": None},
        {"resource_bounds": ResourceBounds(max_concurrency=1, max_batch_size=1_001)},
    ],
)
def test_registry_rejects_invalid_definition_metadata(
    overrides: dict[str, Any],
) -> None:
    registry = BackgroundJobRegistry(allowed_handlers={allowed_handler, sync_handler})

    with pytest.raises(InvalidBackgroundJobDefinitionError):
        registry.register(make_definition(**overrides))


def test_registry_payload_validation_rejects_unknown_fields() -> None:
    registry = BackgroundJobRegistry(allowed_handlers={allowed_handler})
    registry.register(make_definition())

    with pytest.raises(BackgroundPayloadValidationError):
        registry.validate_payload(
            "synthetic_job",
            1,
            {"value": "current", "module_path": "unsafe.dynamic.handler"},
        )
