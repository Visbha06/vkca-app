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


def _loaded_record(record: object) -> object:
    return getattr(record, "record", record)


def _relationships(record: object) -> dict[str, object]:
    return dict(getattr(record, "relationships", {}))


def _loaded_source_key(record: object) -> str:
    source_key = getattr(record, "source_key", None)
    return str(source_key if source_key is not None else _loaded_record(record).id)


def _loaded_source_version(record: object) -> str | None:
    value = getattr(
        record,
        "source_version",
        getattr(_loaded_record(record), "version_number", None),
    )
    return str(value) if value is not None else None


def _loaded_dependency(record: object) -> str | None:
    value = getattr(record, "dependency_fingerprint", None)
    return str(value) if value is not None else None


def _eligible_active_player(record: object) -> bool:
    return bool(getattr(_loaded_record(record), "is_active", False))


def _eligible_relationship_player(record: object) -> bool:
    player = _relationships(record).get("player")
    return player is not None and bool(getattr(player, "is_active", False))


def _build_initial_registry() -> RagSourceRegistry[object]:
    """Register only the nine approved academy source families."""

    from src.services.rag.builders.calendar import (
        CALENDAR_OCCURRENCE_BUILDER_VERSION,
        build_calendar_occurrence_document,
    )
    from src.services.rag.builders.match import (
        MATCH_BUILDER_VERSION,
        build_match_document,
    )
    from src.services.rag.builders.performance import (
        BATTING_PERFORMANCE_BUILDER_VERSION,
        BOWLING_PERFORMANCE_BUILDER_VERSION,
        FIELDING_PERFORMANCE_BUILDER_VERSION,
        build_batting_performance_document,
        build_bowling_performance_document,
        build_fielding_performance_document,
    )
    from src.services.rag.builders.player import (
        PLAYER_PROFILE_BUILDER_VERSION,
        build_player_profile_document,
        is_eligible_player,
    )
    from src.services.rag.builders.statistics import (
        BATTING_STATISTICS_BUILDER_VERSION,
        BOWLING_STATISTICS_BUILDER_VERSION,
        build_batting_statistics_document,
        build_bowling_statistics_document,
    )
    from src.services.rag.builders.team import TEAM_BUILDER_VERSION, build_team_document
    from src.services.rag.loaders import (
        batting_performance_loader,
        batting_statistics_loader,
        bowling_performance_loader,
        bowling_statistics_loader,
        calendar_occurrence_loader,
        fielding_performance_loader,
        match_loader,
        player_profile_loader,
        team_loader,
    )

    definitions: list[RagSourceDefinition[object]] = []

    def add(
        source_type: str,
        builder_version: str,
        loader: object,
        build: object,
        eligible: object,
    ) -> None:
        assert callable(build)
        assert callable(eligible)
        definitions.append(
            RagSourceDefinition(
                source_type=source_type,
                builder_version=builder_version,
                loader=loader,  # type: ignore[arg-type]
                build=build,  # type: ignore[arg-type]
                source_key=_loaded_source_key,
                source_version=_loaded_source_version,
                dependency_fingerprint=_loaded_dependency,
                scope_metadata=lambda record, build=build: build(record).scope,  # type: ignore[union-attr]
                eligible=eligible,  # type: ignore[arg-type]
                dependencies=getattr(loader, "dependencies", ()),
                deletion_policy=MarkMissingDeletedPolicy(),
            )
        )

    add(
        "player_profile",
        PLAYER_PROFILE_BUILDER_VERSION,
        player_profile_loader,
        lambda item: build_player_profile_document(
            _loaded_record(item), team_memberships=_relationships(item).get("teams", ())
        ),
        lambda item: is_eligible_player(_loaded_record(item)),
    )
    add(
        "team",
        TEAM_BUILDER_VERSION,
        team_loader,
        lambda item: build_team_document(
            _loaded_record(item),
            roster=_relationships(item).get("roster", ()),
            coaches=_relationships(item).get("coaches", ()),
        ),
        lambda item: True,
    )
    add(
        "match",
        MATCH_BUILDER_VERSION,
        match_loader,
        lambda item: build_match_document(
            _loaded_record(item),
            home_team=_relationships(item).get("home_team"),
            away_team=_relationships(item).get("away_team"),
        ),
        lambda item: True,
    )
    add(
        "batting_performance",
        BATTING_PERFORMANCE_BUILDER_VERSION,
        batting_performance_loader,
        lambda item: build_batting_performance_document(
            _loaded_record(item),
            player=_relationships(item).get("player"),
            match=_relationships(item).get("match"),
        ),
        _eligible_relationship_player,
    )
    add(
        "bowling_performance",
        BOWLING_PERFORMANCE_BUILDER_VERSION,
        bowling_performance_loader,
        lambda item: build_bowling_performance_document(
            _loaded_record(item),
            player=_relationships(item).get("player"),
            match=_relationships(item).get("match"),
        ),
        _eligible_relationship_player,
    )
    add(
        "fielding_performance",
        FIELDING_PERFORMANCE_BUILDER_VERSION,
        fielding_performance_loader,
        lambda item: build_fielding_performance_document(
            _loaded_record(item),
            player=_relationships(item).get("player"),
            match=_relationships(item).get("match"),
        ),
        _eligible_relationship_player,
    )
    add(
        "player_batting_statistics",
        BATTING_STATISTICS_BUILDER_VERSION,
        batting_statistics_loader,
        lambda item: build_batting_statistics_document(
            _loaded_record(item), player=_relationships(item).get("player")
        ),
        _eligible_relationship_player,
    )
    add(
        "player_bowling_statistics",
        BOWLING_STATISTICS_BUILDER_VERSION,
        bowling_statistics_loader,
        lambda item: build_bowling_statistics_document(
            _loaded_record(item), player=_relationships(item).get("player")
        ),
        _eligible_relationship_player,
    )
    add(
        "calendar_occurrence",
        CALENDAR_OCCURRENCE_BUILDER_VERSION,
        calendar_occurrence_loader,
        lambda item: build_calendar_occurrence_document(_loaded_record(item)),
        lambda item: True,
    )
    return RagSourceRegistry(definitions)


source_registry: RagSourceRegistry[object] = _build_initial_registry()
