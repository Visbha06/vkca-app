"""Focused unit coverage for the Phase 2 Match-scoring foundation."""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from src.enums import (
    SCORING_RUN_COMPONENT_MAX,
    SCORING_RUN_TOTAL_MAX,
    BlockingReasonCode,
    BlockingStateKind,
    FormatCapabilityProfile,
    MatchCompletionMode,
    MatchFormat,
    ScoringDismissalType,
    UserRole,
)
from src.middleware.error_handlers import register_error_handlers
from src.models import Base
from src.models.match import Match
from src.models.team import Team
from src.models.user import User
from src.schemas.scoring import (
    AppendDeliveryRequest,
    BlockingStateResponse,
    InningsCompletionRequest,
    MatchCompletionRequest,
    MatchConfigurationRequest,
    ScoringPolicyConfigurationRequest,
    StartInningsRequest,
)
from src.services.occ import StaleVersionError
from src.services.role_scope import CurrentRoleTeamScope
from src.services.scoring.authorization import (
    ScoringAuthorizationAdapter,
    load_scoring_command_context,
)
from src.services.scoring.errors import (
    ScoringAuthenticationError,
    ScoringAuthorizationError,
    ScoringLifecycleError,
    ScoringVisibilityError,
)


def _fixed_policy(**overrides: object) -> dict[str, object]:
    policy: dict[str, object] = {
        "policy_code": "T20",
        "capability_profile": "T20",
        "capability_version": 1,
        "innings_sequence": ["home", "away"],
        "innings_per_side": 1,
        "legal_ball_limit": 120,
        "over_length_legal_balls": 6,
        "bowler_quota_legal_balls": 24,
        "wicket_limit": 10,
        "consecutive_overs_prohibited": True,
        "target_mode": "prior_innings_plus_one",
        "allow_declaration": False,
        "allow_draw": False,
        "allow_manual_completion": False,
        "explicit_match_completion_boundary": "none",
    }
    policy.update(overrides)
    return policy


def _delivery_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "innings_version_number": 1,
        "attempted_sequence": 1,
        "striker_participant_id": str(uuid4()),
        "non_striker_participant_id": str(uuid4()),
        "bowler_participant_id": str(uuid4()),
        "runs_off_bat": 0,
        "extras": {
            "wide_runs": 0,
            "no_ball_penalty_runs": 0,
            "bye_runs": 0,
            "leg_bye_runs": 0,
            "penalty_runs": 0,
        },
        "wicket": None,
    }
    payload.update(overrides)
    return payload


def _user(role: UserRole = UserRole.HEAD_COACH) -> User:
    return User(
        id=uuid4(),
        first_name="Scoring",
        last_name="Coach",
        email=f"{uuid4().hex}@example.com",
        hashed_password="test-placeholder",
        role=role,
        is_active=True,
    )


def test_canonical_scoring_enums_and_limits_are_exact() -> None:
    assert [profile.value for profile in FormatCapabilityProfile] == [
        "T20",
        "one-day",
        "test",
        "other",
    ]
    assert SCORING_RUN_COMPONENT_MAX == 2_147_483_647
    assert SCORING_RUN_TOTAL_MAX == 2_147_483_647
    assert "obstructing_the_field" not in {
        dismissal.value for dismissal in ScoringDismissalType
    }


def test_model_registry_discovers_complete_scoring_graph() -> None:
    expected = {
        "match_sides",
        "match_scoring_policies",
        "match_participants",
        "innings",
        "innings_batting_entries",
        "innings_transition_events",
        "deliveries",
        "delivery_revisions",
        "wicket_events",
        "delivery_fielders",
        "innings_overs",
        "innings_participant_summaries",
        "match_participant_performances",
    }
    assert expected <= set(Base.metadata.tables)
    assert "uq_delivery_revisions_active_delivery" in {
        index.name for index in Base.metadata.tables["delivery_revisions"].indexes
    }


def test_policy_schema_enforces_canonical_profiles_and_one_day_derivation() -> None:
    t20 = ScoringPolicyConfigurationRequest.model_validate(_fixed_policy())
    assert t20.policy_code is MatchFormat.T20
    assert t20.derived_bowler_quota_legal_balls == 24

    one_day = ScoringPolicyConfigurationRequest.model_validate(
        {
            "policy_code": "one-day",
            "capability_profile": "one-day",
            "innings_sequence": ["away", "home"],
            "legal_ball_limit": 240,
        }
    )
    assert one_day.derived_bowler_quota_legal_balls == 48

    with pytest.raises(ValidationError):
        ScoringPolicyConfigurationRequest.model_validate(
            {
                "policy_code": "one-day",
                "capability_profile": "one-day",
                "innings_sequence": ["home", "away"],
                "legal_ball_limit": 250,
            }
        )
    with pytest.raises(ValidationError):
        ScoringPolicyConfigurationRequest.model_validate(
            {
                "policy_code": "one-day",
                "capability_profile": "one-day",
                "innings_sequence": ["home", "away"],
                "legal_ball_limit": 240,
                "bowler_quota_legal_balls": 48,
            }
        )
    with pytest.raises(ValidationError):
        ScoringPolicyConfigurationRequest.model_validate(
            {
                "policy_code": "t20",
                "capability_profile": "T20",
                "innings_sequence": ["home", "away"],
            }
        )


def test_configuration_schema_rejects_external_account_fields_and_duplicates() -> None:
    home_player = uuid4()
    payload: dict[str, object] = {
        "match_version_number": 1,
        "format": "T20",
        "policy": _fixed_policy(),
        "sides": [
            {"side_code": "home", "side_kind": "academy", "team_id": str(uuid4())},
            {
                "side_code": "away",
                "side_kind": "external",
                "display_name": "Visitors",
            },
        ],
        "participants": [
            {
                "side_code": "home",
                "participant_kind": "internal",
                "player_id": str(home_player),
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
    configured = MatchConfigurationRequest.model_validate(payload)
    assert configured.participants[1].player_id is None

    external = dict(configured.model_dump(mode="json")["participants"][1])
    external["email"] = "opponent@example.com"
    invalid = dict(payload)
    invalid["participants"] = [payload["participants"][0], external]  # type: ignore[index]
    with pytest.raises(ValidationError):
        MatchConfigurationRequest.model_validate(invalid)


def test_delivery_schema_enforces_bounds_one_wicket_and_ordered_fielders() -> None:
    maximum = AppendDeliveryRequest.model_validate(
        _delivery_payload(runs_off_bat=SCORING_RUN_COMPONENT_MAX)
    )
    assert maximum.runs_off_bat == SCORING_RUN_COMPONENT_MAX

    overflow_payload = _delivery_payload(runs_off_bat=SCORING_RUN_COMPONENT_MAX)
    overflow_payload["extras"] = {
        "wide_runs": 0,
        "no_ball_penalty_runs": 1,
        "bye_runs": 0,
        "leg_bye_runs": 0,
        "penalty_runs": 0,
    }
    with pytest.raises(ValidationError):
        AppendDeliveryRequest.model_validate(overflow_payload)

    catcher_id = uuid4()
    caught = _delivery_payload(
        wicket={
            "dismissal_type": "caught",
            "dismissed_participant_id": str(uuid4()),
            "fielders": [{"participant_id": str(catcher_id), "role": "catcher"}],
        }
    )
    parsed = AppendDeliveryRequest.model_validate(caught)
    assert parsed.wicket is not None
    assert parsed.wicket.fielders[0].participant_id == catcher_id

    caught["wicket"] = [caught["wicket"]]
    with pytest.raises(ValidationError):
        AppendDeliveryRequest.model_validate(caught)

    reserved = _delivery_payload(
        wicket={
            "dismissal_type": "timed_out",
            "dismissed_participant_id": str(uuid4()),
            "fielders": [],
        }
    )
    with pytest.raises(ValidationError):
        AppendDeliveryRequest.model_validate(reserved)


def test_completion_and_blocking_schemas_preserve_single_state_boundary() -> None:
    with pytest.raises(ValidationError):
        InningsCompletionRequest.model_validate(
            {
                "innings_version_number": 1,
                "completion_kind": "abandonment",
                "reason": "rain",
            }
        )
    match_completion = MatchCompletionRequest.model_validate(
        {
            "match_version_number": 1,
            "completion_kind": MatchCompletionMode.ABANDONMENT,
            "reason": "Unsafe conditions",
        }
    )
    assert match_completion.completion_kind is MatchCompletionMode.ABANDONMENT

    state = BlockingStateResponse(
        kind=BlockingStateKind.AWAITING_NEXT_BATTER,
        is_blocked=True,
        reason_code=BlockingReasonCode.NEXT_BATTER_REQUIRED,
    )
    assert state.is_blocked
    with pytest.raises(ValidationError):
        BlockingStateResponse(
            kind=BlockingStateKind.NONE,
            is_blocked=True,
            reason_code=BlockingReasonCode.NEXT_BATTER_REQUIRED,
        )


@pytest.mark.asyncio
async def test_authorization_adapter_reloads_user_and_delegates_scope(mocker) -> None:
    authenticated_user = _user(UserRole.ASSISTANT_COACH)
    database_user = _user(UserRole.ASSISTANT_COACH)
    database_user.id = authenticated_user.id
    team = Team(id=uuid4(), name="U15 Falcons", age_group="U15")
    session = mocker.Mock()
    session.scalar = AsyncMock(return_value=database_user)
    resolver = mocker.patch(
        "src.services.scoring.authorization.resolve_current_role_team_scope",
        new=AsyncMock(
            return_value=CurrentRoleTeamScope(
                role=UserRole.ASSISTANT_COACH,
                teams=(team,),
                linked_player_id=None,
            )
        ),
    )

    context = await load_scoring_command_context(session, authenticated_user)

    assert context.user is database_user
    context.require_read_scope({team.id})
    context.require_mutation_scope({team.id})
    with pytest.raises(ScoringVisibilityError):
        context.require_read_scope({uuid4()})
    resolver.assert_awaited_once_with(
        session,
        database_user,
        include_head_coach_teams=True,
    )


@pytest.mark.asyncio
async def test_authorization_adapter_rejects_inactive_and_player_mutation(
    mocker,
) -> None:
    session = mocker.Mock()
    session.scalar = AsyncMock(return_value=None)
    with pytest.raises(ScoringAuthenticationError):
        await ScoringAuthorizationAdapter(session).load_context(uuid4())

    player = _user(UserRole.PLAYER)
    team = Team(id=uuid4(), name="U13 Falcons", age_group="U13")
    session.scalar = AsyncMock(return_value=player)
    mocker.patch(
        "src.services.scoring.authorization.resolve_current_role_team_scope",
        new=AsyncMock(
            return_value=CurrentRoleTeamScope(
                role=UserRole.PLAYER,
                teams=(team,),
                linked_player_id=uuid4(),
            )
        ),
    )
    context = await ScoringAuthorizationAdapter(session).load_context(player.id)
    with pytest.raises(ScoringAuthorizationError):
        context.require_mutation_scope({team.id})


@pytest.mark.asyncio
async def test_error_handlers_return_structured_scoring_envelopes() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/api/v1/matches/{match_id}/innings")
    async def validate_start(
        match_id: UUID, payload: StartInningsRequest
    ) -> dict[str, str]:
        return {"match_id": str(match_id), "status": str(payload.innings_number)}

    @app.get("/api/v1/matches/{match_id}/innings/lifecycle-error")
    async def lifecycle_error(match_id: UUID) -> None:
        raise ScoringLifecycleError(f"Match {match_id} is completed.")

    @app.get("/api/v1/matches/{match_id}/innings/stale-error")
    async def stale_error(match_id: UUID) -> None:
        raise StaleVersionError(Match, match_id, 1)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        invalid = await client.post(
            f"/api/v1/matches/{uuid4()}/innings",
            json={"innings_number": 1},
            headers={"X-Request-ID": "scoring-request"},
        )
        lifecycle = await client.get(
            f"/api/v1/matches/{uuid4()}/innings/lifecycle-error"
        )
        stale = await client.get(f"/api/v1/matches/{uuid4()}/innings/stale-error")

    assert invalid.status_code == 422
    assert invalid.json()["code"] == "scoring_validation_failed"
    assert invalid.json()["request_id"] == "scoring-request"
    assert invalid.json()["field_errors"]
    assert lifecycle.status_code == 409
    assert lifecycle.json()["code"] == "scoring_lifecycle_conflict"
    assert stale.status_code == 409
    assert stale.json()["code"] == "scoring_version_conflict"
