"""A deliberately small opt-in source used to prove RAG extensibility."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.services.rag.canonical import create_canonical_document, stable_component_hash
from src.services.rag.contracts import (
    RagScopeMetadata,
    RagSourceDefinition,
    SourceDependency,
    SourceLoadBatch,
)
from src.services.rag.registry import MarkMissingDeletedPolicy, RagSourceRegistry

SYNTHETIC_SOURCE_TYPE = "synthetic_note"
SYNTHETIC_BUILDER_VERSION = "synthetic-note-v1"


@dataclass(frozen=True, slots=True)
class SyntheticNote:
    """Authoritative test record containing only explicitly allowlisted fields."""

    id: UUID
    title: str
    summary: str
    version: int = 1
    is_eligible: bool = True
    dependency_version: str = "scope-v1"


class SyntheticNoteLoader:
    """Mutable bounded source loader with deterministic key/version ordering."""

    dependencies = (SourceDependency("synthetic_note_scope"),)

    def __init__(self, notes: tuple[SyntheticNote, ...]) -> None:
        self.notes = notes

    async def load_batch(
        self, session: object, *, cursor: str | None, limit: int
    ) -> SourceLoadBatch[SyntheticNote]:
        del session
        ordered = tuple(sorted(self.notes, key=lambda note: str(note.id)))
        page = tuple(
            note for note in ordered if cursor is None or str(note.id) > cursor
        )[:limit]
        return SourceLoadBatch(
            items=page,
            next_cursor=str(page[-1].id) if len(page) == limit else None,
        )


def build_synthetic_note(
    note: SyntheticNote,
    *,
    builder_version: str = SYNTHETIC_BUILDER_VERSION,
):
    """Produce safe deterministic text without provider or persistence access."""

    return create_canonical_document(
        source_type=SYNTHETIC_SOURCE_TYPE,
        source_key=str(note.id),
        source_entity_id=note.id,
        source_version=str(note.version),
        dependency_fingerprint=stable_component_hash(note.dependency_version),
        semantic_text=f"Reference: {note.title}\nSummary: {note.summary}",
        provenance={"source_type": SYNTHETIC_SOURCE_TYPE, "record_id": str(note.id)},
        scope=RagScopeMetadata(
            source_type=SYNTHETIC_SOURCE_TYPE,
            is_all_academy=True,
        ),
        builder_version=builder_version,
        prepared_at=datetime.now(UTC),
    )


def synthetic_registry(
    notes: tuple[SyntheticNote, ...],
    *,
    builder_version: str = SYNTHETIC_BUILDER_VERSION,
) -> tuple[RagSourceRegistry, SyntheticNoteLoader]:
    """Return the registry and mutable loader used by extensibility tests."""

    loader = SyntheticNoteLoader(notes)
    definition = RagSourceDefinition(
        source_type=SYNTHETIC_SOURCE_TYPE,
        builder_version=builder_version,
        loader=loader,
        build=lambda note: build_synthetic_note(note, builder_version=builder_version),
        source_key=lambda note: str(note.id),
        source_version=lambda note: str(note.version),
        dependency_fingerprint=lambda note: stable_component_hash(
            note.dependency_version
        ),
        scope_metadata=lambda note: build_synthetic_note(
            note, builder_version=builder_version
        ).scope,
        eligible=lambda note: note.is_eligible,
        dependencies=loader.dependencies,
        deletion_policy=MarkMissingDeletedPolicy(),
    )
    return RagSourceRegistry((definition,)), loader
