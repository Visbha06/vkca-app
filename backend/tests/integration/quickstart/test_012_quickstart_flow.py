"""Executable quickstart for the authorization-aware RAG foundation."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, func, select, text

from src.database import AsyncSessionFactory
from src.enums import (
    AgeGroup,
    BattingStyle,
    BowlingStyle,
    DismissalType,
    EventType,
    MatchFormat,
    MatchParticipantType,
    PlayerType,
    RecurrenceFrequency,
    RecurrenceTermination,
    ScopeKind,
)
from src.models.auth_audit_log import AuthAuditLog
from src.models.business_audit_event import BusinessAuditEvent
from src.models.calendar import (
    CalendarEvent,
    CalendarEventScope,
    OccurrenceException,
    OccurrenceExceptionScope,
    RecurrenceSeries,
)
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
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.schemas.rag import RagRetrievalRequest
from src.services.calendar_service import CalendarService
from src.services.rag.embedding import (
    EmbeddingUnavailableError,
    FakeEmbeddingProvider,
)
from src.services.rag.indexing import RagIndexingService
from tests.integration.test_rag_authorization import (
    _seed_scope_corpus,
    _visible_keys,
)

INITIAL_SOURCE_TYPES = {
    "player_profile",
    "team",
    "match",
    "match_batting_performance",
    "match_bowling_performance",
    "match_fielding_performance",
    "player_batting_stats",
    "player_bowling_stats",
    "calendar_occurrence",
}


class UnavailableProvider(FakeEmbeddingProvider):
    """Fail without exposing a raw provider exception or request body."""

    async def embed_documents(self, *args, **kwargs):
        del args, kwargs
        raise EmbeddingUnavailableError()


def _player(label: str, *, active: bool = True) -> Player:
    return Player(
        id=uuid4(),
        first_name=label,
        last_name="Quickstart",
        date_of_birth=date(2012, 3, 2),
        bio="Opening batter",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={
            "email": "must-not-be-indexed@example.com",
            "token": "must-not-be-indexed",
        },
        is_active=active,
    )


async def _audit_counts(session) -> tuple[int, int]:
    business = int(
        await session.scalar(select(func.count()).select_from(BusinessAuditEvent)) or 0
    )
    security = int(
        await session.scalar(select(func.count()).select_from(AuthAuditLog)) or 0
    )
    return business, security


@pytest.mark.asyncio(loop_scope="session")
async def test_rag_indexing_foundation_quickstart_flow() -> None:
    """Validate build, sync, failure recovery, authorization, and redaction."""

    today = datetime.now(UTC).date()
    team_a = Team(id=uuid4(), name="012 U13 Blue", age_group=AgeGroup.U13)
    team_b = Team(id=uuid4(), name="012 U15 Gold", age_group=AgeGroup.U15)
    player_a = _player("Asha")
    player_b = _player("Bina")
    inactive_player = _player("Inactive", active=False)
    match = Match(
        id=uuid4(),
        match_date=today,
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=team_a.id,
        away_team_id=None,
        external_opponent_name="012 Visitors",
        venue="North Oval",
        result="Won",
    )
    recurring_event = CalendarEvent(
        id=uuid4(),
        event_type=EventType.PRACTICE,
        name="012 Recurring practice",
        first_date=today,
        is_all_day=False,
        start_time=time(17),
        end_time=time(18, 30),
        version_number=1,
    )
    event_scope = CalendarEventScope(
        id=uuid4(),
        event_id=recurring_event.id,
        scope_kind=ScopeKind.AGE_GROUP,
        age_group=AgeGroup.U13,
    )
    series = RecurrenceSeries(
        id=uuid4(),
        event_id=recurring_event.id,
        frequency=RecurrenceFrequency.WEEKLY,
        weekday=today.weekday(),
        month=None,
        month_day=None,
        termination=RecurrenceTermination.OCCURRENCE_COUNT,
        end_date=None,
        occurrence_count=4,
    )
    moved = OccurrenceException(
        id=uuid4(),
        series_id=series.id,
        original_date=today,
        replacement_date=today + timedelta(days=1),
        event_type=EventType.PRACTICE,
        name="012 Moved practice",
        is_all_day=False,
        start_time=time(18),
        end_time=time(19),
        is_deleted=False,
        version_number=1,
    )
    moved_scope = OccurrenceExceptionScope(
        id=uuid4(),
        exception_id=moved.id,
        scope_kind=ScopeKind.AGE_GROUP,
        age_group=AgeGroup.U13,
    )
    removed = OccurrenceException(
        id=uuid4(),
        series_id=series.id,
        original_date=today + timedelta(days=7),
        replacement_date=None,
        event_type=None,
        name=None,
        is_all_day=None,
        start_time=None,
        end_time=None,
        is_deleted=True,
        version_number=1,
    )

    dependent_records = [
        TeamPlayer(team_id=team_a.id, player_id=player_a.id, roster_order=1),
        TeamPlayer(team_id=team_b.id, player_id=player_b.id, roster_order=1),
        TeamPlayer(
            team_id=team_a.id,
            player_id=inactive_player.id,
            roster_order=2,
        ),
        MatchBattingPerformance(
            id=uuid4(),
            player_id=player_a.id,
            match_id=match.id,
            runs_scored=42,
            balls_faced=31,
            dismissal=DismissalType.CAUGHT,
            fours=6,
            sixes=1,
            notes="unapproved private note",
        ),
        MatchBowlingPerformance(
            id=uuid4(),
            player_id=player_a.id,
            match_id=match.id,
            overs_bowled=Decimal("4.0"),
            maidens=0,
            runs_conceded=18,
            wickets_taken=2,
            wides=1,
            notes="unapproved private note",
        ),
        MatchFieldingPerformance(
            id=uuid4(),
            player_id=player_a.id,
            match_id=match.id,
            catches=1,
            stumpings=0,
            run_outs=0,
            dropped_catches=0,
            notes="unapproved private note",
        ),
        PlayerBattingStats(
            id=uuid4(),
            player_id=player_a.id,
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
            player_id=player_a.id,
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
        assert await session.scalar(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        session.add_all([team_a, team_b, player_a, player_b, inactive_player])
        await session.commit()
        session.add_all([match, recurring_event])
        await session.commit()
        session.add_all([event_scope, series, *dependent_records])
        await session.commit()
        session.add_all([moved, removed])
        await session.commit()
        session.add(moved_scope)
        await session.commit()
        audits_before = await _audit_counts(session)

        projection = await CalendarService(session, now=datetime.now(UTC)).get_range(
            today, today + timedelta(days=44)
        )
        projected_names = {item.name for item in projection.events}
        assert "012 Moved practice" in projected_names
        assert all(
            item.original_date != today + timedelta(days=7)
            for item in projection.events
        )
        assert all(item.event_date >= today for item in projection.events)

        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=4,
            timeout_seconds=30,
        )
        first = await service.run_full()
        assert first.status.value == "completed", first.failure_message
        source_types = set(
            (await session.scalars(select(RagDocument.source_type))).all()
        )
        assert INITIAL_SOURCE_TYPES <= source_types
        assert "calendar_event" not in source_types
        documents_before = tuple(
            (
                row.id,
                row.content_hash,
            )
            for row in (
                await session.scalars(select(RagDocument).order_by(RagDocument.id))
            ).all()
        )
        calls_after_first = provider.document_call_count

        repeated = await service.run_full()
        documents_after = tuple(
            (row.id, row.content_hash)
            for row in (
                await session.scalars(select(RagDocument).order_by(RagDocument.id))
            ).all()
        )
        assert repeated.status.value == "completed"
        assert repeated.counters.unchanged_skipped >= len(documents_before)
        assert documents_after == documents_before
        assert provider.document_call_count == calls_after_first

        unrelated_hash = await session.scalar(
            select(RagDocument.content_hash).where(
                RagDocument.source_type == "player_profile",
                RagDocument.source_key == str(player_b.id),
            )
        )
        player_a.first_name = "Asha Updated"
        player_a.version_number += 1
        moved.name = "012 Replacement practice"
        moved.replacement_date = today + timedelta(days=2)
        moved.version_number += 1
        await session.commit()

        changed = await service.run_incremental()
        assert changed.status.value == "completed"
        assert changed.counters.embeddings_created >= 2
        assert (
            await session.scalar(
                select(RagDocument.content_hash).where(
                    RagDocument.source_type == "player_profile",
                    RagDocument.source_key == str(player_b.id),
                )
            )
            == unrelated_hash
        )

        player_document = await session.scalar(
            select(RagDocument).where(
                RagDocument.source_type == "player_profile",
                RagDocument.source_key == str(player_a.id),
            )
        )
        assert player_document is not None
        prior_text = player_document.semantic_text
        prior_chunks = tuple(
            (
                await session.scalars(
                    select(RagChunk.id).where(
                        RagChunk.document_id == player_document.id,
                        RagChunk.is_searchable.is_(True),
                    )
                )
            ).all()
        )
        player_a.first_name = "Provider Failure Preserved"
        player_a.version_number += 1
        await session.commit()
        failed = await RagIndexingService(
            session,
            provider=UnavailableProvider(),
            batch_size=4,
            timeout_seconds=1,
        ).run_targeted("player_profile")
        await session.refresh(player_document)
        assert failed.status.value == "partial"
        assert player_document.semantic_text == prior_text
        assert player_document.is_searchable
        assert (
            tuple(
                (
                    await session.scalars(
                        select(RagChunk.id).where(
                            RagChunk.document_id == player_document.id,
                            RagChunk.is_searchable.is_(True),
                        )
                    )
                ).all()
            )
            == prior_chunks
        )

        repaired = await service.run_repair()
        assert repaired.status.value == "completed"
        targeted = await service.run_targeted("calendar_occurrence")
        assert targeted.status.value == "completed"
        status = await service.inspect_status()
        serialized_status = repr(status)
        assert status.runs
        assert "Opening batter" not in serialized_status
        assert "unapproved private note" not in serialized_status
        assert "must-not-be-indexed" not in serialized_status

        player_a.is_active = False
        player_a.version_number += 1
        await session.commit()
        inactivated = await service.run_incremental()
        assert inactivated.counters.deleted_or_ineligible >= 1
        assert not await session.scalar(
            select(RagChunk.is_searchable)
            .join(RagDocument, RagDocument.id == RagChunk.document_id)
            .where(
                RagDocument.source_type == "player_profile",
                RagDocument.source_key == str(player_a.id),
            )
        )

        # A representative current-role corpus proves query-time authorization.
        scope_seed = await _seed_scope_corpus(session)
        head_keys = await _visible_keys(
            session, scope_seed["provider"], scope_seed["head"]
        )
        assistant_keys = await _visible_keys(
            session, scope_seed["provider"], scope_seed["assistant_a"]
        )
        unrelated_keys = await _visible_keys(
            session, scope_seed["provider"], scope_seed["assistant_b"]
        )
        linked_keys = await _visible_keys(
            session, scope_seed["provider"], scope_seed["linked"]
        )
        unlinked_keys = await _visible_keys(
            session, scope_seed["provider"], scope_seed["unlinked"]
        )
        assert {"team-a", "team-b"} <= head_keys
        assert {"player-a1", "player-a2", "team-a"} <= assistant_keys
        assert "team-b" not in assistant_keys
        assert "team-b" in unrelated_keys and "team-a" not in unrelated_keys
        assert {"player-a1", "team-a", "performance-a1"} <= linked_keys
        assert unlinked_keys == set()

        query_calls_before_relationship_changes = scope_seed[
            "provider"
        ].document_call_count
        await session.execute(
            delete(TeamCoach).where(TeamCoach.user_id == scope_seed["assistant_a"].id)
        )
        await session.commit()
        assert "team-a" not in await _visible_keys(
            session, scope_seed["provider"], scope_seed["assistant_a"]
        )
        await session.execute(
            delete(TeamPlayer).where(
                TeamPlayer.team_id == scope_seed["team_a"].id,
                TeamPlayer.player_id == scope_seed["player_a1"].id,
            )
        )
        await session.commit()
        membership_changed = await _visible_keys(
            session, scope_seed["provider"], scope_seed["linked"]
        )
        assert "player-a1" in membership_changed and "team-a" not in membership_changed
        scope_seed["player_a1"].user_id = None
        await session.commit()
        assert (
            await _visible_keys(session, scope_seed["provider"], scope_seed["linked"])
            == set()
        )
        scope_seed["player_a1"].user_id = scope_seed["linked"].id
        scope_seed["player_a1"].is_active = False
        await session.commit()
        assert (
            await _visible_keys(session, scope_seed["provider"], scope_seed["linked"])
            == set()
        )
        scope_seed["player_a1"].is_active = True
        scope_seed["linked"].role = "assistant coach"
        await session.commit()
        role_changed = await _visible_keys(
            session, scope_seed["provider"], scope_seed["linked"]
        )
        assert "player-a1" not in role_changed
        assert (
            scope_seed["provider"].document_call_count
            == query_calls_before_relationship_changes
        )

        with pytest.raises(ValidationError):
            RagRetrievalRequest.model_validate(
                {
                    "query": "scope query",
                    "limit": 5,
                    "user_id": str(scope_seed["head"].id),
                    "team_id": str(scope_seed["team_b"].id),
                    "role": "head coach",
                    "age_group": "U15",
                    "scope": "academy",
                }
            )

        assert await _audit_counts(session) == audits_before
        all_responses = (head_keys, assistant_keys, unrelated_keys, linked_keys)
        assert all("player-inactive" not in keys for keys in all_responses)
        assert all(
            {"semantic_text", "chunk_text", "vector", "embedding"}.isdisjoint(
                item.__dataclass_fields__
            )
            for item in (await service.inspect_status()).sources
        )
