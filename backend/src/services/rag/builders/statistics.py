"""Allowlisted Player aggregate statistics canonical document adapters."""

from __future__ import annotations

from src.models.player import Player
from src.models.player_batting_stats import PlayerBattingStats
from src.models.player_bowling_stats import PlayerBowlingStats
from src.services.rag.builders._common import build_document, enum_value, model_version
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

BATTING_STATISTICS_BUILDER_VERSION = "player-batting-statistics-v1"
BOWLING_STATISTICS_BUILDER_VERSION = "player-bowling-statistics-v1"


def _scope(player: Player | None, source_type: str) -> RagScopeMetadata:
    return RagScopeMetadata(
        source_type=source_type, player_ids=(player.id,) if player else ()
    )


def _player_context(player: Player | None) -> list[tuple[str, object]]:
    return [("Player", f"{player.first_name} {player.last_name}" if player else None)]


def _fingerprint(player: Player | None) -> str:
    return stable_component_hash(
        getattr(player, "id", None), getattr(player, "version_number", None)
    )


def build_batting_statistics_document(
    statistics: PlayerBattingStats, *, player: Player | None
) -> CanonicalRagDocument:
    """Prepare explicitly approved batting aggregates for one Player/format."""

    return build_document(
        source_type="player_batting_statistics",
        source_key=f"{statistics.player_id}:{enum_value(statistics.format)}",
        source_entity_id=statistics.id,
        source_version=model_version(statistics),
        dependency_fingerprint=_fingerprint(player),
        fields=_player_context(player)
        + [
            ("Format", enum_value(statistics.format)),
            ("Matches", statistics.matches),
            ("Innings", statistics.innings),
            ("Not outs", statistics.not_outs),
            ("Runs", statistics.runs),
            ("Balls faced", statistics.balls_faced),
            ("High score", statistics.high_score),
            ("Hundreds", statistics.hundreds),
            ("Fifties", statistics.fifties),
            ("Ducks", statistics.ducks),
            ("Fours", statistics.fours),
            ("Sixes", statistics.sixes),
        ],
        provenance={
            "entity": "player_batting_stats",
            "player_id": str(statistics.player_id),
            "format": str(enum_value(statistics.format)),
        },
        scope=_scope(player, "player_batting_statistics"),
        builder_version=BATTING_STATISTICS_BUILDER_VERSION,
        model=statistics,
    )


def build_bowling_statistics_document(
    statistics: PlayerBowlingStats, *, player: Player | None
) -> CanonicalRagDocument:
    """Prepare explicitly approved bowling aggregates for one Player/format."""

    return build_document(
        source_type="player_bowling_statistics",
        source_key=f"{statistics.player_id}:{enum_value(statistics.format)}",
        source_entity_id=statistics.id,
        source_version=model_version(statistics),
        dependency_fingerprint=_fingerprint(player),
        fields=_player_context(player)
        + [
            ("Format", enum_value(statistics.format)),
            ("Matches", statistics.matches),
            ("Innings", statistics.innings),
            ("Overs bowled", statistics.overs_bowled),
            ("Runs conceded", statistics.runs_conceded),
            ("Wickets", statistics.wickets),
            ("Best bowling", statistics.best_bowled),
            ("Maidens", statistics.maidens),
            ("Four wicket hauls", statistics.four_wicket_hauls),
            ("Five wicket hauls", statistics.five_wicket_hauls),
            ("Wides", statistics.wides),
            ("Catches", statistics.catches),
        ],
        provenance={
            "entity": "player_bowling_stats",
            "player_id": str(statistics.player_id),
            "format": str(enum_value(statistics.format)),
        },
        scope=_scope(player, "player_bowling_statistics"),
        builder_version=BOWLING_STATISTICS_BUILDER_VERSION,
        model=statistics,
    )
