"""Phase 3 authorization and fixed-identity validation coverage."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import UserRole
from src.models.player import Player
from src.models.team import Team
from src.schemas.scoring import MatchConfigurationRequest
from src.services.role_scope import CurrentRoleTeamScope
from src.services.scoring.authorization import (
    ScoringAuthorizationAdapter,
    ScoringCommandContext,
    require_configuration_scope,
)
from src.services.scoring.errors import (
    ScoringAuthorizationError,
    ScoringValidationError,
)


def _configuration(**overrides: object) -> dict[str, object]:
    home_team_id = uuid4()
    home_player_id = uuid4()
    payload: dict[str, object] = {
        "match_version_number": 1,
        "format": "T20",
        "policy": {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        },
        "sides": [
            {
                "side_code": "home",
                "side_kind": "academy",
                "team_id": str(home_team_id),
            },
            {
                "side_code": "away",
                "side_kind": "external",
                "display_name": "Northside CC",
            },
        ],
        "participants": [
            {
                "side_code": "home",
                "participant_kind": "internal",
                "player_id": str(home_player_id),
                "batting_order_position": 1,
            },
            {
                "side_code": "away",
                "participant_kind": "external",
                "display_name": "Away Batter",
                "batting_order_position": 1,
            },
        ],
    }
    payload.update(overrides)
    return payload


def _context(role: UserRole, *teams: Team) -> ScoringCommandContext:
    user = Mock(id=uuid4(), role=role)
    return ScoringCommandContext(
        user=user,
        role_scope=CurrentRoleTeamScope(
            role=role,
            teams=tuple(teams),
            linked_player_id=None,
        ),
    )


def test_configuration_scope_uses_current_team_assignments() -> None:
    team = Team(id=uuid4(), name="Scoped Team", age_group="U15")
    require_configuration_scope(
        _context(UserRole.ASSISTANT_COACH, team),
        {team.id},
    )

    with pytest.raises(ScoringAuthorizationError):
        require_configuration_scope(
            _context(UserRole.ASSISTANT_COACH),
            {team.id},
        )
    with pytest.raises(ScoringAuthorizationError):
        require_configuration_scope(_context(UserRole.PLAYER, team), {team.id})


@pytest.mark.asyncio
async def test_internal_player_eligibility_uses_roster_resolver_boundary(
    mocker,
) -> None:
    team_id = uuid4()
    player = Player(id=uuid4(), first_name="Asha", last_name="Singh", is_active=True)
    session = mocker.Mock()
    result = Mock()
    result.all.return_value = [(player, team_id)]
    session.execute = AsyncMock(return_value=result)

    eligible = await ScoringAuthorizationAdapter(
        session
    ).load_eligible_internal_players({player.id: team_id})

    assert eligible == {player.id: player}
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_player_must_belong_to_requested_side(mocker) -> None:
    session = mocker.Mock()
    result = Mock()
    result.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(ScoringValidationError):
        await ScoringAuthorizationAdapter(session).load_eligible_internal_players(
            {uuid4(): uuid4()}
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["participants"].append(  # type: ignore[union-attr]
            dict(payload["participants"][0])  # type: ignore[index]
        ),
        lambda payload: payload["participants"][1].update(  # type: ignore[index,union-attr]
            {"batting_order_position": 1, "side_code": "home"}
        ),
        lambda payload: payload["participants"][1].update(  # type: ignore[index,union-attr]
            {"email": "external@example.com"}
        ),
        lambda payload: payload["participants"].append(  # type: ignore[union-attr]
            {
                **payload["participants"][1],  # type: ignore[index]
                "display_name": "away batter",
                "batting_order_position": 2,
            }
        ),
    ],
)
def test_configuration_rejects_duplicate_cross_side_and_external_account_fields(
    mutate,
) -> None:
    payload = _configuration()
    mutate(payload)
    with pytest.raises(ValidationError):
        MatchConfigurationRequest.model_validate(payload)
