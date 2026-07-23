"""Unit tests for paginated and filtered player queries."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import BattingStyle, BowlingStyle, PlayerType
from src.models.player import Player
from src.services.player_service import PlayerService


def make_player(*, first_name: str, last_name: str) -> Player:
    """Build a complete in-memory player model for service results."""

    now = datetime.now(UTC)
    return Player(
        id=uuid4(),
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date(2000, 1, 1),
        bio=None,
        batting_style=BattingStyle.RIGHT,
        bowling_style=BowlingStyle.RIGHT_ARM_MEDIUM,
        player_type=PlayerType.BATTER,
        player_metadata={},
        is_active=True,
        created_at=now,
        updated_at=now,
        version_number=1,
    )


def make_list_session(
    players: list[Player],
    *,
    total_players: int,
    team_rows: list[tuple] | None = None,
) -> AsyncMock:
    """Build an async session mock for the three list queries."""

    scalar_rows = Mock()
    scalar_rows.all.return_value = players
    membership_rows = Mock()
    membership_rows.all.return_value = team_rows or []
    session = AsyncMock()
    session.scalar.return_value = total_players
    session.scalars.return_value = scalar_rows
    session.execute.return_value = membership_rows
    return session


@pytest.mark.asyncio
async def test_list_players_paginates_orders_and_embeds_teams() -> None:
    first = make_player(first_name="Anika", last_name="Patel")
    second = make_player(first_name="Ben", last_name="Shah")
    team_id = uuid4()
    session = make_list_session(
        [first, second],
        total_players=12,
        team_rows=[(first.id, team_id, "Senior XI")],
    )

    result = await PlayerService(session).list_players(page=2, page_size=10)

    assert result.page == 2
    assert result.page_size == 10
    assert result.total_players == 12
    assert result.total_pages == 2
    assert result.has_previous is True
    assert result.has_next is False
    assert result.players[0].teams[0].name == "Senior XI"
    assert result.players[1].teams == []

    player_statement = session.scalars.await_args.args[0]
    statement_text = str(player_statement)
    parameters = player_statement.compile().params
    assert "players.is_active IS true" in statement_text
    assert (
        "ORDER BY players.last_name, players.first_name, players.id" in statement_text
    )
    assert 10 in parameters.values()


@pytest.mark.asyncio
async def test_list_players_filters_by_team_membership() -> None:
    team_id = uuid4()
    session = make_list_session([], total_players=0)

    await PlayerService(session).list_players(team_id=team_id)

    count_statement = session.scalar.await_args.args[0]
    assert "EXISTS" in str(count_statement)
    assert team_id in count_statement.compile().params.values()


@pytest.mark.asyncio
async def test_list_players_filters_unassigned_players() -> None:
    session = make_list_session([], total_players=0)

    await PlayerService(session).list_players(unassigned=True)

    count_statement = session.scalar.await_args.args[0]
    assert "NOT (EXISTS" in str(count_statement)


@pytest.mark.asyncio
async def test_get_player_by_id_embeds_team_memberships() -> None:
    player = make_player(first_name="Anika", last_name="Patel")
    team_id = uuid4()
    membership_rows = Mock()
    membership_rows.all.return_value = [
        (player.id, team_id, "Senior XI"),
    ]
    session = AsyncMock()
    session.get.return_value = player
    session.execute.return_value = membership_rows

    result = await PlayerService(session).get_player_by_id(player.id)

    assert result.id == player.id
    assert result.teams[0].id == team_id
    assert result.teams[0].name == "Senior XI"


@pytest.mark.asyncio
async def test_list_players_rejects_conflicting_filters() -> None:
    session = make_list_session([], total_players=0)

    with pytest.raises(
        ValueError,
        match="team_id and unassigned are mutually exclusive",
    ):
        await PlayerService(session).list_players(
            team_id=uuid4(),
            unassigned=True,
        )

    session.scalar.assert_not_awaited()
