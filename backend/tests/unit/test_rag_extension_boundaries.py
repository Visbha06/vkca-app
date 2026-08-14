"""Extensions stay inside the typed builder/authorization hand-off boundary."""

from dataclasses import replace

import pytest

from src.services.rag.registry import RagSourceRegistry, RegistryValidationError
from tests.unit.test_rag_registry import _definition


def test_registry_rejects_a_builder_that_captures_provider_or_persistence_state():
    provider = object()

    def unsafe_builder(record):
        return provider.embed_documents(record)  # type: ignore[attr-defined]

    definition = replace(_definition(), build=unsafe_builder)

    with pytest.raises(RegistryValidationError, match="provider"):
        RagSourceRegistry((definition,))


def test_scope_contract_rejects_user_acl_metadata():
    from src.services.rag.contracts import RagScopeMetadata

    with pytest.raises(ValueError, match="ACL"):
        RagScopeMetadata(
            source_type="synthetic_source",
            relationship_labels={"user_acl": ("someone",)},
        )
