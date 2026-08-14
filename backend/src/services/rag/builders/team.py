"""Allowlisted Team canonical document adapter."""

from __future__ import annotations

from collections.abc import Iterable

from src.models.player import Player
from src.models.team import Team
from src.services.rag.builders._common import build_document, model_version
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

TEAM_BUILDER_VERSION = "team-v1"


def build_team_document(
    team: Team,
    *,
    roster: Iterable[Player] = (),
    coaches: Iterable[str] = (),
    dependency_fingerprint: str | None = None,
) -> CanonicalRagDocument:
    """Prepare a team with a bounded, deterministic roster/coaching context."""

    active_roster = tuple(
        sorted(
            (player for player in roster if player.is_active),
            key=lambda player: (
                player.last_name.casefold(),
                player.first_name.casefold(),
                str(player.id),
            ),
        )
    )
    roster_labels = tuple(
        f"{player.first_name} {player.last_name}" for player in active_roster
    )
    coach_labels = tuple(
        sorted({coach.strip() for coach in coaches if coach.strip()}, key=str.casefold)
    )
    fingerprint = dependency_fingerprint or stable_component_hash(
        tuple((player.id, player.version_number) for player in active_roster),
        coach_labels,
    )
    return build_document(
        source_type="team",
        source_key=str(team.id),
        source_entity_id=team.id,
        source_version=model_version(team),
        dependency_fingerprint=fingerprint,
        fields=[
            ("Team", team.name),
            ("Age group", team.age_group),
            ("Active roster", roster_labels),
            ("Coaching context", coach_labels),
        ],
        provenance={"entity": "team"},
        scope=RagScopeMetadata(
            source_type="team",
            team_ids=(team.id,),
            age_groups=(team.age_group,),
            relationship_labels={"roster": roster_labels},
        ),
        builder_version=TEAM_BUILDER_VERSION,
        model=team,
    )
