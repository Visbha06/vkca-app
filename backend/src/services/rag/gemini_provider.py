"""Google GenAI adapter for Gemini ``gemini-embedding-001`` embeddings."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol, cast

from google import genai
from google.genai import errors, types

from src.services.rag.contracts import (
    EmbeddingBatch,
    EmbeddingInput,
    EmbeddingProfile,
    EmbeddingPurpose,
    EmbeddingVector,
)
from src.services.rag.embedding import (
    GEMINI_EMBEDDING_MODEL,
    RAG_VECTOR_DIMENSION,
    EmbeddingAuthenticationError,
    EmbeddingCompatibilityError,
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    EmbeddingResponseError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    normalize_vector,
    validate_embedding_batch,
)

GEMINI_ADAPTER_VERSION = "google-genai-1.45-v1"
DOCUMENT_TASK_TYPE = "RETRIEVAL_DOCUMENT"
QUERY_TASK_TYPE = "RETRIEVAL_QUERY"


class _AsyncGeminiModels(Protocol):
    async def embed_content(
        self,
        *,
        model: str,
        contents: list[str],
        config: types.EmbedContentConfig,
    ) -> object: ...


class _AsyncGeminiClient(Protocol):
    models: _AsyncGeminiModels


class _GeminiClient(Protocol):
    aio: _AsyncGeminiClient


class GeminiEmbeddingProvider:
    """Bounded async Gemini adapter with sanitized all-or-nothing failures."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: object | None = None,
        model_name: str = GEMINI_EMBEDDING_MODEL,
        dimension: int = RAG_VECTOR_DIMENSION,
        batch_size: int = 32,
        timeout_seconds: float = 30.0,
    ) -> None:
        if model_name != GEMINI_EMBEDDING_MODEL:
            raise EmbeddingConfigurationError(
                "The Gemini adapter requires gemini-embedding-001."
            )
        if dimension != RAG_VECTOR_DIMENSION:
            raise EmbeddingConfigurationError(
                "The Gemini adapter must match the vector(1536) migration."
            )
        if batch_size <= 0:
            raise EmbeddingConfigurationError(
                "Gemini embedding batch size must be positive."
            )
        if timeout_seconds <= 0:
            raise EmbeddingConfigurationError(
                "Gemini embedding timeout must be positive."
            )
        if client is None and not api_key:
            raise EmbeddingConfigurationError(
                "Gemini embedding requires a private API key."
            )

        selected_client = (
            client if client is not None else genai.Client(api_key=api_key)
        )
        self._client = cast(_GeminiClient, selected_client)
        self._profile = EmbeddingProfile(
            provider_name="gemini",
            model_name=model_name,
            dimension=dimension,
            adapter_version=GEMINI_ADAPTER_VERSION,
        )
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds

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
                "Requested embedding profile is incompatible with Gemini; an "
                "explicit re-index is required."
            )

    async def _request(
        self,
        inputs: Sequence[EmbeddingInput],
        *,
        task_type: str,
    ) -> EmbeddingBatch:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                aio = self._client.aio
                response = await aio.models.embed_content(
                    model=self.profile.model_name,
                    contents=[item.text for item in inputs],
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.profile.dimension,
                    ),
                )
        except TimeoutError:
            raise EmbeddingTimeoutError() from None
        except errors.ClientError as exc:
            if getattr(exc, "code", None) in {401, 403}:
                raise EmbeddingAuthenticationError() from None
            raise EmbeddingResponseError(
                "Embedding provider rejected the bounded request."
            ) from None
        except (errors.ServerError, errors.APIError):
            raise EmbeddingUnavailableError() from None
        except EmbeddingProviderError:
            raise
        except Exception:
            raise EmbeddingUnavailableError() from None

        raw_embeddings = getattr(response, "embeddings", None)
        if raw_embeddings is None:
            raise EmbeddingResponseError(
                "Embedding response did not contain an ordered vector batch."
            )
        response_embeddings = tuple(raw_embeddings)
        if len(response_embeddings) != len(inputs):
            raise EmbeddingResponseError(
                "Embedding response count does not match the submitted batch."
            )
        vectors: list[EmbeddingVector] = []
        for item, returned in zip(inputs, response_embeddings, strict=True):
            values = getattr(returned, "values", None)
            if values is None:
                raise EmbeddingResponseError(
                    "Embedding response contained a malformed vector."
                )
            vectors.append(
                EmbeddingVector(
                    item_key=item.item_key,
                    values=normalize_vector(
                        values,
                        expected_dimension=self.profile.dimension,
                    ),
                )
            )
        batch = EmbeddingBatch(profile=self.profile, vectors=tuple(vectors))
        return validate_embedding_batch(
            inputs,
            batch,
            expected_profile=self.profile,
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
                "Gemini document batches require document-purpose inputs."
            )
        vectors: list[EmbeddingVector] = []
        for offset in range(0, len(ordered), self.batch_size):
            submitted = ordered[offset : offset + self.batch_size]
            returned = await self._request(
                submitted,
                task_type=DOCUMENT_TASK_TYPE,
            )
            vectors.extend(returned.vectors)
        batch = EmbeddingBatch(profile=self.profile, vectors=tuple(vectors))
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
        submitted = (
            EmbeddingInput(
                item_key="query",
                text=query,
                purpose=EmbeddingPurpose.QUERY,
            ),
        )
        batch = await self._request(submitted, task_type=QUERY_TASK_TYPE)
        return batch.vectors[0]
