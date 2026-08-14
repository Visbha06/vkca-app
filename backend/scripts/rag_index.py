"""Run bounded full, incremental, targeted, or repair RAG reconciliation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_settings  # noqa: E402
from src.database import AsyncSessionFactory, engine  # noqa: E402
from src.services.rag.contracts import (  # noqa: E402
    RagIndexRunReport,
    RagOperationalStatusReport,
    RagRunMode,
    RagRunStatus,
)
from src.services.rag.embedding import create_embedding_provider  # noqa: E402
from src.services.rag.indexing import (  # noqa: E402
    RagIndexingService,
    failure_from_exception,
)
from src.services.rag.registry import source_registry  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--mode",
        choices=tuple(mode.value for mode in RagRunMode),
    )
    operation.add_argument(
        "--status",
        nargs="?",
        const="latest",
        metavar="RUN_ID",
        help="inspect one run or the latest bounded operational status",
    )
    parser.add_argument("--source-type", help="target/filter one registered source")
    parser.add_argument("--limit", type=int, default=100)
    return parser.parse_args()


def _safe_report(report: RagIndexRunReport) -> dict[str, object]:
    """Serialize aggregate operational state only; no corpus text/vector data."""

    return {
        "run_id": str(report.run_id),
        "mode": report.mode.value,
        "source_type": report.source_type,
        "status": report.status.value,
        "counters": report.counters.as_dict(),
        "failure_code": report.failure_code,
        "failure_message": report.failure_message,
    }


def _safe_status_report(report: RagOperationalStatusReport) -> dict[str, object]:
    """Serialize only bounded telemetry; never dereference corpus rows."""

    return {
        "source_filter": report.source_filter,
        "status_counts": dict(report.status_counts),
        "recoverable_source_count": report.recoverable_source_count,
        "repair_guidance": (
            "Run --mode repair for recoverable source states, or use "
            "--mode targeted --source-type <registered-source>."
            if report.recoverable_source_count
            else None
        ),
        "runs": [_safe_report(run) for run in report.runs],
        "sources": [
            {
                "source_type": source.source_type,
                "source_key": source.source_key,
                "status": source.status.value,
                "observed_source_version": source.observed_source_version,
                "builder_version": source.builder_version,
                "provider_name": source.provider_name,
                "model_name": source.model_name,
                "embedding_dimension": source.embedding_dimension,
                "last_attempt_at": (
                    source.last_attempt_at.isoformat()
                    if source.last_attempt_at is not None
                    else None
                ),
                "last_success_at": (
                    source.last_success_at.isoformat()
                    if source.last_success_at is not None
                    else None
                ),
                "failure_code": source.failure_code,
                "failure_message": source.failure_message,
                "recoverable": source.recoverable,
            }
            for source in report.sources
        ],
    }


async def _run(args: argparse.Namespace) -> int:
    if args.status is not None:
        run_id = None if args.status == "latest" else UUID(args.status)
        if args.source_type and args.source_type not in source_registry:
            raise ValueError("--source-type must name a registered RAG source")
        settings = get_settings()
        provider = create_embedding_provider(settings)
        async with AsyncSessionFactory() as session:
            service = RagIndexingService(
                session,
                provider=provider,
                batch_size=settings.rag_embedding_batch_size,
                timeout_seconds=settings.rag_embedding_timeout_seconds,
            )
            status_report = await service.inspect_status(
                run_id=run_id,
                source_type=args.source_type,
                limit=args.limit,
            )
        print(json.dumps(_safe_status_report(status_report), sort_keys=True))
        return 0

    if args.mode == "targeted" and not args.source_type:
        raise ValueError("--source-type is required for targeted mode")
    if args.mode != "targeted" and args.source_type:
        raise ValueError("--source-type is only valid with targeted mode")
    if args.source_type and args.source_type not in source_registry:
        raise ValueError("--source-type must name a registered RAG source")

    settings = get_settings()
    provider = create_embedding_provider(settings)
    async with AsyncSessionFactory() as session:
        service = RagIndexingService(
            session,
            provider=provider,
            batch_size=settings.rag_embedding_batch_size,
            timeout_seconds=settings.rag_embedding_timeout_seconds,
        )
        if args.mode == "targeted":
            run_report = await service.run_targeted(args.source_type)
        elif args.mode == "incremental":
            run_report = await service.run_incremental()
        elif args.mode == "repair":
            run_report = await service.run_repair()
        else:
            run_report = await service.run_full()
    print(json.dumps(_safe_report(run_report), sort_keys=True))
    if run_report.status is RagRunStatus.COMPLETED:
        return 0
    if run_report.status is RagRunStatus.PARTIAL:
        return 3
    return 2


async def _run_cli(args: argparse.Namespace) -> int:
    """Run the command and release database resources on the same event loop."""

    try:
        return await _run(args)
    except Exception as error:
        failure = failure_from_exception(error)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_code": failure.code,
                    "failure_message": failure.message,
                },
                sort_keys=True,
            )
        )
        return 2
    finally:
        await engine.dispose()


def main() -> None:
    """Execute the operator command with sanitized errors and documented exits."""

    raise SystemExit(asyncio.run(_run_cli(_parse_args())))


if __name__ == "__main__":
    main()
