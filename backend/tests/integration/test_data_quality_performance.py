"""Seeded query-count and deterministic-scan regression coverage."""

from __future__ import annotations

from datetime import date, timedelta
from time import monotonic

import pytest

from src.database import AsyncSessionFactory
from src.enums import RecurrenceTermination, UserRole
from src.schemas.data_quality import DataQualityQuery
from src.services.data_quality_service import DataQualityService
from tests.data_quality_builders import (
    build_quality_calendar_exception,
    build_quality_calendar_series,
    build_quality_coach,
    build_quality_coach_assignment,
    build_quality_player,
    build_quality_roster_membership,
    build_quality_team,
)


async def _scan(query: DataQualityQuery, data_quality_query_counter):
    async with AsyncSessionFactory() as session:
        with data_quality_query_counter.count() as counter:
            started_at = monotonic()
            result = await DataQualityService(session).scan(query)
            elapsed = monotonic() - started_at
    return result, counter, elapsed


@pytest.mark.asyncio
async def test_seeded_scan_is_bounded_batched_and_deterministic(
    data_quality_query_counter,
) -> None:
    """Dataset growth must not add projection queries or unbound a response."""

    async with AsyncSessionFactory() as session:
        head_coach = build_quality_coach(
            first_name="Performance",
            last_name="Head Coach",
            role=UserRole.HEAD_COACH,
        )
        session.add(head_coach)
        session.add_all(
            [
                build_quality_player(
                    first_name=f"Baseline {index}",
                    last_name="Unassigned",
                    date_of_birth=date(2013, 1, index + 1),
                )
                for index in range(2)
            ]
        )
        await session.commit()

    baseline, baseline_counter, _ = await _scan(
        DataQualityQuery(),
        data_quality_query_counter,
    )
    assert baseline.page_size == 20
    assert baseline_counter.select_count == 5
    baseline_counter.assert_at_most(6)

    async with AsyncSessionFactory() as session:
        teams = [
            build_quality_team(name=f"Performance Team {index}") for index in range(8)
        ]
        roster_players = [
            build_quality_player(
                first_name=f"Roster {team_index}",
                last_name=f"Player {player_index}",
                date_of_birth=date(2012, 1, player_index + 1),
            )
            for team_index in range(len(teams))
            for player_index in range(8)
        ]
        session.add_all([*teams, *roster_players])
        await session.flush()
        session.add_all(
            [
                build_quality_roster_membership(
                    team=team,
                    player=roster_players[team_index * 8 + player_index],
                    roster_order=player_index + 1,
                )
                for team_index, team in enumerate(teams)
                for player_index in range(8)
            ]
        )
        session.add_all(
            [
                build_quality_coach_assignment(team=team, coach=head_coach)
                for team in teams
            ]
        )
        for index, team in enumerate(teams[:4]):
            inactive_assistant = build_quality_coach(
                first_name=f"Inactive {index}",
                last_name="Assistant",
                role=UserRole.ASSISTANT_COACH,
                is_active=False,
            )
            session.add(inactive_assistant)
            await session.flush()
            session.add(
                build_quality_coach_assignment(
                    team=team,
                    coach=inactive_assistant,
                )
            )
        session.add_all(
            [
                build_quality_coach(
                    first_name=f"Available {index}",
                    last_name="Assistant",
                    role=UserRole.ASSISTANT_COACH,
                )
                for index in range(4)
            ]
        )
        session.add_all(
            [
                build_quality_player(
                    first_name=f"Unassigned {index}",
                    last_name="Performance",
                    date_of_birth=date(2011, 1, 1) + timedelta(days=index),
                )
                for index in range(130)
            ]
        )
        broken_series = build_quality_calendar_series(
            first_date=date(2026, 8, 1),
            termination=RecurrenceTermination.END_DATE,
            end_date=date(2026, 7, 31),
        )
        stale_series = build_quality_calendar_series(first_date=date(2026, 8, 1))
        stale_exception = build_quality_calendar_exception(
            series=stale_series,
            original_date=date(2026, 8, 2),
        )
        session.add_all([broken_series, stale_series, stale_exception])
        await session.commit()

    query = DataQualityQuery(page_size=100)
    first, first_counter, first_elapsed = await _scan(
        query,
        data_quality_query_counter,
    )
    second, second_counter, second_elapsed = await _scan(
        query,
        data_quality_query_counter,
    )

    assert first.page_size == 100
    assert len(first.findings) == 100
    assert first.total_findings > first.page_size
    assert first.has_next is True
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first_counter.select_count == baseline_counter.select_count == 5
    assert second_counter.select_count == 5
    first_counter.assert_at_most(6)
    second_counter.assert_at_most(6)
    normalized_statements = [
        " ".join(statement.lower().split()) for statement in first_counter.statements
    ]
    for source in (
        "players",
        "teams",
        "team_players",
        "users",
        "calendar_events",
    ):
        assert any(source in statement for statement in normalized_statements)
    print(
        "data_quality_scan_regression "
        f"findings={first.total_findings} queries={first_counter.select_count} "
        f"elapsed_samples={[round(first_elapsed, 4), round(second_elapsed, 4)]}"
    )
