"""Bounded background-job status, dispatch, recovery, and RAG trigger commands."""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

from arq.connections import RedisSettings, create_pool

from src.config import get_settings
from src.database import AsyncSessionFactory, engine
from src.schemas.background_jobs import BackgroundCommandReport
from src.services.background_jobs.contracts import (
    BackgroundWorkState,
    json_job_deserializer,
    json_job_serializer,
)
from src.services.background_jobs.dispatcher import BackgroundJobDispatcher
from src.services.background_jobs.outbox import (
    BackgroundJobOutbox,
    BackgroundWorkNotFoundError,
)
from src.services.background_jobs.registry import build_background_job_registry
from src.services.background_jobs.retry import RetryPolicy
from src.services.rag.contracts import RagReconciliationPayloadV1, RagTargetRef
from src.services.rag.registry import source_registry

MAX_MANUAL_RETRIES = 3


def _bounded_limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 500:
        raise argparse.ArgumentTypeError("limit must be between 1 and 500")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse only allowlisted operator commands and bounded scalar inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="inspect sanitized durable work")
    status.add_argument(
        "--state",
        choices=tuple(state.value for state in BackgroundWorkState),
    )
    status.add_argument("--limit", type=_bounded_limit, default=50)

    dispatch = commands.add_parser("dispatch", help="run one dispatcher batch")
    dispatch.add_argument("--limit", type=_bounded_limit, default=50)

    recover = commands.add_parser("recover", help="reclaim expired work leases")
    recover.add_argument("--limit", type=_bounded_limit, default=50)

    retry = commands.add_parser("retry", help="retry one approved dead item")
    retry.add_argument("--work-id", type=UUID, required=True)

    trigger = commands.add_parser(
        "trigger-rag",
        help="stage one approved targeted RAG reconciliation",
    )
    trigger.add_argument("--source-type", required=True)
    trigger.add_argument("--source-key", required=True)

    args = parser.parse_args(argv)
    if args.command == "status" and args.limit > 100:
        parser.error("status --limit must be between 1 and 100")
    return args


def _retry_policy(settings: Any) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=int(settings.background_max_attempts),
        base_delay_seconds=float(settings.background_retry_base_seconds),
        max_delay_seconds=float(settings.background_retry_max_seconds),
        jitter_seconds=float(settings.background_retry_jitter_seconds),
        timeout_seconds=float(settings.background_job_timeout_seconds),
    )


async def _run(args: argparse.Namespace) -> object:
    settings = get_settings()
    registry = build_background_job_registry(settings=settings)
    outbox = BackgroundJobOutbox(
        registry,
        completed_retention_days=settings.background_completed_retention_days,
        dead_retention_days=settings.background_dead_retention_days,
    )

    if args.command == "status":
        selected_states = (
            (BackgroundWorkState(args.state),) if args.state is not None else None
        )
        async with AsyncSessionFactory() as session:
            return await outbox.inspect_status(
                session,
                states=selected_states,
                limit=args.limit,
            )

    if args.command == "recover":
        async with AsyncSessionFactory() as session:
            async with session.begin():
                return await outbox.recover_expired_leases(
                    session,
                    limit=args.limit,
                )

    if args.command == "retry":
        async with AsyncSessionFactory() as session:
            async with session.begin():
                current = await outbox.reload(session, args.work_id)
                if current is None:
                    raise BackgroundWorkNotFoundError("Background work was not found")
                requeued = await outbox.manual_requeue(
                    session,
                    current.id,
                    expected_version=current.version_number,
                    max_manual_retries=MAX_MANUAL_RETRIES,
                )
        return BackgroundCommandReport(
            command="retry",
            work_id=requeued.id,
            state=BackgroundWorkState(requeued.state),
        )

    if args.command == "trigger-rag":
        target = RagTargetRef(
            source_type=args.source_type,
            source_key=args.source_key,
        )
        source_registry.validate_targets((target,))
        payload = RagReconciliationPayloadV1(
            mode="targets",
            reason="manual",
            targets=(target,),
        )
        coalescing_key = f"rag:{target.source_type}:{target.source_key}"
        async with AsyncSessionFactory() as session:
            async with session.begin():
                staged = await outbox.stage(
                    session,
                    "rag_reconciliation",
                    payload,
                    coalescing_key=coalescing_key,
                    source_type=target.source_type,
                    source_key=target.source_key,
                    safe_metadata={
                        "reason": payload.reason,
                        "trigger": "operator",
                    },
                )
        return BackgroundCommandReport(
            command="trigger-rag",
            work_id=staged.id,
            state=BackgroundWorkState(staged.state),
        )

    if args.command == "dispatch":
        redis = await create_pool(
            RedisSettings.from_dsn(str(settings.redis_url)),
            job_serializer=json_job_serializer,
            job_deserializer=json_job_deserializer,
            default_queue_name=settings.background_queue_name,
        )
        try:
            dispatcher = BackgroundJobDispatcher(
                session_factory=AsyncSessionFactory,
                broker=redis,
                outbox=outbox,
                retry_policy=_retry_policy(settings),
                queue_name=settings.background_queue_name,
                dispatcher_id=f"operator:{uuid4()}",
                batch_size=settings.background_dispatch_batch_size,
                lease_seconds=settings.background_claim_lease_seconds,
                random_uniform=random.uniform,
            )
            return await dispatcher.dispatch_once(limit=args.limit)
        finally:
            await redis.aclose()

    raise ValueError("Unsupported background command")


def _json_payload(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    return model_dump(mode="json") if callable(model_dump) else value


async def _run_cli(args: argparse.Namespace) -> int:
    try:
        result = await _run(args)
        print(json.dumps(_json_payload(result), sort_keys=True))
        return 0
    except Exception:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_category": "invalid_or_unavailable_operation",
                    "message": "The bounded background command could not complete.",
                },
                sort_keys=True,
            )
        )
        return 2
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> None:
    """Execute one bounded command and emit only JSON-safe operational fields."""

    raise SystemExit(asyncio.run(_run_cli(parse_args(argv))))


if __name__ == "__main__":
    main()
