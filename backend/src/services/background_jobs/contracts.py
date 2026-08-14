"""Typed, bounded contracts shared by dispatchers and background workers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

MAX_JOB_PAYLOAD_BYTES: Final = 16 * 1024
MAX_QUEUE_MESSAGE_BYTES: Final = 4 * 1024
MAX_SAFE_COLLECTION_ITEMS: Final = 128

_FORBIDDEN_PAYLOAD_FIELDS: Final = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "csrf_token",
        "document",
        "documents",
        "database_url",
        "embedding",
        "embeddings",
        "hashed_password",
        "jwt",
        "password",
        "password_hash",
        "payload",
        "provider_credential",
        "provider_response",
        "refresh_token",
        "redis_url",
        "secret",
        "session",
        "session_id",
        "token",
        "vector",
        "vectors",
    }
)
_FORBIDDEN_PAYLOAD_FIELD_PARTS: Final = (
    "authorization",
    "cookie",
    "credential",
    "csrf",
    "document",
    "embedding",
    "password",
    "secret",
    "session",
    "token",
    "vector",
)


class BackgroundWorkState(StrEnum):
    """Durable processing states for a background work item."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    DEAD = "dead"


ACTIVE_COALESCING_STATES: Final = frozenset(
    {
        BackgroundWorkState.PENDING,
        BackgroundWorkState.SCHEDULED,
        BackgroundWorkState.DISPATCHING,
        BackgroundWorkState.DISPATCHED,
        BackgroundWorkState.RETRYING,
    }
)
DISPATCH_ELIGIBLE_STATES: Final = frozenset(
    {
        BackgroundWorkState.PENDING,
        BackgroundWorkState.SCHEDULED,
        BackgroundWorkState.RETRYING,
    }
)
TERMINAL_STATES: Final = frozenset(
    {BackgroundWorkState.COMPLETED, BackgroundWorkState.DEAD}
)


class BackgroundJobContractError(ValueError):
    """Base class for safe background-processing contract failures."""


class BackgroundPayloadValidationError(BackgroundJobContractError):
    """Raised when a queue envelope or durable payload is unsafe or invalid."""


class UnregisteredBackgroundJobError(BackgroundJobContractError):
    """Raised when a job type is absent from the execution allowlist."""


class IncompatiblePayloadVersionError(BackgroundJobContractError):
    """Raised when stored work uses an unsupported payload version."""


class BackgroundWorkConflictError(RuntimeError):
    """Raised when an optimistic state transition loses to another writer."""

    def __init__(
        self,
        work_id: UUID,
        expected_version: int,
        *,
        current: object | None = None,
    ) -> None:
        self.work_id = work_id
        self.expected_version = expected_version
        self.current = current
        super().__init__(
            f"Background work {work_id} changed after version {expected_version}."
        )


class BackgroundJobEnvelopeV1(BaseModel):
    """The only application payload permitted to cross the Redis boundary."""

    contract_version: Literal[1] = 1
    work_id: UUID

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class VersionedPayloadAdapter[PayloadModelT: BaseModel]:
    """Validate one explicit payload model/version and its serialized bounds."""

    version: int
    payload_model: type[PayloadModelT]
    max_serialized_bytes: int = MAX_JOB_PAYLOAD_BYTES

    def __post_init__(self) -> None:
        if not 1 <= self.version <= 32_767:
            raise ValueError("Payload versions must be between 1 and 32767")
        if not isinstance(self.payload_model, type) or not issubclass(
            self.payload_model, BaseModel
        ):
            raise TypeError("payload_model must be a Pydantic BaseModel type")
        if not 1 <= self.max_serialized_bytes <= MAX_JOB_PAYLOAD_BYTES:
            raise ValueError("Payload byte bounds must be within 16 KiB")

    def validate(self, payload: object) -> PayloadModelT:
        """Return the typed payload after strict JSON, field, and size checks."""

        if isinstance(payload, self.payload_model):
            validated_input = validate_json_object(
                payload.model_dump(mode="json", by_alias=True),
                max_serialized_bytes=self.max_serialized_bytes,
                reject_forbidden_fields=True,
            )
        else:
            validated_input = validate_json_object(
                payload,
                max_serialized_bytes=self.max_serialized_bytes,
                reject_forbidden_fields=True,
            )
        allowed_fields = set(self.payload_model.model_fields)
        allowed_aliases = {
            field.alias
            for field in self.payload_model.model_fields.values()
            if field.alias is not None
        }
        unknown_fields = set(validated_input).difference(
            allowed_fields | allowed_aliases
        )
        if unknown_fields:
            raise BackgroundPayloadValidationError(
                "Background job payload contains unknown fields."
            )
        try:
            model = self.payload_model.model_validate(validated_input)
        except ValidationError as exc:
            raise BackgroundPayloadValidationError(
                "Background job payload does not match its registered schema."
            ) from exc

        serialized = model.model_dump(mode="json", by_alias=True)
        validate_json_object(
            serialized,
            max_serialized_bytes=self.max_serialized_bytes,
            reject_forbidden_fields=True,
        )
        return model

    def dump(self, payload: PayloadModelT | object) -> dict[str, Any]:
        """Return the normalized JSON object for persistence."""

        model = (
            payload
            if isinstance(payload, self.payload_model)
            else self.validate(payload)
        )
        dumped = model.model_dump(mode="json", by_alias=True)
        return validate_json_object(
            dumped,
            max_serialized_bytes=self.max_serialized_bytes,
            reject_forbidden_fields=True,
        )


def _validate_json_tree(
    value: object,
    *,
    reject_forbidden_fields: bool,
    depth: int = 0,
) -> None:
    if depth > 12:
        raise BackgroundPayloadValidationError(
            "Background job JSON nesting exceeds the supported bound."
        )
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise BackgroundPayloadValidationError(
                "Background job JSON contains a non-finite number."
            )
        return
    if isinstance(value, list):
        if len(value) > MAX_SAFE_COLLECTION_ITEMS:
            raise BackgroundPayloadValidationError(
                "Background job JSON collection exceeds the supported bound."
            )
        for item in value:
            _validate_json_tree(
                item,
                reject_forbidden_fields=reject_forbidden_fields,
                depth=depth + 1,
            )
        return
    if isinstance(value, dict):
        if len(value) > MAX_SAFE_COLLECTION_ITEMS:
            raise BackgroundPayloadValidationError(
                "Background job JSON object exceeds the supported field bound."
            )
        for key, item in value.items():
            if not isinstance(key, str):
                raise BackgroundPayloadValidationError(
                    "Background job JSON keys must be strings."
                )
            normalized_key = key.strip().casefold()
            forbidden_key = normalized_key in _FORBIDDEN_PAYLOAD_FIELDS or any(
                part in normalized_key for part in _FORBIDDEN_PAYLOAD_FIELD_PARTS
            )
            if reject_forbidden_fields and forbidden_key:
                raise BackgroundPayloadValidationError(
                    "Background job payload contains a forbidden field."
                )
            _validate_json_tree(
                item,
                reject_forbidden_fields=reject_forbidden_fields,
                depth=depth + 1,
            )
        return
    raise BackgroundPayloadValidationError(
        "Background job data must contain JSON-compatible values only."
    )


def _encode_json(value: object, *, max_serialized_bytes: int) -> bytes:
    _validate_json_tree(value, reject_forbidden_fields=False)
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise BackgroundPayloadValidationError(
            "Background job data could not be serialized as JSON."
        ) from exc
    if len(encoded) > max_serialized_bytes:
        bound = "16 KiB" if max_serialized_bytes == MAX_JOB_PAYLOAD_BYTES else "size"
        raise BackgroundPayloadValidationError(
            f"Background job JSON exceeds the configured {bound} bound."
        )
    return encoded


def validate_json_object(
    value: object,
    *,
    max_serialized_bytes: int = MAX_JOB_PAYLOAD_BYTES,
    reject_forbidden_fields: bool = True,
) -> dict[str, Any]:
    """Validate a bounded JSON object without coercing unsafe Python values."""

    if not isinstance(value, dict):
        raise BackgroundPayloadValidationError(
            "Background job payload must be a JSON object."
        )
    _validate_json_tree(
        value,
        reject_forbidden_fields=reject_forbidden_fields,
    )
    _encode_json(value, max_serialized_bytes=max_serialized_bytes)
    return dict(value)


def encode_job_envelope(envelope: BackgroundJobEnvelopeV1) -> bytes:
    """Serialize the application queue envelope without pickle."""

    return _encode_json(
        envelope.model_dump(mode="json"),
        max_serialized_bytes=MAX_QUEUE_MESSAGE_BYTES,
    )


def decode_job_envelope(data: bytes | bytearray | str) -> BackgroundJobEnvelopeV1:
    """Decode and strictly validate one bounded queue envelope."""

    if isinstance(data, str):
        raw = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raise BackgroundPayloadValidationError("Queue envelope must be JSON bytes.")
    if len(raw) > MAX_QUEUE_MESSAGE_BYTES:
        raise BackgroundPayloadValidationError(
            "Queue envelope exceeds the configured size bound."
        )
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackgroundPayloadValidationError(
            "Queue envelope is not valid JSON."
        ) from exc
    if not isinstance(decoded, dict):
        raise BackgroundPayloadValidationError("Queue envelope must be a JSON object.")
    try:
        return BackgroundJobEnvelopeV1.model_validate(decoded)
    except ValidationError as exc:
        raise BackgroundPayloadValidationError(
            "Queue envelope does not match contract version 1."
        ) from exc


def json_job_serializer(data: dict[str, Any]) -> bytes:
    """Serialize ARQ's internal job dictionary through a bounded JSON codec."""

    if not isinstance(data, dict):
        raise BackgroundPayloadValidationError("ARQ job data must be a JSON object.")
    normalized = _normalize_arq_json(data)
    return _encode_json(normalized, max_serialized_bytes=MAX_QUEUE_MESSAGE_BYTES)


def json_job_deserializer(data: bytes) -> dict[str, Any]:
    """Deserialize ARQ job data and reject non-object or oversized values."""

    if len(data) > MAX_QUEUE_MESSAGE_BYTES:
        raise BackgroundPayloadValidationError(
            "ARQ job data exceeds the configured size bound."
        )
    try:
        decoded = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackgroundPayloadValidationError(
            "ARQ job data is not valid JSON."
        ) from exc
    return validate_json_object(
        decoded,
        max_serialized_bytes=MAX_QUEUE_MESSAGE_BYTES,
        reject_forbidden_fields=False,
    )


def _normalize_arq_json(value: object) -> Any:
    """Normalize ARQ's required tuple args while rejecting arbitrary objects."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_arq_json(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise BackgroundPayloadValidationError("ARQ job keys must be strings.")
        return {key: _normalize_arq_json(item) for key, item in value.items()}
    raise BackgroundPayloadValidationError(
        "ARQ job data must contain JSON-compatible values only."
    )
