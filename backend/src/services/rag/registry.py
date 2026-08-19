"""Explicit opt-in registry and validation for RAG source definitions."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.background_jobs.outbox import BackgroundJobOutbox
from src.services.background_jobs.registry import build_background_job_registry
from src.services.rag.contracts import (
    MAX_RAG_MUTATION_TARGETS,
    CanonicalRagDocument,
    RagMutationImpact,
    RagMutationSource,
    RagReconciliationPayloadV1,
    RagSourceDefinition,
    RagTargetRef,
)

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


_FORBIDDEN_EXTENSION_NAMES = frozenset(
    {
        "embedding",
        "embed_documents",
        "embed_query",
        "google",
        "provider",
        "session",
        "sqlalchemy",
        "vector",
    }
)
_FORBIDDEN_METADATA_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "credential",
    "session",
    "csrf",
    "email",
    "user_id",
    "acl",
    "vector",
    "embedding",
)

_MUTATION_SOURCE_TYPES: Mapping[RagMutationSource, str] = {
    RagMutationSource.PLAYER: "player_profile",
    RagMutationSource.TEAM: "team",
    RagMutationSource.MATCH: "match",
    RagMutationSource.MATCH_BATTING_PERFORMANCE: "match_batting_performance",
    RagMutationSource.MATCH_BOWLING_PERFORMANCE: "match_bowling_performance",
    RagMutationSource.MATCH_FIELDING_PERFORMANCE: "match_fielding_performance",
    RagMutationSource.PLAYER_BATTING_STATS: "player_batting_stats",
    RagMutationSource.PLAYER_BOWLING_STATS: "player_bowling_stats",
    RagMutationSource.CALENDAR_OCCURRENCE: "calendar_occurrence",
}


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

    # Source adapters are deliberately pure preparation code.  The runtime
    # contracts also make direct persistence impossible, but rejecting obvious
    # SDK/session/vector captures gives extension authors an early, actionable
    # failure instead of silently bypassing the shared pipeline.
    try:
        names = set(definition.build.__code__.co_names)
        names.update(inspect.getclosurevars(definition.build).nonlocals)
    except (AttributeError, TypeError):
        names = set()
    forbidden = sorted(
        name for name in names if name.casefold() in _FORBIDDEN_EXTENSION_NAMES
    )
    if forbidden:
        raise RegistryValidationError(
            "source builders must not access provider, vector, or persistence "
            "boundaries: " + ", ".join(forbidden)
        )


def _validate_safe_mapping(value: object, *, context: str) -> None:
    """Reject fields that cannot cross from a source builder into RAG state."""

    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized_key = str(key).strip().casefold()
            if any(
                fragment in normalized_key for fragment in _FORBIDDEN_METADATA_FRAGMENTS
            ):
                raise RegistryValidationError(
                    f"{context} contains an unapproved sensitive field"
                )
            _validate_safe_mapping(nested, context=context)
    elif isinstance(value, (tuple, list, set, frozenset)):
        for nested in value:
            _validate_safe_mapping(nested, context=context)


def validate_built_document[RecordT](
    definition: RagSourceDefinition[RecordT],
    record: RecordT,
    document: CanonicalRagDocument,
) -> None:
    """Validate a registered builder output before any chunk/provider work."""

    source_key = str(definition.source_key(record)).strip()
    if (
        document.source_type != definition.source_type
        or document.source_key != source_key
    ):
        raise RegistryValidationError(
            "registered builder returned a mismatched RAG source identity"
        )
    if document.builder_version != definition.builder_version:
        raise RegistryValidationError(
            "registered builder output does not match its declared version"
        )
    if document.scope != definition.scope_metadata(record):
        raise RegistryValidationError(
            "registered builder bypassed its declared authorization metadata"
        )
    _validate_safe_mapping(document.provenance, context="RAG provenance")
    _validate_safe_mapping(document.scope.relationship_labels, context="RAG scope")


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

    def resolve_mutation_impact(
        self,
        impact: RagMutationImpact,
    ) -> tuple[RagTargetRef, ...]:
        """Map bounded domain identities to explicitly registered source targets."""

        if not impact.semantic_change:
            return ()
        targets: dict[tuple[str, str], RagTargetRef] = {}
        for reference in (*impact.current_refs, *impact.previous_refs):
            source_type = _MUTATION_SOURCE_TYPES[reference.source]
            self.get(source_type)
            target = RagTargetRef(
                source_type=source_type,
                source_key=reference.source_key,
            )
            targets[(target.source_type, target.source_key)] = target
        if len(targets) > MAX_RAG_MUTATION_TARGETS:
            raise RegistryValidationError(
                f"mutation impacts support at most {MAX_RAG_MUTATION_TARGETS} targets"
            )
        return tuple(targets[key] for key in sorted(targets))

    def resolve_coalescing_target(self, impact: RagMutationImpact) -> RagTargetRef:
        """Return the stable logical identity used to coalesce rapid mutations."""

        reference = impact.coalescing_ref
        if reference is None:
            refs = (*impact.current_refs, *impact.previous_refs)
            if not refs:
                raise RegistryValidationError(
                    "semantic mutation impact has no coalescing identity"
                )
            reference = refs[0]
        source_type = _MUTATION_SOURCE_TYPES[reference.source]
        self.get(source_type)
        return RagTargetRef(
            source_type=source_type,
            source_key=reference.source_key,
        )

    def validate_targets(
        self,
        targets: Iterable[RagTargetRef],
    ) -> tuple[RagTargetRef, ...]:
        """Validate bounded stable targets against this registry's allowlist."""

        validated: list[RagTargetRef] = []
        seen: set[tuple[str, str]] = set()
        for raw_target in targets:
            target = RagTargetRef.model_validate(raw_target)
            self.get(target.source_type)
            identity = (target.source_type, target.source_key)
            if identity in seen:
                continue
            seen.add(identity)
            validated.append(target)
        if not validated:
            raise RegistryValidationError("RAG reconciliation requires a target")
        if len(validated) > MAX_RAG_MUTATION_TARGETS:
            raise RegistryValidationError(
                f"RAG reconciliation supports at most {MAX_RAG_MUTATION_TARGETS} "
                "targets"
            )
        return tuple(validated)

    async def resolve_dependency_closure(
        self,
        session: object,
        targets: Iterable[RagTargetRef],
    ) -> tuple[RagTargetRef, ...]:
        """Add dependents declared on source definitions from current rows.

        Resolvers receive only the original authoritative mutation targets. A
        dependent document target is not recursively reinterpreted as another
        domain mutation, which keeps Player/Team relationships narrow and avoids
        artificial dependency cycles.
        """

        roots = self.validate_targets(targets)
        roots_by_type: dict[str, tuple[str, ...]] = {}
        for source_type in sorted({target.source_type for target in roots}):
            roots_by_type[source_type] = tuple(
                target.source_key
                for target in roots
                if target.source_type == source_type
            )
        resolved = list(roots)
        seen = {(target.source_type, target.source_key) for target in roots}
        for definition in self.select():
            for dependency in definition.dependencies:
                resolver = dependency.target_resolver
                if resolver is None:
                    continue
                for trigger_source_type in dependency.trigger_source_types:
                    trigger_keys = roots_by_type.get(trigger_source_type)
                    if not trigger_keys:
                        continue
                    remaining = MAX_RAG_MUTATION_TARGETS - len(resolved)
                    if remaining <= 0:
                        raise RegistryValidationError(
                            "RAG dependency closure exceeds its bounded target limit"
                        )
                    dependent_keys = await resolver(
                        session,
                        trigger_source_type=trigger_source_type,
                        trigger_source_keys=trigger_keys,
                        limit=remaining,
                    )
                    for source_key in dependent_keys:
                        target = RagTargetRef(
                            source_type=definition.source_type,
                            source_key=source_key,
                        )
                        identity = (target.source_type, target.source_key)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        resolved.append(target)
                        if len(resolved) > MAX_RAG_MUTATION_TARGETS:
                            raise RegistryValidationError(
                                "RAG dependency closure exceeds its bounded "
                                "target limit"
                            )
        roots_count = len(roots)
        return (
            *roots,
            *sorted(
                resolved[roots_count:],
                key=lambda item: (
                    item.source_type,
                    item.source_key,
                ),
            ),
        )

    def select_targets(
        self,
        targets: Iterable[RagTargetRef],
    ) -> tuple[tuple[RagSourceDefinition[RecordT], tuple[str, ...]], ...]:
        """Group validated stable keys by registered source definition."""

        validated = self.validate_targets(targets)
        grouped: list[tuple[RagSourceDefinition[RecordT], tuple[str, ...]]] = []
        for source_type in sorted({target.source_type for target in validated}):
            keys = tuple(
                sorted(
                    target.source_key
                    for target in validated
                    if target.source_type == source_type
                )
            )
            grouped.append((self.get(source_type), keys))
        return tuple(grouped)

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
    loaded = cast(Any, _loaded_record(record))
    return str(source_key if source_key is not None else loaded.id)


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

    from src.models.match import Match
    from src.models.match_batting_performance import MatchBattingPerformance
    from src.models.match_bowling_performance import MatchBowlingPerformance
    from src.models.match_fielding_performance import MatchFieldingPerformance
    from src.models.player import Player
    from src.models.player_batting_stats import PlayerBattingStats
    from src.models.player_bowling_stats import PlayerBowlingStats
    from src.models.team import Team
    from src.schemas.calendar import CalendarEventInstance
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
        build: Callable[[object], CanonicalRagDocument],
        eligible: Callable[[object], bool],
    ) -> None:
        definitions.append(
            RagSourceDefinition(
                source_type=source_type,
                builder_version=builder_version,
                loader=loader,  # type: ignore[arg-type]
                build=build,  # type: ignore[arg-type]
                source_key=_loaded_source_key,
                source_version=_loaded_source_version,
                dependency_fingerprint=_loaded_dependency,
                scope_metadata=lambda record: build(record).scope,
                eligible=eligible,
                dependencies=getattr(loader, "dependencies", ()),
                deletion_policy=MarkMissingDeletedPolicy(),
            )
        )

    add(
        "player_profile",
        PLAYER_PROFILE_BUILDER_VERSION,
        player_profile_loader,
        lambda item: build_player_profile_document(
            cast(Player, _loaded_record(item)),
            team_memberships=cast(
                Iterable[Team], _relationships(item).get("teams", ())
            ),
        ),
        lambda item: is_eligible_player(cast(Player, _loaded_record(item))),
    )
    add(
        "team",
        TEAM_BUILDER_VERSION,
        team_loader,
        lambda item: build_team_document(
            cast(Team, _loaded_record(item)),
            roster=cast(Iterable[Player], _relationships(item).get("roster", ())),
            coaches=cast(Iterable[str], _relationships(item).get("coaches", ())),
        ),
        lambda item: True,
    )
    add(
        "match",
        MATCH_BUILDER_VERSION,
        match_loader,
        lambda item: build_match_document(
            cast(Match, _loaded_record(item)),
            home_team=cast(Team | None, _relationships(item).get("home_team")),
            away_team=cast(Team | None, _relationships(item).get("away_team")),
        ),
        lambda item: True,
    )
    add(
        "match_batting_performance",
        BATTING_PERFORMANCE_BUILDER_VERSION,
        batting_performance_loader,
        lambda item: build_batting_performance_document(
            cast(MatchBattingPerformance, _loaded_record(item)),
            player=cast(Player | None, _relationships(item).get("player")),
            match=cast(Match | None, _relationships(item).get("match")),
        ),
        _eligible_relationship_player,
    )
    add(
        "match_bowling_performance",
        BOWLING_PERFORMANCE_BUILDER_VERSION,
        bowling_performance_loader,
        lambda item: build_bowling_performance_document(
            cast(MatchBowlingPerformance, _loaded_record(item)),
            player=cast(Player | None, _relationships(item).get("player")),
            match=cast(Match | None, _relationships(item).get("match")),
        ),
        _eligible_relationship_player,
    )
    add(
        "match_fielding_performance",
        FIELDING_PERFORMANCE_BUILDER_VERSION,
        fielding_performance_loader,
        lambda item: build_fielding_performance_document(
            cast(MatchFieldingPerformance, _loaded_record(item)),
            player=cast(Player | None, _relationships(item).get("player")),
            match=cast(Match | None, _relationships(item).get("match")),
        ),
        _eligible_relationship_player,
    )
    add(
        "player_batting_stats",
        BATTING_STATISTICS_BUILDER_VERSION,
        batting_statistics_loader,
        lambda item: build_batting_statistics_document(
            cast(PlayerBattingStats, _loaded_record(item)),
            player=cast(Player | None, _relationships(item).get("player")),
            teams=cast(Iterable[Team], _relationships(item).get("teams", ())),
        ),
        _eligible_relationship_player,
    )
    add(
        "player_bowling_stats",
        BOWLING_STATISTICS_BUILDER_VERSION,
        bowling_statistics_loader,
        lambda item: build_bowling_statistics_document(
            cast(PlayerBowlingStats, _loaded_record(item)),
            player=cast(Player | None, _relationships(item).get("player")),
            teams=cast(Iterable[Team], _relationships(item).get("teams", ())),
        ),
        _eligible_relationship_player,
    )
    add(
        "calendar_occurrence",
        CALENDAR_OCCURRENCE_BUILDER_VERSION,
        calendar_occurrence_loader,
        lambda item: build_calendar_occurrence_document(
            cast(CalendarEventInstance, _loaded_record(item))
        ),
        lambda item: True,
    )
    return RagSourceRegistry(definitions)


source_registry: RagSourceRegistry[object] = _build_initial_registry()


def _build_mutation_staging_outbox() -> BackgroundJobOutbox:
    return BackgroundJobOutbox(build_background_job_registry())


class RagMutationStager:
    """Translate semantic mutation impacts into transaction-local durable work."""

    def __init__(
        self,
        registry: RagSourceRegistry[object],
        *,
        outbox: BackgroundJobOutbox | None = None,
    ) -> None:
        self.registry = registry
        self.outbox = outbox or _build_mutation_staging_outbox()

    async def stage(
        self,
        session: AsyncSession,
        impact: RagMutationImpact,
    ) -> object | None:
        """Stage bounded work without committing or contacting external services."""

        targets = self.registry.resolve_mutation_impact(impact)
        if not targets:
            return None
        coalescing_target = self.registry.resolve_coalescing_target(impact)
        payload = RagReconciliationPayloadV1(targets=targets)
        return await self.outbox.stage(
            session,
            "rag_reconciliation",
            payload,
            coalescing_key=(
                f"rag:{coalescing_target.source_type}:{coalescing_target.source_key}"
            ),
            correlation_id=impact.correlation_id,
            source_type=coalescing_target.source_type,
            source_key=coalescing_target.source_key,
            safe_metadata={"reason": "mutation", "source_count": len(targets)},
        )


_default_mutation_stager: RagMutationStager | None = None


def get_rag_mutation_stager() -> RagMutationStager:
    """Return the resource-free default transaction-local staging adapter."""

    global _default_mutation_stager
    if _default_mutation_stager is None:
        _default_mutation_stager = RagMutationStager(source_registry)
    return _default_mutation_stager


async def stage_rag_mutation_impact(
    session: object,
    impact: RagMutationImpact,
) -> object | None:
    """Application-service facade for same-transaction mutation staging."""

    # Unit tests for existing application services use lightweight session
    # doubles. They opt into staging explicitly when that boundary is under
    # test; production and integration paths always provide a real session.
    if not isinstance(session, AsyncSession):
        return None
    return await get_rag_mutation_stager().stage(session, impact)
