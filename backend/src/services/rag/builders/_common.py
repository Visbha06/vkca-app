"""Small shared helpers for deterministic source document adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.services.rag.canonical import canonicalize_fields, create_canonical_document
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def model_version(model: object) -> str | None:
    """Return an optimistic version without exposing ORM internals to providers."""

    value = getattr(model, "version_number", None)
    return str(value) if value is not None else None


def prepared_at(model: object) -> datetime:
    """Prefer persisted update time and retain deterministic in-memory test output."""

    value = getattr(model, "updated_at", None) or getattr(model, "created_at", None)
    return value if isinstance(value, datetime) else _EPOCH


def build_document(
    *,
    source_type: str,
    source_key: str,
    source_entity_id: UUID | None,
    source_version: str | None,
    dependency_fingerprint: str | None,
    fields: list[tuple[str, object]],
    provenance: dict[str, object],
    scope: RagScopeMetadata,
    builder_version: str,
    model: object,
) -> CanonicalRagDocument:
    """Build one allowlisted canonical document without ORM/provider side effects."""

    safe_provenance: dict[str, object] = {
        "source_type": source_type,
        "source_entity_id": str(source_entity_id) if source_entity_id else None,
    }
    safe_provenance.update(provenance)
    return create_canonical_document(
        source_type=source_type,
        source_key=source_key,
        source_entity_id=source_entity_id,
        source_version=source_version,
        dependency_fingerprint=dependency_fingerprint,
        semantic_text=canonicalize_fields(fields),
        provenance=safe_provenance,
        scope=scope,
        builder_version=builder_version,
        prepared_at=prepared_at(model),
    )


def enum_value(value: Any) -> Any:
    """Return an enum's stable value while accepting plain model strings."""

    return getattr(value, "value", value)
