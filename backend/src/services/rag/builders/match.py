"""Explicit-participant Match canonical document adapter."""

from __future__ import annotations

from src.models.match import Match
from src.models.team import Team
from src.services.rag.builders._common import build_document, enum_value, model_version
from src.services.rag.canonical import stable_component_hash
from src.services.rag.contracts import CanonicalRagDocument, RagScopeMetadata

MATCH_BUILDER_VERSION = "match-v1"


def build_match_document(
    match: Match,
    *,
    home_team: Team | None,
    away_team: Team | None,
    dependency_fingerprint: str | None = None,
) -> CanonicalRagDocument:
    """Prepare a Match without inferring academy identities from opponent text."""

    teams = tuple(team for team in (home_team, away_team) if team is not None)
    team_ids = tuple(sorted((team.id for team in teams), key=str))
    age_groups = tuple(sorted({team.age_group for team in teams}))
    participant_type = str(enum_value(match.participant_type))
    fingerprint = dependency_fingerprint or stable_component_hash(
        match.home_team_id,
        match.away_team_id,
        tuple((team.id, team.version_number) for team in teams),
    )
    fields: list[tuple[str, object]] = [
        ("Match date", match.match_date),
        ("Format", enum_value(match.format)),
        ("Participant type", participant_type),
        ("Home team", home_team.name if home_team else None),
        ("Away team", away_team.name if away_team else None),
        (
            "External opponent",
            match.external_opponent_name if participant_type == "external" else None,
        ),
        ("Venue", match.venue),
        ("Result", match.result),
    ]
    return build_document(
        source_type="match",
        source_key=str(match.id),
        source_entity_id=match.id,
        source_version=model_version(match),
        dependency_fingerprint=fingerprint,
        fields=fields,
        provenance={"entity": "match", "participant_type": participant_type},
        scope=RagScopeMetadata(
            source_type="match",
            team_ids=team_ids,
            age_groups=age_groups,
            relationship_labels={"teams": tuple(team.name for team in teams)},
        ),
        builder_version=MATCH_BUILDER_VERSION,
        model=match,
    )
