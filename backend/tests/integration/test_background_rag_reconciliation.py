"""Targeted background RAG reconciliation integration coverage."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.database import AsyncSessionFactory
from src.enums import (
    BattingStyle,
    BowlingStyle,
    DismissalType,
    MatchFormat,
    MatchParticipantType,
    PlayerType,
    UserRole,
)
from src.models.auth_audit_log import AuthAuditLog
from src.models.background_work_item import BackgroundWorkItem
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.schemas.rag import RagRetrievalRequest
from src.services.rag.contracts import (
    RagMutationImpact,
    RagMutationOperation,
    RagMutationRef,
    RagMutationSource,
    RagTargetRef,
)
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from src.services.rag.registry import get_rag_mutation_stager
from src.services.rag.retrieval import RagRetrievalService


def _player(player_id, *, first_name: str, active: bool = True) -> Player:
    return Player(
        id=player_id,
        first_name=first_name,
        last_name="Targeted",
        date_of_birth=date(2012, 3, 2),
        bio="Targeted reconciliation source",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=active,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_targeted_reconciliation_reloads_closure_and_replays() -> None:
    player_id, unrelated_player_id, team_id, match_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    batting_id, bowling_id, fielding_id = uuid4(), uuid4(), uuid4()
    batting_stats_id, bowling_stats_id = uuid4(), uuid4()
    head = User(
        id=uuid4(),
        first_name="RAG",
        last_name="Operator",
        email=f"rag-operator-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=UserRole.HEAD_COACH,
        is_active=True,
    )
    team = Team(id=team_id, name="Targeted U13", age_group="U13")
    player = _player(player_id, first_name="InitialAsha")
    unrelated = _player(unrelated_player_id, first_name="UnrelatedMaya")
    match = Match(
        id=match_id,
        match_date=date(2026, 8, 19),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=team_id,
        away_team_id=None,
        external_opponent_name="Visitors",
        venue="North Oval",
        result="Won",
    )
    provider = FakeEmbeddingProvider()

    async with AsyncSessionFactory() as session:
        session.add_all([head, team, player, unrelated])
        await session.commit()
        session.add_all(
            [
                TeamPlayer(team_id=team_id, player_id=player_id, roster_order=1),
                match,
            ]
        )
        await session.commit()
        session.add_all(
            [
                MatchBattingPerformance(
                    id=batting_id,
                    player_id=player_id,
                    match_id=match_id,
                    runs_scored=42,
                    balls_faced=31,
                    dismissal=DismissalType.CAUGHT,
                    fours=6,
                    sixes=1,
                ),
                MatchBowlingPerformance(
                    id=bowling_id,
                    player_id=player_id,
                    match_id=match_id,
                    overs_bowled=Decimal("4.0"),
                    maidens=0,
                    runs_conceded=18,
                    wickets_taken=2,
                    wides=1,
                ),
                MatchFieldingPerformance(
                    id=fielding_id,
                    player_id=player_id,
                    match_id=match_id,
                    catches=1,
                    stumpings=0,
                    run_outs=0,
                    dropped_catches=0,
                ),
                PlayerBattingStats(
                    id=batting_stats_id,
                    player_id=player_id,
                    format=MatchFormat.T20,
                    matches=1,
                    innings=1,
                    not_outs=0,
                    runs=42,
                    balls_faced=31,
                    high_score=42,
                    hundreds=0,
                    fifties=0,
                    ducks=0,
                    fours=6,
                    sixes=1,
                ),
                PlayerBowlingStats(
                    id=bowling_stats_id,
                    player_id=player_id,
                    format=MatchFormat.T20,
                    matches=1,
                    innings=1,
                    overs_bowled=Decimal("4.0"),
                    runs_conceded=18,
                    wickets=2,
                    best_bowled="2/18",
                    maidens=0,
                    four_wicket_hauls=0,
                    five_wicket_hauls=0,
                    wides=1,
                    catches=1,
                ),
            ]
        )
        await session.commit()
        before_business = int(
            await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0
        )
        before_auth = int(
            await session.scalar(select(func.count(AuthAuditLog.id))) or 0
        )

        # The queued stable ID is only an instruction. Current committed state wins.
        player.first_name = "CurrentAsha"
        player.version_number += 1
        await session.commit()
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=16,
            timeout_seconds=30,
        )
        reports = await service.reconcile_targets(
            (RagTargetRef(source_type="player_profile", source_key=str(player_id)),)
        )

        assert reports and all(report.status.value == "completed" for report in reports)
        documents = tuple((await session.scalars(select(RagDocument))).all())
        source_types = {document.source_type for document in documents}
        assert source_types == {
            "player_profile",
            "team",
            "match_batting_performance",
            "match_bowling_performance",
            "match_fielding_performance",
            "player_batting_stats",
            "player_bowling_stats",
        }
        assert not any(
            document.source_key == str(unrelated_player_id) for document in documents
        )
        player_document = next(
            document
            for document in documents
            if document.source_type == "player_profile"
        )
        assert "CurrentAsha" in player_document.semantic_text
        assert "InitialAsha" not in player_document.semantic_text

        # Exercise direct Match/performance/statistics targeting without a corpus run.
        direct_reports = await service.reconcile_targets(
            (
                RagTargetRef(source_type="match", source_key=str(match_id)),
                RagTargetRef(
                    source_type="match_batting_performance",
                    source_key=str(batting_id),
                ),
                RagTargetRef(
                    source_type="player_batting_stats",
                    source_key=str(batting_stats_id),
                ),
            )
        )
        assert all(report.status.value == "completed" for report in direct_reports)

        counts_before_replay = (
            int(await session.scalar(select(func.count(RagSourceState.id))) or 0),
            int(await session.scalar(select(func.count(RagDocument.id))) or 0),
            int(await session.scalar(select(func.count(RagChunk.id))) or 0),
        )
        calls_before_replay = provider.document_call_count
        replay = await service.reconcile_targets(
            (RagTargetRef(source_type="player_profile", source_key=str(player_id)),)
        )
        counts_after_replay = (
            int(await session.scalar(select(func.count(RagSourceState.id))) or 0),
            int(await session.scalar(select(func.count(RagDocument.id))) or 0),
            int(await session.scalar(select(func.count(RagChunk.id))) or 0),
        )
        assert all(report.status.value == "completed" for report in replay)
        assert counts_after_replay == counts_before_replay
        assert provider.document_call_count == calls_before_replay
        active_duplicates = (
            await session.execute(
                select(RagDocument.source_type, RagDocument.source_key)
                .where(RagDocument.is_searchable.is_(True))
                .group_by(RagDocument.source_type, RagDocument.source_key)
                .having(func.count(RagDocument.id) > 1)
            )
        ).all()
        assert active_duplicates == []

        retrieval = await RagRetrievalService(
            session,
            provider=provider,
            query_max_characters=200,
            result_limit_default=20,
            result_limit_max=20,
            timeout_seconds=5,
        ).retrieve(
            head,
            RagRetrievalRequest(query="CurrentAsha Targeted", limit=20),
        )
        assert any(result.source_key == str(player_id) for result in retrieval.results)
        assert (
            int(await session.scalar(select(func.count(BusinessAuditEvent.id))) or 0)
            == before_business
        )
        assert (
            int(await session.scalar(select(func.count(AuthAuditLog.id))) or 0)
            == before_auth
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_targeted_reconciliation_marks_ineligible_and_deleted_sources() -> None:
    player_id = uuid4()
    provider = FakeEmbeddingProvider()
    async with AsyncSessionFactory() as session:
        player = _player(player_id, first_name="Lifecycle")
        session.add(player)
        await session.commit()
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=8,
            timeout_seconds=30,
        )
        target = RagTargetRef(source_type="player_profile", source_key=str(player_id))
        await service.reconcile_targets((target,))

        player.is_active = False
        player.version_number += 1
        await session.commit()
        await service.reconcile_targets((target,))
        state = await session.scalar(
            select(RagSourceState).where(
                RagSourceState.source_type == "player_profile",
                RagSourceState.source_key == str(player_id),
            )
        )
        assert state is not None and state.status == "ineligible"

        await session.delete(player)
        await session.commit()
        await service.reconcile_targets((target,))
        await session.refresh(state)
        assert state.status == "deleted"
        assert not (
            await session.scalars(
                select(RagDocument).where(
                    RagDocument.source_key == str(player_id),
                    RagDocument.is_searchable.is_(True),
                )
            )
        ).all()


@pytest.mark.asyncio(loop_scope="session")
async def test_rag_work_coalesces_targets_and_running_work_gets_successor() -> None:
    first, second = uuid4(), uuid4()
    stager = get_rag_mutation_stager()
    team_ref = RagMutationRef(source=RagMutationSource.TEAM, source_key=str(first))
    player_ref = RagMutationRef(
        source=RagMutationSource.PLAYER,
        source_key=str(second),
    )
    async with AsyncSessionFactory() as session:
        first_work = await stager.stage(
            session,
            RagMutationImpact(
                operation=RagMutationOperation.UPSERT,
                current_refs=(team_ref,),
                coalescing_ref=team_ref,
            ),
        )
        merged = await stager.stage(
            session,
            RagMutationImpact(
                operation=RagMutationOperation.RELATIONSHIP,
                current_refs=(team_ref, player_ref),
                coalescing_ref=team_ref,
            ),
        )
        await session.flush()
        assert first_work is not None and merged is not None
        assert first_work.id == merged.id
        assert len(merged.payload["targets"]) == 2

        merged.state = "running"
        merged.lease_owner = "worker:test"
        merged.lease_expires_at = merged.run_after
        await session.flush()
        successor = await stager.stage(
            session,
            RagMutationImpact(
                operation=RagMutationOperation.UPSERT,
                current_refs=(team_ref,),
                coalescing_ref=team_ref,
            ),
        )
        await session.flush()

        assert successor is not None and successor.id != merged.id
        active = tuple(
            (
                await session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.coalescing_key == f"rag:team:{first}"
                    )
                )
            ).all()
        )
        assert {item.state for item in active} == {"running", "pending"}
