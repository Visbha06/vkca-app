"""Registered background handler for bounded current-state RAG reconciliation."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select

from src.services.background_jobs.retry import (
    SAFE_FAILURE_MESSAGES,
    FailureCategory,
    FailureClassification,
    RetryDisposition,
    classify_failure,
)
from src.services.rag.contracts import (
    MAX_RAG_MUTATION_TARGETS,
    RagReconciliationPayloadV1,
    RagRunStatus,
    RagTargetRef,
)
from src.services.rag.indexing import RagIndexingService
from src.services.rag.registry import source_registry


class RagReconciliationExecutionError(RuntimeError):
    """A safe retryable RAG run outcome did not fully reconcile its targets."""


@dataclass(frozen=True, slots=True)
class RagManualTriggerRequest:
    """Validated, minimal operator intent for the registered RAG trigger."""

    payload: RagReconciliationPayloadV1
    coalescing_key: str
    source_type: str | None
    source_key: str | None
    safe_metadata: dict[str, object]


def build_rag_manual_trigger(
    *,
    safety: bool,
    source_type: str | None = None,
    source_key: str | None = None,
) -> RagManualTriggerRequest:
    """Create one approved targeted or incremental/repair trigger request."""

    if safety:
        if source_type is not None or source_key is not None:
            raise ValueError("RAG safety triggers do not accept source targets.")
        payload = RagReconciliationPayloadV1(
            mode="incremental_safety",
            reason="repair",
        )
        return RagManualTriggerRequest(
            payload=payload,
            coalescing_key="rag:incremental-safety",
            source_type=None,
            source_key=None,
            safe_metadata={
                "reason": payload.reason,
                "trigger": "operator",
                "trigger_kind": "incremental_safety",
            },
        )

    if source_type is None or source_key is None:
        raise ValueError("Targeted RAG triggers require a source type and key.")
    target = RagTargetRef(source_type=source_type, source_key=source_key)
    source_registry.validate_targets((target,))
    payload = RagReconciliationPayloadV1(
        mode="targets",
        reason="manual",
        targets=(target,),
    )
    return RagManualTriggerRequest(
        payload=payload,
        coalescing_key=f"rag:{target.source_type}:{target.source_key}",
        source_type=target.source_type,
        source_key=target.source_key,
        safe_metadata={"reason": payload.reason, "trigger": "operator"},
    )


def classify_rag_reconciliation_failure(
    error: BaseException,
) -> FailureClassification:
    """Classify failed RAG run reports without retaining provider details."""

    if isinstance(error, RagReconciliationExecutionError):
        category = FailureCategory.TRANSIENT_DEPENDENCY_FAILURE
        return FailureClassification(
            category=category,
            disposition=RetryDisposition.RETRY,
            safe_message=SAFE_FAILURE_MESSAGES[category],
        )
    return classify_failure(error)


def coalesce_rag_reconciliation_payloads(
    existing: BaseModel,
    incoming: BaseModel,
) -> RagReconciliationPayloadV1:
    """Merge stable target instructions without retaining stale source snapshots."""

    old = RagReconciliationPayloadV1.model_validate(existing)
    new = RagReconciliationPayloadV1.model_validate(incoming)
    if old.mode == "incremental_safety":
        return old
    if new.mode == "incremental_safety":
        return new
    targets = {
        (target.source_type, target.source_key): target
        for target in (*old.targets, *new.targets)
    }
    if len(targets) > MAX_RAG_MUTATION_TARGETS:
        return RagReconciliationPayloadV1(
            mode="incremental_safety",
            reason="safety",
        )
    reason = "mutation" if "mutation" in {old.reason, new.reason} else new.reason
    scoring_refresh = None
    refreshes = [
        value
        for value in (old.scoring_refresh, new.scoring_refresh)
        if value is not None
    ]
    if refreshes:
        scoring_refresh = max(
            enumerate(refreshes),
            key=lambda item: (item[1].projection_revision, item[0]),
        )[1]
    return RagReconciliationPayloadV1(
        mode="targets",
        reason=reason,
        targets=tuple(targets[key] for key in sorted(targets)),
        scoring_refresh=scoring_refresh,
    )


async def rag_reconciliation_handler(context: object, payload: BaseModel) -> None:
    """Reload current registered sources and delegate all RAG work to its service."""

    typed_payload = RagReconciliationPayloadV1.model_validate(payload)
    settings = getattr(context, "settings", None)
    session_factory = getattr(context, "session_factory", None)
    provider = getattr(context, "provider", None)
    if settings is None or not callable(session_factory) or provider is None:
        raise RuntimeError("RAG reconciliation runtime resources are unavailable")

    if typed_payload.mode == "targets":
        # Reject unknown source families before opening a run. The indexing service
        # resolves current dependency closure from the same registry afterward.
        source_registry.validate_targets(typed_payload.targets)
        if typed_payload.scoring_refresh is not None and not any(
            target.source_type == "match"
            and target.source_key == str(typed_payload.scoring_refresh.match_id)
            for target in typed_payload.targets
        ):
            raise ValueError("A scoring refresh must target its current Match source.")

    async with session_factory() as session:
        if typed_payload.scoring_refresh is not None:
            from src.models.scoring.scoring_policy import ScoringPolicy
            from src.services.performance_service import (
                sync_delivery_derived_legacy_performances,
            )

            policy = await session.scalar(
                select(ScoringPolicy).where(
                    ScoringPolicy.match_id == typed_payload.scoring_refresh.match_id
                )
            )
            if policy is not None:
                await sync_delivery_derived_legacy_performances(
                    session,
                    match_id=typed_payload.scoring_refresh.match_id,
                    over_length_legal_balls=policy.over_length_legal_balls,
                )
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=int(settings.rag_embedding_batch_size),
            timeout_seconds=float(settings.rag_embedding_timeout_seconds),
            registry=source_registry,
        )
        if typed_payload.mode == "targets":
            reports = await service.reconcile_targets(typed_payload.targets)
        elif typed_payload.reason == "repair":
            reports = (await service.run_repair(),)
        else:
            reports = (await service.run_incremental(),)

    if not reports or any(
        report.status is not RagRunStatus.COMPLETED for report in reports
    ):
        raise RagReconciliationExecutionError(
            "RAG reconciliation did not reach a complete safe outcome"
        )
