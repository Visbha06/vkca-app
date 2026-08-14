"""Allowlisted Player profile canonical document adapter."""

from __future__ import annotations

from collections.abc import Iterable

from src.models.player import Player
from src.models.team import Team
from src.services.rag.builders._common import build_document, enum_value, model_version
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

PLAYER_PROFILE_BUILDER_VERSION = "player-profile-v1"


def is_eligible_player(player: Player) -> bool:
    """Only active Player profiles participate in the initial corpus."""

    return bool(player.is_active)


def build_player_profile_document(
    player: Player,
    *,
    team_memberships: Iterable[Team] = (),
    dependency_fingerprint: str | None = None,
) -> CanonicalRagDocument:
    """Prepare an active Player using explicit non-sensitive profile allowlists."""

    teams = tuple(
        sorted(team_memberships, key=lambda team: (team.name.casefold(), str(team.id)))
    )
    team_ids = tuple(team.id for team in teams)
    age_groups = tuple(team.age_group for team in teams)
    team_labels = tuple(team.name for team in teams)
    fingerprint = dependency_fingerprint or stable_component_hash(
        tuple((team.id, team.version_number) for team in teams)
    )
    return build_document(
        source_type="player_profile",
        source_key=str(player.id),
        source_entity_id=player.id,
        source_version=model_version(player),
        dependency_fingerprint=fingerprint,
        fields=[
            ("Player", f"{player.first_name} {player.last_name}"),
            ("Player type", enum_value(player.player_type)),
            ("Batting style", enum_value(player.batting_style)),
            ("Bowling style", enum_value(player.bowling_style)),
            ("Profile", player.bio),
            ("Current teams", team_labels),
        ],
        provenance={"entity": "player"},
        scope=RagScopeMetadata(
            source_type="player_profile",
            player_ids=(player.id,),
            team_ids=team_ids,
            age_groups=age_groups,
            relationship_labels={"teams": team_labels},
        ),
        builder_version=PLAYER_PROFILE_BUILDER_VERSION,
        model=player,
    )
