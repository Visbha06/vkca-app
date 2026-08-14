"""Explicit opt-in registry and validation for RAG source definitions."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from src.services.rag.contracts import RagSourceDefinition

_SOURCE_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_RESERVED_SOURCE_TYPES = frozenset(
    {
        "auth_audit_log",
        "auth_session",
        "auth_sessions",
        "business_audit",
        "business_audit_events",
        "data_sync_log",
        "data_sync_logs",
        "secret",
        "secrets",
        "user",
        "users",
    }
)


class RegistryValidationError(ValueError):
    """A source cannot safely participate in the shared RAG pipeline."""


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    """Bounded eligibility outcome without copying an authoritative record."""

    eligible: bool
    reason_code: str | None = None


class MarkMissingDeletedPolicy:
    """Mark every formerly known source absent from the current projection deleted."""

    def reconcile_deleted(
        self,
        *,
        seen_keys: set[str],
        previous_keys: set[str],
    ) -> tuple[str, ...]:
        return tuple(sorted(previous_keys - seen_keys))


class IgnoreMissingPolicy:
    """Explicit policy for sources whose loader cannot authoritatively see deletions."""

    def reconcile_deleted(
        self,
        *,
        seen_keys: set[str],
        previous_keys: set[str],
    ) -> tuple[str, ...]:
        del seen_keys, previous_keys
        return ()


def validate_source_definition[RecordT](
    definition: RagSourceDefinition[RecordT],
) -> None:
    """Validate all mandatory extension metadata before registration."""

    source_type = definition.source_type.strip()
    if not _SOURCE_TYPE_PATTERN.fullmatch(source_type):
        raise RegistryValidationError(
            "source_type must be a lowercase snake_case identifier"
        )
    if source_type in _RESERVED_SOURCE_TYPES:
        raise RegistryValidationError(
            f"source_type {source_type!r} is excluded from RAG registration"
        )
    if not definition.builder_version.strip():
        raise RegistryValidationError("builder_version must not be blank")

    hooks = {
        "loader.load_batch": getattr(definition.loader, "load_batch", None),
        "build": definition.build,
        "source_key": definition.source_key,
        "source_version": definition.source_version,
        "dependency_fingerprint": definition.dependency_fingerprint,
        "scope_metadata": definition.scope_metadata,
        "eligible": definition.eligible,
        "deletion_policy.reconcile_deleted": getattr(
            definition.deletion_policy, "reconcile_deleted", None
        ),
    }
    missing = sorted(name for name, hook in hooks.items() if not callable(hook))
    if missing:
        raise RegistryValidationError(
            "source definition is missing required hooks: " + ", ".join(missing)
        )

    dependency_names = [dependency.name for dependency in definition.dependencies]
    if len(dependency_names) != len(set(dependency_names)):
        raise RegistryValidationError("source dependency names must be unique")


class RagSourceRegistry[RecordT]:
    """Validated collection that is the sole source-participation entry point."""

    def __init__(
        self,
        definitions: Iterable[RagSourceDefinition[RecordT]] = (),
    ) -> None:
        self._definitions: dict[str, RagSourceDefinition[RecordT]] = {}
        for definition in definitions:
            self.register(definition)

    @property
    def source_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    def register(
        self,
        definition: RagSourceDefinition[RecordT],
    ) -> RagSourceDefinition[RecordT]:
        """Register exactly one validated definition; replacement is explicit."""

        validate_source_definition(definition)
        if definition.source_type in self._definitions:
            raise RegistryValidationError(
                f"source_type {definition.source_type!r} is already registered"
            )
        self._definitions[definition.source_type] = definition
        return definition

    def replace(
        self,
        definition: RagSourceDefinition[RecordT],
    ) -> RagSourceDefinition[RecordT]:
        """Explicitly replace a definition, primarily for isolated tests."""

        validate_source_definition(definition)
        if definition.source_type not in self._definitions:
            raise RegistryValidationError(
                f"source_type {definition.source_type!r} is not registered"
            )
        self._definitions[definition.source_type] = definition
        return definition

    def get(self, source_type: str) -> RagSourceDefinition[RecordT]:
        try:
            return self._definitions[source_type]
        except KeyError:
            raise RegistryValidationError(
                f"source_type {source_type!r} is not registered"
            ) from None

    def select(
        self,
        source_types: Iterable[str] | None = None,
    ) -> tuple[RagSourceDefinition[RecordT], ...]:
        """Resolve an optional targeted selection with no implicit model discovery."""

        if source_types is None:
            selected = self.source_types
        else:
            selected = tuple(source_types)
            if len(selected) != len(set(selected)):
                raise RegistryValidationError("targeted source types must be unique")
        return tuple(self.get(source_type) for source_type in selected)

    def eligibility(
        self,
        source_type: str,
        record: RecordT,
    ) -> EligibilityDecision:
        """Run only the registered source's domain/Data Quality eligibility hook."""

        definition = self.get(source_type)
        return EligibilityDecision(eligible=bool(definition.eligible(record)))

    def __contains__(self, source_type: object) -> bool:
        return source_type in self._definitions

    def __iter__(self) -> Iterator[RagSourceDefinition[RecordT]]:
        return iter(self.select())

    def __len__(self) -> int:
        return len(self._definitions)


# This remains intentionally empty until Phase 3 registers the nine initial sources.
source_registry: RagSourceRegistry[object] = RagSourceRegistry()
