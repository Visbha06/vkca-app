"""Completion commands, strict handlers, and transaction-owned side effects."""

import pytest
from pydantic import ValidationError

from src.schemas.scoring import InningsCompletionRequest, MatchCompletionRequest
from src.services.scoring.service import ScoringService
from tests.unit.test_scoring_correction_commands import (
    correction_command as _completion_setup,
)

completion_setup = _completion_setup


@pytest.mark.parametrize(
    "schema,version,kind",
    [
        (InningsCompletionRequest, "innings_version_number", "declaration"),
        (MatchCompletionRequest, "match_version_number", "abandonment"),
    ],
)
@pytest.mark.parametrize("reason", ["", "   ", "x" * 501])
def test_completion_rejects_blank_or_unbounded_reasons(schema, version, kind, reason):
    with pytest.raises(ValidationError):
        schema.model_validate({version: 1, "completion_kind": kind, "reason": reason})


@pytest.mark.asyncio
async def test_abandonment_preserves_innings_and_stages_one_refresh(
    completion_setup, mocker
):
    service, session, actor, match, innings, *_ = completion_setup
    audit = mocker.patch(
        "src.services.scoring.service.record_match_completed", new=mocker.AsyncMock()
    )
    result = await service.complete_match(
        match.id,
        MatchCompletionRequest(
            match_version_number=3, completion_kind="abandonment", reason="Rain"
        ),
        actor,
    )
    assert result.lifecycle_state == "abandoned"
    assert result.result_code == "no_result"
    assert result.blocking_state.kind == "match_abandoned"
    assert innings.lifecycle_state == "in_progress"
    assert innings.transition_events == []
    audit.assert_awaited_once()
    from src.services.scoring.service import stage_scoring_refresh

    stage_scoring_refresh.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["abandonment", "derived_result"])
async def test_reconciliation_blocks_all_completion(completion_setup, kind):
    from src.services.scoring.errors import ScoringReconciliationError

    service, session, actor, match, innings, *_ = completion_setup
    innings.lifecycle_state = "reconciliation_required"
    with pytest.raises(ScoringReconciliationError):
        await service.complete_match(
            match.id,
            MatchCompletionRequest(
                match_version_number=3,
                completion_kind=kind,
                reason="Rain" if kind == "abandonment" else None,
            ),
            actor,
        )
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_innings_completion_requires_derived_condition(completion_setup):
    from src.services.scoring.errors import ScoringLifecycleError

    service, session, actor, match, innings, *_ = completion_setup
    with pytest.raises(ScoringLifecycleError):
        await service.complete_innings(
            match.id,
            innings.id,
            InningsCompletionRequest(
                innings_version_number=2, completion_kind="all_out"
            ),
            actor,
        )
    session.commit.assert_not_awaited()


def test_completion_commands_exist():
    assert callable(ScoringService.complete_innings)
    assert callable(ScoringService.complete_match)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["complete_innings", "complete_match"])
async def test_match_service_and_route_delegate_completion(name, mocker):
    from uuid import uuid4

    from src.routes import match_scoring
    from src.services.match_service import MatchService

    actor, session, response = mocker.Mock(), mocker.Mock(), mocker.sentinel.response
    payload = (
        InningsCompletionRequest(innings_version_number=1, completion_kind="all_out")
        if name == "complete_innings"
        else MatchCompletionRequest(
            match_version_number=1, completion_kind="derived_result"
        )
    )
    ids = [uuid4(), uuid4()] if name == "complete_innings" else [uuid4()]
    command = mocker.patch.object(
        ScoringService, name, new=mocker.AsyncMock(return_value=response)
    )
    assert (
        await getattr(MatchService(session), name)(
            *ids, payload, actor, request_id="request"
        )
        is response
    )
    command.assert_awaited_once_with(*ids, payload, actor, request_id="request")
    facade = mocker.patch.object(
        MatchService, name, new=mocker.AsyncMock(return_value=response)
    )
    assert (
        await getattr(match_scoring, name)(
            *ids, payload, session, (actor, None), "request"
        )
        is response
    )
    facade.assert_awaited_once_with(*ids, payload, actor, request_id="request")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["stale", "audit", "refresh"])
async def test_completion_failures_roll_back(completion_setup, mocker, failure):
    from src.services.occ import StaleVersionError

    service, session, actor, match, *_ = completion_setup
    audit = mocker.patch(
        "src.services.scoring.service.record_match_completed", new=mocker.AsyncMock()
    )
    if failure == "stale":
        mocker.patch(
            "src.services.scoring.service.check_and_increment_version",
            new=mocker.AsyncMock(
                side_effect=StaleVersionError(type(match), match.id, 3)
            ),
        )
    elif failure == "audit":
        audit.side_effect = RuntimeError("audit failed")
    else:
        from src.services.scoring.service import stage_scoring_refresh

        stage_scoring_refresh.side_effect = RuntimeError("refresh failed")
    with pytest.raises((StaleVersionError, RuntimeError)):
        await service.complete_match(
            match.id,
            MatchCompletionRequest(
                match_version_number=3, completion_kind="abandonment", reason="Rain"
            ),
            actor,
        )
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile,kind", [("test", "declaration"), ("other", "manual")])
async def test_explicit_innings_completion_replays_transition(
    completion_setup, mocker, profile, kind
):
    from src.services.scoring.projections import persist_innings_projection
    from tests.unit.test_scoring_projections import _completion_policy

    service, session, actor, match, innings, *_ = completion_setup
    match.scoring_policy = _completion_policy(profile).to_model(match.id)
    match.scoring_policy.id = match.id
    match.scoring_policy.version_number = 1
    # Exercise actual projection persistence with an isolated database boundary.
    mocker.patch(
        "src.services.scoring.service.persist_innings_projection",
        new=persist_innings_projection,
    )
    session.execute = mocker.AsyncMock()
    audit = mocker.patch(
        "src.services.scoring.service.record_innings_completed", new=mocker.AsyncMock()
    )
    result = await service.complete_innings(
        match.id,
        innings.id,
        InningsCompletionRequest(
            innings_version_number=2, completion_kind=kind, reason="Close innings"
        ),
        actor,
    )
    assert result.lifecycle_state == "completed"
    assert result.completion_reason == kind
    assert len(innings.transition_events) == 1
    assert innings.transition_events[0].reason == "Close innings"
    audit.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["complete_innings", "complete_match"])
async def test_completion_denies_player_mutations(completion_setup, mocker, name):
    from src.enums import UserRole
    from src.services.scoring.authorization import ScoringCommandContext
    from src.services.scoring.errors import ScoringAuthorizationError

    service, session, actor, match, innings, *_ = completion_setup
    actor.role = UserRole.PLAYER
    context = ScoringCommandContext(actor, mocker.Mock(role=UserRole.PLAYER))
    mocker.patch(
        "src.services.scoring.service.ScoringAuthorizationAdapter.load_context",
        new=mocker.AsyncMock(return_value=context),
    )
    payload = (
        InningsCompletionRequest(innings_version_number=2, completion_kind="all_out")
        if name == "complete_innings"
        else MatchCompletionRequest(
            match_version_number=3, completion_kind="abandonment", reason="Rain"
        )
    )
    ids = [match.id, innings.id] if name == "complete_innings" else [match.id]
    with pytest.raises(ScoringAuthorizationError):
        await getattr(service, name)(*ids, payload, actor)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_completion_refresh_identity_uses_match_version(mocker):
    from uuid import uuid4

    from src.services.background_jobs.outbox import stage_scoring_refresh

    stager = mocker.Mock()
    stager.outbox.stage = mocker.AsyncMock()
    mocker.patch(
        "src.services.rag.registry.get_rag_mutation_stager", return_value=stager
    )
    match_id, innings_id = uuid4(), uuid4()
    for version, reason in [(10, "completion"), (10, "correction"), (11, "correction")]:
        await stage_scoring_refresh(
            mocker.Mock(),
            match_id=match_id,
            innings_id=innings_id,
            projection_revision=4,
            refresh_version=version,
            reason=reason,
        )
    first, same, later = stager.outbox.stage.await_args_list
    assert first.kwargs["idempotency_key"] == same.kwargs["idempotency_key"]
    assert later.kwargs["idempotency_key"] != first.kwargs["idempotency_key"]
    assert first.kwargs["coalescing_key"] == later.kwargs["coalescing_key"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,kind",
    [
        ("record_innings_completed", "scoring.innings_completed"),
        ("record_match_completed", "scoring.match_completed"),
    ],
)
async def test_completion_audit_is_bounded_and_caller_owned(
    completion_setup, mocker, name, kind
):
    from src.enums import AuditActionType
    from src.services.business_audit_registry import get_action_definition
    from src.services.scoring import audit

    _, _, actor, match, innings, *_ = completion_setup
    innings.completion_reason = "all_out"
    match.result_code = "tie"
    service = mocker.Mock(record=mocker.AsyncMock())
    kwargs = {"innings": innings} if name == "record_innings_completed" else {}
    await getattr(audit, name)(
        service, actor=actor, match=match, reason=None, request_id="trace", **kwargs
    )
    call = service.record.await_args.kwargs
    assert call["action_type"] == kind
    assert call["actor"].user_id == actor.id
    assert call["target"].entity_id == match.id
    assert (
        set(call["metadata"])
        <= get_action_definition(AuditActionType(kind)).metadata_fields
    )
    service.commit.assert_not_called()


@pytest.mark.parametrize(
    "schema,version,kind",
    [
        (InningsCompletionRequest, "innings_version_number", "manual"),
        (MatchCompletionRequest, "match_version_number", "manual"),
    ],
)
@pytest.mark.parametrize("field", ["total_runs", "result_code", "blocking_state"])
def test_completion_rejects_client_derived_state(schema, version, kind, field):
    with pytest.raises(ValidationError):
        schema.model_validate(
            {version: 1, "completion_kind": kind, "reason": "Agreed end", field: 1}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["complete_innings", "complete_match"])
async def test_fixed_over_completion_rejects_manual_modes(completion_setup, name):
    from src.services.scoring.errors import ScoringValidationError

    service, session, actor, match, innings, *_ = completion_setup
    payload = (
        InningsCompletionRequest(
            innings_version_number=2, completion_kind="manual", reason="End"
        )
        if name == "complete_innings"
        else MatchCompletionRequest(
            match_version_number=3, completion_kind="manual", reason="End"
        )
    )
    ids = [match.id, innings.id] if name == "complete_innings" else [match.id]
    with pytest.raises(ScoringValidationError, match="not allowed"):
        await getattr(service, name)(*ids, payload, actor)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_completion_checks_aggregate_overflow(completion_setup):
    from src.enums import SCORING_RUN_TOTAL_MAX
    from src.services.scoring.errors import ScoringValidationError

    service, session, actor, match, innings, *_ = completion_setup
    innings.total_runs = SCORING_RUN_TOTAL_MAX + 1
    with pytest.raises(ScoringValidationError, match="Match total"):
        await service.complete_match(
            match.id,
            MatchCompletionRequest(
                match_version_number=3, completion_kind="abandonment", reason="Rain"
            ),
            actor,
        )
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
