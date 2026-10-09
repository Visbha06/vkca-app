"""Unit tests for Match participant persistence and ordering."""

from datetime import date
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.enums import MatchFormat, MatchParticipantType, ScoringAuthority
from src.models.match import Match
from src.models.team import Team
from src.schemas.match import MatchCreate, MatchUpdate
from src.services.match_service import MatchService, TeamNotFoundError
from src.services.occ import StaleVersionError
from src.services.scoring.errors import ScoringAuthorityError


def external_payload() -> MatchCreate:
    """Build an external request model."""

    return MatchCreate.model_validate(
        {
            "match_date": "2026-07-02",
            "format": "T20",
            "venue": "Main Ground",
            "result": "Scheduled",
            "participants": {
                "participant_type": "external",
                "academy_team_id": str(uuid4()),
                "external_opponent_name": "Northside CC",
                "academy_side": "away",
            },
        }
    )


def mock_session_with_teams(*teams: Team) -> Mock:
    """Return a session whose set-based Team lookup returns ``teams``."""

    session = Mock()
    session.scalars = AsyncMock()
    session.get = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    scalars_result = Mock()
    scalars_result.all.return_value = list(teams)
    session.scalars.return_value = scalars_result
    return session


@pytest.mark.asyncio
async def test_create_maps_external_participant_to_one_academy_side() -> None:
    payload = external_payload()
    team = Team(id=payload.participants.academy_team_id, name="U15", age_group="U15")
    session = mock_session_with_teams(team)

    loaded_result = Mock()
    loaded_result.one_or_none.return_value = Match(
        id=uuid4(),
        match_date=payload.match_date,
        format=payload.format,
        participant_type=MatchParticipantType.EXTERNAL,
        away_team_id=team.id,
        external_opponent_name="Northside CC",
        venue=payload.venue,
        result=payload.result,
    )
    session.scalars.side_effect = [session.scalars.return_value, loaded_result]

    await MatchService(session).create_match(payload)
    match = session.add.call_args.args[0]

    assert match.participant_type is MatchParticipantType.EXTERNAL
    assert match.home_team_id is None
    assert match.away_team_id == team.id
    assert match.external_opponent_name == "Northside CC"
    session.add.assert_called_once_with(match)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_maps_internal_participant_to_both_academy_sides() -> None:
    payload = MatchCreate.model_validate(
        {
            "match_date": "2026-07-02",
            "format": "T20",
            "venue": "Main Ground",
            "result": "Scheduled",
            "participants": {
                "participant_type": "internal",
                "home_team_id": str(uuid4()),
                "away_team_id": str(uuid4()),
            },
        }
    )
    home_team = Team(id=payload.participants.home_team_id, name="U13", age_group="U13")
    away_team = Team(id=payload.participants.away_team_id, name="U15", age_group="U15")
    session = mock_session_with_teams(home_team, away_team)
    loaded_result = Mock()
    loaded_result.one_or_none.return_value = Match(
        id=uuid4(),
        match_date=payload.match_date,
        format=payload.format,
        participant_type=MatchParticipantType.INTERNAL,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        venue=payload.venue,
        result=payload.result,
    )
    session.scalars.side_effect = [session.scalars.return_value, loaded_result]

    await MatchService(session).create_match(payload)

    match = session.add.call_args.args[0]
    assert match.participant_type is MatchParticipantType.INTERNAL
    assert match.home_team_id == home_team.id
    assert match.away_team_id == away_team.id
    assert match.external_opponent_name is None


@pytest.mark.asyncio
async def test_create_rejects_unknown_teams_before_mutation() -> None:
    session = mock_session_with_teams()

    with pytest.raises(TeamNotFoundError):
        await MatchService(session).create_match(external_payload())

    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_rolls_back_stale_match_without_audit_write(mocker) -> None:
    match_id = uuid4()
    payload = MatchUpdate.model_validate(
        {**external_payload().model_dump(mode="json"), "version_number": 1}
    )
    team = Team(id=payload.participants.academy_team_id, name="U15", age_group="U15")
    session = mock_session_with_teams(team)
    session.get.return_value = Match(
        id=match_id,
        match_date=date(2026, 7, 1),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=uuid4(),
        external_opponent_name="Old CC",
        venue="Old Ground",
        result="Scheduled",
    )
    mocker.patch(
        "src.services.match_service.check_and_increment_version",
        side_effect=StaleVersionError(Match, match_id, 1),
    )

    with pytest.raises(StaleVersionError):
        await MatchService(session).update_match(match_id, payload)

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_match_update_cannot_replace_locked_scoring_identity() -> None:
    match_id = uuid4()
    payload = MatchUpdate.model_validate(
        {**external_payload().model_dump(mode="json"), "version_number": 1}
    )
    session = mock_session_with_teams()
    session.get.return_value = Match(
        id=match_id,
        match_date=date(2026, 7, 1),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=payload.participants.academy_team_id,
        external_opponent_name="Locked CC",
        venue="Ground",
        result="Scheduled",
        scoring_authority=ScoringAuthority.DELIVERY_HISTORY,
    )

    with pytest.raises(ScoringAuthorityError):
        await MatchService(session).update_match(match_id, payload)

    session.scalars.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_matches_uses_chronological_order_and_loaded_teams() -> None:
    session = Mock()
    session.scalars = AsyncMock()
    result = Mock()
    result.all.return_value = []
    session.scalars.return_value = result

    matches = await MatchService(session).list_matches()

    assert matches == []
    statement = session.scalars.await_args.args[0]
    assert "ORDER BY matches.match_date, matches.id" in str(statement)
