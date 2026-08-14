"""Provider-neutral typed contracts for the RAG foundation.

The classes in this module deliberately contain no SQLAlchemy session, vector
column, provider SDK client, or request-time authorization implementation.
They are the hand-off boundary between source loading, deterministic document
preparation, chunking, embedding, persistence, and operational reporting.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_RAG_MUTATION_TARGETS = 128


class RagRunMode(StrEnum):
    """Supported operator indexing modes."""

    FULL = "full"
    INCREMENTAL = "incremental"
    TARGETED = "targeted"
    REPAIR = "repair"


class RagRunStatus(StrEnum):
    """Aggregate lifecycle of one technical indexing run."""

    INDEXING = "indexing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class RagSourceStatus(StrEnum):
    """Lifecycle of one registered authoritative source identity."""

    CURRENT = "current"
    PENDING = "pending"
    STALE = "stale"
    INDEXING = "indexing"
    FAILED = "failed"
    INELIGIBLE = "ineligible"
    DELETED = "deleted"


class EmbeddingPurpose(StrEnum):
    """Semantic purpose supplied to an embedding provider."""

    DOCUMENT = "document"
    QUERY = "query"


class RagMutationSource(StrEnum):
    """Stable domain identities that may affect a registered RAG source."""

    PLAYER = "player"
    TEAM = "team"
    MATCH = "match"
    MATCH_BATTING_PERFORMANCE = "match_batting_performance"
    MATCH_BOWLING_PERFORMANCE = "match_bowling_performance"
    MATCH_FIELDING_PERFORMANCE = "match_fielding_performance"
    PLAYER_BATTING_STATS = "player_batting_stats"
    PLAYER_BOWLING_STATS = "player_bowling_stats"
    CALENDAR_OCCURRENCE = "calendar_occurrence"


class RagMutationOperation(StrEnum):
    """Why current and/or previous stable identities became dirty."""

    UPSERT = "upsert"
    DELETE = "delete"
    RELATIONSHIP = "relationship"


class RagMutationRef(BaseModel):
    """One bounded domain identity; it never contains an authoritative snapshot."""

    source: RagMutationSource
    source_key: str = Field(min_length=1, max_length=160)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("source_key")
    @classmethod
    def normalize_source_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError("RAG mutation source_key must be a safe non-blank value")
        return normalized


class RagTargetRef(BaseModel):
    """One registered source identity carried by reconciliation work."""

    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    source_key: str = Field(min_length=1, max_length=160)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("source_key")
    @classmethod
    def normalize_source_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(ord(character) < 32 for character in normalized):
            raise ValueError("RAG target source_key must be a safe non-blank value")
        return normalized


class RagReconciliationPayloadV1(BaseModel):
    """Bounded durable payload that instructs later current-state reconciliation."""

    mode: Literal["targets"] = "targets"
    reason: Literal["mutation"] = "mutation"
    targets: tuple[RagTargetRef, ...] = Field(
        min_length=1,
        max_length=MAX_RAG_MUTATION_TARGETS,
    )

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def reject_duplicate_targets(self) -> Self:
        identities = [
            (target.source_type, target.source_key) for target in self.targets
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("RAG reconciliation targets must be unique")
        return self


class RagMutationImpact(BaseModel):
    """Bounded current/previous identities staged by an academy mutation."""

    operation: RagMutationOperation
    current_refs: tuple[RagMutationRef, ...] = Field(
        default=(),
        max_length=MAX_RAG_MUTATION_TARGETS,
    )
    previous_refs: tuple[RagMutationRef, ...] = Field(
        default=(),
        max_length=MAX_RAG_MUTATION_TARGETS,
    )
    coalescing_ref: RagMutationRef | None = None
    semantic_change: bool = True
    correlation_id: UUID | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_bounded_identity_set(self) -> Self:
        identities = {
            (reference.source, reference.source_key)
            for reference in (*self.current_refs, *self.previous_refs)
        }
        if self.semantic_change and not identities:
            raise ValueError("semantic RAG mutation impacts require a stable reference")
        if len(identities) > MAX_RAG_MUTATION_TARGETS:
            raise ValueError(
                f"RAG mutation impacts support at most {MAX_RAG_MUTATION_TARGETS} "
                "stable references"
            )
        if self.coalescing_ref is not None and self.semantic_change:
            coalescing_identity = (
                self.coalescing_ref.source,
                self.coalescing_ref.source_key,
            )
            if coalescing_identity not in identities:
                raise ValueError("coalescing_ref must be included in the impact refs")
        return self


@dataclass(frozen=True, slots=True)
class RagScopeMetadata:
    """Intrinsic source facets; never a snapshot of current User permissions."""

    source_type: str
    player_ids: tuple[UUID, ...] = ()
    team_ids: tuple[UUID, ...] = ()
    age_groups: tuple[str, ...] = ()
    is_all_academy: bool = False
    relationship_labels: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source_type = self.source_type.strip()
        if not source_type:
            raise ValueError("scope source_type must not be blank")
        object.__setattr__(self, "source_type", source_type)
        object.__setattr__(
            self,
            "player_ids",
            tuple(sorted(set(self.player_ids), key=str)),
        )
        object.__setattr__(
            self,
            "team_ids",
            tuple(sorted(set(self.team_ids), key=str)),
        )
        object.__setattr__(
            self,
            "age_groups",
            tuple(sorted({item.strip() for item in self.age_groups if item.strip()})),
        )

        labels: dict[str, tuple[str, ...]] = {}
        forbidden_fragments = ("user", "role", "permission", "authorized", "acl")
        for raw_key, raw_values in self.relationship_labels.items():
            key = raw_key.strip()
            if not key:
                raise ValueError("scope relationship labels require non-blank keys")
            if any(fragment in key.casefold() for fragment in forbidden_fragments):
                raise ValueError(
                    "scope metadata must not contain User authorization ACLs"
                )
            labels[key] = tuple(
                sorted({value.strip() for value in raw_values if value.strip()})
            )
        object.__setattr__(self, "relationship_labels", labels)

    def as_json(self) -> dict[str, object]:
        """Return the safe JSON representation used by persistence adapters."""

        return {
            "source_type": self.source_type,
            "player_ids": [str(item) for item in self.player_ids],
            "team_ids": [str(item) for item in self.team_ids],
            "age_groups": list(self.age_groups),
            "is_all_academy": self.is_all_academy,
            "relationship_labels": {
                key: list(values)
                for key, values in sorted(self.relationship_labels.items())
            },
        }


@dataclass(frozen=True, slots=True)
class CanonicalRagDocument:
    """One deterministic, provider- and persistence-neutral source document."""

    document_id: UUID
    source_type: str
    source_key: str
    source_entity_id: UUID | None
    source_version: str | None
    dependency_fingerprint: str | None
    semantic_text: str
    content_hash: str
    provenance: Mapping[str, object]
    scope: RagScopeMetadata
    builder_version: str
    prepared_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "source_type",
            "source_key",
            "semantic_text",
            "content_hash",
            "builder_version",
        ):
            value = getattr(self, field_name)
            if not value or not str(value).strip():
                raise ValueError(f"{field_name} must not be blank")
        if self.scope.source_type != self.source_type:
            raise ValueError("document and scope source_type values must match")

    @property
    def id(self) -> UUID:
        """Compatibility alias for persistence-oriented callers."""

        return self.document_id

    @property
    def provenance_metadata(self) -> Mapping[str, object]:
        """Name used by the persisted document model."""

        return self.provenance


@dataclass(frozen=True, slots=True)
class RagChunkCandidate:
    """One deterministic bounded document child before embedding."""

    chunk_id: UUID
    document_id: UUID
    source_type: str
    source_key: str
    source_entity_id: UUID | None
    ordinal: int
    semantic_text: str
    content_hash: str
    provenance: Mapping[str, object]
    scope: RagScopeMetadata
    builder_version: str
    chunking_version: str

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("chunk ordinal must be non-negative")
        if not self.semantic_text.strip():
            raise ValueError("chunk semantic_text must not be blank")
        if self.scope.source_type != self.source_type:
            raise ValueError("chunk and scope source_type values must match")

    @property
    def id(self) -> UUID:
        return self.chunk_id

    @property
    def provenance_metadata(self) -> Mapping[str, object]:
        return self.provenance


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    """Exact provider/model/vector profile for compatibility decisions."""

    provider_name: str
    model_name: str
    dimension: int
    adapter_version: str

    def __post_init__(self) -> None:
        for field_name in ("provider_name", "model_name", "adapter_version"):
            normalized = getattr(self, field_name).strip()
            if not normalized:
                raise ValueError(f"embedding {field_name} must not be blank")
            object.__setattr__(self, field_name, normalized)
        if self.dimension <= 0:
            raise ValueError("embedding dimension must be positive")

    @property
    def compatibility_key(self) -> tuple[str, str, int, str]:
        """Fields that must match before existing vectors can be reused."""

        return (
            self.provider_name,
            self.model_name,
            self.dimension,
            self.adapter_version,
        )


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    """A bounded local item sent through the centralized provider boundary."""

    item_key: str
    text: str
    purpose: EmbeddingPurpose

    def __post_init__(self) -> None:
        if not self.item_key.strip():
            raise ValueError("embedding item_key must not be blank")
        if not self.text.strip():
            raise ValueError("embedding text must not be blank")


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """One provider vector mapped to its stable local item key."""

    item_key: str
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    """An ordered all-or-nothing provider response."""

    profile: EmbeddingProfile
    vectors: tuple[EmbeddingVector, ...]


@dataclass(frozen=True, slots=True)
class SourceDependency:
    """A declared relationship/projection input used for invalidation."""

    name: str
    required: bool = True

    def __post_init__(self) -> None:
        normalized = self.name.strip()
        if not normalized:
            raise ValueError("source dependency name must not be blank")
        object.__setattr__(self, "name", normalized)


@dataclass(frozen=True, slots=True)
class SourceLoadBatch[RecordT]:
    """One bounded, cursor-addressable page of authoritative source records."""

    items: tuple[RecordT, ...]
    next_cursor: str | None = None
    source_fingerprint: str | None = None


class RagSourceLoader[RecordT](Protocol):
    """Bounded source-loader protocol implemented without per-record queries."""

    async def load_batch(
        self,
        session: object,
        *,
        cursor: str | None,
        limit: int,
    ) -> SourceLoadBatch[RecordT]: ...


class RagDeletionPolicy(Protocol):
    """Identify formerly known keys absent from the authoritative batch set."""

    def reconcile_deleted(
        self,
        *,
        seen_keys: set[str],
        previous_keys: set[str],
    ) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class RagSourceDefinition[RecordT]:
    """Complete explicit opt-in contract for one RAG source type."""

    source_type: str
    builder_version: str
    loader: RagSourceLoader[RecordT]
    build: Callable[[RecordT], CanonicalRagDocument]
    source_key: Callable[[RecordT], str]
    source_version: Callable[[RecordT], str | None]
    dependency_fingerprint: Callable[[RecordT], str | None]
    scope_metadata: Callable[[RecordT], RagScopeMetadata]
    eligible: Callable[[RecordT], bool]
    dependencies: tuple[SourceDependency, ...]
    deletion_policy: RagDeletionPolicy


@dataclass(slots=True)
class RagRunCounters:
    """Bounded aggregate telemetry with no semantic bodies or vectors."""

    source_records_inspected: int = 0
    documents_prepared: int = 0
    chunks_generated: int = 0
    embeddings_created: int = 0
    unchanged_skipped: int = 0
    deleted_or_ineligible: int = 0
    failed_sources: int = 0

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.as_dict().values()):
            raise ValueError("RAG run counters must be non-negative")

    def as_dict(self) -> dict[str, int]:
        return {
            "source_records_inspected": self.source_records_inspected,
            "documents_prepared": self.documents_prepared,
            "chunks_generated": self.chunks_generated,
            "embeddings_created": self.embeddings_created,
            "unchanged_skipped": self.unchanged_skipped,
            "deleted_or_ineligible": self.deleted_or_ineligible,
            "failed_sources": self.failed_sources,
        }

    def add(self, **increments: int) -> None:
        """Increment known counters while preserving their non-negative invariant."""

        for name, increment in increments.items():
            if name not in self.as_dict():
                raise ValueError(f"unknown RAG counter: {name}")
            if increment < 0:
                raise ValueError("RAG counter increments must be non-negative")
            setattr(self, name, getattr(self, name) + increment)


@dataclass(frozen=True, slots=True)
class RagIndexRunReport:
    """Safe completion result for a full, targeted, incremental, or repair run."""

    run_id: UUID
    mode: RagRunMode
    status: RagRunStatus
    source_type: str | None
    started_at: datetime
    finished_at: datetime | None
    counters: RagRunCounters
    failure_code: str | None = None
    failure_message: str | None = None


@dataclass(frozen=True, slots=True)
class RagSourceStatusSummary:
    """Safe per-source operational state; intentionally excludes corpus data."""

    source_type: str
    source_key: str
    status: RagSourceStatus
    observed_source_version: str | None
    builder_version: str
    provider_name: str
    model_name: str
    embedding_dimension: int
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    recoverable: bool


@dataclass(frozen=True, slots=True)
class RagOperationalStatusReport:
    """Bounded run/source status suitable for CLI output and operator support."""

    runs: tuple[RagIndexRunReport, ...]
    sources: tuple[RagSourceStatusSummary, ...]
    source_filter: str | None
    status_counts: Mapping[str, int]
    recoverable_source_count: int


# Concise aliases for callers that do not need the RAG prefix in local names.
CanonicalDocument = CanonicalRagDocument
ChunkCandidate = RagChunkCandidate
SourceDefinition = RagSourceDefinition


def as_embedding_inputs(
    chunks: Sequence[RagChunkCandidate],
) -> tuple[EmbeddingInput, ...]:
    """Map chunk candidates to ordered provider-neutral document inputs."""

    return tuple(
        EmbeddingInput(
            item_key=str(chunk.chunk_id),
            text=chunk.semantic_text,
            purpose=EmbeddingPurpose.DOCUMENT,
        )
        for chunk in chunks
    )
