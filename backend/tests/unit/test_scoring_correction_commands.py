"""Correction command isolation, revision provenance, and strict API boundary."""

from datetime import UTC, date, datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.enums import DeliveryRevisionState, MatchLifecycleState
from src.main import app
from src.middleware.auth import get_current_user
from src.models.match import Match
from src.models.scoring.batting_entry import BattingOrderEntry
from src.models.scoring.delivery import Delivery
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.models.scoring.match_side import MatchSide
from src.models.scoring.participant import MatchParticipant
from src.schemas.scoring import DeliveryCorrectionRequest
from src.services.occ import StaleVersionError
from src.services.scoring.errors import ScoringLifecycleError, ScoringRevisionError
from src.services.scoring.policy import resolve_format_capability
from src.services.scoring.service import ScoringService
from tests.fixtures.match_scoring import build_scoring_user


@pytest.fixture
def correction_command(mocker):
    session = mocker.Mock(spec=AsyncSession)
    session.commit = mocker.AsyncMock()
    session.rollback = mocker.AsyncMock()
    session.flush = mocker.AsyncMock()
    service = ScoringService(session)
    actor = build_scoring_user()
    match_id, innings_id = uuid4(), uuid4()
    home, away = uuid4(), uuid4()
    batters, bowlers = [uuid4() for _ in range(3)], [uuid4(), uuid4()]
    policy = resolve_format_capability(
        {
            "policy_code": "T20",
            "capability_profile": "T20",
            "innings_sequence": ["home", "away"],
        }
    ).to_model(match_id)
    policy.id, policy.version_number = uuid4(), 1
    match = Match(
        id=match_id,
        match_date=date(2026, 8, 1),
        venue="Academy",
        version_number=3,
        lifecycle_state="in_progress",
        result_code="pending",
        result_details={},
        scoring_authority="delivery_history",
        scoring_policy=policy,
        scoring_sides=[
            MatchSide(id=home, side_code="home"),
            MatchSide(id=away, side_code="away"),
        ],
        scoring_participants=[
            MatchParticipant(
                id=p, match_id=match_id, side_id=side, batting_order_position=i
            )
            for side, ids in [(home, batters), (away, bowlers)]
            for i, p in enumerate(ids, 1)
        ],
    )
    facts = {
        "striker_participant_id": batters[0],
        "non_striker_participant_id": batters[1],
        "bowler_participant_id": bowlers[0],
        "runs_off_bat": 0,
    }
    revision = DeliveryRevision(
        id=uuid4(),
        revision_number=1,
        revision_state="active",
        **facts,
        wide_runs=0,
        no_ball_penalty_runs=0,
        bye_runs=0,
        leg_bye_runs=0,
        penalty_runs=0,
        total_runs=0,
        is_legal=True,
        completed_runs=0,
        balls_faced=True,
        bowler_conceded_runs=0,
        over_number=0,
        ball_in_over=1,
        recorded_by_user_id=actor.id,
        recorded_at=datetime.now(UTC),
        wicket_event=None,
        fielders=[],
    )
    delivery = Delivery(
        id=uuid4(), innings_id=innings_id, attempted_sequence=1, revisions=[revision]
    )
    revision.delivery_id = delivery.id
    innings = Innings(
        id=innings_id,
        match_id=match_id,
        innings_number=1,
        batting_side_id=home,
        fielding_side_id=away,
        lifecycle_state="in_progress",
        version_number=2,
        projection_revision=2,
        total_runs=0,
        legal_balls=1,
        wickets_lost=0,
        striker_participant_id=batters[0],
        non_striker_participant_id=batters[1],
        current_bowler_participant_id=bowlers[0],
        state_snapshot={
            "opening_selections": {
                "striker_participant_id": str(batters[0]),
                "non_striker_participant_id": str(batters[1]),
                "bowler_participant_id": str(bowlers[0]),
            }
        },
        deliveries=[delivery],
        transition_events=[],
        overs=[],
        participant_summaries=[],
        batting_entries=[
            BattingOrderEntry(
                participant_id=p,
                participation_state="active" if i < 3 else "not_batted",
            )
            for i, p in enumerate(batters, 1)
        ],
    )
    match.scoring_innings = [innings]
    context = mocker.Mock(user=actor)
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
        new=mocker.AsyncMock(
            side_effect=lambda session, model, id, version: version + 1
        ),
    )
    projection = mocker.patch(
        "src.services.scoring.service.persist_innings_projection",
        new=mocker.AsyncMock(),
    )
    audit = mocker.patch(
        "src.services.scoring.service.record_delivery_corrected", new=mocker.AsyncMock()
    )
    refresh = mocker.patch(
        "src.services.scoring.service.stage_scoring_refresh", new=mocker.AsyncMock()
    )
    payload = DeliveryCorrectionRequest(
        innings_version_number=2,
        match_version_number=3,
        expected_revision_number=1,
        reason="Correct boundary",
        replacement={**facts, "runs_off_bat": 4},
    )
    return (
        service,
        session,
        actor,
        match,
        innings,
        delivery,
        payload,
        version,
        projection,
        audit,
        refresh,
    )


@pytest.mark.asyncio
async def test_correct_delivery_preserves_revision_and_stages_once(correction_command):
    (
        service,
        session,
        actor,
        match,
        innings,
        delivery,
        payload,
        version,
        projection,
        audit,
        refresh,
    ) = correction_command
    original = delivery.revisions[0]
    result = await service.correct_delivery(
        match.id, innings.id, delivery.id, payload, actor, request_id="correction-1"
    )
    assert original.revision_state is DeliveryRevisionState.SUPERSEDED
    assert original.runs_off_bat == 0
    assert original.recorded_by_user_id == actor.id
    replacement = delivery.revisions[1]
    assert replacement.supersedes_revision_id == original.id
    assert replacement.revision_number == 2
    assert replacement.replacement_reason == "Correct boundary"
    assert replacement.recorded_by_user_id == actor.id
    assert replacement.runs_off_bat == 4
    assert result.active_revision.id == replacement.id
    assert result.match_version_number == 4
    assert result.match_lifecycle_state is MatchLifecycleState.IN_PROGRESS
    assert version.await_count == 2
    session.commit.assert_awaited_once()
    projection.assert_awaited_once()
    audit.assert_awaited_once()
    refresh.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "match_version",
        "innings_version",
        "revision",
        "abandoned",
        "reprocessing",
        "audit",
        "refresh",
        "projection",
    ],
)
async def test_correction_failure_rolls_back(correction_command, failure):
    (
        service,
        session,
        actor,
        match,
        innings,
        delivery,
        payload,
        version,
        projection,
        audit,
        refresh,
    ) = correction_command
    expected = RuntimeError
    if failure in {"match_version", "innings_version"}:
        version.side_effect = StaleVersionError(Match, match.id, 3)
        if failure == "innings_version":
            version.side_effect = [4, StaleVersionError(Innings, innings.id, 2)]
        expected = StaleVersionError
    elif failure == "revision":
        payload = payload.model_copy(update={"expected_revision_number": 2})
        expected = ScoringRevisionError
    elif failure in {"abandoned", "reprocessing"}:
        match.lifecycle_state = (
            "abandoned" if failure == "abandoned" else "correction_reprocessing"
        )
        expected = ScoringLifecycleError
    else:
        {"audit": audit, "refresh": refresh, "projection": projection}[
            failure
        ].side_effect = RuntimeError("Unavailable")
    with pytest.raises(expected):
        await service.correct_delivery(
            match.id, innings.id, delivery.id, payload, actor
        )
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", " "),
        ("reason", "x" * 501),
        ("match_version_number", None),
        ("innings_version_number", None),
        ("expected_revision_number", 0),
    ],
)
def test_correction_schema_requires_versions_and_bounded_reason(field, value):
    body = {
        "match_version_number": 1,
        "innings_version_number": 1,
        "expected_revision_number": 1,
        "reason": "Fix",
        "replacement": {
            "striker_participant_id": uuid4(),
            "non_striker_participant_id": uuid4(),
            "bowler_participant_id": uuid4(),
            "runs_off_bat": 0,
        },
    }
    body[field] = value
    with pytest.raises(ValidationError):
        DeliveryCorrectionRequest.model_validate(body)


@pytest.mark.asyncio
async def test_correction_handler_auth_strictness_and_conflict_translation(
    correction_command, mocker
):
    service, session, actor, match, innings, delivery, payload, *_ = correction_command
    response = await service.correct_delivery(
        match.id, innings.id, delivery.id, payload, actor
    )
    handler_service = mocker.Mock()
    handler_service.correct_delivery = mocker.AsyncMock(return_value=response)
    mocker.patch(
        "src.routes.match_scoring.ScoringService", return_value=handler_service
    )

    async def db():
        yield session

    async def user():
        return actor, mocker.Mock()

    saved = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = db
    path = (
        f"/api/v1/matches/{match.id}/innings/{innings.id}"
        f"/deliveries/{delivery.id}/correction"
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            assert (
                await client.post(path, json=payload.model_dump(mode="json"))
            ).status_code == 401
            app.dependency_overrides[get_current_user] = user
            assert (
                await client.post(path, json=payload.model_dump(mode="json"))
            ).status_code == 200
            assert (
                await client.post(
                    path, json={**payload.model_dump(mode="json"), "total_runs": 4}
                )
            ).status_code == 422
            handler_service.correct_delivery.side_effect = ScoringRevisionError(
                "Stale revision"
            )
            conflict = await client.post(path, json=payload.model_dump(mode="json"))
            assert conflict.status_code == 409
            assert conflict.json()["code"] == "scoring_revision_conflict"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


@pytest.mark.asyncio
async def test_identical_correction_keeps_provenance_without_refresh(
    correction_command,
):
    service, session, actor, match, innings, delivery, payload, _, _, audit, refresh = (
        correction_command
    )
    payload = payload.model_copy(
        update={
            "replacement": payload.replacement.model_copy(update={"runs_off_bat": 0})
        }
    )
    response = await service.correct_delivery(
        match.id, innings.id, delivery.id, payload, actor
    )
    assert response.active_revision.revision_number == 2
    audit.assert_awaited_once()
    refresh.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_correction_audit_allowlist_and_actor_snapshot(
    correction_command, mocker
):
    from src.enums import AuditActionType
    from src.services.business_audit_service import BusinessAuditService
    from src.services.scoring.audit import record_delivery_corrected

    service, session, actor, match, innings, delivery, payload, *_ = correction_command
    await service.correct_delivery(match.id, innings.id, delivery.id, payload, actor)
    revision = delivery.revisions[-1]
    session.add.reset_mock()
    await record_delivery_corrected(
        BusinessAuditService(session),
        actor=actor,
        match=match,
        innings=innings,
        delivery_id=delivery.id,
        prior_revision_id=delivery.revisions[0].id,
        revision=revision,
        prior_lifecycle=MatchLifecycleState.COMPLETED,
        request_id="audit-correction",
    )
    event = session.add.call_args.args[0]
    assert event.action_type == AuditActionType.SCORING_DELIVERY_CORRECTED
    assert event.actor_user_id == actor.id
    assert event.target_entity_id == match.id
    assert event.request_id == "audit-correction"
    assert event.event_metadata == {
        "innings_id": str(innings.id),
        "delivery_id": str(delivery.id),
        "prior_revision_id": str(delivery.revisions[0].id),
        "revision_id": str(revision.id),
        "revision_number": 2,
        "reason": "Correct boundary",
        "prior_lifecycle": "completed",
        "final_lifecycle": "in_progress",
    }


@pytest.mark.asyncio
async def test_completion_and_correction_share_coalesced_refresh(mocker):
    from src.services.background_jobs.handlers.rag_reconciliation import (
        coalesce_rag_reconciliation_payloads,
    )
    from src.services.background_jobs.outbox import stage_scoring_refresh
    from src.services.rag.contracts import RagReconciliationPayloadV1

    session = mocker.Mock(spec=AsyncSession)
    stager = mocker.Mock()
    stager.outbox.stage = mocker.AsyncMock()
    mocker.patch(
        "src.services.rag.registry.get_rag_mutation_stager", return_value=stager
    )
    match_id, innings_id = uuid4(), uuid4()
    for reason in ("completion", "correction"):
        await stage_scoring_refresh(
            session,
            match_id=match_id,
            innings_id=innings_id,
            projection_revision=3,
            reason=reason,
        )
    first, second = stager.outbox.stage.await_args_list
    assert (
        first.kwargs["coalescing_key"]
        == second.kwargs["coalescing_key"]
        == f"rag:match:{match_id}"
    )
    assert first.kwargs["idempotency_key"] == second.kwargs["idempotency_key"]
    payload = second.args[2]
    assert payload.scoring_refresh.model_dump(mode="json") == {
        "match_id": str(match_id),
        "innings_id": str(innings_id),
        "projection_revision": 3,
        "reason": "correction",
    }
    merged = coalesce_rag_reconciliation_payloads(first.args[2], payload)
    assert merged.scoring_refresh == payload.scoring_refresh
    assert len(merged.targets) == 1
    assert RagReconciliationPayloadV1.model_validate(merged.model_dump()) == merged


@pytest.mark.parametrize(
    "defect", ["duplicate_active", "broken_predecessor", "skipped_number"]
)
def test_invalid_revision_chains_fail_closed(correction_command, defect):
    from src.services.scoring.errors import ScoringReconciliationError

    service, _, _, _, _, delivery, *_ = correction_command
    original = delivery.revisions[0]
    second = DeliveryRevision(
        id=uuid4(),
        revision_number=2,
        revision_state="active",
        supersedes_revision_id=original.id,
    )
    delivery.revisions.append(second)
    if defect != "duplicate_active":
        original.revision_state = "superseded"
    if defect == "broken_predecessor":
        second.supersedes_revision_id = uuid4()
    if defect == "skipped_number":
        second.revision_number = 3
    with pytest.raises((ScoringRevisionError, ScoringReconciliationError)):
        service._validate_revision_chain(delivery)


@pytest.mark.asyncio
async def test_correction_uses_current_mutation_scope_before_writing(
    correction_command, mocker
):
    from src.services.scoring.errors import ScoringAuthorizationError

    (
        service,
        session,
        actor,
        match,
        innings,
        delivery,
        payload,
        version,
        _,
        audit,
        refresh,
    ) = correction_command
    context = mocker.Mock(user=actor)
    context.require_mutation_scope.side_effect = ScoringAuthorizationError(
        "Current role or team scope cannot correct"
    )
    mocker.patch(
        "src.services.scoring.service.ScoringAuthorizationAdapter.load_context",
        new=mocker.AsyncMock(return_value=context),
    )
    with pytest.raises(ScoringAuthorizationError):
        await service.correct_delivery(
            match.id, innings.id, delivery.id, payload, actor
        )
    version.assert_not_awaited()
    audit.assert_not_awaited()
    refresh.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


def test_completion_replay_recovers_original_test_outcome_from_revision_history(
    correction_command,
):
    from datetime import timedelta

    from src.enums import InningsCompletionMode, InningsTransitionType
    from src.models.scoring.transition_event import InningsTransitionEvent
    from src.models.scoring.wicket_event import WicketEvent

    _, _, _, match, innings, _, _, *_ = correction_command
    match.scoring_policy = resolve_format_capability(
        {
            "policy_code": "test",
            "capability_profile": "test",
            "innings_sequence": ["home", "away", "home", "away"],
        }
    ).to_model(match.id)
    recorded = datetime.now(UTC)
    innings.deliveries = [
        Delivery(
            attempted_sequence=i,
            revisions=[
                DeliveryRevision(
                    revision_number=1,
                    recorded_at=recorded - timedelta(seconds=1),
                    wicket_event=WicketEvent(counts_as_team_wicket=True),
                ),
                DeliveryRevision(
                    revision_number=2,
                    recorded_at=recorded + timedelta(seconds=1),
                    wicket_event=None,
                ),
            ],
        )
        for i in range(1, 11)
    ]
    event = InningsTransitionEvent(
        event_kind=InningsTransitionType.INNINGS_COMPLETED,
        anchored_attempted_sequence=10,
        created_at=recorded,
    )
    innings.completion_reason = None
    assert (
        ScoringService._completion_kind_from_history(match, innings, event)
        is InningsCompletionMode.ALL_OUT
    )
    event.anchored_attempted_sequence = 9
    assert (
        ScoringService._completion_kind_from_history(match, innings, event)
        is InningsCompletionMode.DECLARATION
    )
