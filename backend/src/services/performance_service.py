"""Atomic match performance persistence and aggregate recalculation."""

from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import (
    DismissalType,
    MatchFormat,
    ScoringAuthority,
    ScoringDismissalType,
)
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.models.scoring.innings import Innings
from src.models.scoring.match_participant_performance import (
    MatchParticipantPerformance,
)
from src.models.scoring.over import InningsOver
from src.models.scoring.participant import MatchParticipant
from src.models.user import User
from src.schemas.performance import (
    BatchPerformanceResponse,
    DerivedParticipantPerformanceResponse,
    LegacyBattingPerformanceResponse,
    LegacyBowlingPerformanceResponse,
    LegacyFieldingPerformanceResponse,
    MatchPerformanceResponse,
    PlayerPerformance,
)
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
        (reference.source, reference.source_key): reference for reference in references
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


_DELIVERY_DERIVED_NOTE = "[delivery_derived] synchronized scoring projection"


def _legacy_dismissal(value: ScoringDismissalType | None) -> DismissalType:
    if value is None:
        return DismissalType.NOT_OUT
    return {
        ScoringDismissalType.CAUGHT: DismissalType.CAUGHT,
        ScoringDismissalType.CAUGHT_AND_BOWLED: DismissalType.CAUGHT,
        ScoringDismissalType.BOWLED: DismissalType.BOWLED,
        ScoringDismissalType.LBW: DismissalType.LBW,
        ScoringDismissalType.RUN_OUT: DismissalType.RUN_OUT,
        ScoringDismissalType.STUMPED: DismissalType.STUMPED,
    }.get(value, DismissalType.OTHER)


async def sync_delivery_derived_legacy_performances(
    session: AsyncSession,
    *,
    match_id: UUID,
    over_length_legal_balls: int,
) -> None:
    """Synchronize academy-only compatibility rows without creating scoring truth."""

    query_result = await session.execute(
        select(MatchParticipant, MatchParticipantPerformance)
        .join(
            MatchParticipantPerformance,
            MatchParticipantPerformance.participant_id == MatchParticipant.id,
        )
        .where(
            MatchParticipant.match_id == match_id,
            MatchParticipant.player_id.is_not(None),
        )
        .order_by(
            MatchParticipant.player_id,
            MatchParticipantPerformance.innings_id,
        )
    )
    rows = query_result.all()
    if hasattr(rows, "__await__"):
        rows = await rows
    rows = list(rows)
    grouped: defaultdict[UUID, list[MatchParticipantPerformance]] = defaultdict(list)
    for participant, performance in rows:
        if participant.player_id is not None:
            grouped[participant.player_id].append(performance)
    if not grouped:
        return

    player_ids = set(grouped)
    batting_by_player = {
        row.player_id: row
        for row in (
            await session.scalars(
                select(MatchBattingPerformance).where(
                    MatchBattingPerformance.match_id == match_id,
                    MatchBattingPerformance.player_id.in_(player_ids),
                )
            )
        ).all()
    }
    bowling_by_player = {
        row.player_id: row
        for row in (
            await session.scalars(
                select(MatchBowlingPerformance).where(
                    MatchBowlingPerformance.match_id == match_id,
                    MatchBowlingPerformance.player_id.in_(player_ids),
                )
            )
        ).all()
    }
    fielding_by_player = {
        row.player_id: row
        for row in (
            await session.scalars(
                select(MatchFieldingPerformance).where(
                    MatchFieldingPerformance.match_id == match_id,
                    MatchFieldingPerformance.player_id.in_(player_ids),
                )
            )
        ).all()
    }
    maiden_rows = (
        await session.execute(
            select(MatchParticipant.player_id, func.count(InningsOver.id))
            .join(
                InningsOver,
                InningsOver.bowler_participant_id == MatchParticipant.id,
            )
            .join(Innings, Innings.id == InningsOver.innings_id)
            .where(
                Innings.match_id == match_id,
                InningsOver.is_complete.is_(True),
                InningsOver.runs_conceded == 0,
                MatchParticipant.player_id.is_not(None),
            )
            .group_by(MatchParticipant.player_id)
        )
    ).all()
    maidens = {player_id: int(count) for player_id, count in maiden_rows}

    def writable(record: object | None) -> bool:
        return record is None or str(getattr(record, "notes", "") or "").startswith(
            "[delivery_derived]"
        )

    for player_id, performances in grouped.items():
        dismissal = next(
            (
                item.dismissal_type
                for item in reversed(performances)
                if item.dismissal_type is not None
            ),
            None,
        )
        batting_values = {
            "runs_scored": sum(item.batting_runs for item in performances),
            "balls_faced": sum(item.balls_faced for item in performances),
            "dismissal": _legacy_dismissal(dismissal),
            "fours": sum(item.fours for item in performances),
            "sixes": sum(item.sixes for item in performances),
            "notes": _DELIVERY_DERIVED_NOTE,
        }
        bowling_legal_balls = sum(item.bowling_legal_balls for item in performances)
        bowling_values = {
            "overs_bowled": Decimal(
                f"{bowling_legal_balls // over_length_legal_balls}."
                f"{bowling_legal_balls % over_length_legal_balls}"
            ),
            "maidens": maidens.get(player_id, 0),
            "runs_conceded": sum(item.runs_conceded for item in performances),
            "wickets_taken": sum(item.bowling_wickets for item in performances),
            "wides": sum(item.wides for item in performances),
            "notes": _DELIVERY_DERIVED_NOTE,
        }
        fielding_values = {
            "catches": sum(item.catches for item in performances),
            "stumpings": sum(item.stumpings for item in performances),
            "run_outs": sum(item.run_out_involvements for item in performances),
            "dropped_catches": 0,
            "notes": _DELIVERY_DERIVED_NOTE,
        }
        for model, existing, values in (
            (MatchBattingPerformance, batting_by_player.get(player_id), batting_values),
            (MatchBowlingPerformance, bowling_by_player.get(player_id), bowling_values),
            (
                MatchFieldingPerformance,
                fielding_by_player.get(player_id),
                fielding_values,
            ),
        ):
            if not writable(existing):
                continue
            if existing is None:
                session.add(model(match_id=match_id, player_id=player_id, **values))
            else:
                for field, value in values.items():
                    setattr(existing, field, value)
                existing.version_number += 1


class PerformanceService:
    """Write performance batches and derived career totals atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def submit_batch_performance(
        self,
        match_id: UUID,
        performances: list[PlayerPerformance],
        authenticated_user: User | UUID | None = None,
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
                match = await self.session.scalar(
                    select(Match)
                    .options(selectinload(Match.scoring_sides))
                    .where(Match.id == match_id)
                )
                if match is None:
                    raise MatchNotFoundError
                if ScoringAuthority(match.scoring_authority) is (
                    ScoringAuthority.DELIVERY_HISTORY
                ):
                    from src.services.scoring.errors import ScoringAuthorityError

                    raise ScoringAuthorityError(
                        "Direct aggregate performance writes are disabled for a "
                        "delivery-history Match."
                    )
                if authenticated_user is not None:
                    from src.services.scoring.authorization import (
                        ScoringAuthorizationAdapter,
                        require_scoring_mutation_scope,
                    )

                    context = await ScoringAuthorizationAdapter(
                        self.session
                    ).load_context(authenticated_user)
                    require_scoring_mutation_scope(context, match)

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

    async def get_match_performances(
        self,
        match_id: UUID,
        authenticated_user: User | UUID,
    ) -> MatchPerformanceResponse:
        """Read legacy aggregates or canonical delivery-derived projections."""

        from src.services.scoring.authorization import (
            ScoringAuthorizationAdapter,
            require_scoring_read_scope,
        )

        match = await self.session.scalar(
            select(Match)
            .options(selectinload(Match.scoring_sides))
            .where(Match.id == match_id)
        )
        if match is None:
            raise MatchNotFoundError
        context = await ScoringAuthorizationAdapter(self.session).load_context(
            authenticated_user
        )
        require_scoring_read_scope(context, match)
        authority = ScoringAuthority(match.scoring_authority)
        if authority is ScoringAuthority.DELIVERY_HISTORY:
            rows = list(
                (
                    await self.session.scalars(
                        select(MatchParticipantPerformance)
                        .where(MatchParticipantPerformance.match_id == match_id)
                        .order_by(
                            MatchParticipantPerformance.innings_id,
                            MatchParticipantPerformance.participant_id,
                        )
                    )
                ).all()
            )
            participant_ids = {row.participant_id for row in rows}
            participants = {
                item.id: item
                for item in (
                    await self.session.scalars(
                        select(MatchParticipant).where(
                            MatchParticipant.id.in_(participant_ids)
                        )
                    )
                ).all()
            }
            return MatchPerformanceResponse(
                match_id=match_id,
                scoring_authority=authority,
                derived=[
                    DerivedParticipantPerformanceResponse(
                        participant_id=row.participant_id,
                        innings_id=row.innings_id,
                        player_id=participants[row.participant_id].player_id,
                        display_name=participants[
                            row.participant_id
                        ].display_name_snapshot,
                        **{
                            field: getattr(row, field)
                            for field in (
                                "batting_runs",
                                "balls_faced",
                                "fours",
                                "sixes",
                                "dismissal_type",
                                "bowling_legal_balls",
                                "runs_conceded",
                                "bowling_wickets",
                                "wides",
                                "no_balls",
                                "extras_conceded",
                                "catches",
                                "stumpings",
                                "run_out_involvements",
                                "projection_revision",
                                "provenance",
                            )
                        },
                    )
                    for row in rows
                ],
            )

        batting = list(
            (
                await self.session.scalars(
                    select(MatchBattingPerformance)
                    .where(MatchBattingPerformance.match_id == match_id)
                    .order_by(MatchBattingPerformance.player_id)
                )
            ).all()
        )
        bowling = list(
            (
                await self.session.scalars(
                    select(MatchBowlingPerformance)
                    .where(MatchBowlingPerformance.match_id == match_id)
                    .order_by(MatchBowlingPerformance.player_id)
                )
            ).all()
        )
        fielding = list(
            (
                await self.session.scalars(
                    select(MatchFieldingPerformance)
                    .where(MatchFieldingPerformance.match_id == match_id)
                    .order_by(MatchFieldingPerformance.player_id)
                )
            ).all()
        )
        return MatchPerformanceResponse(
            match_id=match_id,
            scoring_authority=authority,
            legacy_batting=[
                LegacyBattingPerformanceResponse.model_validate(
                    row, from_attributes=True
                )
                for row in batting
            ],
            legacy_bowling=[
                LegacyBowlingPerformanceResponse.model_validate(
                    row, from_attributes=True
                )
                for row in bowling
            ],
            legacy_fielding=[
                LegacyFieldingPerformanceResponse.model_validate(
                    row, from_attributes=True
                )
                for row in fielding
            ],
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
