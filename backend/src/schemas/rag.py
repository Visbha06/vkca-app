"""Strict, vector-free schemas for the protected RAG retrieval boundary."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_RAG_QUERY_CHARACTERS = 1_000
MAX_RAG_RESULTS = 20


class RagRetrievalRequest(BaseModel):
    """Bounded query input; authorization scope is never client supplied."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=MAX_RAG_QUERY_CHARACTERS)
    limit: int = Field(default=5, ge=1, le=MAX_RAG_RESULTS)

    @field_validator("query")
    @classmethod
    def validate_nonblank_query(cls, value: str) -> str:
        """Reject whitespace-only text after request normalization."""

        if not value:
            raise ValueError("query must not be blank")
        return value


class RagRetrievalProvenance(BaseModel):
    """Allowlisted source identity required for future citations."""

    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1, max_length=80)
    source_entity_id: UUID | None = None


class RagRetrievalResult(BaseModel):
    """Safe result metadata without vectors or provider response details."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    chunk_id: UUID
    document_id: UUID
    source_type: str = Field(min_length=1, max_length=80)
    source_key: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=16_000)
    score: float
    provenance: RagRetrievalProvenance


class RagRetrievalResponse(BaseModel):
    """Bounded retrieval response envelope."""

    model_config = ConfigDict(extra="forbid")

    results: list[RagRetrievalResult] = Field(
        default_factory=list,
        max_length=MAX_RAG_RESULTS,
    )
    returned_count: int = Field(ge=0, le=MAX_RAG_RESULTS)
    limit: int = Field(ge=1, le=MAX_RAG_RESULTS)

    @model_validator(mode="after")
    def validate_counts(self) -> RagRetrievalResponse:
        """Keep the envelope consistent with the bounded result list."""

        if self.returned_count != len(self.results):
            raise ValueError("returned_count must match results")
        if self.returned_count > self.limit:
            raise ValueError("returned_count cannot exceed limit")
        return self


class RagRetrievalErrorResponse(BaseModel):
    """Sanitized API error envelope."""

    detail: str = Field(min_length=1, max_length=500)
