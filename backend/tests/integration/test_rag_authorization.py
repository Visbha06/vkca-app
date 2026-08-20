"""Database-backed authorization coverage for RAG candidate retrieval."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from src.database import AsyncSessionFactory
from src.enums import (
    BattingStyle,
    BowlingStyle,
    PlayerType,
    UserRole,
)
from src.models.player import Player
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.rag_source_state import RagSourceState
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.schemas.rag import RagRetrievalRequest
from src.services.rag.canonical import (
    canonical_content_hash,
    derive_chunk_id,
    derive_document_id,
    derive_source_id,
)
from src.services.rag.contracts import RagTargetRef
from src.services.rag.embedding import FakeEmbeddingProvider
from src.services.rag.indexing import RagIndexingService
from src.services.rag.retrieval import RagRetrievalService


def _user(role: UserRole, label: str) -> User:
    return User(
        id=uuid4(),
        first_name=label,
        last_name="Scope",
        email=f"rag-{label.casefold()}-{uuid4().hex}@example.com",
        hashed_password="not-used",
        role=role,
        is_active=True,
    )


def _player(label: str, day: int, *, user_id=None, active: bool = True) -> Player:
    return Player(
        id=uuid4(),
        user_id=user_id,
        first_name=label,
        last_name="Player",
        date_of_birth=date(2012, 1, day),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={},
        is_active=active,
    )


async def _add_chunk(
    session,
    *,
    vector,
    source_type: str,
    source_key: str,
    player_ids: tuple[UUID, ...] = (),
    team_ids: tuple[UUID, ...] = (),
    age_groups: tuple[str, ...] = (),
    is_all_academy: bool = False,
) -> None:
    state_id = derive_source_id(source_type, source_key)
    document_id = derive_document_id(source_type, source_key)
    chunk_id = derive_chunk_id(document_id, 0)
    text = f"Knowledge: {source_key}"
    content_hash = canonical_content_hash(text)
    scope = {
        "source_type": source_type,
        "player_ids": [str(item) for item in player_ids],
        "team_ids": [str(item) for item in team_ids],
        "age_groups": list(age_groups),
        "is_all_academy": is_all_academy,
        "relationship_labels": {},
    }
    state = RagSourceState(
        id=state_id,
        source_type=source_type,
        source_key=source_key,
        observed_source_version="1",
        observed_content_hash=content_hash,
        last_successful_content_hash=content_hash,
        builder_version="test-v1",
        chunking_version="rag-chunk-v1",
        provider_name="fake",
        model_name="gemini-embedding-001",
        embedding_dimension=1536,
        status="current",
    )
    session.add(state)
    await session.flush()
    document = RagDocument(
        id=document_id,
        source_state_id=state_id,
        source_type=source_type,
        source_key=source_key,
        semantic_text=text,
        provenance_metadata={"source_type": source_type},
        scope_metadata=scope,
        player_ids=list(player_ids),
        team_ids=list(team_ids),
        age_groups=list(age_groups),
        is_all_academy=is_all_academy,
        content_hash=content_hash,
        builder_version="test-v1",
        chunking_version="rag-chunk-v1",
        prepared_at=datetime.now(UTC),
        is_searchable=True,
    )
    session.add(document)
    await session.flush()
    session.add(
        RagChunk(
            id=chunk_id,
            document_id=document_id,
            source_type=source_type,
            source_key=source_key,
            ordinal=0,
            semantic_text=text,
            content_hash=content_hash,
            provenance_metadata={"source_type": source_type},
            scope_metadata=scope,
            player_ids=list(player_ids),
            team_ids=list(team_ids),
            age_groups=list(age_groups),
            is_all_academy=is_all_academy,
            embedding=list(vector),
            provider_name="fake",
            model_name="gemini-embedding-001",
            embedding_dimension=1536,
            builder_version="test-v1",
            chunking_version="rag-chunk-v1",
            is_searchable=True,
        )
    )
    await session.flush()
    state.active_document_id = document_id


async def _seed_scope_corpus(session):
    head = _user(UserRole.HEAD_COACH, "Head")
    assistant_a = _user(UserRole.ASSISTANT_COACH, "AssistantA")
    assistant_b = _user(UserRole.ASSISTANT_COACH, "AssistantB")
    linked_user = _user(UserRole.PLAYER, "Linked")
    unlinked_user = _user(UserRole.PLAYER, "Unlinked")
    team_a = Team(id=uuid4(), name="U13 Blue", age_group="U13")
    team_b = Team(id=uuid4(), name="U15 Gold", age_group="U15")
    player_a1 = _player("AOne", 1, user_id=linked_user.id)
    player_a2 = _player("ATwo", 2)
    inactive_a = _player("Inactive", 3, active=False)
    player_b = _player("BOne", 4)
    session.add_all(
        [
            head,
            assistant_a,
            assistant_b,
            linked_user,
            unlinked_user,
            team_a,
            team_b,
            player_a1,
            player_a2,
            inactive_a,
            player_b,
        ]
    )
    await session.commit()
    session.add_all(
        [
            TeamCoach(team_id=team_a.id, user_id=assistant_a.id),
            TeamCoach(team_id=team_b.id, user_id=assistant_b.id),
            TeamPlayer(team_id=team_a.id, player_id=player_a1.id, roster_order=1),
            TeamPlayer(team_id=team_a.id, player_id=player_a2.id, roster_order=2),
            TeamPlayer(team_id=team_a.id, player_id=inactive_a.id, roster_order=3),
            TeamPlayer(team_id=team_b.id, player_id=player_b.id, roster_order=1),
        ]
    )
    await session.commit()
    provider = FakeEmbeddingProvider()
    query_vector = (await provider.embed_query("scope query")).values
    chunks = [
        ("player_profile", "player-a1", (player_a1.id,), (team_a.id,), ("U13",), False),
        ("player_profile", "player-a2", (player_a2.id,), (team_a.id,), ("U13",), False),
        (
            "player_profile",
            "player-inactive",
            (inactive_a.id,),
            (team_a.id,),
            ("U13",),
            False,
        ),
        ("player_profile", "player-b", (player_b.id,), (team_b.id,), ("U15",), False),
        ("team", "team-a", (), (team_a.id,), ("U13",), False),
        ("team", "team-b", (), (team_b.id,), ("U15",), False),
        ("match", "match-a", (), (team_a.id,), ("U13",), False),
        ("match", "match-b", (), (team_b.id,), ("U15",), False),
        (
            "match_batting_performance",
            "performance-a1",
            (player_a1.id,),
            (team_a.id,),
            (),
            False,
        ),
        (
            "match_batting_performance",
            "performance-a2",
            (player_a2.id,),
            (team_a.id,),
            (),
            False,
        ),
        (
            "match_batting_performance",
            "performance-b",
            (player_b.id,),
            (team_b.id,),
            (),
            False,
        ),
        (
            "player_batting_stats",
            "stats-a1",
            (player_a1.id,),
            (team_a.id,),
            (),
            False,
        ),
        (
            "player_batting_stats",
            "stats-a2",
            (player_a2.id,),
            (team_a.id,),
            (),
            False,
        ),
        (
            "player_batting_stats",
            "stats-b",
            (player_b.id,),
            (team_b.id,),
            (),
            False,
        ),
        ("calendar_occurrence", "calendar-all", (), (), (), True),
        ("calendar_occurrence", "calendar-u13", (), (), ("U13",), False),
        ("calendar_occurrence", "calendar-u15", (), (), ("U15",), False),
    ]
    for source_type, key, players, teams, ages, all_academy in chunks:
        await _add_chunk(
            session,
            vector=query_vector,
            source_type=source_type,
            source_key=key,
            player_ids=players,
            team_ids=teams,
            age_groups=ages,
            is_all_academy=all_academy,
        )
    await session.commit()
    return {
        "head": head,
        "assistant_a": assistant_a,
        "assistant_b": assistant_b,
        "linked": linked_user,
        "unlinked": unlinked_user,
        "team_a": team_a,
        "team_b": team_b,
        "player_a1": player_a1,
        "player_a2": player_a2,
        "provider": provider,
    }


async def _visible_keys(session, provider, user) -> set[str]:
    response = await RagRetrievalService(
        session,
        provider=provider,
        query_max_characters=100,
        result_limit_default=20,
        result_limit_max=20,
        timeout_seconds=5,
    ).retrieve(user, RagRetrievalRequest(query="scope query", limit=20))
    assert all("embedding" not in item.model_dump() for item in response.results)
    return {item.source_key for item in response.results}


@pytest.mark.asyncio(loop_scope="session")
async def test_role_and_source_visibility_matrix_is_enforced_in_the_candidate_query():
    async with AsyncSessionFactory() as session:
        seed = await _seed_scope_corpus(session)

        head = await _visible_keys(session, seed["provider"], seed["head"])
        assistant_a = await _visible_keys(
            session, seed["provider"], seed["assistant_a"]
        )
        assistant_b = await _visible_keys(
            session, seed["provider"], seed["assistant_b"]
        )
        linked = await _visible_keys(session, seed["provider"], seed["linked"])
        unlinked = await _visible_keys(session, seed["provider"], seed["unlinked"])

        assert "player-inactive" not in head
        assert {"player-a1", "player-a2"} <= assistant_a
        assert "player-inactive" not in assistant_a
        assert not any(key.endswith("-b") or key.endswith("u15") for key in assistant_a)
        assert {"player-b", "team-b", "match-b", "calendar-u15"} <= assistant_b
        assert {
            "player-a1",
            "team-a",
            "match-a",
            "performance-a1",
            "stats-a1",
        } <= linked
        assert "player-a2" not in linked
        assert "performance-a2" not in linked
        assert unlinked == set()


@pytest.mark.asyncio(loop_scope="session")
async def test_targeted_refresh_is_immediately_subject_to_protected_retrieval_scope():
    async with AsyncSessionFactory() as session:
        seed = await _seed_scope_corpus(session)
        player = seed["player_a1"]
        player.bio = "Fresh targeted authorization detail"
        player.version_number += 1
        await session.commit()

        reports = await RagIndexingService(
            session,
            provider=seed["provider"],
            batch_size=8,
            timeout_seconds=30,
        ).reconcile_targets(
            (
                RagTargetRef(
                    source_type="player_profile",
                    source_key=str(player.id),
                ),
            )
        )
        assert reports and all(report.status.value == "completed" for report in reports)

        key = str(player.id)
        assert key in await _visible_keys(session, seed["provider"], seed["head"])
        assert key in await _visible_keys(
            session, seed["provider"], seed["assistant_a"]
        )
        assert key in await _visible_keys(session, seed["provider"], seed["linked"])
        assert key not in await _visible_keys(
            session, seed["provider"], seed["assistant_b"]
        )
        assert key not in await _visible_keys(
            session, seed["provider"], seed["unlinked"]
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_relationship_role_link_and_active_changes_apply_without_reembedding():
    async with AsyncSessionFactory() as session:
        seed = await _seed_scope_corpus(session)
        provider = seed["provider"]
        calls_before = provider.document_call_count

        await session.execute(
            delete(TeamCoach).where(
                TeamCoach.team_id == seed["team_a"].id,
                TeamCoach.user_id == seed["assistant_a"].id,
            )
        )
        await session.commit()
        no_assignment = await _visible_keys(session, provider, seed["assistant_a"])
        assert no_assignment == {"calendar-all"}

        session.add(
            TeamCoach(
                team_id=seed["team_b"].id,
                user_id=seed["assistant_a"].id,
            )
        )
        await session.commit()
        reassigned = await _visible_keys(session, provider, seed["assistant_a"])
        assert "team-b" in reassigned and "team-a" not in reassigned

        await session.execute(
            delete(TeamPlayer).where(
                TeamPlayer.team_id == seed["team_a"].id,
                TeamPlayer.player_id == seed["player_a1"].id,
            )
        )
        await session.commit()
        no_membership = await _visible_keys(session, provider, seed["linked"])
        assert "player-a1" in no_membership
        assert "team-a" not in no_membership
        assert "calendar-u13" not in no_membership

        seed["player_a1"].is_active = False
        seed["player_a1"].version_number += 1
        await session.commit()
        assert await _visible_keys(session, provider, seed["linked"]) == set()

        seed["player_a1"].is_active = True
        seed["player_a1"].version_number += 1
        await session.commit()
        assert "player-a1" in await _visible_keys(session, provider, seed["linked"])

        seed["player_a1"].user_id = None
        seed["player_a1"].version_number += 1
        await session.commit()
        assert await _visible_keys(session, provider, seed["linked"]) == set()

        seed["linked"].role = UserRole.ASSISTANT_COACH
        seed["linked"].version_number += 1
        await session.commit()
        assert await _visible_keys(session, provider, seed["linked"]) == {
            "calendar-all"
        }

        seed["linked"].is_active = False
        seed["linked"].version_number += 1
        await session.commit()
        assert await _visible_keys(session, provider, seed["linked"]) == set()
        assert provider.document_call_count == calls_before
