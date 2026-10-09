"""Public Phase 8 scoring reads and cross-cutting boundary coverage."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.routes import match_scoring, performances
from src.services.background_jobs.handlers import rag_reconciliation as handler_module
from src.services.background_jobs.handlers.rag_reconciliation import (
    coalesce_rag_reconciliation_payloads,
    rag_reconciliation_handler,
)
from src.services.background_jobs.registry import build_background_job_registry
from src.services.match_service import MatchService
from src.services.rag.contracts import (
    RagReconciliationPayloadV1,
    RagRunStatus,
    RagTargetRef,
    ScoringRefreshRef,
)
from src.services.rag.registry import source_registry
from src.services.scoring.service import ScoringService


@pytest.mark.asyncio
async def test_scorecard_route_and_match_facade_delegate_actor(mocker):
    match_id = uuid4()
    session, actor, response = mocker.Mock(), mocker.Mock(), mocker.sentinel.response
    query = mocker.patch.object(
        ScoringService, "get_scorecard", new=mocker.AsyncMock(return_value=response)
    )

    assert await MatchService(session).get_scorecard(match_id, actor) is response
    query.assert_awaited_once_with(match_id, actor)

    facade = mocker.patch.object(
        MatchService, "get_scorecard", new=mocker.AsyncMock(return_value=response)
    )
    assert (
        await match_scoring.read_match_scorecard(match_id, session, (actor, None))
        is response
    )
    facade.assert_awaited_once_with(match_id, actor)


@pytest.mark.asyncio
async def test_innings_and_history_routes_forward_protected_actor_and_bounds(mocker):
    match_id, innings_id = uuid4(), uuid4()
    session, actor = mocker.Mock(), mocker.Mock()
    innings_response, history_response = (
        mocker.sentinel.innings,
        mocker.sentinel.history,
    )
    service = mocker.Mock()
    service.get_innings = mocker.AsyncMock(return_value=innings_response)
    service.list_delivery_history = mocker.AsyncMock(return_value=history_response)
    mocker.patch.object(match_scoring, "ScoringService", return_value=service)

    assert (
        await match_scoring.read_match_innings(
            match_id, innings_id, session, (actor, None)
        )
        is innings_response
    )
    assert (
        await match_scoring.read_delivery_history(
            match_id,
            innings_id,
            session,
            (actor, None),
            after_sequence=17,
            limit=25,
        )
        is history_response
    )
    service.get_innings.assert_awaited_once_with(match_id, innings_id, actor)
    service.list_delivery_history.assert_awaited_once_with(
        match_id, innings_id, actor, after_sequence=17, limit=25
    )


@pytest.mark.asyncio
async def test_performance_read_route_delegates_current_actor_and_maps_not_found(
    mocker,
):
    from fastapi import HTTPException

    from src.services.performance_service import MatchNotFoundError

    match_id = uuid4()
    session, actor, response = mocker.Mock(), mocker.Mock(), mocker.sentinel.response
    service = mocker.Mock()
    service.get_match_performances = mocker.AsyncMock(return_value=response)
    mocker.patch.object(performances, "PerformanceService", return_value=service)

    assert (
        await performances.read_match_performances(match_id, session, (actor, None))
        is response
    )
    service.get_match_performances.assert_awaited_once_with(match_id, actor)

    service.get_match_performances.side_effect = MatchNotFoundError()
    with pytest.raises(HTTPException) as failure:
        await performances.read_match_performances(match_id, session, (actor, None))
    assert failure.value.status_code == 404


def test_scoring_refresh_coalescing_keeps_latest_current_projection():
    match_id, innings_id = uuid4(), uuid4()
    target = RagTargetRef(source_type="match", source_key=str(match_id))

    older = RagReconciliationPayloadV1(
        targets=(target,),
        scoring_refresh=ScoringRefreshRef(
            match_id=match_id,
            innings_id=innings_id,
            projection_revision=8,
            reason="correction",
        ),
    )
    newer = older.model_copy(
        update={
            "scoring_refresh": older.scoring_refresh.model_copy(
                update={"projection_revision": 9, "reason": "completion"}
            )
        }
    )

    assert (
        coalesce_rag_reconciliation_payloads(newer, older).scoring_refresh
        == newer.scoring_refresh
    )
    assert (
        coalesce_rag_reconciliation_payloads(older, newer).scoring_refresh
        == newer.scoring_refresh
    )
    definition = build_background_job_registry().get(
        "rag_reconciliation", payload_version=1
    )
    assert definition.handler is rag_reconciliation_handler
    assert definition.coalescer is coalesce_rag_reconciliation_payloads


class _SessionScope:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_scoring_refresh_handler_syncs_compatibility_then_reloads_match(mocker):
    match_id, innings_id = uuid4(), uuid4()
    target = RagTargetRef(source_type="match", source_key=str(match_id))
    payload = RagReconciliationPayloadV1(
        targets=(target,),
        scoring_refresh=ScoringRefreshRef(
            match_id=match_id,
            innings_id=innings_id,
            projection_revision=3,
            reason="completion",
        ),
    )
    session = mocker.Mock()
    session.scalar = mocker.AsyncMock(
        return_value=SimpleNamespace(over_length_legal_balls=6)
    )
    sync = mocker.patch(
        "src.services.performance_service.sync_delivery_derived_legacy_performances",
        new=mocker.AsyncMock(),
    )
    service = mocker.Mock()
    service.reconcile_targets = mocker.AsyncMock(
        return_value=(SimpleNamespace(status=RagRunStatus.COMPLETED),)
    )
    mocker.patch.object(handler_module, "RagIndexingService", return_value=service)
    context = SimpleNamespace(
        settings=SimpleNamespace(
            rag_embedding_batch_size=8,
            rag_embedding_timeout_seconds=12.0,
        ),
        session_factory=lambda: _SessionScope(session),
        provider=mocker.Mock(),
    )

    await rag_reconciliation_handler(context, payload)

    sync.assert_awaited_once_with(
        session,
        match_id=match_id,
        over_length_legal_balls=6,
    )
    service.reconcile_targets.assert_awaited_once_with((target,))


def test_rag_registry_has_only_bounded_match_scoring_source():
    source_types = {definition.source_type for definition in source_registry}

    assert "match" in source_types
    assert "delivery" not in source_types
    assert "delivery_revision" not in source_types
