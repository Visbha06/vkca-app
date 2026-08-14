"""Atomic match performance persistence and aggregate recalculation."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import DismissalType, MatchFormat
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.schemas.performance import BatchPerformanceResponse, PlayerPerformance
from src.services.occ import StaleVersionError
from src.services.rag.contracts import (
    RagMutationImpact,
    RagMutationOperation,
    RagMutationRef,
    RagMutationSource,
)


async def _stage_performance_impacts(
    session: AsyncSession,
    references: list[RagMutationRef],
) -> None:
    from src.services.rag.registry import stage_rag_mutation_impact

    unique = {
        (reference.source, reference.source_key): reference
        for reference in references
    }
    ordered = tuple(unique[key] for key in sorted(unique, key=lambda item: str(item)))
    if not ordered:
        return
    await stage_rag_mutation_impact(
        session,
        RagMutationImpact(
            operation=RagMutationOperation.UPSERT,
            current_refs=ordered,
            coalescing_ref=ordered[0],
        ),
    )


class MatchNotFoundError(Exception):
    """Raised when a performance batch references an unknown match."""

    def __init__(self) -> None:
        super().__init__("Match not found.")


class PlayerNotFoundError(Exception):
    """Raised when a performance batch references an unknown player."""

    def __init__(self, player_id: UUID) -> None:
        self.player_id = player_id
        super().__init__(f"Player not found: {player_id}.")


class PerformanceService:
    """Write performance batches and derived career totals atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_batch_performance(
        self,
        match_id: UUID,
        performances: list[PlayerPerformance],
    ) -> BatchPerformanceResponse:
        """Persist one validated batch and recalculate affected aggregate rows."""

        batting_records = 0
        bowling_records = 0
        fielding_records = 0
        stats_players: set[UUID] = set()
        performance_sources: list[tuple[RagMutationSource, Any]] = []
        statistic_refs: list[RagMutationRef] = []

        transaction = (
            self.session.begin_nested()
            if self.session.in_transaction()
            else self.session.begin()
        )
        try:
            async with transaction:
                match = await self.session.get(Match, match_id)
                if match is None:
                    raise MatchNotFoundError

                requested_player_ids = {item.player_id for item in performances}
                existing_player_ids = set(
                    (
                        await self.session.scalars(
                            select(Player.id).where(Player.id.in_(requested_player_ids))
                        )
                    ).all()
                )
                missing_player_ids = requested_player_ids - existing_player_ids
                if missing_player_ids:
                    missing_id = min(missing_player_ids, key=str)
                    raise PlayerNotFoundError(missing_id)

                for item in performances:
                    if item.batting is not None:
                        batting_record = MatchBattingPerformance(
                            player_id=item.player_id,
                            match_id=match_id,
                            **item.batting.model_dump(),
                        )
                        self.session.add(batting_record)
                        performance_sources.append(
                            (
                                RagMutationSource.MATCH_BATTING_PERFORMANCE,
                                batting_record,
                            )
                        )
                        batting_records += 1
                    if item.bowling is not None:
                        bowling_record = MatchBowlingPerformance(
                            player_id=item.player_id,
                            match_id=match_id,
                            **item.bowling.model_dump(),
                        )
                        self.session.add(bowling_record)
                        performance_sources.append(
                            (
                                RagMutationSource.MATCH_BOWLING_PERFORMANCE,
                                bowling_record,
                            )
                        )
                        bowling_records += 1
                    if item.fielding is not None:
                        fielding_record = MatchFieldingPerformance(
                            player_id=item.player_id,
                            match_id=match_id,
                            **item.fielding.model_dump(),
                        )
                        self.session.add(fielding_record)
                        performance_sources.append(
                            (
                                RagMutationSource.MATCH_FIELDING_PERFORMANCE,
                                fielding_record,
                            )
                        )
                        fielding_records += 1

                await self.session.flush()

                for item in performances:
                    if item.batting is not None:
                        stats_id = await self._recalculate_batting_stats(
                            item.player_id,
                            match.format,
                        )
                        statistic_refs.append(
                            RagMutationRef(
                                source=RagMutationSource.PLAYER_BATTING_STATS,
                                source_key=str(stats_id),
                            )
                        )
                        stats_players.add(item.player_id)
                    if item.bowling is not None or item.fielding is not None:
                        stats_id = await self._recalculate_bowling_stats(
                            item.player_id,
                            match.format,
                        )
                        statistic_refs.append(
                            RagMutationRef(
                                source=RagMutationSource.PLAYER_BOWLING_STATS,
                                source_key=str(stats_id),
                            )
                        )
                        stats_players.add(item.player_id)
                performance_refs = [
                    RagMutationRef(
                        source=source,
                        source_key=str(record.id),
                    )
                    for source, record in performance_sources
                ]
                await _stage_performance_impacts(
                    self.session,
                    [*performance_refs, *statistic_refs],
                )
            if self.session.in_transaction():
                await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return BatchPerformanceResponse(
            match_id=match_id,
            performances_created=len(performances),
            batting_records=batting_records,
            bowling_records=bowling_records,
            fielding_records=fielding_records,
            players_stats_updated=len(stats_players),
        )

    async def _recalculate_batting_stats(
        self,
        player_id: UUID,
        match_format: MatchFormat,
    ) -> UUID:
        """Recompute one player's batting totals from source performances."""

        await self._lock_stats_key(PlayerBattingStats, player_id, match_format)
        performance = MatchBattingPerformance
        statement = (
            select(
                func.count(performance.id).label("matches"),
                func.count(performance.id).label("innings"),
                func.count()
                .filter(performance.dismissal == DismissalType.NOT_OUT)
                .label("not_outs"),
                func.coalesce(func.sum(performance.runs_scored), 0).label("runs"),
                func.coalesce(func.sum(performance.balls_faced), 0).label(
                    "balls_faced"
                ),
                func.coalesce(func.max(performance.runs_scored), 0).label("high_score"),
                func.count().filter(performance.runs_scored >= 100).label("hundreds"),
                func.count()
                .filter(
                    performance.runs_scored >= 50,
                    performance.runs_scored < 100,
                )
                .label("fifties"),
                func.count().filter(performance.runs_scored == 0).label("ducks"),
                func.coalesce(func.sum(performance.fours), 0).label("fours"),
                func.coalesce(func.sum(performance.sixes), 0).label("sixes"),
            )
            .join(Match, Match.id == performance.match_id)
            .where(
                performance.player_id == player_id,
                Match.format == match_format,
            )
        )
        totals = (await self.session.execute(statement)).mappings().one()
        values = {key: int(value) for key, value in totals.items()}
        return await self._upsert_stats(
            PlayerBattingStats,
            player_id,
            match_format,
            values,
        )

    async def _recalculate_bowling_stats(
        self,
        player_id: UUID,
        match_format: MatchFormat,
    ) -> UUID:
        """Recompute one player's bowling totals and fielding catches."""

        await self._lock_stats_key(PlayerBowlingStats, player_id, match_format)
        performance = MatchBowlingPerformance
        statement = (
            select(
                func.count(performance.id).label("matches"),
                func.count(performance.id).label("innings"),
                func.coalesce(func.sum(performance.overs_bowled), 0).label(
                    "overs_bowled"
                ),
                func.coalesce(func.sum(performance.runs_conceded), 0).label(
                    "runs_conceded"
                ),
                func.coalesce(func.sum(performance.wickets_taken), 0).label("wickets"),
                func.coalesce(func.sum(performance.maidens), 0).label("maidens"),
                func.count()
                .filter(
                    performance.wickets_taken >= 4,
                    performance.wickets_taken < 5,
                )
                .label("four_wicket_hauls"),
                func.count()
                .filter(performance.wickets_taken >= 5)
                .label("five_wicket_hauls"),
                func.coalesce(func.sum(performance.wides), 0).label("wides"),
            )
            .join(Match, Match.id == performance.match_id)
            .where(
                performance.player_id == player_id,
                Match.format == match_format,
            )
        )
        totals = dict((await self.session.execute(statement)).mappings().one())

        best_figures = (
            await self.session.execute(
                select(performance.wickets_taken, performance.runs_conceded)
                .join(Match, Match.id == performance.match_id)
                .where(
                    performance.player_id == player_id,
                    Match.format == match_format,
                )
                .order_by(
                    performance.wickets_taken.desc(),
                    performance.runs_conceded.asc(),
                )
                .limit(1)
            )
        ).one_or_none()
        catches = await self.session.scalar(
            select(func.coalesce(func.sum(MatchFieldingPerformance.catches), 0))
            .join(Match, Match.id == MatchFieldingPerformance.match_id)
            .where(
                MatchFieldingPerformance.player_id == player_id,
                Match.format == match_format,
            )
        )

        values: dict[str, Any] = {
            "matches": int(totals["matches"]),
            "innings": int(totals["innings"]),
            "overs_bowled": Decimal(totals["overs_bowled"]),
            "runs_conceded": int(totals["runs_conceded"]),
            "wickets": int(totals["wickets"]),
            "best_bowled": (
                f"{best_figures.wickets_taken}/{best_figures.runs_conceded}"
                if best_figures is not None
                else None
            ),
            "maidens": int(totals["maidens"]),
            "four_wicket_hauls": int(totals["four_wicket_hauls"]),
            "five_wicket_hauls": int(totals["five_wicket_hauls"]),
            "wides": int(totals["wides"]),
            "catches": int(catches or 0),
        }
        return await self._upsert_stats(
            PlayerBowlingStats,
            player_id,
            match_format,
            values,
        )

    async def _lock_stats_key(
        self,
        model: type[PlayerBattingStats] | type[PlayerBowlingStats],
        player_id: UUID,
        match_format: MatchFormat,
    ) -> None:
        """Serialize recalculations even before an aggregate row exists."""

        lock_key = f"{model.__tablename__}:{player_id}:{match_format}"
        await self.session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0)))
        )

    async def _upsert_stats(
        self,
        model: type[PlayerBattingStats] | type[PlayerBowlingStats],
        player_id: UUID,
        match_format: MatchFormat,
        values: Mapping[str, Any],
    ) -> UUID:
        """Insert aggregates or update them with a version-guarded write."""

        model_type: Any = model
        existing = await self.session.scalar(
            select(model_type)
            .where(
                model_type.player_id == player_id,
                model_type.format == match_format,
            )
            .with_for_update()
        )
        if existing is None:
            created = model_type(
                player_id=player_id,
                format=match_format,
                **dict(values),
            )
            self.session.add(created)
            await self.session.flush()
            return created.id

        incoming_version = existing.version_number
        statement = (
            update(model_type)
            .where(
                model_type.id == existing.id,
                model_type.version_number == incoming_version,
            )
            .values(
                **dict(values),
                version_number=incoming_version + 1,
                updated_at=func.now(),
            )
            .returning(model_type.version_number)
        )
        new_version = (await self.session.execute(statement)).scalar_one_or_none()
        if new_version is None:
            raise StaleVersionError(
                model_type,
                existing.id,
                incoming_version,
            )
        return existing.id
