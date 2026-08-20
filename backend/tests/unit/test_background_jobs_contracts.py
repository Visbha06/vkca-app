"""Unit coverage for bounded background-job payload and queue contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from arq.jobs import deserialize_job, serialize_job
from pydantic import BaseModel

from src.schemas.background_jobs import BackgroundJobStatus
from src.services.background_jobs.contracts import (
    MAX_JOB_PAYLOAD_BYTES,
    BackgroundJobEnvelopeV1,
    BackgroundPayloadValidationError,
    BackgroundWorkState,
    VersionedPayloadAdapter,
    decode_job_envelope,
    encode_job_envelope,
    json_job_deserializer,
    json_job_serializer,
)


class ExamplePayloadV1(BaseModel):
    """Small synthetic payload used to exercise the generic adapter."""

    source_id: str
    labels: list[str] = []


def test_job_envelope_round_trips_as_bounded_json() -> None:
    work_id = uuid4()
    encoded = encode_job_envelope(
        BackgroundJobEnvelopeV1(contract_version=1, work_id=work_id)
    )

    assert decode_job_envelope(encoded).work_id == work_id
    assert json.loads(encoded) == {
        "contract_version": 1,
        "work_id": str(work_id),
    }
    assert b"pickle" not in encoded.lower()


@pytest.mark.parametrize(
    "raw",
    [
        b'[{"contract_version":1}]',
        b'{"contract_version":2,"work_id":"00000000-0000-4000-8000-000000000000"}',
        b'{"contract_version":1,"work_id":"not-a-uuid"}',
        b'{"contract_version":1,"work_id":"00000000-0000-4000-8000-000000000000","payload":{}}',
    ],
)
def test_job_envelope_rejects_wrong_shape_type_version_and_fields(raw: bytes) -> None:
    with pytest.raises(BackgroundPayloadValidationError):
        decode_job_envelope(raw)


def test_job_envelope_rejects_oversized_input_before_json_parsing() -> None:
    with pytest.raises(BackgroundPayloadValidationError, match="size"):
        decode_job_envelope(b"{" + b" " * 5_000 + b"}")


def test_versioned_payload_adapter_accepts_json_and_rejects_unknown_fields() -> None:
    adapter = VersionedPayloadAdapter(version=1, payload_model=ExamplePayloadV1)

    validated = adapter.validate(
        {"source_id": "player:1", "labels": ["profile", "team"]}
    )

    assert validated.source_id == "player:1"
    with pytest.raises(BackgroundPayloadValidationError):
        adapter.validate({"source_id": "player:1", "unexpected": True})


@pytest.mark.parametrize(
    "payload",
    [
        {"source_id": "player:1", "password": "secret"},
        {"source_id": "player:1", "provider_api_key": "secret"},
        {"source_id": "player:1", "labels": [{"access_token": "secret"}]},
        {"source_id": "player:1", "labels": {"not", "json"}},
        {"source_id": "player:1", "labels": [float("nan")]},
    ],
)
def test_versioned_payload_adapter_rejects_forbidden_or_non_json_values(
    payload: object,
) -> None:
    adapter = VersionedPayloadAdapter(version=1, payload_model=ExamplePayloadV1)

    with pytest.raises(BackgroundPayloadValidationError):
        adapter.validate(payload)


def test_versioned_payload_adapter_enforces_serialized_payload_limit() -> None:
    adapter = VersionedPayloadAdapter(version=1, payload_model=ExamplePayloadV1)

    with pytest.raises(BackgroundPayloadValidationError, match="16 KiB"):
        adapter.validate(
            {
                "source_id": "player:1",
                "labels": ["x" * MAX_JOB_PAYLOAD_BYTES],
            }
        )


def test_arq_json_codec_round_trips_only_json_compatible_job_data() -> None:
    work_id = uuid4()
    raw_job = {
        "f": "run_background_work",
        "a": ({"contract_version": 1, "work_id": str(work_id)},),
        "k": {},
        "t": 1,
        "et": 1_700_000_000_000,
    }

    decoded = json_job_deserializer(json_job_serializer(raw_job))
    assert decoded == {**raw_job, "a": list(raw_job["a"])}
    with pytest.raises(BackgroundPayloadValidationError):
        json_job_serializer({**raw_job, "a": [object()]})

    serialized = serialize_job(
        "run_background_work",
        raw_job["a"],
        {},
        1,
        raw_job["et"],
        serializer=json_job_serializer,
    )
    job = deserialize_job(serialized, deserializer=json_job_deserializer)
    assert job.function == "run_background_work"
    assert job.args[0] == {"contract_version": 1, "work_id": str(work_id)}


def test_safe_status_projection_has_no_payload_or_internal_keys() -> None:
    work_id = uuid4()
    projected = BackgroundJobStatus(
        id=work_id,
        job_type="synthetic_job",
        payload_version=1,
        state=BackgroundWorkState.PENDING,
        correlation_id=None,
        source_type="player_profile",
        source_key="player:1",
        dispatch_attempt_count=0,
        execution_attempt_count=0,
        manual_retry_count=0,
        run_after=datetime.now(UTC),
        last_attempt_at=None,
        dispatched_at=None,
        started_at=None,
        completed_at=None,
        terminal_at=None,
        last_failure_category=None,
        last_failure_message=None,
        manual_retry_allowed=True,
        retention_until=None,
        version_number=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    ).model_dump(mode="json")

    assert projected["id"] == str(work_id)
    assert "payload" not in projected
    assert "idempotency_key" not in projected
    assert "coalescing_key" not in projected
    assert "lease_owner" not in projected
