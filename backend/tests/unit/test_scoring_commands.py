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
    AppendDeliveryRequest,
    BlockingStateResponse,
    DeliveryExtrasResponse,
    DeliveryHistoryResponse,
    DeliveryResponse,
    DeliveryRevisionResponse,
    InningsResponse,
    MatchConfigurationRequest,
    MatchConfigurationResponse,
    MatchParticipantResponse,
    MatchSideResponse,
    ScoringPolicyConfigurationRequest,
    ScoringPolicyResponse,
    StartInningsRequest,
)
from src.services.match_service import MatchService
from src.services.scoring.errors import ScoringAuthenticationError
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.service import (
    ScoringService,
    append_delivery,
    configure_match,
    retire_hurt,
    retired_hurt_return,
    select_next_batter,
    start_innings,
)


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


def _innings_response() -> InningsResponse:
    return InningsResponse(
        id=uuid4(),
        match_id=uuid4(),
        innings_number=1,
        batting_side_id=uuid4(),
        fielding_side_id=uuid4(),
        lifecycle_state="in_progress",
        reconciliation_reason=None,
        striker_participant_id=uuid4(),
        non_striker_participant_id=uuid4(),
        current_bowler_participant_id=uuid4(),
        legal_balls=0,
        total_runs=0,
        wickets_lost=0,
        target_runs=None,
        completion_reason=None,
        completed_at=None,
        projection_revision=1,
        version_number=1,
        blocking_state=BlockingStateResponse(
            kind="none", is_blocked=False, reason_code=None
        ),
    )


def _delivery_response() -> DeliveryResponse:
    innings = _innings_response()
    return DeliveryResponse(
        id=uuid4(),
        innings_id=innings.id,
        attempted_sequence=1,
        active_revision=DeliveryRevisionResponse(
            id=uuid4(),
            revision_number=1,
            revision_state="active",
            striker_participant_id=innings.striker_participant_id,
            non_striker_participant_id=innings.non_striker_participant_id,
            bowler_participant_id=innings.current_bowler_participant_id,
            runs_off_bat=4,
            extras=DeliveryExtrasResponse(
                wide_runs=0,
                no_ball_penalty_runs=0,
                bye_runs=0,
                leg_bye_runs=0,
                penalty_runs=0,
            ),
            total_runs=4,
            is_legal=True,
            completed_runs=4,
            balls_faced=True,
            bowler_conceded_runs=4,
            over_number=0,
            ball_in_over=1,
            wicket=None,
            replacement_reason=None,
            supersedes_revision_id=None,
            recorded_by_user_id=uuid4(),
            recorded_at=datetime.now(UTC),
        ),
        innings_version_number=innings.version_number,
        innings_total_runs=innings.total_runs,
        innings_legal_balls=innings.legal_balls,
        innings_wickets_lost=innings.wickets_lost,
        striker_participant_id=innings.striker_participant_id,
        non_striker_participant_id=innings.non_striker_participant_id,
        current_bowler_participant_id=innings.current_bowler_participant_id,
        blocking_state=innings.blocking_state,
    )


@pytest_asyncio.fixture
async def phase4_scoring_client(mocker):
    session = Mock()
    innings = _innings_response()
    delivery = _delivery_response()

    async def override_get_db():
        yield session

    async def override_current_user():
        return Mock(id=uuid4(), role=UserRole.HEAD_COACH), Mock()

    service = mocker.Mock()
    service.start_innings = AsyncMock(return_value=innings)
    service.get_innings = AsyncMock(return_value=innings)
    service.append_delivery = AsyncMock(return_value=delivery)
    service.list_delivery_history = AsyncMock(
        return_value=DeliveryHistoryResponse(
            innings_id=innings.id,
            after_sequence=0,
            limit=100,
            deliveries=[delivery],
            next_after_sequence=None,
        )
    )
    service.select_next_batter = AsyncMock(return_value=innings)
    service.retire_hurt = AsyncMock(return_value=innings)
    service.retired_hurt_return = AsyncMock(return_value=innings)
    mocker.patch("src.routes.match_scoring.ScoringService", return_value=service)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client, service, innings, delivery
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_phase4_handlers_are_protected_strict_bounded_and_server_derived(
    phase4_scoring_client,
) -> None:
    client, service, innings, delivery = phase4_scoring_client
    match_id = uuid4()
    start = await client.post(
        f"/api/v1/matches/{match_id}/innings",
        json={
            "match_version_number": 1,
            "innings_number": 1,
            "opening_striker_participant_id": str(uuid4()),
            "opening_non_striker_participant_id": str(uuid4()),
            "opening_bowler_participant_id": str(uuid4()),
        },
    )
    append = await client.post(
        f"/api/v1/matches/{match_id}/innings/{innings.id}/deliveries",
        json={
            "innings_version_number": 1,
            "attempted_sequence": 1,
            "striker_participant_id": str(uuid4()),
            "non_striker_participant_id": str(uuid4()),
            "bowler_participant_id": str(uuid4()),
            "runs_off_bat": 4,
            "extras": {},
        },
    )
    read = await client.get(f"/api/v1/matches/{match_id}/innings/{innings.id}")
    history = await client.get(
        f"/api/v1/matches/{match_id}/innings/{innings.id}/deliveries?limit=100"
    )
    bad_history = await client.get(
        f"/api/v1/matches/{match_id}/innings/{innings.id}/deliveries?limit=201"
    )

    assert start.status_code == 200
    assert append.status_code == 200
    assert append.json()["active_revision"]["total_runs"] == 4
    assert (
        "total_runs" not in service.append_delivery.await_args.args[2].model_fields_set
    )
    assert read.status_code == 200
    assert history.status_code == 200
    assert history.json()["deliveries"][0]["id"] == str(delivery.id)
    assert bad_history.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload", "method"),
    [
        (
            "next-batter",
            {
                "innings_version_number": 2,
                "batter_participant_id": str(uuid4()),
                "replacing_participant_id": str(uuid4()),
                "reason": "dismissal",
            },
            "select_next_batter",
        ),
        (
            "retired-hurt",
            {
                "innings_version_number": 2,
                "participant_id": str(uuid4()),
                "reason": "injury",
            },
            "retire_hurt",
        ),
        (
            "retired-hurt-return",
            {
                "innings_version_number": 3,
                "participant_id": str(uuid4()),
                "reason": "cleared",
            },
            "retired_hurt_return",
        ),
    ],
)
async def test_phase4_transition_handlers_delegate_without_business_audit(
    phase4_scoring_client,
    path: str,
    payload: dict[str, object],
    method: str,
) -> None:
    client, service, innings, _delivery = phase4_scoring_client
    response = await client.post(
        f"/api/v1/matches/{uuid4()}/innings/{innings.id}/{path}", json=payload
    )

    assert response.status_code == 200
    getattr(service, method).assert_awaited_once()


@pytest.mark.asyncio
async def test_public_phase4_commands_delegate_to_transaction_service(mocker) -> None:
    session = Mock()
    user_id, match_id, innings_id = uuid4(), uuid4(), uuid4()
    expected_innings = _innings_response()
    expected_delivery = _delivery_response()
    start_payload = StartInningsRequest(
        match_version_number=1,
        innings_number=1,
        opening_striker_participant_id=uuid4(),
        opening_non_striker_participant_id=uuid4(),
        opening_bowler_participant_id=uuid4(),
    )
    append_payload = AppendDeliveryRequest(
        innings_version_number=1,
        attempted_sequence=1,
        striker_participant_id=uuid4(),
        non_striker_participant_id=uuid4(),
        bowler_participant_id=uuid4(),
    )
    start_mock = mocker.patch.object(
        ScoringService, "start_innings", new=AsyncMock(return_value=expected_innings)
    )
    append_mock = mocker.patch.object(
        ScoringService,
        "append_delivery",
        new=AsyncMock(return_value=expected_delivery),
    )

    assert await start_innings(session, match_id, start_payload, user_id) is (
        expected_innings
    )
    assert (
        await append_delivery(session, match_id, innings_id, append_payload, user_id)
        is expected_delivery
    )
    start_mock.assert_awaited_once()
    append_mock.assert_awaited_once()

    for command, method_name, payload in (
        (select_next_batter, "select_next_batter", Mock()),
        (retire_hurt, "retire_hurt", Mock()),
        (retired_hurt_return, "retired_hurt_return", Mock()),
    ):
        delegated = mocker.patch.object(
            ScoringService,
            method_name,
            new=AsyncMock(return_value=expected_innings),
        )
        assert await command(session, match_id, innings_id, payload, user_id) is (
            expected_innings
        )
        delegated.assert_awaited_once()
