"""Phase 3 policy, configuration-command, and route unit coverage."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import ValidationError

from src.database import get_db
from src.enums import (
    BlockingReasonCode,
    BlockingStateKind,
    MatchLifecycleState,
    ScoringAuthority,
    UserRole,
)
from src.main import app
from src.middleware.auth import get_current_user
from src.schemas.scoring import (
    BlockingStateResponse,
    MatchConfigurationRequest,
    MatchConfigurationResponse,
    MatchParticipantResponse,
    MatchSideResponse,
    ScoringPolicyConfigurationRequest,
    ScoringPolicyResponse,
)
from src.services.match_service import MatchService
from src.services.scoring.errors import ScoringAuthenticationError
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.service import ScoringService, configure_match


def _policy(profile: str, **overrides: object) -> dict[str, object]:
    sequence = (
        ["home", "away", "home", "away"]
        if profile == "test"
        else [
            "home",
            "away",
        ]
    )
    payload: dict[str, object] = {
        "policy_code": profile,
        "capability_profile": profile,
        "innings_sequence": sequence,
    }
    if profile == "one-day":
        payload["legal_ball_limit"] = 240
    if profile == "other":
        payload.update(
            {
                "innings_per_side": 1,
                "legal_ball_limit": None,
                "over_length_legal_balls": 8,
                "bowler_quota_legal_balls": None,
                "wicket_limit": 8,
                "consecutive_overs_prohibited": False,
                "target_mode": "none",
                "allow_declaration": False,
                "allow_draw": False,
                "allow_manual_completion": True,
                "explicit_match_completion_boundary": "any_nonterminal_state",
                "allowed_dismissal_types": ["bowled"],
                "allowed_transition_types": [],
                "allowed_innings_completion_modes": ["manual"],
                "allowed_match_completion_modes": ["manual", "abandonment"],
                "allowed_result_codes": ["pending", "manual", "no_result"],
            }
        )
    payload.update(overrides)
    return payload


def _configuration_payload() -> dict[str, object]:
    return {
        "match_version_number": 1,
        "format": "T20",
        "policy": _policy("T20"),
        "sides": [
            {
                "side_code": "home",
                "side_kind": "academy",
                "team_id": str(uuid4()),
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
                "player_id": str(uuid4()),
                "batting_order_position": 1,
            },
            {
                "side_code": "away",
                "participant_kind": "external",
                "display_name": "External Batter",
                "batting_order_position": 1,
            },
        ],
    }


@pytest.mark.parametrize(
    ("profile", "legal_limit", "quota", "sequence_length"),
    [
        ("T20", 120, 24, 2),
        ("one-day", 240, 48, 2),
        ("test", None, None, 4),
        ("other", None, None, 2),
    ],
)
def test_public_capability_resolver_is_canonical_and_deterministic(
    profile: str,
    legal_limit: int | None,
    quota: int | None,
    sequence_length: int,
) -> None:
    capability = resolve_format_capability(_policy(profile))

    assert capability.policy_code.value == profile
    assert capability.capability_profile.value == profile
    assert capability.legal_ball_limit == legal_limit
    assert capability.bowler_quota_legal_balls == quota
    assert len(capability.innings_sequence) == sequence_length
    assert capability.capability_version == 1


@pytest.mark.parametrize("profile", ["t20", "one_day", "other_manual"])
def test_policy_rejects_format_aliases(profile: str) -> None:
    with pytest.raises(ValidationError):
        ScoringPolicyConfigurationRequest.model_validate(_policy(profile))


@pytest.mark.parametrize(
    "policy",
    [
        _policy("one-day", legal_ball_limit=None),
        _policy("one-day", legal_ball_limit=250),
        _policy("one-day", bowler_quota_legal_balls=48),
    ],
)
def test_one_day_rejects_missing_non_divisible_and_client_quota(
    policy: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ScoringPolicyConfigurationRequest.model_validate(policy)


@pytest.mark.asyncio
async def test_public_configure_command_rolls_back_authentication_failure(
    mocker,
) -> None:
    session = mocker.Mock()
    session.rollback = AsyncMock()
    mocker.patch(
        "src.services.scoring.service.ScoringAuthorizationAdapter.load_context",
        side_effect=ScoringAuthenticationError("Authentication required."),
    )

    with pytest.raises(ScoringAuthenticationError):
        await configure_match(
            session,
            uuid4(),
            MatchConfigurationRequest.model_validate(_configuration_payload()),
            uuid4(),
        )

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_match_service_configure_scoring_delegates_to_scoring_command(
    mocker,
) -> None:
    session = mocker.Mock()
    payload = MatchConfigurationRequest.model_validate(_configuration_payload())
    expected = mocker.Mock()
    command = mocker.patch.object(
        ScoringService,
        "configure_match",
        new=AsyncMock(return_value=expected),
    )

    result = await MatchService(session).configure_scoring(uuid4(), payload, uuid4())

    assert result is expected
    command.assert_awaited_once()


def _configuration_response() -> MatchConfigurationResponse:
    match_id = uuid4()
    side_id = uuid4()
    return MatchConfigurationResponse(
        match_id=match_id,
        match_version_number=2,
        lifecycle_state=MatchLifecycleState.SCHEDULED,
        scoring_authority=ScoringAuthority.DELIVERY_HISTORY,
        configured_at=datetime.now(UTC),
        policy=ScoringPolicyResponse(
            id=uuid4(),
            policy_code="T20",
            policy_version=1,
            capability_profile="T20",
            capability_version=1,
            innings_sequence=["home", "away"],
            innings_per_side=1,
            legal_ball_limit=120,
            over_length_legal_balls=6,
            bowler_quota_legal_balls=24,
            wicket_limit=10,
            consecutive_overs_prohibited=True,
            target_mode="prior_innings_plus_one",
            allowed_dismissal_types=["bowled"],
            allowed_transition_types=["retired_hurt"],
            allowed_innings_completion_modes=["all_out"],
            allowed_match_completion_modes=["derived_result", "abandonment"],
            allowed_result_codes=["pending", "win_by_runs", "no_result"],
            allow_declaration=False,
            allow_draw=False,
            allow_manual_completion=False,
            explicit_match_completion_boundary="none",
            version_number=1,
        ),
        sides=[
            MatchSideResponse(
                id=side_id,
                side_code="home",
                side_kind="academy",
                team_id=uuid4(),
                display_name_snapshot="Academy",
            ),
            MatchSideResponse(
                id=uuid4(),
                side_code="away",
                side_kind="external",
                team_id=None,
                display_name_snapshot="Northside CC",
            ),
        ],
        participants=[
            MatchParticipantResponse(
                id=uuid4(),
                side_id=side_id,
                participant_kind="internal",
                player_id=uuid4(),
                display_name_snapshot="Asha Singh",
                batting_order_position=1,
            )
        ],
        blocking_state=BlockingStateResponse(
            kind=BlockingStateKind.INNINGS_NOT_STARTED,
            is_blocked=True,
            reason_code=BlockingReasonCode.INNINGS_NOT_STARTED,
        ),
    )


@pytest_asyncio.fixture
async def scoring_client(mocker):
    session = Mock()

    async def override_get_db():
        yield session

    async def override_current_user():
        return Mock(id=uuid4(), role=UserRole.HEAD_COACH), Mock()

    service = mocker.Mock()
    service.configure_scoring = AsyncMock(return_value=_configuration_response())
    mocker.patch("src.routes.match_scoring.MatchService", return_value=service)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client, service
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_configuration_handler_is_mounted_strict_and_versioned(
    scoring_client,
) -> None:
    client, service = scoring_client
    match_id = uuid4()
    success = await client.put(
        f"/api/v1/matches/{match_id}/configuration",
        json=_configuration_payload(),
    )
    invalid = _configuration_payload()
    invalid["server_total"] = 99
    rejected = await client.put(
        f"/api/v1/matches/{match_id}/configuration",
        json=invalid,
    )

    assert success.status_code == 200
    assert success.json()["match_version_number"] == 2
    assert success.json()["policy"]["capability_profile"] == "T20"
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "scoring_validation_failed"
    service.configure_scoring.assert_awaited_once()
