"""Unit coverage for the centralized embedding provider boundary."""

from __future__ import annotations

import asyncio
import math
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.config import Settings
from src.services.rag.contracts import (
    EmbeddingBatch,
    EmbeddingInput,
    EmbeddingProfile,
    EmbeddingPurpose,
    EmbeddingVector,
)
from src.services.rag.embedding import (
    EmbeddingBatcher,
    EmbeddingCompatibilityError,
    EmbeddingProviderError,
    EmbeddingResponseError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    FakeEmbeddingProvider,
    assert_compatible_profile_transition,
    create_embedding_provider,
    validate_embedding_batch,
)
from src.services.rag.gemini_provider import GeminiEmbeddingProvider


def _inputs(count: int = 3) -> tuple[EmbeddingInput, ...]:
    return tuple(
        EmbeddingInput(
            item_key=f"chunk-{index}",
            text=f"safe document {index}",
            purpose=EmbeddingPurpose.DOCUMENT,
        )
        for index in range(count)
    )


@pytest.mark.asyncio
async def test_fake_provider_is_deterministic_ordered_finite_and_normalized() -> None:
    profile = EmbeddingProfile("fake", "gemini-embedding-001", 1536, "fake-v1")
    provider = FakeEmbeddingProvider(profile=profile)

    first = await provider.embed_documents(_inputs())
    second = await provider.embed_documents(_inputs())

    assert first == second
    assert [item.item_key for item in first.vectors] == [
        "chunk-0",
        "chunk-1",
        "chunk-2",
    ]
    assert all(len(item.values) == 1536 for item in first.vectors)
    assert all(
        math.isclose(math.sqrt(sum(v * v for v in item.values)), 1.0)
        for item in first.vectors
    )
    assert provider.document_call_count == 2

    same_text = await provider.embed_documents(
        (
            EmbeddingInput("first-key", "same text", EmbeddingPurpose.DOCUMENT),
            EmbeddingInput("second-key", "same text", EmbeddingPurpose.DOCUMENT),
        )
    )
    assert same_text.vectors[0].values == same_text.vectors[1].values


@pytest.mark.parametrize(
    ("vectors", "message"),
    [
        ((), "count"),
        ((EmbeddingVector("chunk-0", (0.0,) * 10),), "dimension"),
        ((EmbeddingVector("wrong-key", (0.0,) * 1536),), "order"),
        ((EmbeddingVector("chunk-0", (float("nan"),) + (0.0,) * 1535),), "finite"),
    ],
)
def test_validation_rejects_malformed_provider_batches(
    vectors: tuple[EmbeddingVector, ...], message: str
) -> None:
    profile = EmbeddingProfile("fake", "gemini-embedding-001", 1536, "fake-v1")
    batch = EmbeddingBatch(profile=profile, vectors=vectors)

    with pytest.raises(EmbeddingResponseError, match=message):
        validate_embedding_batch(_inputs(1), batch, expected_profile=profile)


class SlowProvider:
    profile = EmbeddingProfile("slow", "replacement-model", 1536, "adapter-v1")

    async def embed_documents(
        self,
        inputs: tuple[EmbeddingInput, ...],
        profile: EmbeddingProfile | None = None,
    ) -> EmbeddingBatch:
        del inputs, profile
        await asyncio.sleep(0.05)
        raise AssertionError("timeout should cancel the provider call")

    async def embed_query(
        self, query: str, profile: EmbeddingProfile | None = None
    ) -> EmbeddingVector:
        del query, profile
        raise NotImplementedError


@pytest.mark.asyncio
async def test_batcher_enforces_timeout_with_sanitized_error() -> None:
    batcher = EmbeddingBatcher(batch_size=2, timeout_seconds=0.001)

    with pytest.raises(EmbeddingTimeoutError) as raised:
        await batcher.embed_documents(SlowProvider(), _inputs())

    assert "safe document" not in str(raised.value)
    assert "credential" not in str(raised.value).casefold()


@pytest.mark.asyncio
async def test_batcher_splits_bounds_and_never_returns_a_partial_failure() -> None:
    profile = EmbeddingProfile("fake", "gemini-embedding-001", 1536, "fake-v1")
    provider = FakeEmbeddingProvider(profile=profile)
    batcher = EmbeddingBatcher(batch_size=2, timeout_seconds=1)

    completed = await batcher.embed_documents(provider, _inputs(5))

    assert len(completed.vectors) == 5
    assert provider.document_batch_keys == [
        ("chunk-0", "chunk-1"),
        ("chunk-2", "chunk-3"),
        ("chunk-4",),
    ]

    class FailsSecondBatch(FakeEmbeddingProvider):
        async def embed_documents(self, inputs, profile=None):
            if self.document_call_count == 1:
                raise EmbeddingUnavailableError()
            return await super().embed_documents(inputs, profile)

    failing = FailsSecondBatch(profile=profile)
    with pytest.raises(EmbeddingUnavailableError):
        await batcher.embed_documents(failing, _inputs(5))
    assert failing.document_batch_keys == [("chunk-0", "chunk-1")]


def test_provider_model_transitions_are_explicit() -> None:
    current = EmbeddingProfile("gemini", "gemini-embedding-001", 1536, "v1")

    assert_compatible_profile_transition(current, current)
    with pytest.raises(EmbeddingCompatibilityError, match="re-index"):
        assert_compatible_profile_transition(
            current,
            EmbeddingProfile("replacement", "new-model", 1536, "v1"),
        )
    with pytest.raises(EmbeddingCompatibilityError, match="migration"):
        assert_compatible_profile_transition(
            current,
            EmbeddingProfile("gemini", "gemini-embedding-001", 768, "v1"),
        )


def test_provider_errors_never_render_raw_secrets() -> None:
    error = EmbeddingProviderError(
        "provider_unavailable",
        safe_message="Embedding provider is unavailable.",
        internal_error=RuntimeError("api_key=super-secret request=private body"),
    )

    assert str(error) == "Embedding provider is unavailable."
    assert "super-secret" not in repr(error)
    assert "private body" not in repr(error)


@pytest.mark.asyncio
async def test_gemini_adapter_uses_document_task_and_normalizes_reduced_vectors() -> (
    None
):
    response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[3.0, 4.0] + [0.0] * 1534)]
    )
    calls: list[dict[str, object]] = []

    class Models:
        async def embed_content(self, **kwargs):
            calls.append(kwargs)
            return response

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    provider = GeminiEmbeddingProvider(
        client=client,
        dimension=1536,
        batch_size=4,
        timeout_seconds=1,
    )

    batch = await provider.embed_documents(_inputs(1))

    assert calls[0]["model"] == "gemini-embedding-001"
    assert calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert calls[0]["config"].output_dimensionality == 1536
    assert batch.profile.provider_name == "gemini"
    assert math.isclose(batch.vectors[0].values[0], 0.6)
    assert math.isclose(batch.vectors[0].values[1], 0.8)


@pytest.mark.asyncio
async def test_gemini_adapter_uses_the_distinct_query_task_type() -> None:
    response = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[1.0] + [0.0] * 1535)]
    )
    calls: list[dict[str, object]] = []

    class Models:
        async def embed_content(self, **kwargs):
            calls.append(kwargs)
            return response

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    provider = GeminiEmbeddingProvider(
        client=client,
        dimension=1536,
        batch_size=4,
        timeout_seconds=1,
    )

    vector = await provider.embed_query("safe bounded query")

    assert calls[0]["config"].task_type == "RETRIEVAL_QUERY"
    assert vector.item_key == "query"
    assert len(vector.values) == 1536


@pytest.mark.asyncio
async def test_gemini_adapter_rejects_extra_vectors_without_truncating() -> None:
    response = SimpleNamespace(
        embeddings=[
            SimpleNamespace(values=[1.0] + [0.0] * 1535),
            SimpleNamespace(values=[0.0, 1.0] + [0.0] * 1534),
        ]
    )

    class Models:
        async def embed_content(self, **kwargs):
            del kwargs
            return response

    provider = GeminiEmbeddingProvider(
        client=SimpleNamespace(aio=SimpleNamespace(models=Models())),
        dimension=1536,
        batch_size=4,
        timeout_seconds=1,
    )

    with pytest.raises(EmbeddingResponseError, match="count"):
        await provider.embed_documents(_inputs(1))


def test_provider_selection_uses_fake_without_constructing_gemini_client() -> None:
    settings = SimpleNamespace(
        rag_embedding_provider="fake",
        rag_embedding_model="gemini-embedding-001",
        rag_embedding_dimension=1536,
        rag_embedding_batch_size=4,
        rag_embedding_timeout_seconds=1.0,
        gemini_api_key=None,
    )

    provider = create_embedding_provider(settings)

    assert isinstance(provider, FakeEmbeddingProvider)
    assert provider.profile.model_name == "gemini-embedding-001"


def test_settings_reject_profiles_incompatible_with_migration_014() -> None:
    required = {
        "database_url": "postgresql+asyncpg://postgres:test@localhost/academy_test",
        "jwt_secret": "unit-test-secret",
    }

    with pytest.raises(ValidationError, match="1536"):
        Settings(**required, rag_embedding_dimension=768)
    with pytest.raises(ValidationError, match="gemini-embedding-001"):
        Settings(
            **required,
            rag_embedding_provider="gemini",
            rag_embedding_model="replacement-model",
        )

    settings = Settings(**required, gemini_api_key="private-test-key")
    assert "private-test-key" not in repr(settings)
    assert settings.rag_chunking_version == "rag-chunk-v1"
