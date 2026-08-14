"""Contract tests for the initial safe RAG source document builders."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from src.enums import (
    BattingStyle,
    BowlingStyle,
    DismissalType,
    MatchFormat,
    MatchParticipantType,
    PlayerType,
)
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.team import Team
from src.services.rag.builders.match import build_match_document
from src.services.rag.builders.player import build_player_profile_document
from src.services.rag.builders.statistics import build_batting_statistics_document
from src.services.rag.builders.team import build_team_document


def _player() -> Player:
    return Player(
        id=uuid4(),
        first_name="Ada",
        last_name="Player",
        date_of_birth=date(2012, 1, 1),
        bio="A careful batter.",
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.ALL_ROUNDER,
        player_metadata={"token": "must-not-leak"},
        is_active=True,
        version_number=3,
        updated_at=datetime(2026, 8, 13, tzinfo=UTC),
    )


def test_player_builder_is_deterministic_and_excludes_sensitive_fields() -> None:
    player = _player()

    document = build_player_profile_document(player, team_memberships=())

    assert document.source_type == "player_profile"
    assert document.source_entity_id == player.id
    assert "Ada Player" in document.semantic_text
    assert "must-not-leak" not in document.semantic_text
    assert "date_of_birth" not in document.semantic_text
    assert document.scope.player_ids == (player.id,)
    assert (
        document.content_hash
        == build_player_profile_document(player, team_memberships=()).content_hash
    )


def test_team_and_match_builders_keep_explicit_relationship_semantics() -> None:
    home = Team(id=uuid4(), name="U13 Blue", age_group="U13", version_number=1)
    away = Team(id=uuid4(), name="U13 Gold", age_group="U13", version_number=1)
    match = Match(
        id=uuid4(),
        match_date=date(2026, 8, 10),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.INTERNAL,
        home_team_id=home.id,
        away_team_id=away.id,
        venue="North Oval",
        result="Blue won",
        version_number=1,
    )

    team_document = build_team_document(home, roster=(), coaches=())
    match_document = build_match_document(match, home_team=home, away_team=away)

    assert team_document.scope.team_ids == (home.id,)
    assert "U13 Blue" in team_document.semantic_text
    assert match_document.scope.team_ids == tuple(sorted((home.id, away.id), key=str))
    assert "Participant type: internal" in match_document.semantic_text
    assert "Home team: U13 Blue" in match_document.semantic_text
    assert "Away team: U13 Gold" in match_document.semantic_text


def test_performance_and_statistics_builders_allowlist_numeric_fields() -> None:
    player = _player()
    match_id = uuid4()
    performance = MatchBattingPerformance(
        id=uuid4(),
        player_id=player.id,
        match_id=match_id,
        runs_scored=42,
        balls_faced=31,
        dismissal=DismissalType.CAUGHT,
        fours=6,
        sixes=1,
        notes="private coaching note",
        version_number=2,
    )
    statistics = PlayerBattingStats(
        id=uuid4(),
        player_id=player.id,
        format=MatchFormat.T20,
        matches=10,
        innings=9,
        not_outs=2,
        runs=300,
        balls_faced=210,
        high_score=75,
        hundreds=0,
        fifties=2,
        ducks=1,
        fours=35,
        sixes=10,
        version_number=2,
    )
    from src.services.rag.builders.performance import build_batting_performance_document

    performance_document = build_batting_performance_document(
        performance, player=player, match=None
    )
    statistics_document = build_batting_statistics_document(statistics, player=player)

    assert "private coaching note" not in performance_document.semantic_text
    assert "Runs: 42" in performance_document.semantic_text
    assert "Runs: 300" in statistics_document.semantic_text
    assert statistics_document.scope.player_ids == (player.id,)


@pytest.mark.parametrize("active", [False])
def test_inactive_player_is_not_an_eligible_profile_source(active: bool) -> None:
    from src.services.rag.builders.player import is_eligible_player

    player = _player()
    player.is_active = active
    assert not is_eligible_player(player)
