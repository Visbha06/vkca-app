"""Typed external schemas reserved for the protected RAG boundary.

The route and service behavior are implemented in later phases. Keeping these
schemas in a dedicated module prevents provider and persistence types leaking
into the API surface.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RagRetrievalRequest(BaseModel):
    """Bounded query input; authorization scope is never client supplied."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=1_000)
    limit: int = Field(default=5, ge=0, le=20)


class RagRetrievalResult(BaseModel):
    """Safe result metadata without vectors or provider response details."""

    source_type: str
    source_key: str
    chunk_id: UUID
    text: str
    score: float


class RagRetrievalResponse(BaseModel):
    """Bounded retrieval response envelope."""

    results: list[RagRetrievalResult] = Field(default_factory=list)
