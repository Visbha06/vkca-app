"""Regression coverage for the registry's explicit opt-in boundary."""

from src.models.player import Player
from src.services.rag.registry import RagSourceRegistry


def test_unregistered_sqlalchemy_models_cannot_be_selected_as_rag_sources() -> None:
    registry = RagSourceRegistry()

    assert Player.__tablename__ not in registry
    assert registry.source_types == ()
