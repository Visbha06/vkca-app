"""Central provider protocol, validation, batching, and deterministic fake."""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol

from src.services.rag.contracts import (
    EmbeddingBatch,
    EmbeddingInput,
    EmbeddingProfile,
    EmbeddingPurpose,
    EmbeddingVector,
)

RAG_VECTOR_DIMENSION = 1536
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
FAKE_ADAPTER_VERSION = "fake-v1"

_SENSITIVE_PROVIDER_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token|credential)"
    r"\s*[:=]\s*[^\s,;]+"
)
_URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+:[^/@\s]+@", re.I)


def sanitize_provider_message(message: str) -> str:
    """Bound a provider-facing error without preserving credentials or bodies."""

    normalized = " ".join(message.split())
    normalized = _SENSITIVE_PROVIDER_VALUE.sub(
        lambda match: f"{match.group(1)}=[redacted]", normalized
    )
    normalized = _URL_CREDENTIALS.sub(r"\1[redacted]@", normalized)
    if "request body" in normalized.casefold() or "vector=" in normalized.casefold():
        return "Embedding provider rejected the bounded request."
    return normalized[:500]


class EmbeddingErrorCategory(StrEnum):
    """Sanitized provider failures safe for technical status telemetry."""

    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    INCOMPATIBLE_PROFILE = "incompatible_profile"


class EmbeddingProviderError(RuntimeError):
    """Base provider error whose string/repr never contains a raw exception."""

    def __init__(
        self,
        category: EmbeddingErrorCategory | str,
        *,
        safe_message: str,
        retryable: bool = False,
        internal_error: BaseException | None = None,
    ) -> None:
        del internal_error
        self.category = (
            category
            if isinstance(category, EmbeddingErrorCategory)
            else EmbeddingErrorCategory(category)
        )
        self.safe_message = sanitize_provider_message(safe_message)
        self.retryable = retryable
        super().__init__(self.safe_message)

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(category={self.category.value!r}, "
            f"safe_message={self.safe_message!r}, retryable={self.retryable!r})"
        )


class EmbeddingConfigurationError(EmbeddingProviderError):
    def __init__(self, safe_message: str) -> None:
        super().__init__(
            EmbeddingErrorCategory.CONFIGURATION,
            safe_message=safe_message,
        )


class EmbeddingAuthenticationError(EmbeddingProviderError):
    def __init__(self) -> None:
        super().__init__(
            EmbeddingErrorCategory.AUTHENTICATION,
            safe_message="Embedding provider authentication failed.",
        )


class EmbeddingTimeoutError(EmbeddingProviderError):
    def __init__(self) -> None:
        super().__init__(
            EmbeddingErrorCategory.TIMEOUT,
            safe_message="Embedding provider timed out.",
            retryable=True,
        )


class EmbeddingUnavailableError(EmbeddingProviderError):
    def __init__(self) -> None:
        super().__init__(
            EmbeddingErrorCategory.PROVIDER_UNAVAILABLE,
            safe_message="Embedding provider is unavailable.",
            retryable=True,
        )


class EmbeddingResponseError(EmbeddingProviderError):
    def __init__(self, safe_message: str) -> None:
        super().__init__(
            EmbeddingErrorCategory.MALFORMED_RESPONSE,
            safe_message=safe_message,
        )


class EmbeddingCompatibilityError(EmbeddingProviderError):
    def __init__(self, safe_message: str) -> None:
        super().__init__(
            EmbeddingErrorCategory.INCOMPATIBLE_PROFILE,
            safe_message=safe_message,
        )


class EmbeddingProvider(Protocol):
    """Only boundary through which document/query vectors are produced."""

    @property
    def profile(self) -> EmbeddingProfile: ...

    async def embed_documents(
        self,
        inputs: Sequence[EmbeddingInput],
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingBatch: ...

    async def embed_query(
        self,
        query: str,
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingVector: ...


class EmbeddingSettings(Protocol):
    """Minimal settings surface consumed by provider selection."""

    @property
    def rag_embedding_provider(self) -> str: ...

    @property
    def rag_embedding_model(self) -> str: ...

    @property
    def rag_embedding_dimension(self) -> int: ...

    @property
    def rag_embedding_batch_size(self) -> int: ...

    @property
    def rag_embedding_timeout_seconds(self) -> float: ...

    @property
    def gemini_api_key(self) -> object | None: ...


def normalize_vector(
    values: Sequence[float],
    *,
    expected_dimension: int,
) -> tuple[float, ...]:
    """Validate finite output and manually L2-normalize a reduced vector."""

    if len(values) != expected_dimension:
        raise EmbeddingResponseError(
            "Embedding response has an invalid vector dimension."
        )
    converted = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in converted):
        raise EmbeddingResponseError("Embedding response contains non-finite values.")
    magnitude = math.sqrt(sum(value * value for value in converted))
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise EmbeddingResponseError("Embedding response contains an invalid vector.")
    return tuple(value / magnitude for value in converted)


def validate_embedding_batch(
    inputs: Sequence[EmbeddingInput],
    batch: EmbeddingBatch,
    *,
    expected_profile: EmbeddingProfile,
) -> EmbeddingBatch:
    """Reject ambiguous, partial, malformed, incompatible, or non-finite output."""

    if batch.profile.compatibility_key != expected_profile.compatibility_key:
        raise EmbeddingCompatibilityError(
            "Embedding profile is incompatible; an explicit re-index is required."
        )
    if len(batch.vectors) != len(inputs):
        raise EmbeddingResponseError(
            "Embedding response count does not match the submitted batch."
        )
    for submitted, returned in zip(inputs, batch.vectors, strict=True):
        if returned.item_key != submitted.item_key:
            raise EmbeddingResponseError(
                "Embedding response order cannot be mapped to submitted items."
            )
        if len(returned.values) != expected_profile.dimension:
            raise EmbeddingResponseError(
                "Embedding response has an invalid vector dimension."
            )
        if not all(math.isfinite(value) for value in returned.values):
            raise EmbeddingResponseError(
                "Embedding response contains non-finite values."
            )
        magnitude = math.sqrt(sum(value * value for value in returned.values))
        if not math.isfinite(magnitude) or magnitude <= 0:
            raise EmbeddingResponseError(
                "Embedding response contains an invalid vector."
            )
        if not math.isclose(magnitude, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise EmbeddingResponseError(
                "Embedding response vectors must be L2 normalized."
            )
    return batch


def assert_compatible_profile_transition(
    current: EmbeddingProfile | None,
    candidate: EmbeddingProfile,
) -> None:
    """Prevent silent vector mixing and describe the required recovery path."""

    if current is None:
        return
    if current.dimension != candidate.dimension:
        raise EmbeddingCompatibilityError(
            "Embedding dimension changed; a vector migration and full rebuild "
            "are required."
        )
    if current.compatibility_key != candidate.compatibility_key:
        raise EmbeddingCompatibilityError(
            "Embedding provider/model profile changed; an explicit targeted or full "
            "re-index is required."
        )


def validate_embedding_configuration(
    *,
    provider_name: str,
    model_name: str,
    dimension: int,
) -> None:
    """Validate the configured profile against migration 014 before provider work."""

    if dimension != RAG_VECTOR_DIMENSION:
        raise EmbeddingConfigurationError(
            "Configured embedding dimension is incompatible with vector(1536)."
        )
    if provider_name == "gemini" and model_name != GEMINI_EMBEDDING_MODEL:
        raise EmbeddingConfigurationError(
            "The Gemini adapter requires gemini-embedding-001; use an explicit "
            "provider transition for another model."
        )


def _deterministic_values(
    input_item: EmbeddingInput, dimension: int
) -> tuple[float, ...]:
    payload = f"{input_item.purpose.value}\x1f{input_item.text}".encode()
    raw = hashlib.shake_256(payload).digest(dimension * 2)
    values = tuple(
        (int.from_bytes(raw[index : index + 2], "big") - 32_767.5) / 32_767.5
        for index in range(0, len(raw), 2)
    )
    return normalize_vector(values, expected_dimension=dimension)


class FakeEmbeddingProvider:
    """Offline deterministic provider honoring the production typed contract."""

    def __init__(self, *, profile: EmbeddingProfile | None = None) -> None:
        self._profile = profile or EmbeddingProfile(
            provider_name="fake",
            model_name=GEMINI_EMBEDDING_MODEL,
            dimension=RAG_VECTOR_DIMENSION,
            adapter_version=FAKE_ADAPTER_VERSION,
        )
        self.document_call_count = 0
        self.query_call_count = 0
        self.document_batch_keys: list[tuple[str, ...]] = []

    @property
    def profile(self) -> EmbeddingProfile:
        return self._profile

    def _validate_requested_profile(
        self,
        requested: EmbeddingProfile | None,
    ) -> None:
        if (
            requested is not None
            and requested.compatibility_key != self.profile.compatibility_key
        ):
            raise EmbeddingCompatibilityError(
                "Requested embedding profile is incompatible with this provider."
            )

    async def embed_documents(
        self,
        inputs: Sequence[EmbeddingInput],
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingBatch:
        self._validate_requested_profile(profile)
        ordered = tuple(inputs)
        if any(item.purpose is not EmbeddingPurpose.DOCUMENT for item in ordered):
            raise EmbeddingConfigurationError(
                "Document embedding batches require document-purpose inputs."
            )
        self.document_call_count += 1
        self.document_batch_keys.append(tuple(item.item_key for item in ordered))
        batch = EmbeddingBatch(
            profile=self.profile,
            vectors=tuple(
                EmbeddingVector(
                    item_key=item.item_key,
                    values=_deterministic_values(item, self.profile.dimension),
                )
                for item in ordered
            ),
        )
        return validate_embedding_batch(
            ordered,
            batch,
            expected_profile=self.profile,
        )

    async def embed_query(
        self,
        query: str,
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingVector:
        self._validate_requested_profile(profile)
        if not query.strip():
            raise EmbeddingConfigurationError("Embedding query must not be blank.")
        self.query_call_count += 1
        input_item = EmbeddingInput(
            item_key="query",
            text=query,
            purpose=EmbeddingPurpose.QUERY,
        )
        return EmbeddingVector(
            item_key=input_item.item_key,
            values=_deterministic_values(input_item, self.profile.dimension),
        )


class EmbeddingBatcher:
    """Apply bounded all-or-nothing document batches and per-call timeouts."""

    def __init__(self, *, batch_size: int, timeout_seconds: float) -> None:
        if batch_size <= 0:
            raise ValueError("embedding batch size must be positive")
        if timeout_seconds <= 0:
            raise ValueError("embedding timeout must be positive")
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds

    async def embed_documents(
        self,
        provider: EmbeddingProvider,
        inputs: Sequence[EmbeddingInput],
        *,
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingBatch:
        expected_profile = profile or provider.profile
        ordered = tuple(inputs)
        vectors: list[EmbeddingVector] = []
        for offset in range(0, len(ordered), self.batch_size):
            submitted = ordered[offset : offset + self.batch_size]
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    returned = await provider.embed_documents(
                        submitted,
                        expected_profile,
                    )
            except TimeoutError:
                raise EmbeddingTimeoutError() from None
            validated = validate_embedding_batch(
                submitted,
                returned,
                expected_profile=expected_profile,
            )
            vectors.extend(validated.vectors)
        return EmbeddingBatch(profile=expected_profile, vectors=tuple(vectors))

    async def embed_query(
        self,
        provider: EmbeddingProvider,
        query: str,
        *,
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingVector:
        expected_profile = profile or provider.profile
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await provider.embed_query(query, expected_profile)
        except TimeoutError:
            raise EmbeddingTimeoutError() from None
        normalized = normalize_vector(
            result.values,
            expected_dimension=expected_profile.dimension,
        )
        return EmbeddingVector(item_key=result.item_key, values=normalized)


def _secret_value(value: object) -> str | None:
    if value is None:
        return None
    get_secret_value = getattr(value, "get_secret_value", None)
    resolved = get_secret_value() if callable(get_secret_value) else str(value)
    return resolved or None


def create_embedding_provider(settings: EmbeddingSettings) -> EmbeddingProvider:
    """Select one configured provider without constructing clients at import time."""

    provider_name = str(settings.rag_embedding_provider).strip().casefold()
    model_name = str(settings.rag_embedding_model).strip()
    dimension = int(settings.rag_embedding_dimension)
    validate_embedding_configuration(
        provider_name=provider_name,
        model_name=model_name,
        dimension=dimension,
    )
    if provider_name == "fake":
        return FakeEmbeddingProvider(
            profile=EmbeddingProfile(
                provider_name="fake",
                model_name=model_name,
                dimension=dimension,
                adapter_version=FAKE_ADAPTER_VERSION,
            )
        )
    if provider_name == "gemini":
        api_key = _secret_value(getattr(settings, "gemini_api_key", None))
        if api_key is None:
            raise EmbeddingConfigurationError(
                "Gemini embedding requires a private GEMINI_API_KEY."
            )
        from src.services.rag.gemini_provider import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(
            api_key=api_key,
            model_name=model_name,
            dimension=dimension,
            batch_size=int(settings.rag_embedding_batch_size),
            timeout_seconds=float(settings.rag_embedding_timeout_seconds),
        )
    raise EmbeddingConfigurationError("Unsupported embedding provider configuration.")


build_embedding_provider = create_embedding_provider
ensure_compatible_profile = assert_compatible_profile_transition
