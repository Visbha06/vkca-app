"""Isolated next-bowler command, replay, and protected handler coverage."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import InningsTransitionType
from src.main import app
from src.middleware.auth import get_current_user
from src.models.match import Match
from src.models.scoring.innings import Innings
from src.models.scoring.over import InningsOver
from src.models.scoring.participant import MatchParticipant
from src.models.scoring.participant_summary import InningsParticipantSummary
from src.schemas.scoring import SelectNextBowlerRequest
from src.services.occ import StaleVersionError
from src.services.scoring.errors import (
    ScoringConflictError,
    ScoringLifecycleError,
    ScoringValidationError,
)
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.service import ScoringService


@pytest.fixture
def bowler_command(mocker):
    session = mocker.Mock(spec=AsyncSession)
    session.commit = mocker.AsyncMock()
    session.rollback = mocker.AsyncMock()
    service = ScoringService(session)
    match_id, innings_id, side_id = uuid4(), uuid4(), uuid4()
    ids = [uuid4() for _ in range(3)]
    capability = resolve_format_capability(
        {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        }
    )
    policy = capability.to_model(match_id)
    policy.id = uuid4()
    policy.version_number = 1
    match = Match(
        id=match_id,
        version_number=4,
        lifecycle_state="in_progress",
        scoring_policy=policy,
        scoring_sides=[],
        scoring_innings=[],
        scoring_participants=[
            MatchParticipant(
                id=id, match_id=match_id, side_id=side_id, display_name_snapshot=name
            )
            for id, name in zip(ids, ["Asha", "Bela", "Cora"], strict=True)
        ],
    )
    innings = Innings(
        id=innings_id,
        match_id=match_id,
        innings_number=1,
        batting_side_id=uuid4(),
        fielding_side_id=side_id,
        lifecycle_state="in_progress",
        striker_participant_id=uuid4(),
        non_striker_participant_id=uuid4(),
        current_bowler_participant_id=None,
        legal_balls=6,
        total_runs=0,
        wickets_lost=0,
        version_number=7,
        projection_revision=7,
        state_snapshot={},
        batting_entries=[],
        deliveries=[],
        transition_events=[],
        participant_summaries=[],
        overs=[
            InningsOver(
                over_number=0,
                bowler_participant_id=ids[0],
                legal_ball_count=6,
                total_runs=0,
                runs_conceded=0,
                wickets=0,
                is_complete=True,
                projection_revision=7,
            )
        ],
    )
    context = mocker.Mock()
    context.user.id = uuid4()
    mocker.patch(
        "src.services.scoring.service.ScoringAuthorizationAdapter.load_context",
        new=mocker.AsyncMock(return_value=context),
    )
    mocker.patch.object(
        service, "_load_match", new=mocker.AsyncMock(return_value=match)
    )
    mocker.patch.object(
        service, "_load_innings", new=mocker.AsyncMock(return_value=innings)
    )
    version = mocker.patch(
        "src.services.scoring.service.check_and_increment_version",
        new=mocker.AsyncMock(return_value=8),
    )
    audit = mocker.patch("src.services.scoring.service.BusinessAuditService")
    replay = mocker.patch.object(service, "_replay_orm")
    projection = mocker.patch(
        "src.services.scoring.service.persist_innings_projection",
        new=mocker.AsyncMock(),
    )
    return (
        service,
        session,
        match,
        innings,
        ids,
        context,
        version,
        audit,
        replay,
        projection,
    )


@pytest.mark.asyncio
async def test_query_is_read_only_and_reports_usage(bowler_command):
    service, session, match, innings, ids, context, version, audit, replay, _ = (
        bowler_command
    )
    response = await service.get_next_bowler(match.id, innings.id, context.user)
    assert response.suggested_bowler_participant_id == ids[1]
    assert response.innings_version_number == 7
    assert response.completed_bowler_participant_ids == [ids[0]]
    assert response.candidates[0].reason_code == "consecutive_over_prohibited"
    assert response.policy.bowler_quota_legal_balls == 24
    context.require_read_scope.assert_called_once()
    session.commit.assert_not_awaited()
    version.assert_not_awaited()
    replay.assert_not_called()
    audit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [False, True])
async def test_selection_anchors_override_and_versions_without_audit(
    bowler_command, mocker, override
):
    (
        service,
        session,
        match,
        innings,
        ids,
        context,
        version,
        audit,
        replay,
        projection,
    ) = bowler_command
    revision_id = uuid4()
    mocker.patch.object(service, "_last_replay_anchor", return_value=(8, revision_id))
    payload = SelectNextBowlerRequest(
        innings_version_number=7,
        bowler_participant_id=ids[2 if override else 1],
        override_reason="Change of tactics" if override else None,
    )
    await service.select_next_bowler(match.id, innings.id, payload, context.user)
    event = innings.transition_events[-1]
    assert event.event_kind == InningsTransitionType.NEXT_BOWLER
    assert event.participant_id == payload.bowler_participant_id
    assert event.anchored_attempted_sequence == 8
    assert event.anchored_revision_id == revision_id
    assert event.over_number == 1
    assert event.reason == payload.override_reason
    assert event.created_by_user_id == context.user.id
    assert event.created_at <= datetime.now(UTC)
    version.assert_awaited_once_with(session, Innings, innings.id, 7)
    replay.assert_called_once()
    projection.assert_awaited_once()
    session.commit.assert_awaited_once()
    audit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "consecutive",
        "quota",
        "outside",
        "reason",
        "mid_over",
        "selected",
        "match_completed",
        "abandoned",
        "innings_completed",
        "reconciliation",
        "stale",
    ],
)
async def test_selection_rejects_conflicts_atomically(bowler_command, failure):
    (
        service,
        session,
        match,
        innings,
        ids,
        context,
        version,
        audit,
        replay,
        projection,
    ) = bowler_command
    selected = ids[1]
    if failure == "consecutive":
        selected = ids[0]
    elif failure == "quota":
        innings.participant_summaries = [
            InningsParticipantSummary(participant_id=selected, bowling_legal_balls=24)
        ]
    elif failure == "outside":
        selected = uuid4()
    elif failure == "reason":
        selected = ids[2]
    elif failure == "mid_over":
        innings.legal_balls = 5
    elif failure == "selected":
        innings.current_bowler_participant_id = ids[1]
    elif failure in {"match_completed", "abandoned"}:
        match.lifecycle_state = (
            "completed" if failure == "match_completed" else "abandoned"
        )
    elif failure == "innings_completed":
        innings.lifecycle_state = "completed"
    elif failure == "reconciliation":
        innings.lifecycle_state = "reconciliation_required"
    elif failure == "stale":
        version.side_effect = StaleVersionError(Innings, innings.id, 7)
    expected_error = (
        ScoringValidationError
        if failure == "reason"
        else StaleVersionError
        if failure == "stale"
        else ScoringConflictError
        if failure in {"consecutive", "quota", "outside"}
        else ScoringLifecycleError
    )
    with pytest.raises(expected_error):
        await service.select_next_bowler(
            match.id,
            innings.id,
            SelectNextBowlerRequest(
                innings_version_number=7, bowler_participant_id=selected
            ),
            context.user,
        )
    assert not innings.transition_events
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
    projection.assert_not_awaited()
    replay.assert_not_called()
    audit.assert_not_called()


@pytest.mark.parametrize("reason", ["", "   ", "x" * 501])
def test_override_reason_is_bounded_nonblank(reason):
    with pytest.raises(ValidationError):
        SelectNextBowlerRequest(
            innings_version_number=1,
            bowler_participant_id=uuid4(),
            override_reason=reason,
        )


@pytest.mark.asyncio
async def test_append_rechecks_quota_before_any_write(bowler_command, mocker):
    from src.schemas.scoring import AppendDeliveryRequest

    (
        service,
        session,
        match,
        innings,
        ids,
        context,
        version,
        audit,
        replay,
        projection,
    ) = bowler_command
    mocker.patch("src.services.scoring.service.validate_innings_selections")
    innings.current_bowler_participant_id = ids[1]
    innings.participant_summaries = [
        InningsParticipantSummary(participant_id=ids[1], bowling_legal_balls=24)
    ]
    payload = AppendDeliveryRequest(
        innings_version_number=7,
        attempted_sequence=1,
        striker_participant_id=innings.striker_participant_id,
        non_striker_participant_id=innings.non_striker_participant_id,
        bowler_participant_id=ids[1],
        runs_off_bat=0,
    )
    with pytest.raises(ScoringConflictError, match="quota_exhausted"):
        await service.append_delivery(match.id, innings.id, payload, context.user)
    version.assert_not_awaited()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    replay.assert_not_called()
    projection.assert_not_awaited()
    audit.assert_not_called()


@pytest.mark.asyncio
async def test_projection_failure_rolls_back_selection(bowler_command):
    service, session, match, innings, ids, context, _, audit, _, projection = (
        bowler_command
    )
    projection.side_effect = RuntimeError("projection unavailable")
    with pytest.raises(RuntimeError, match="projection unavailable"):
        await service.select_next_bowler(
            match.id,
            innings.id,
            SelectNextBowlerRequest(
                innings_version_number=7, bowler_participant_id=ids[1]
            ),
            context.user,
        )
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    audit.assert_not_called()


@pytest.mark.asyncio
async def test_next_bowler_handlers_are_protected_strict_and_translate_conflicts(
    bowler_command, mocker
):
    service, session, match, innings, ids, context, *_ = bowler_command
    query = await service.get_next_bowler(match.id, innings.id, context.user)
    mock_service = mocker.Mock()
    mock_service.get_next_bowler = mocker.AsyncMock(return_value=query)
    mock_service.select_next_bowler = mocker.AsyncMock(
        side_effect=ScoringConflictError("quota_exhausted")
    )
    mocker.patch("src.routes.match_scoring.ScoringService", return_value=mock_service)

    async def db():
        yield session

    async def actor():
        return context.user, mocker.Mock()

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = db
    path = f"/api/v1/matches/{match.id}/innings/{innings.id}/next-bowler"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            assert (await client.get(path)).status_code == 401
            app.dependency_overrides[get_current_user] = actor
            response = await client.get(path)
            assert response.status_code == 200, response.text
            assert response.json()["suggested_bowler_participant_id"] == str(ids[1])
            body = {"innings_version_number": 7, "bowler_participant_id": str(ids[1])}
            assert (
                await client.post(path, json={**body, "quota_override": True})
            ).status_code == 422
            conflict = await client.post(path, json=body)
            assert conflict.status_code == 409
            mock_service.select_next_bowler.assert_awaited_once()
            from src.services.scoring.service import _innings_response

            mock_service.select_next_bowler.side_effect = None
            mock_service.select_next_bowler.return_value = _innings_response(
                innings, match
            )
            assert (await client.post(path, json=body)).status_code == 200
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
