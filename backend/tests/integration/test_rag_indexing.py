"""Full-build coverage for the initial registered RAG corpus."""

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
)
from src.models.auth_audit_log import AuthAuditLog
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
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService


@pytest.mark.asyncio(loop_scope="session")
async def test_full_build_persists_registered_sources_and_skips_unchanged_chunks() -> (
    None
):
    team_id, player_id, match_id = uuid4(), uuid4(), uuid4()
    team = Team(id=team_id, name="U13 Blue", age_group="U13")
    player = Player(
        id=player_id,
        first_name="Asha",
        last_name="Khan",
        date_of_birth=date(2012, 3, 2),
        bio="Opening batter",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={"email": "excluded@example.com", "token": "excluded"},
        is_active=True,
    )
    match = Match(
        id=match_id,
        match_date=date(2026, 8, 10),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=team_id,
        away_team_id=None,
        external_opponent_name="Visitors",
        venue="North Oval",
        result="Won",
    )
    dependent_records = [
        TeamPlayer(team_id=team_id, player_id=player_id, roster_order=1),
        MatchBattingPerformance(
            id=uuid4(),
            player_id=player_id,
            match_id=match_id,
            runs_scored=42,
            balls_faced=31,
            dismissal=DismissalType.CAUGHT,
            fours=6,
            sixes=1,
            notes="private note",
        ),
        MatchBowlingPerformance(
            id=uuid4(),
            player_id=player_id,
            match_id=match_id,
            overs_bowled=Decimal("4.0"),
            maidens=0,
            runs_conceded=18,
            wickets_taken=2,
            wides=1,
            notes="private note",
        ),
        MatchFieldingPerformance(
            id=uuid4(),
            player_id=player_id,
            match_id=match_id,
            catches=1,
            stumpings=0,
            run_outs=0,
            dropped_catches=0,
            notes="private note",
        ),
        PlayerBattingStats(
            id=uuid4(),
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
            id=uuid4(),
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
    provider = FakeEmbeddingProvider()
    async with AsyncSessionFactory() as session:
        session.add_all([team, player])
        await session.commit()
        session.add(match)
        await session.commit()
        session.add_all(dependent_records)
        await session.commit()
        business_audit_count = await session.scalar(
            select(func.count()).select_from(BusinessAuditEvent)
        )
        auth_audit_count = await session.scalar(
            select(func.count()).select_from(AuthAuditLog)
        )
        service = RagIndexingService(
            session, provider=provider, batch_size=32, timeout_seconds=30
        )
        first = await service.run_full()
        document_count = await session.scalar(
            select(func.count()).select_from(RagDocument)
        )
        chunk_count = await session.scalar(select(func.count()).select_from(RagChunk))
        first_calls = provider.document_call_count
        second = await service.run_full()

        assert first.status.value == "completed", (
            first.failure_code,
            first.failure_message,
        )
        assert first.counters.documents_prepared == 8
        assert document_count == 8
        assert chunk_count == 8
        assert second.counters.unchanged_skipped == 8
        assert provider.document_call_count == first_calls
        semantic_texts = (
            await session.execute(select(RagDocument.semantic_text))
        ).scalars()
        assert all("excluded@example.com" not in text for text in semantic_texts)
        assert (
            await session.scalar(select(func.count()).select_from(BusinessAuditEvent))
            == business_audit_count
        )
        assert (
            await session.scalar(select(func.count()).select_from(AuthAuditLog))
            == auth_audit_count
        )
        await session.rollback()
