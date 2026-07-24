"""Unit tests for paginated and filtered player queries."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

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
    membership_statement = session.execute.await_args.args[0]
    assert "ORDER BY teams.name, teams.id" in str(membership_statement)


@pytest.mark.asyncio
async def test_list_players_searches_partial_names_before_pagination() -> None:
    session = make_list_session([], total_players=0)

    await PlayerService(session).list_players(
        page=2,
        page_size=5,
        search="  PaTeL  ",
    )

    count_statement = session.scalar.await_args.args[0]
    player_statement = session.scalars.await_args.args[0]
    count_sql = str(count_statement.compile(dialect=postgresql.dialect()))
    player_sql = str(player_statement.compile(dialect=postgresql.dialect()))
    count_parameters = count_statement.compile().params

    assert "players.is_active IS true" in count_sql
    assert count_sql.count(" ILIKE ") == 3
    assert "concat(players.first_name" in count_sql
    assert "players.last_name" in count_sql
    assert "%PaTeL%" in count_parameters.values()
    assert "LIMIT" not in count_sql
    assert "OFFSET" not in count_sql
    assert " ILIKE " in player_sql
    assert "LIMIT" in player_sql
    assert "OFFSET" in player_sql


@pytest.mark.asyncio
@pytest.mark.parametrize("search", [None, "", " ", "\t\n"])
async def test_list_players_blank_search_preserves_existing_query(
    search: str | None,
) -> None:
    session = make_list_session([], total_players=0)

    await PlayerService(session).list_players(search=search)

    count_statement = session.scalar.await_args.args[0]
    count_sql = str(count_statement.compile(dialect=postgresql.dialect()))
    assert "LIKE" not in count_sql
    assert "concat" not in count_sql


@pytest.mark.asyncio
async def test_list_players_combines_search_and_team_filter_with_and() -> None:
    team_id = uuid4()
    session = make_list_session([], total_players=0)

    await PlayerService(session).list_players(search="ani", team_id=team_id)

    count_statement = session.scalar.await_args.args[0]
    count_sql = str(count_statement.compile(dialect=postgresql.dialect()))
    assert "players.is_active IS true AND" in count_sql
    assert "ILIKE" in count_sql
    assert "EXISTS" in count_sql
    assert team_id in count_statement.compile().params.values()


@pytest.mark.asyncio
async def test_list_players_combines_search_and_unassigned_filter_with_and() -> None:
    session = make_list_session([], total_players=0)

    await PlayerService(session).list_players(search="shah", unassigned=True)

    count_statement = session.scalar.await_args.args[0]
    count_sql = str(count_statement.compile(dialect=postgresql.dialect()))
    assert "players.is_active IS true AND" in count_sql
    assert "ILIKE" in count_sql
    assert "NOT (EXISTS" in count_sql


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
