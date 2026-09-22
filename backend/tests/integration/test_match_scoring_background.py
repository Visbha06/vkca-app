"""Scoring completion/correction refreshes use the durable RAG outbox seam."""

from __future__ import annotations

from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from src.config import get_settings
from src.database import AsyncSessionFactory
from src.main import app
from src.models.background_work_item import BackgroundWorkItem
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.rag_document import RagDocument
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
from src.services.background_jobs.handlers.rag_reconciliation import (
    RagReconciliationExecutionError,
    rag_reconciliation_handler,
)
from src.services.background_jobs.registry import build_background_job_registry
from src.services.background_jobs.runtime import BackgroundHandlerContext
from src.services.rag.contracts import RagReconciliationPayloadV1
from src.services.rag.embedding import FakeEmbeddingProvider
from tests.integration.test_match_scoring_api import (
    _phase7_all_out,
    _phase7_configuration,
    _phase7_score,
    _phase7_start,
)


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as value:
        yield value


@pytest_asyncio.fixture(loop_scope="session")
async def scoring_background_match_ids(authenticated_client):
    ids: list[UUID] = []
    try:
        yield ids
    finally:
        async with AsyncSessionFactory() as session:
            for match_id in ids:
                for model in (
                    MatchBattingPerformance,
                    MatchBowlingPerformance,
                    MatchFieldingPerformance,
                ):
                    await session.execute(
                        delete(model).where(model.match_id == match_id)
                    )
                await session.execute(
                    delete(Innings).where(Innings.match_id == match_id)
                )
                await session.execute(delete(Match).where(Match.id == match_id))
            await session.commit()


class _UnavailableEmbeddingProvider(FakeEmbeddingProvider):
    async def embed_documents(self, inputs, profile=None):
        del inputs, profile
        raise ConnectionError("simulated local provider outage")


@pytest.mark.asyncio
@pytest.mark.usefixtures("authenticated_client")
async def test_scoring_refresh_is_bounded_coalesced_and_failure_isolated(
    client, scoring_background_match_ids
):
    """Only terminal/material edits stage one current-state Match refresh."""

    config, participants = await _phase7_configuration(
        client, "T20", True, scoring_background_match_ids
    )
    match_id = UUID(config["match_id"])
    first = await _phase7_start(
        client, config, participants, 1, config["match_version_number"]
    )
    first_state = await _phase7_all_out(
        client,
        str(match_id),
        first,
        participants["home"],
        participants["away"],
        4,
    )
    async with AsyncSessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(BackgroundWorkItem.id)).where(
                    BackgroundWorkItem.source_type == "match",
                    BackgroundWorkItem.source_key == str(match_id),
                )
            )
            == 0
        )

    second = await _phase7_start(
        client,
        config,
        participants,
        2,
        first_state["match_version_number"],
    )
    second_state, winning_delivery = await _phase7_score(
        client, str(match_id), second, 1, runs=5
    )
    assert second_state["lifecycle_state"] == "completed"

    async with AsyncSessionFactory() as session:
        completion_work = list(
            (
                await session.scalars(
                    select(BackgroundWorkItem).where(
                        BackgroundWorkItem.source_type == "match",
                        BackgroundWorkItem.source_key == str(match_id),
                    )
                )
            ).all()
        )
        assert len(completion_work) == 1
        work_id = completion_work[0].id
        completion_payload = RagReconciliationPayloadV1.model_validate(
            completion_work[0].payload
        )
        assert completion_work[0].coalescing_key == f"rag:match:{match_id}"
        assert completion_payload.scoring_refresh is not None
        assert completion_payload.scoring_refresh.reason == "completion"
        assert completion_payload.scoring_refresh.match_id == match_id
        assert completion_payload.targets[0].source_type == "match"
        assert completion_payload.targets[0].source_key == str(match_id)
        assert "Visitor 1" not in str(completion_work[0].payload)
        before_audit = int(
            await session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(
                    BusinessAuditEvent.target_entity_id == match_id
                )
            )
            or 0
        )

    # Head-Coach scoring findings are a read boundary and stage no work/audit.
    findings = await client.get(
        "/api/v1/data-quality", params={"domain": "scoring", "page_size": 100}
    )
    assert findings.status_code == 200, findings.text
    async with AsyncSessionFactory() as session:
        assert (
            await session.scalar(
                select(func.count(BackgroundWorkItem.id)).where(
                    BackgroundWorkItem.source_type == "match",
                    BackgroundWorkItem.source_key == str(match_id),
                )
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count(BusinessAuditEvent.id)).where(
                    BusinessAuditEvent.target_entity_id == match_id
                )
            )
            == before_audit
        )

    history = await client.get(
        f"/api/v1/matches/{match_id}/innings/{second_state['id']}/deliveries"
    )
    assert history.status_code == 200, history.text
    active = history.json()["deliveries"][0]
    scorecard = await client.get(f"/api/v1/matches/{match_id}/scorecard")
    assert scorecard.status_code == 200, scorecard.text
    replacement = {
        "striker_participant_id": winning_delivery["active_revision"][
            "striker_participant_id"
        ],
        "non_striker_participant_id": winning_delivery["active_revision"][
            "non_striker_participant_id"
        ],
        "bowler_participant_id": winning_delivery["active_revision"][
            "bowler_participant_id"
        ],
        "runs_off_bat": 6,
        "extras": {},
    }
    corrected = await client.post(
        f"/api/v1/matches/{match_id}/innings/{second_state['id']}/deliveries/"
        f"{winning_delivery['id']}/correction",
        json={
            "match_version_number": scorecard.json()["match_version_number"],
            "innings_version_number": second_state["version_number"],
            "expected_revision_number": active["active_revision"]["revision_number"],
            "reason": "Correct the recorded winning boundary",
            "replacement": replacement,
        },
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["match_lifecycle_state"] == "completed"

    async with AsyncSessionFactory() as session:
        work = await session.get(BackgroundWorkItem, work_id)
        assert work is not None
        assert (
            await session.scalar(
                select(func.count(BackgroundWorkItem.id)).where(
                    BackgroundWorkItem.source_type == "match",
                    BackgroundWorkItem.source_key == str(match_id),
                )
            )
            == 1
        )
        corrected_payload = RagReconciliationPayloadV1.model_validate(work.payload)
        assert corrected_payload.scoring_refresh is not None
        assert corrected_payload.scoring_refresh.reason == "correction"
        assert (
            corrected_payload.scoring_refresh.projection_revision
            > completion_payload.scoring_refresh.projection_revision
        )
        final_revision = await session.scalar(
            select(DeliveryRevision).where(
                DeliveryRevision.delivery_id == UUID(winning_delivery["id"]),
                DeliveryRevision.revision_state == "active",
            )
        )
        assert final_revision is not None and final_revision.runs_off_bat == 6

    typed_payload = RagReconciliationPayloadV1.model_validate(work.payload)
    settings = get_settings()
    registry = build_background_job_registry(settings=settings)
    provider = FakeEmbeddingProvider()
    context = BackgroundHandlerContext(
        settings=settings,
        session_factory=AsyncSessionFactory,
        redis=None,
        provider=provider,
        registry=registry,
    )
    await rag_reconciliation_handler(context, typed_payload)
    calls_after_refresh = provider.document_call_count
    assert calls_after_refresh > 0
    await rag_reconciliation_handler(context, typed_payload)
    assert provider.document_call_count == calls_after_refresh

    async with AsyncSessionFactory() as session:
        document = await session.scalar(
            select(RagDocument).where(
                RagDocument.source_type == "match",
                RagDocument.source_key == str(match_id),
            )
        )
        assert document is not None
        assert "innings 2: 6/0 from 1 legal balls" in document.semantic_text
        assert "Visitor 1" not in document.semantic_text
        match_before_failure = await session.get(Match, match_id)
        assert match_before_failure is not None
        lifecycle_before_failure = match_before_failure.lifecycle_state
        total_before_failure = corrected.json()["innings_total_runs"]
        count_before_failure = await session.scalar(
            select(func.count(DeliveryRevision.id)).where(
                DeliveryRevision.delivery_id == UUID(winning_delivery["id"])
            )
        )

    # A local provider outage affects only the background refresh lifecycle.
    async with AsyncSessionFactory() as session:
        match_row = await session.get(Match, match_id)
        assert match_row is not None
        match_row.venue = "Changed for refresh failure check"
        match_row.version_number += 1
        await session.commit()
    failing_context = BackgroundHandlerContext(
        settings=settings,
        session_factory=AsyncSessionFactory,
        redis=None,
        provider=_UnavailableEmbeddingProvider(),
        registry=registry,
    )
    with pytest.raises(RagReconciliationExecutionError):
        await rag_reconciliation_handler(failing_context, typed_payload)
    async with AsyncSessionFactory() as session:
        match_after_failure = await session.get(Match, match_id)
        assert match_after_failure is not None
        assert match_after_failure.lifecycle_state == lifecycle_before_failure
        current_innings = await session.get(Innings, UUID(second_state["id"]))
        assert current_innings is not None
        assert current_innings.total_runs == total_before_failure
        assert (
            await session.scalar(
                select(func.count(DeliveryRevision.id)).where(
                    DeliveryRevision.delivery_id == UUID(winning_delivery["id"])
                )
            )
            == count_before_failure
        )
