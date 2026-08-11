"""Unit tests for Match participant API routes."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio

from src.database import get_db
from src.enums import MatchFormat, UserRole
from src.main import app
from src.middleware.auth import get_current_user
from src.models.match import Match
from src.models.team import Team
from src.services.match_service import MatchNotFoundError, TeamNotFoundError
from src.services.occ import StaleVersionError


def request_payload(*, version_number: int | None = None) -> dict[str, object]:
    """Build a valid external participant request."""

    payload: dict[str, object] = {
        "match_date": "2026-07-01",
        "format": "T20",
        "venue": "Main Ground",
        "result": "Scheduled",
        "participants": {
            "participant_type": "external",
            "academy_team_id": str(uuid4()),
            "external_opponent_name": "Challengers CC",
            "academy_side": "home",
        },
    }
    if version_number is not None:
        payload["version_number"] = version_number
    return payload


def make_match(match_id: UUID | None = None) -> Match:
    """Build a Match with loaded Team relationships for route serialization."""

    team = Team(id=uuid4(), name="U15 Falcons", age_group="U15")
    now = datetime.now(UTC)
    return Match(
        id=match_id or uuid4(),
        match_date=date(2026, 7, 1),
        format=MatchFormat.T20,
        participant_type="external",
        home_team_id=team.id,
        away_team_id=None,
        external_opponent_name="Challengers CC",
        venue="Main Ground",
        result="Scheduled",
        created_at=now,
        updated_at=now,
        version_number=1,
        home_team=team,
    )


@pytest.fixture
def service_mock(mocker):
    service = mocker.Mock()
    service.create_match = AsyncMock()
    service.list_matches = AsyncMock()
    service.update_match = AsyncMock()
    mocker.patch("src.routes.matches.MatchService", return_value=service)
    return service


@pytest_asyncio.fixture
async def client():
    session = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return Mock(role=UserRole.HEAD_COACH), Mock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_match_returns_participant_response(client, service_mock) -> None:
    match = make_match()
    service_mock.create_match.return_value = match

    result = await client.post("/api/v1/matches", json=request_payload())

    assert result.status_code == 201
    assert result.json()["participants"] == {
        "kind": "external",
        "academy_team": {"id": str(match.home_team_id), "name": "U15 Falcons"},
        "opponent_name": "Challengers CC",
        "academy_side": "home",
    }
    service_mock.create_match.assert_awaited_once()


@pytest.mark.asyncio
async def test_routes_reject_malformed_payload_and_unknown_team(
    client, service_mock
) -> None:
    malformed = await client.post(
        "/api/v1/matches",
        json={"match_date": "2026-07-01", "format": "T20"},
    )
    service_mock.create_match.side_effect = TeamNotFoundError()
    unknown_team = await client.post("/api/v1/matches", json=request_payload())

    assert malformed.status_code == 422
    assert unknown_team.status_code == 404


@pytest.mark.asyncio
async def test_update_match_maps_stale_version_to_conflict(
    client, service_mock
) -> None:
    match_id = uuid4()
    service_mock.update_match.side_effect = StaleVersionError(Match, match_id, 1)

    result = await client.put(
        f"/api/v1/matches/{match_id}", json=request_payload(version_number=1)
    )

    assert result.status_code == 409


@pytest.mark.asyncio
async def test_get_and_update_return_participant_shapes(client, service_mock) -> None:
    match = make_match()
    service_mock.list_matches.return_value = [match]
    service_mock.update_match.return_value = match

    listed = await client.get("/api/v1/matches")
    updated = await client.put(
        f"/api/v1/matches/{match.id}", json=request_payload(version_number=1)
    )

    assert listed.status_code == 200
    assert listed.json()[0]["participants"]["kind"] == "external"
    assert updated.status_code == 200
    service_mock.update_match.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_maps_missing_match_to_not_found(client, service_mock) -> None:
    service_mock.update_match.side_effect = MatchNotFoundError()

    result = await client.put(
        f"/api/v1/matches/{uuid4()}", json=request_payload(version_number=1)
    )

    assert result.status_code == 404


@pytest.mark.asyncio
async def test_match_write_routes_keep_existing_role_authorization(client) -> None:
    async def player_user():
        return Mock(id=uuid4(), role=UserRole.PLAYER), Mock(id=uuid4())

    app.dependency_overrides[get_current_user] = player_user

    result = await client.post("/api/v1/matches", json=request_payload())

    assert result.status_code == 403
