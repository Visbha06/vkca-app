"""Deterministic normalization, formatting, identity, and hashing helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import NAMESPACE_URL, UUID, uuid5

from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

RAG_NAMESPACE = uuid5(NAMESPACE_URL, "https://vkca.local/rag/v1")
RAG_SOURCE_NAMESPACE = uuid5(RAG_NAMESPACE, "source")
RAG_DOCUMENT_NAMESPACE = uuid5(RAG_NAMESPACE, "document")
RAG_CHUNK_NAMESPACE = uuid5(RAG_NAMESPACE, "chunk")

_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\r\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(value: str) -> str:
    """Normalize Unicode and collapse all whitespace into single spaces."""

    normalized = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", value))
    return " ".join(normalized.split())


def normalize_semantic_text(value: str) -> str:
    """Normalize semantic text while preserving deterministic paragraph breaks."""

    normalized = unicodedata.normalize("NFC", unicodedata.normalize("NFKC", value))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [
        _HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in normalized.split("\n")
    ]
    collapsed = "\n".join(lines).strip()
    return _EXCESS_BLANK_LINES.sub("\n\n", collapsed)


def format_decimal(value: Decimal | int | float) -> str:
    """Format a finite number without exponent notation or insignificant zeros."""

    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("numeric canonical values must be finite") from exc
    if not decimal_value.is_finite():
        raise ValueError("numeric canonical values must be finite")
    if decimal_value == 0:
        return "0"
    rendered = format(decimal_value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def format_date(value: date) -> str:
    """Return a fixed ISO calendar date."""

    return value.isoformat()


def format_time(value: time) -> str:
    """Return a fixed second-precision time, retaining an explicit offset."""

    return value.isoformat(timespec="seconds")


def format_datetime(value: datetime) -> str:
    """Return a stable ISO timestamp, normalizing aware values to UTC."""

    if value.tzinfo is None:
        return value.isoformat(timespec="seconds")
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_mapping(value: Mapping[object, object]) -> str:
    normalized: dict[str, str] = {}
    for key, item in value.items():
        rendered = format_value(item)
        if rendered is not None:
            normalized[normalize_text(str(key))] = rendered
    return json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def format_value(value: object) -> str | None:
    """Format one approved scalar or collection deterministically."""

    if value is None:
        return None
    if isinstance(value, str):
        normalized = normalize_text(value)
        return normalized or None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return format_datetime(value)
    if isinstance(value, date):
        return format_date(value)
    if isinstance(value, time):
        return format_time(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return format_value(value.value)
    if isinstance(value, (Decimal, int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric canonical values must be finite")
        return format_decimal(value)
    if isinstance(value, Mapping):
        return _format_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return format_list(value)
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def format_list(values: Iterable[object]) -> str:
    """Format a collection using stable lexical ordering and de-duplication."""

    rendered = {
        item
        for value in values
        if (item := format_value(value)) is not None and item != ""
    }
    return ", ".join(sorted(rendered, key=lambda item: (item.casefold(), item)))


def canonicalize_fields(fields: Iterable[tuple[str, object]]) -> str:
    """Render an ordered allowlist of labelled fields and omit null/blank values."""

    lines: list[str] = []
    for raw_label, raw_value in fields:
        label = normalize_text(raw_label)
        if not label:
            raise ValueError("canonical field labels must not be blank")
        value = format_value(raw_value)
        if value is not None and value != "":
            lines.append(f"{label}: {value}")
    if not lines:
        raise ValueError("a canonical document requires at least one safe field")
    return normalize_semantic_text("\n".join(lines))


def _identity_component(value: str, *, field_name: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if "\x00" in normalized:
        raise ValueError(f"{field_name} contains an invalid null byte")
    return normalized


def derive_source_id(source_type: str, source_key: str) -> UUID:
    """Derive a stable namespaced ID for per-source operational state."""

    source = _identity_component(source_type, field_name="source_type").casefold()
    key = _identity_component(source_key, field_name="source_key")
    return uuid5(RAG_SOURCE_NAMESPACE, f"{source}\x1f{key}")


def derive_document_id(source_type: str, source_key: str) -> UUID:
    """Derive a provider-independent canonical document identity."""

    source = _identity_component(source_type, field_name="source_type").casefold()
    key = _identity_component(source_key, field_name="source_key")
    return uuid5(RAG_DOCUMENT_NAMESPACE, f"{source}\x1f{key}")


def derive_chunk_id(document_id: UUID, ordinal: int) -> UUID:
    """Derive a stable child identity from document ID and zero-based ordinal."""

    if ordinal < 0:
        raise ValueError("chunk ordinal must be non-negative")
    return uuid5(RAG_CHUNK_NAMESPACE, f"{document_id}:{ordinal}")


def canonical_content_hash(semantic_text: str) -> str:
    """Hash normalized semantic content with SHA-256."""

    normalized = normalize_semantic_text(semantic_text)
    if not normalized:
        raise ValueError("semantic content must not be blank")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def stable_component_hash(*components: object) -> str:
    """Hash deterministic fingerprints for source and relationship components."""

    def structured(value: object) -> object:
        if isinstance(value, Mapping):
            return {
                normalize_text(str(key)): structured(item)
                for key, item in sorted(
                    value.items(),
                    key=lambda pair: normalize_text(str(pair[0])),
                )
            }
        if isinstance(value, (set, frozenset)):
            normalized_items = [structured(item) for item in value]
            return sorted(
                normalized_items,
                key=lambda item: json.dumps(
                    item,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            return [structured(item) for item in value]
        return {
            "type": type(value).__name__,
            "value": format_value(value),
        }

    rendered = [structured(component) for component in components]
    payload = json.dumps(rendered, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_canonical_document(
    *,
    source_type: str,
    source_key: str,
    source_entity_id: UUID | None,
    source_version: str | None,
    dependency_fingerprint: str | None,
    semantic_text: str,
    provenance: Mapping[str, object],
    scope: RagScopeMetadata,
    builder_version: str,
    prepared_at: datetime,
) -> CanonicalRagDocument:
    """Construct the complete canonical contract from already allowlisted input."""

    normalized_source_type = _identity_component(
        source_type, field_name="source_type"
    ).casefold()
    normalized_source_key = _identity_component(source_key, field_name="source_key")
    normalized_text = normalize_semantic_text(semantic_text)
    if not normalized_text:
        raise ValueError("semantic_text must not be blank")
    normalized_builder_version = _identity_component(
        builder_version, field_name="builder_version"
    )
    return CanonicalRagDocument(
        document_id=derive_document_id(normalized_source_type, normalized_source_key),
        source_type=normalized_source_type,
        source_key=normalized_source_key,
        source_entity_id=source_entity_id,
        source_version=(
            normalize_text(source_version) if source_version is not None else None
        ),
        dependency_fingerprint=(
            normalize_text(dependency_fingerprint)
            if dependency_fingerprint is not None
            else None
        ),
        semantic_text=normalized_text,
        content_hash=canonical_content_hash(normalized_text),
        provenance=dict(provenance),
        scope=scope,
        builder_version=normalized_builder_version,
        prepared_at=prepared_at,
    )


# Conventional aliases used by source-specific builders.
content_hash = canonical_content_hash
document_id_for = derive_document_id
chunk_id_for = derive_chunk_id
