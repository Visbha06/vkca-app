"""Bounded set-based source-loading seams shared by registered adapters."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.schemas.calendar import CalendarEventInstance
from src.services.calendar_service import CalendarService
from src.services.rag.builders.calendar import load_projected_calendar_occurrences
from src.services.rag.canonical import normalize_text, stable_component_hash
from src.services.rag.contracts import SourceDependency, SourceLoadBatch

DEFAULT_SOURCE_BATCH_SIZE = 100
MAX_SOURCE_BATCH_SIZE = 1_000
MAX_LOADER_CURSOR_CHARACTERS = 512


class LoaderContractError(ValueError):
    """A registered loader violated its bounded/set-based contract."""


@dataclass(frozen=True, slots=True)
class FetchedSourcePage[RecordT]:
    """Authoritative page returned by one set-based source query."""

    records: tuple[RecordT, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class LoadedSourceRecord[RecordT]:
    """One source plus the declared relationship inputs loaded for its builder."""

    record: RecordT
    source_key: str
    source_version: str | None
    source_fingerprint: str
    dependency_fingerprint: str | None
    relationships: Mapping[str, object]


class SourcePageFetcher[RecordT](Protocol):
    """Execute one ordered page query, not one query per source record."""

    async def __call__(
        self,
        session: AsyncSession,
        *,
        cursor: str | None,
        limit: int,
    ) -> FetchedSourcePage[RecordT]: ...


class SourceTargetFetcher[RecordT](Protocol):
    """Load only explicitly requested authoritative source identities."""

    async def __call__(
        self,
        session: AsyncSession,
        *,
        source_keys: tuple[str, ...],
        limit: int,
    ) -> FetchedSourcePage[RecordT]: ...


class RelationshipDependencyLoader[RecordT](Protocol):
    """Load all declared relationships for the whole page in bounded queries."""

    async def __call__(
        self,
        session: AsyncSession,
        records: Sequence[RecordT],
        dependencies: tuple[SourceDependency, ...],
    ) -> Mapping[str, Mapping[str, object]]: ...


class SourceFingerprintHook[RecordT](Protocol):
    """Compute the authoritative source/version fingerprint for one loaded row."""

    def __call__(
        self,
        record: RecordT,
        relationships: Mapping[str, object],
    ) -> str: ...


class DependencyFingerprintHook[RecordT](Protocol):
    """Hash only the declared relationship/projection inputs for invalidation."""

    def __call__(
        self,
        record: RecordT,
        relationships: Mapping[str, object],
    ) -> str | None: ...


class BoundedSetBasedLoader[RecordT]:
    """Validate bounds and combine a page query with one relationship-load seam."""

    def __init__(
        self,
        *,
        fetch_page: SourcePageFetcher[RecordT],
        fetch_targets: SourceTargetFetcher[RecordT] | None = None,
        source_key: Callable[[RecordT], object],
        source_version: Callable[[RecordT], object | None],
        source_fingerprint: SourceFingerprintHook[RecordT],
        dependencies: tuple[SourceDependency, ...] = (),
        load_relationships: RelationshipDependencyLoader[RecordT] | None = None,
        dependency_fingerprint: DependencyFingerprintHook[RecordT] | None = None,
        max_batch_size: int = DEFAULT_SOURCE_BATCH_SIZE,
    ) -> None:
        if not 1 <= max_batch_size <= MAX_SOURCE_BATCH_SIZE:
            raise LoaderContractError(
                f"loader max_batch_size must be between 1 and {MAX_SOURCE_BATCH_SIZE}"
            )
        dependency_names = [dependency.name for dependency in dependencies]
        if len(dependency_names) != len(set(dependency_names)):
            raise LoaderContractError("declared loader dependencies must be unique")
        if dependencies and load_relationships is None:
            raise LoaderContractError(
                "declared relationships require one set-based dependency loader"
            )
        self.fetch_page = fetch_page
        self.fetch_targets = fetch_targets
        self.source_key = source_key
        self.source_version = source_version
        self.source_fingerprint = source_fingerprint
        self.dependencies = dependencies
        self.load_relationships = load_relationships
        self.dependency_fingerprint = dependency_fingerprint
        self.max_batch_size = max_batch_size

    @staticmethod
    def _validate_cursor(cursor: str | None) -> None:
        if cursor is not None and (
            not cursor.strip() or len(cursor) > MAX_LOADER_CURSOR_CHARACTERS
        ):
            raise LoaderContractError("loader cursor is blank or exceeds its bound")

    async def load_batch(
        self,
        session: object,
        *,
        cursor: str | None,
        limit: int,
    ) -> SourceLoadBatch[LoadedSourceRecord[RecordT]]:
        """Load one capped page and all its relationships without N+1 dispatch."""

        self._validate_cursor(cursor)
        if limit <= 0:
            raise LoaderContractError("loader batch limit must be positive")
        typed_session = cast(AsyncSession, session)
        bounded_limit = min(limit, self.max_batch_size)
        page = await self.fetch_page(
            typed_session,
            cursor=cursor,
            limit=bounded_limit,
        )
        if len(page.records) > bounded_limit:
            raise LoaderContractError(
                "source fetcher returned more than its batch limit"
            )
        self._validate_cursor(page.next_cursor)

        return await self._prepare_page(typed_session, page)

    async def load_targets(
        self,
        session: object,
        *,
        source_keys: Sequence[str],
        limit: int,
    ) -> SourceLoadBatch[LoadedSourceRecord[RecordT]]:
        """Load only bounded requested keys; never traverse an unrelated corpus."""

        if self.fetch_targets is None:
            raise LoaderContractError("source loader does not support stable targets")
        if limit <= 0:
            raise LoaderContractError("loader target limit must be positive")
        normalized_keys = tuple(str(key).strip() for key in source_keys)
        if not normalized_keys or any(not key for key in normalized_keys):
            raise LoaderContractError("loader target keys must not be blank")
        if len(normalized_keys) != len(set(normalized_keys)):
            raise LoaderContractError("loader target keys must be unique")
        bounded_limit = min(limit, self.max_batch_size)
        if len(normalized_keys) > bounded_limit:
            raise LoaderContractError("loader target keys exceed the bounded limit")
        typed_session = cast(AsyncSession, session)
        page = await self.fetch_targets(
            typed_session,
            source_keys=normalized_keys,
            limit=bounded_limit,
        )
        if page.next_cursor is not None:
            raise LoaderContractError("targeted source fetches must not paginate")
        if len(page.records) > bounded_limit:
            raise LoaderContractError(
                "targeted source fetcher returned more than its batch limit"
            )
        prepared = await self._prepare_page(typed_session, page)
        requested = set(normalized_keys)
        if any(item.source_key not in requested for item in prepared.items):
            raise LoaderContractError(
                "targeted source fetcher returned an unrequested key"
            )
        return prepared

    async def _prepare_page(
        self,
        session: AsyncSession,
        page: FetchedSourcePage[RecordT],
    ) -> SourceLoadBatch[LoadedSourceRecord[RecordT]]:
        """Load declared relationships and normalize one already-bounded page."""

        relationships_by_key: Mapping[str, Mapping[str, object]] = {}
        if self.load_relationships is not None and page.records:
            relationships_by_key = await self.load_relationships(
                session,
                page.records,
                self.dependencies,
            )

        loaded: list[LoadedSourceRecord[RecordT]] = []
        seen_keys: set[str] = set()
        for record in page.records:
            key = normalize_text(str(self.source_key(record)))
            if not key:
                raise LoaderContractError("loaded source key must not be blank")
            if key in seen_keys:
                raise LoaderContractError("source page contains duplicate source keys")
            seen_keys.add(key)
            relationships = dict(relationships_by_key.get(key, {}))
            fingerprint = normalize_text(self.source_fingerprint(record, relationships))
            if not fingerprint:
                raise LoaderContractError("source fingerprint must not be blank")
            dependency_hash = (
                self.dependency_fingerprint(record, relationships)
                if self.dependency_fingerprint is not None
                else None
            )
            version = self.source_version(record)
            loaded.append(
                LoadedSourceRecord(
                    record=record,
                    source_key=key,
                    source_version=(
                        normalize_text(str(version)) if version is not None else None
                    ),
                    source_fingerprint=fingerprint,
                    dependency_fingerprint=(
                        normalize_text(dependency_hash)
                        if dependency_hash is not None
                        else None
                    ),
                    relationships=relationships,
                )
            )

        aggregate_fingerprint = (
            stable_component_hash(
                tuple((item.source_key, item.source_fingerprint) for item in loaded)
            )
            if loaded
            else None
        )
        return SourceLoadBatch(
            items=tuple(loaded),
            next_cursor=page.next_cursor,
            source_fingerprint=aggregate_fingerprint,
        )


async def iter_loader_batches[RecordT](
    loader: BoundedSetBasedLoader[RecordT],
    session: AsyncSession,
    *,
    batch_size: int | None = None,
) -> AsyncIterator[SourceLoadBatch[LoadedSourceRecord[RecordT]]]:
    """Traverse a loader through bounded cursors and reject cursor cycles."""

    cursor: str | None = None
    seen_cursors: set[str] = set()
    selected_size = batch_size or loader.max_batch_size
    while True:
        batch = await loader.load_batch(
            session,
            cursor=cursor,
            limit=selected_size,
        )
        yield batch
        if batch.next_cursor is None:
            return
        if batch.next_cursor in seen_cursors:
            raise LoaderContractError("source loader produced a cursor cycle")
        seen_cursors.add(batch.next_cursor)
        cursor = batch.next_cursor


SetBasedLoader = BoundedSetBasedLoader


# Initial academy loaders. Relationship queries are page-scoped so builders do
# not perform hidden per-record database work.


def _model_cursor_page[ModelT](model: type[ModelT]) -> SourcePageFetcher[ModelT]:
    async def fetch(
        session: AsyncSession, *, cursor: str | None, limit: int
    ) -> FetchedSourcePage[ModelT]:
        statement = (
            select(model)
            .order_by(model.id)  # type: ignore[attr-defined]
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        if cursor is not None:
            statement = statement.where(model.id > UUID(cursor))  # type: ignore[attr-defined]
        rows = tuple((await session.execute(statement)).scalars().all())
        return FetchedSourcePage(
            records=rows,
            next_cursor=str(rows[-1].id) if len(rows) == limit else None,  # type: ignore[attr-defined]
        )

    return fetch


def _uuid_target_keys(source_keys: Sequence[str]) -> tuple[UUID, ...]:
    try:
        return tuple(UUID(source_key) for source_key in source_keys)
    except (TypeError, ValueError, AttributeError) as exc:
        raise LoaderContractError(
            "registered model targets require UUID source keys"
        ) from exc


def _model_target_page[ModelT](model: type[ModelT]) -> SourceTargetFetcher[ModelT]:
    async def fetch(
        session: AsyncSession,
        *,
        source_keys: tuple[str, ...],
        limit: int,
    ) -> FetchedSourcePage[ModelT]:
        if len(source_keys) > limit:
            raise LoaderContractError("targeted model query exceeds its bound")
        identifiers = _uuid_target_keys(source_keys)
        rows = tuple(
            (
                await session.scalars(
                    select(model)
                    .where(model.id.in_(identifiers))  # type: ignore[attr-defined]
                    .order_by(model.id)  # type: ignore[attr-defined]
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        return FetchedSourcePage(records=rows)

    return fetch


async def _bounded_target_ids(
    session: AsyncSession,
    statement: Any,
    *,
    limit: int,
) -> tuple[str, ...]:
    if not 1 <= limit <= MAX_SOURCE_BATCH_SIZE:
        raise LoaderContractError("dependency target limit is outside its bound")
    bounded = statement.limit(limit + 1)
    identifiers = tuple((await session.scalars(bounded)).all())
    if len(identifiers) > limit:
        raise LoaderContractError("declared dependency closure exceeds its bound")
    return tuple(str(identifier) for identifier in identifiers)


async def _players_for_team_dependency(
    session: object,
    *,
    trigger_source_type: str,
    trigger_source_keys: tuple[str, ...],
    limit: int,
) -> tuple[str, ...]:
    if trigger_source_type != "team":
        return ()
    team_ids = _uuid_target_keys(trigger_source_keys)
    statement = (
        select(TeamPlayer.player_id)
        .where(TeamPlayer.team_id.in_(team_ids))
        .distinct()
        .order_by(TeamPlayer.player_id)
    )
    return await _bounded_target_ids(
        cast(AsyncSession, session), statement, limit=limit
    )


async def _teams_for_player_dependency(
    session: object,
    *,
    trigger_source_type: str,
    trigger_source_keys: tuple[str, ...],
    limit: int,
) -> tuple[str, ...]:
    if trigger_source_type != "player_profile":
        return ()
    player_ids = _uuid_target_keys(trigger_source_keys)
    statement = (
        select(TeamPlayer.team_id)
        .where(TeamPlayer.player_id.in_(player_ids))
        .distinct()
        .order_by(TeamPlayer.team_id)
    )
    return await _bounded_target_ids(
        cast(AsyncSession, session), statement, limit=limit
    )


async def _matches_for_team_dependency(
    session: object,
    *,
    trigger_source_type: str,
    trigger_source_keys: tuple[str, ...],
    limit: int,
) -> tuple[str, ...]:
    if trigger_source_type != "team":
        return ()
    team_ids = _uuid_target_keys(trigger_source_keys)
    statement = (
        select(Match.id)
        .where((Match.home_team_id.in_(team_ids)) | (Match.away_team_id.in_(team_ids)))
        .distinct()
        .order_by(Match.id)
    )
    return await _bounded_target_ids(
        cast(AsyncSession, session), statement, limit=limit
    )


def _performance_dependency_resolver(model: type[object]):
    async def resolve(
        session: object,
        *,
        trigger_source_type: str,
        trigger_source_keys: tuple[str, ...],
        limit: int,
    ) -> tuple[str, ...]:
        identifiers = _uuid_target_keys(trigger_source_keys)
        if trigger_source_type == "player_profile":
            predicate = model.player_id.in_(identifiers)  # type: ignore[attr-defined]
        elif trigger_source_type == "match":
            predicate = model.match_id.in_(identifiers)  # type: ignore[attr-defined]
        else:
            return ()
        statement = (
            select(model.id)  # type: ignore[attr-defined]
            .where(predicate)
            .distinct()
            .order_by(model.id)  # type: ignore[attr-defined]
        )
        return await _bounded_target_ids(
            cast(AsyncSession, session), statement, limit=limit
        )

    return resolve


def _statistics_dependency_resolver(model: type[object]):
    async def resolve(
        session: object,
        *,
        trigger_source_type: str,
        trigger_source_keys: tuple[str, ...],
        limit: int,
    ) -> tuple[str, ...]:
        identifiers = _uuid_target_keys(trigger_source_keys)
        if trigger_source_type == "player_profile":
            statement = (
                select(model.id)  # type: ignore[attr-defined]
                .where(model.player_id.in_(identifiers))  # type: ignore[attr-defined]
                .distinct()
                .order_by(model.id)  # type: ignore[attr-defined]
            )
        elif trigger_source_type == "team":
            statement = (
                select(model.id)  # type: ignore[attr-defined]
                .join(TeamPlayer, TeamPlayer.player_id == model.player_id)  # type: ignore[attr-defined]
                .where(TeamPlayer.team_id.in_(identifiers))
                .distinct()
                .order_by(model.id)  # type: ignore[attr-defined]
            )
        else:
            return ()
        return await _bounded_target_ids(
            cast(AsyncSession, session), statement, limit=limit
        )

    return resolve


def _model_version(record: object) -> object | None:
    return getattr(record, "version_number", None)


def _attribute(record: object, name: str) -> object:
    """Read a known ORM attribute from generic loader records."""

    return getattr(record, name)


def _uuid_attribute(record: object, name: str) -> UUID:
    """Read and validate a UUID identity from a generic ORM record."""

    value = _attribute(record, name)
    if not isinstance(value, UUID):
        raise LoaderContractError(f"loaded source {name} must be a UUID")
    return value


def _fingerprint_value(value: object) -> object:
    """Reduce ORM relationship values to deterministic identity/version inputs."""

    if isinstance(value, Mapping):
        return {str(key): _fingerprint_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_fingerprint_value(item) for item in value)
    identifier = getattr(value, "id", None)
    if identifier is not None:
        return (identifier, getattr(value, "version_number", None))
    return value


def _model_fingerprint(record: object, relationships: Mapping[str, object]) -> str:
    return stable_component_hash(
        getattr(record, "id", None),
        getattr(record, "version_number", None),
        _fingerprint_value(relationships),
    )


def _dependency_hash(record: object, relationships: Mapping[str, object]) -> str:
    del record
    return stable_component_hash(_fingerprint_value(relationships))


async def _player_relationships(
    session: AsyncSession,
    records: Sequence[Player],
    dependencies: tuple[SourceDependency, ...],
) -> Mapping[str, Mapping[str, object]]:
    del dependencies
    rows = await session.execute(
        select(TeamPlayer.player_id, Team)
        .join(Team, Team.id == TeamPlayer.team_id)
        .where(TeamPlayer.player_id.in_([record.id for record in records]))
        .order_by(TeamPlayer.player_id, Team.name, Team.id)
        .execution_options(populate_existing=True)
    )
    teams: defaultdict[str, list[Team]] = defaultdict(list)
    for player_id, team in rows:
        teams[str(player_id)].append(team)
    return {key: {"teams": tuple(value)} for key, value in teams.items()}


async def _team_relationships(
    session: AsyncSession,
    records: Sequence[Team],
    dependencies: tuple[SourceDependency, ...],
) -> Mapping[str, Mapping[str, object]]:
    del dependencies
    team_ids = [record.id for record in records]
    roster_rows = await session.execute(
        select(TeamPlayer.team_id, Player)
        .join(Player, Player.id == TeamPlayer.player_id)
        .where(TeamPlayer.team_id.in_(team_ids), Player.is_active.is_(True))
        .order_by(TeamPlayer.team_id, TeamPlayer.roster_order, Player.id)
        .execution_options(populate_existing=True)
    )
    coach_rows = await session.execute(
        select(TeamCoach.team_id, User.first_name, User.last_name)
        .join(User, User.id == TeamCoach.user_id)
        .where(TeamCoach.team_id.in_(team_ids), User.is_active.is_(True))
        .order_by(TeamCoach.team_id, User.last_name, User.first_name)
    )
    rosters: defaultdict[str, list[Player]] = defaultdict(list)
    coaches: defaultdict[str, list[str]] = defaultdict(list)
    for team_id, player in roster_rows:
        rosters[str(team_id)].append(player)
    for team_id, first_name, last_name in coach_rows:
        coaches[str(team_id)].append(f"{first_name} {last_name}")
    return {
        str(team_id): {
            "roster": tuple(rosters[str(team_id)]),
            "coaches": tuple(coaches[str(team_id)]),
        }
        for team_id in team_ids
    }


async def _match_relationships(
    session: AsyncSession,
    records: Sequence[Match],
    dependencies: tuple[SourceDependency, ...],
) -> Mapping[str, Mapping[str, object]]:
    del dependencies
    team_ids = {
        team_id
        for record in records
        for team_id in (record.home_team_id, record.away_team_id)
        if team_id is not None
    }
    teams = {}
    if team_ids:
        teams = {
            team.id: team
            for team in (
                await session.execute(
                    select(Team)
                    .where(Team.id.in_(team_ids))
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        }
    return {
        str(record.id): {
            "home_team": (
                teams.get(record.home_team_id)
                if record.home_team_id is not None
                else None
            ),
            "away_team": (
                teams.get(record.away_team_id)
                if record.away_team_id is not None
                else None
            ),
        }
        for record in records
    }


async def _performance_relationships(
    session: AsyncSession,
    records: Sequence[object],
    dependencies: tuple[SourceDependency, ...],
) -> Mapping[str, Mapping[str, object]]:
    del dependencies
    player_ids = {_uuid_attribute(record, "player_id") for record in records}
    match_ids = {_uuid_attribute(record, "match_id") for record in records}
    players = {
        item.id: item
        for item in (
            await session.execute(
                select(Player)
                .where(Player.id.in_(player_ids))
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }
    matches = {
        item.id: item
        for item in (
            await session.execute(
                select(Match)
                .where(Match.id.in_(match_ids))
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }
    team_ids = {
        team_id
        for match in matches.values()
        for team_id in (match.home_team_id, match.away_team_id)
        if team_id is not None
    }
    teams = (
        tuple(
            (
                await session.scalars(
                    select(Team)
                    .where(Team.id.in_(team_ids))
                    .order_by(Team.id)
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        if team_ids
        else ()
    )
    return {
        str(_attribute(record, "id")): {
            "player": players.get(_uuid_attribute(record, "player_id")),
            "match": matches.get(_uuid_attribute(record, "match_id")),
            "teams": teams,
        }
        for record in records
    }


async def _statistics_relationships(
    session: AsyncSession,
    records: Sequence[object],
    dependencies: tuple[SourceDependency, ...],
) -> Mapping[str, Mapping[str, object]]:
    del dependencies
    player_ids = {_uuid_attribute(record, "player_id") for record in records}
    players = {
        item.id: item
        for item in (
            await session.execute(
                select(Player)
                .where(Player.id.in_(player_ids))
                .execution_options(populate_existing=True)
            )
        ).scalars()
    }
    team_rows = await session.execute(
        select(TeamPlayer.player_id, Team)
        .join(Team, Team.id == TeamPlayer.team_id)
        .where(TeamPlayer.player_id.in_(player_ids))
        .order_by(TeamPlayer.player_id, Team.name, Team.id)
        .execution_options(populate_existing=True)
    )
    teams: defaultdict[UUID, list[Team]] = defaultdict(list)
    for player_id, team in team_rows:
        teams[player_id].append(team)
    return {
        str(_attribute(record, "id")): {
            "player": players.get(_uuid_attribute(record, "player_id")),
            "teams": tuple(teams[_uuid_attribute(record, "player_id")]),
        }
        for record in records
    }


def _loader[RecordT](
    model: type[RecordT],
    *,
    dependencies: tuple[SourceDependency, ...] = (),
    relationship_loader: RelationshipDependencyLoader[RecordT] | None = None,
    active_only: bool = False,
) -> BoundedSetBasedLoader[RecordT]:
    fetch = _model_cursor_page(model)
    if active_only:

        async def fetch_active(
            session: AsyncSession, *, cursor: str | None, limit: int
        ) -> FetchedSourcePage[RecordT]:
            statement = (
                select(model)
                .where(Player.is_active.is_(True))
                .order_by(model.id)  # type: ignore[attr-defined]
                .limit(limit)
                .execution_options(populate_existing=True)
            )
            if cursor is not None:
                statement = statement.where(model.id > UUID(cursor))  # type: ignore[attr-defined]
            rows = tuple((await session.execute(statement)).scalars().all())
            return FetchedSourcePage(
                records=rows,
                next_cursor=(str(rows[-1].id) if len(rows) == limit else None),  # type: ignore[attr-defined]
            )

        fetch = fetch_active
    return BoundedSetBasedLoader(
        fetch_page=fetch,
        fetch_targets=_model_target_page(model),
        source_key=lambda record: _attribute(record, "id"),
        source_version=_model_version,
        source_fingerprint=_model_fingerprint,
        dependencies=dependencies,
        load_relationships=relationship_loader,
        dependency_fingerprint=_dependency_hash,
    )


player_profile_loader = _loader(
    Player,
    active_only=True,
    dependencies=(
        SourceDependency(
            "team_memberships",
            trigger_source_types=("team",),
            target_resolver=_players_for_team_dependency,
        ),
    ),
    relationship_loader=_player_relationships,
)
team_loader = _loader(
    Team,
    dependencies=(
        SourceDependency(
            "active_roster",
            trigger_source_types=("player_profile",),
            target_resolver=_teams_for_player_dependency,
        ),
        SourceDependency("coaching_context"),
    ),
    relationship_loader=_team_relationships,
)
match_loader = _loader(
    Match,
    dependencies=(
        SourceDependency(
            "explicit_participants",
            trigger_source_types=("team",),
            target_resolver=_matches_for_team_dependency,
        ),
    ),
    relationship_loader=_match_relationships,
)
batting_performance_loader = _loader(
    MatchBattingPerformance,
    dependencies=(
        SourceDependency(
            "player_match",
            trigger_source_types=("player_profile", "match"),
            target_resolver=_performance_dependency_resolver(MatchBattingPerformance),
        ),
    ),
    relationship_loader=_performance_relationships,
)
bowling_performance_loader = _loader(
    MatchBowlingPerformance,
    dependencies=(
        SourceDependency(
            "player_match",
            trigger_source_types=("player_profile", "match"),
            target_resolver=_performance_dependency_resolver(MatchBowlingPerformance),
        ),
    ),
    relationship_loader=_performance_relationships,
)
fielding_performance_loader = _loader(
    MatchFieldingPerformance,
    dependencies=(
        SourceDependency(
            "player_match",
            trigger_source_types=("player_profile", "match"),
            target_resolver=_performance_dependency_resolver(MatchFieldingPerformance),
        ),
    ),
    relationship_loader=_performance_relationships,
)
batting_statistics_loader = _loader(
    PlayerBattingStats,
    dependencies=(
        SourceDependency(
            "player",
            trigger_source_types=("player_profile",),
            target_resolver=_statistics_dependency_resolver(PlayerBattingStats),
        ),
        SourceDependency(
            "team_memberships",
            trigger_source_types=("team",),
            target_resolver=_statistics_dependency_resolver(PlayerBattingStats),
        ),
    ),
    relationship_loader=_statistics_relationships,
)
bowling_statistics_loader = _loader(
    PlayerBowlingStats,
    dependencies=(
        SourceDependency(
            "player",
            trigger_source_types=("player_profile",),
            target_resolver=_statistics_dependency_resolver(PlayerBowlingStats),
        ),
        SourceDependency(
            "team_memberships",
            trigger_source_types=("team",),
            target_resolver=_statistics_dependency_resolver(PlayerBowlingStats),
        ),
    ),
    relationship_loader=_statistics_relationships,
)


class CalendarOccurrenceLoader:
    """Bounded page loader over CalendarService's effective occurrence projection."""

    async def _project(
        self,
        session: object,
    ) -> tuple[CalendarEventInstance, ...]:
        now = datetime.now(UTC)
        occurrences = await load_projected_calendar_occurrences(
            CalendarService(cast(AsyncSession, session), now=now), now=now
        )
        return tuple(sorted(occurrences, key=lambda item: item.occurrence_id))

    @staticmethod
    def _prepare(
        page: Sequence[CalendarEventInstance],
        *,
        next_cursor: str | None = None,
    ) -> SourceLoadBatch[LoadedSourceRecord[CalendarEventInstance]]:
        records = tuple(
            LoadedSourceRecord(
                record=item,
                source_key=item.occurrence_id,
                source_version=(
                    f"event:{item.event_version_number}:"
                    f"exception:{item.exception_version_number or 0}"
                ),
                source_fingerprint=stable_component_hash(
                    item.occurrence_id,
                    item.event_date,
                    item.event_version_number,
                    item.exception_version_number,
                ),
                dependency_fingerprint=stable_component_hash(
                    item.series_id, item.original_date, item.age_groups, item.scope_kind
                ),
                relationships={},
            )
            for item in page
        )
        return SourceLoadBatch(items=records, next_cursor=next_cursor)

    async def load_batch(
        self, session: object, *, cursor: str | None, limit: int
    ) -> SourceLoadBatch[LoadedSourceRecord[CalendarEventInstance]]:
        if limit <= 0:
            raise LoaderContractError("loader batch limit must be positive")
        ordered = await self._project(session)
        bounded_limit = min(limit, MAX_SOURCE_BATCH_SIZE)
        page = tuple(
            item for item in ordered if cursor is None or item.occurrence_id > cursor
        )[:bounded_limit]
        return self._prepare(
            page,
            next_cursor=(
                page[-1].occurrence_id if len(page) == bounded_limit else None
            ),
        )

    async def load_targets(
        self,
        session: object,
        *,
        source_keys: Sequence[str],
        limit: int,
    ) -> SourceLoadBatch[LoadedSourceRecord[CalendarEventInstance]]:
        """Filter the existing bounded effective-occurrence projection by stable key."""

        if not 1 <= len(source_keys) <= min(limit, MAX_SOURCE_BATCH_SIZE):
            raise LoaderContractError("calendar target keys exceed the bounded limit")
        normalized = tuple(str(key).strip() for key in source_keys)
        if any(not key for key in normalized) or len(normalized) != len(
            set(normalized)
        ):
            raise LoaderContractError(
                "calendar target keys must be unique and non-blank"
            )
        requested = set(normalized)
        projected = await self._project(session)
        page = tuple(item for item in projected if item.occurrence_id in requested)
        return self._prepare(page)


calendar_occurrence_loader = CalendarOccurrenceLoader()
