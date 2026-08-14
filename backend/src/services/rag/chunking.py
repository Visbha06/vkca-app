"""Versioned, bounded, deterministic semantic chunking policy."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.services.rag.canonical import (
    canonical_content_hash,
    derive_chunk_id,
    normalize_semantic_text,
    normalize_text,
)
from src.services.rag.contracts import CanonicalRagDocument, RagChunkCandidate

DEFAULT_CHUNKING_VERSION = "rag-chunk-v1"
_CONTEXT_PREFIX = "Context: "
_PARAGRAPH_SEPARATOR = "\n\n"
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_MIN_CONTINUATION_PAYLOAD = 32


@dataclass(frozen=True, slots=True)
class ChunkingPolicy:
    """Fixed bounds and version metadata for deterministic chunk output."""

    version: str = DEFAULT_CHUNKING_VERSION
    max_characters: int = 4_000
    context_characters: int = 240

    def __post_init__(self) -> None:
        normalized_version = self.version.strip()
        if not normalized_version:
            raise ValueError("chunking version must not be blank")
        object.__setattr__(self, "version", normalized_version)
        if self.max_characters < 64:
            raise ValueError("chunk maximum must be at least 64 characters")
        if self.context_characters < 0:
            raise ValueError("chunk context must be non-negative")
        overhead = len(_CONTEXT_PREFIX) + len(_PARAGRAPH_SEPARATOR)
        if (
            self.context_characters + overhead + _MIN_CONTINUATION_PAYLOAD
            > self.max_characters
        ):
            raise ValueError("chunk context must leave room for continuation content")


def _truncate_at_word(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    candidate = value[:maximum].rstrip()
    if " " in candidate:
        candidate = candidate.rsplit(" ", 1)[0]
    return candidate.rstrip(" ,;:-")


def _continuation_context(text: str, maximum: int) -> str:
    if maximum == 0:
        return ""
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    return _truncate_at_word(normalize_text(first_line), maximum)


def _split_words(value: str, maximum: int) -> list[str]:
    """Split an overlong sentence without producing an unbounded fragment."""

    pieces: list[str] = []
    current = ""
    for word in value.split():
        while len(word) > maximum:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:maximum])
            word = word[maximum:]
        proposed = word if not current else f"{current} {word}"
        if len(proposed) <= maximum:
            current = proposed
        else:
            if current:
                pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _semantic_units(text: str, maximum: int) -> list[str]:
    """Prefer paragraphs, then sentence boundaries, then bounded word splits."""

    units: list[str] = []
    for paragraph in text.split(_PARAGRAPH_SEPARATOR):
        normalized_paragraph = normalize_semantic_text(paragraph)
        if not normalized_paragraph:
            continue
        if len(normalized_paragraph) <= maximum:
            units.append(normalized_paragraph)
            continue
        for sentence in _SENTENCE_BOUNDARY.split(normalized_paragraph):
            normalized_sentence = normalize_text(sentence)
            if not normalized_sentence:
                continue
            if len(normalized_sentence) <= maximum:
                units.append(normalized_sentence)
            else:
                units.extend(_split_words(normalized_sentence, maximum))
    return units


def _pack_units(units: list[str], maximum: int) -> list[str]:
    payloads: list[str] = []
    current = ""
    for unit in units:
        proposed = unit if not current else f"{current}{_PARAGRAPH_SEPARATOR}{unit}"
        if len(proposed) <= maximum:
            current = proposed
            continue
        if current:
            payloads.append(current)
        current = unit
    if current:
        payloads.append(current)
    return payloads


def chunk_document(
    document: CanonicalRagDocument,
    policy: ChunkingPolicy | None = None,
) -> tuple[RagChunkCandidate, ...]:
    """Split one canonical document into stable, bounded chunk candidates."""

    selected_policy = policy or ChunkingPolicy()
    text = normalize_semantic_text(document.semantic_text)
    if not text:
        raise ValueError("cannot chunk a blank canonical document")

    if len(text) <= selected_policy.max_characters:
        payloads = [text]
        context = ""
    else:
        context = _continuation_context(
            text,
            selected_policy.context_characters,
        )
        prefix_length = (
            len(_CONTEXT_PREFIX) + len(context) + len(_PARAGRAPH_SEPARATOR)
            if context
            else 0
        )
        payload_limit = selected_policy.max_characters - prefix_length
        payloads = _pack_units(_semantic_units(text, payload_limit), payload_limit)

    chunks: list[RagChunkCandidate] = []
    for ordinal, payload in enumerate(payloads):
        chunk_text = payload
        if ordinal > 0 and context:
            chunk_text = f"{_CONTEXT_PREFIX}{context}{_PARAGRAPH_SEPARATOR}{payload}"
        chunk_text = normalize_semantic_text(chunk_text)
        if len(chunk_text) > selected_policy.max_characters:
            raise ValueError("chunking policy produced an over-bound chunk")
        provenance = dict(document.provenance)
        provenance["chunk_ordinal"] = ordinal
        chunks.append(
            RagChunkCandidate(
                chunk_id=derive_chunk_id(document.document_id, ordinal),
                document_id=document.document_id,
                source_type=document.source_type,
                source_key=document.source_key,
                source_entity_id=document.source_entity_id,
                ordinal=ordinal,
                semantic_text=chunk_text,
                content_hash=canonical_content_hash(chunk_text),
                provenance=provenance,
                scope=document.scope,
                builder_version=document.builder_version,
                chunking_version=selected_policy.version,
            )
        )
    return tuple(chunks)


class RagChunker:
    """Reusable callable wrapper around one immutable chunking policy."""

    def __init__(self, policy: ChunkingPolicy | None = None) -> None:
        self.policy = policy or ChunkingPolicy()

    def chunk(self, document: CanonicalRagDocument) -> tuple[RagChunkCandidate, ...]:
        return chunk_document(document, self.policy)

    def __call__(self, document: CanonicalRagDocument) -> tuple[RagChunkCandidate, ...]:
        return self.chunk(document)


chunk_canonical_document = chunk_document
