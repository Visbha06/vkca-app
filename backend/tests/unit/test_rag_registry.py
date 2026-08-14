"""Unit coverage for explicit opt-in RAG source registration."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.rag.contracts import (
    CanonicalRagDocument,
    RagScopeMetadata,
    RagSourceDefinition,
    SourceDependency,
    SourceLoadBatch,
)
from src.services.rag.loaders import (
    BoundedSetBasedLoader,
    FetchedSourcePage,
    LoaderContractError,
)
from src.services.rag.registry import (
    MarkMissingDeletedPolicy,
    RagSourceRegistry,
    RegistryValidationError,
    validate_built_document,
)


class StubLoader:
    async def load_batch(
        self, session: object, *, cursor: str | None, limit: int
    ) -> SourceLoadBatch[object]:
        del session, cursor, limit
        return SourceLoadBatch(items=())


def _build(record: object) -> CanonicalRagDocument:
    assert isinstance(record, CanonicalRagDocument)
    return record


def _definition(source_type: str = "synthetic_source") -> RagSourceDefinition[object]:
    return RagSourceDefinition(
        source_type=source_type,
        builder_version="synthetic-v1",
        loader=StubLoader(),
        build=_build,
        source_key=lambda record: str(record),
        source_version=lambda record: "1",
        dependency_fingerprint=lambda record: "dependency-v1",
        scope_metadata=lambda record: RagScopeMetadata(source_type=source_type),
        eligible=lambda record: True,
        dependencies=(SourceDependency("synthetic_relationship"),),
        deletion_policy=MarkMissingDeletedPolicy(),
    )


def test_registry_requires_explicit_valid_unique_registration() -> None:
    registry = RagSourceRegistry()
    definition = _definition()

    registry.register(definition)

    assert registry.source_types == ("synthetic_source",)
    assert registry.get("synthetic_source") is definition
    assert registry.select(("synthetic_source",)) == (definition,)
    with pytest.raises(RegistryValidationError, match="already registered"):
        registry.register(definition)
    with pytest.raises(RegistryValidationError, match="not registered"):
        registry.get("unregistered_model")


@pytest.mark.parametrize("source_type", ["", "Player Profile", "users", "a/b"])
def test_registry_rejects_unsafe_or_reserved_source_types(source_type: str) -> None:
    registry = RagSourceRegistry()

    with pytest.raises(RegistryValidationError):
        registry.register(_definition(source_type))


def test_registry_validates_dependencies_and_required_hooks() -> None:
    registry = RagSourceRegistry()
    duplicated_dependencies = replace(
        _definition(),
        dependencies=(SourceDependency("team"), SourceDependency("team")),
    )

    with pytest.raises(RegistryValidationError, match="dependency"):
        registry.register(duplicated_dependencies)


def test_deletion_policy_returns_only_previously_known_missing_keys() -> None:
    policy = MarkMissingDeletedPolicy()

    assert policy.reconcile_deleted(
        seen_keys={"current", "shared"},
        previous_keys={"deleted", "shared"},
    ) == ("deleted",)


def test_synthetic_registration_declares_targeting_dependencies_and_eligibility():
    definition = _definition()
    registry = RagSourceRegistry((definition,))

    assert registry.select(("synthetic_source",)) == (definition,)
    assert registry.eligibility("synthetic_source", object()).eligible
    assert definition.dependencies == (SourceDependency("synthetic_relationship"),)
    assert definition.deletion_policy.reconcile_deleted(
        seen_keys={"present"}, previous_keys={"missing", "present"}
    ) == ("missing",)


def test_builder_output_must_use_declared_scope_and_safe_metadata() -> None:
    document = CanonicalRagDocument(
        document_id=uuid4(),
        source_type="synthetic_source",
        source_key="record-1",
        source_entity_id=None,
        source_version="1",
        dependency_fingerprint="dependency-v1",
        semantic_text="Synthetic safe text",
        content_hash="hash",
        provenance={"source_type": "synthetic_source", "email": "nope"},
        scope=RagScopeMetadata(source_type="synthetic_source"),
        builder_version="synthetic-v1",
        prepared_at=datetime.now(UTC),
    )
    definition = _definition()
    definition = replace(
        definition,
        source_key=lambda record: "record-1",
        scope_metadata=lambda record: RagScopeMetadata(source_type="synthetic_source"),
    )

    with pytest.raises(RegistryValidationError, match="unapproved"):
        validate_built_document(definition, object(), document)


def test_source_definition_has_no_provider_or_persistence_escape_hatch() -> None:
    public_fields = set(_definition().__dataclass_fields__)

    assert "loader" in public_fields
    assert "build" in public_fields
    assert not public_fields.intersection(
        {"provider", "provider_client", "embedding", "session", "vector_store"}
    )


@dataclass(frozen=True)
class StubRecord:
    key: str
    version: int


@pytest.mark.asyncio
async def test_set_based_loader_caps_pages_and_loads_dependencies_once() -> None:
    session = Mock(spec=AsyncSession)
    fetch_page = AsyncMock(
        return_value=FetchedSourcePage(
            records=(StubRecord("one", 1), StubRecord("two", 2)),
            next_cursor="two",
        )
    )
    load_relationships = AsyncMock(
        return_value={
            "one": {"teams": ("team-a",)},
            "two": {"teams": ("team-b",)},
        }
    )
    loader = BoundedSetBasedLoader(
        fetch_page=fetch_page,
        source_key=lambda record: record.key,
        source_version=lambda record: record.version,
        source_fingerprint=lambda record, relationships: (
            f"{record.version}:{relationships['teams'][0]}"
        ),
        dependencies=(SourceDependency("teams"),),
        load_relationships=load_relationships,
        dependency_fingerprint=lambda record, relationships: str(
            relationships["teams"][0]
        ),
        max_batch_size=2,
    )

    batch = await loader.load_batch(session, cursor=None, limit=99)

    fetch_page.assert_awaited_once_with(session, cursor=None, limit=2)
    load_relationships.assert_awaited_once_with(
        session,
        (StubRecord("one", 1), StubRecord("two", 2)),
        (SourceDependency("teams"),),
    )
    assert [item.source_key for item in batch.items] == ["one", "two"]
    assert batch.items[1].source_version == "2"
    assert batch.next_cursor == "two"
    assert batch.source_fingerprint is not None


@pytest.mark.asyncio
async def test_set_based_loader_rejects_duplicate_keys_and_bad_cursors() -> None:
    session = Mock(spec=AsyncSession)
    loader = BoundedSetBasedLoader(
        fetch_page=AsyncMock(
            return_value=FetchedSourcePage(
                records=(StubRecord("same", 1), StubRecord("same", 2))
            )
        ),
        source_key=lambda record: record.key,
        source_version=lambda record: record.version,
        source_fingerprint=lambda record, relationships: str(record.version),
        max_batch_size=2,
    )

    with pytest.raises(LoaderContractError, match="duplicate"):
        await loader.load_batch(session, cursor=None, limit=2)
    with pytest.raises(LoaderContractError, match="cursor"):
        await loader.load_batch(session, cursor=" ", limit=2)
