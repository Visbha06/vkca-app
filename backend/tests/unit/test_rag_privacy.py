"""Privacy boundary checks for safe canonical RAG builder inputs."""

from datetime import date
from uuid import uuid4

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.player import Player
from src.services.rag.builders.player import build_player_profile_document


def test_profile_builder_never_serializes_private_model_fields() -> None:
    player = Player(
        id=uuid4(),
        first_name="Riya",
        last_name="Singh",
        date_of_birth=date(2012, 9, 3),
        bio="Reliable teammate",
        batting_style=BattingStyle.LEFT,
        bowling_style=BowlingStyle.LEFT_ARM_MEDIUM,
        player_type=PlayerType.BATTER,
        player_metadata={
            "password_hash": "not-for-provider",
            "token": "not-for-provider",
            "csrf": "not-for-provider",
            "arbitrary_json": {"secret": "not-for-provider"},
        },
        is_active=True,
    )
    document = build_player_profile_document(player)

    serialized = (
        f"{document.semantic_text}\n{document.provenance}\n{document.scope.as_json()}"
    )
    for forbidden in (
        "not-for-provider",
        "date_of_birth",
        "password_hash",
        "token",
        "csrf",
        "arbitrary_json",
    ):
        assert forbidden not in serialized
