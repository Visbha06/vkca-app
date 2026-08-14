"""Allowlisted per-match performance canonical document adapters."""

from __future__ import annotations

from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.services.rag.builders._common import build_document, enum_value, model_version
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

BATTING_PERFORMANCE_BUILDER_VERSION = "batting-performance-v1"
BOWLING_PERFORMANCE_BUILDER_VERSION = "bowling-performance-v1"
FIELDING_PERFORMANCE_BUILDER_VERSION = "fielding-performance-v1"


def _scope(
    player: Player | None, match: Match | None, source_type: str
) -> RagScopeMetadata:
    team_ids = tuple(
        sorted(
            (
                team_id
                for team_id in (
                    getattr(match, "home_team_id", None),
                    getattr(match, "away_team_id", None),
                )
                if team_id is not None
            ),
            key=str,
        )
    )
    return RagScopeMetadata(
        source_type=source_type,
        player_ids=(player.id,) if player is not None else (),
        team_ids=team_ids,
    )


def _dependency(player: Player | None, match: Match | None) -> str:
    return stable_component_hash(
        getattr(player, "id", None),
        getattr(player, "version_number", None),
        getattr(match, "id", None),
        getattr(match, "version_number", None),
        getattr(match, "home_team_id", None),
        getattr(match, "away_team_id", None),
    )


def _context_fields(
    player: Player | None, match: Match | None
) -> list[tuple[str, object]]:
    return [
        ("Player", f"{player.first_name} {player.last_name}" if player else None),
        ("Match date", match.match_date if match else None),
        ("Match format", enum_value(match.format) if match else None),
    ]


def build_batting_performance_document(
    performance: MatchBattingPerformance,
    *,
    player: Player | None,
    match: Match | None,
) -> CanonicalRagDocument:
    """Prepare recorded batting figures; unapproved free-text notes never enter RAG."""

    return build_document(
        source_type="batting_performance",
        source_key=str(performance.id),
        source_entity_id=performance.id,
        source_version=model_version(performance),
        dependency_fingerprint=_dependency(player, match),
        fields=_context_fields(player, match)
        + [
            ("Runs", performance.runs_scored),
            ("Balls faced", performance.balls_faced),
            ("Dismissal", enum_value(performance.dismissal)),
            ("Fours", performance.fours),
            ("Sixes", performance.sixes),
        ],
        provenance={
            "entity": "match_batting_performance",
            "player_id": str(performance.player_id),
            "match_id": str(performance.match_id),
        },
        scope=_scope(player, match, "batting_performance"),
        builder_version=BATTING_PERFORMANCE_BUILDER_VERSION,
        model=performance,
    )


def build_bowling_performance_document(
    performance: MatchBowlingPerformance,
    *,
    player: Player | None,
    match: Match | None,
) -> CanonicalRagDocument:
    """Prepare recorded bowling figures; unapproved free-text notes never enter RAG."""

    return build_document(
        source_type="bowling_performance",
        source_key=str(performance.id),
        source_entity_id=performance.id,
        source_version=model_version(performance),
        dependency_fingerprint=_dependency(player, match),
        fields=_context_fields(player, match)
        + [
            ("Overs bowled", performance.overs_bowled),
            ("Maidens", performance.maidens),
            ("Runs conceded", performance.runs_conceded),
            ("Wickets", performance.wickets_taken),
            ("Wides", performance.wides),
        ],
        provenance={
            "entity": "match_bowling_performance",
            "player_id": str(performance.player_id),
            "match_id": str(performance.match_id),
        },
        scope=_scope(player, match, "bowling_performance"),
        builder_version=BOWLING_PERFORMANCE_BUILDER_VERSION,
        model=performance,
    )


def build_fielding_performance_document(
    performance: MatchFieldingPerformance,
    *,
    player: Player | None,
    match: Match | None,
) -> CanonicalRagDocument:
    """Prepare recorded fielding figures; unapproved free-text notes never enter RAG."""

    return build_document(
        source_type="fielding_performance",
        source_key=str(performance.id),
        source_entity_id=performance.id,
        source_version=model_version(performance),
        dependency_fingerprint=_dependency(player, match),
        fields=_context_fields(player, match)
        + [
            ("Catches", performance.catches),
            ("Stumpings", performance.stumpings),
            ("Run outs", performance.run_outs),
            ("Dropped catches", performance.dropped_catches),
        ],
        provenance={
            "entity": "match_fielding_performance",
            "player_id": str(performance.player_id),
            "match_id": str(performance.match_id),
        },
        scope=_scope(player, match, "fielding_performance"),
        builder_version=FIELDING_PERFORMANCE_BUILDER_VERSION,
        model=performance,
    )
