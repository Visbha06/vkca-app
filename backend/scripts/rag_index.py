"""Run bounded full, incremental, targeted, or repair RAG reconciliation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_settings  # noqa: E402
from src.database import AsyncSessionFactory, engine  # noqa: E402
from src.services.rag.contracts import RagRunMode, RagRunStatus  # noqa: E402
from src.services.rag.embedding import create_embedding_provider  # noqa: E402
from src.services.rag.indexing import (  # noqa: E402
    RagIndexingService,
    failure_from_exception,
)
from src.services.rag.registry import source_registry  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=tuple(mode.value for mode in RagRunMode),
        required=True,
    )
    parser.add_argument("--source-type")
    return parser.parse_args()


def _safe_report(report: object) -> dict[str, object]:
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


async def _run(args: argparse.Namespace) -> int:
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
            report = await service.run_targeted(args.source_type)
        elif args.mode == "incremental":
            report = await service.run_incremental()
        elif args.mode == "repair":
            report = await service.run_repair()
        else:
            report = await service.run_full()
    print(json.dumps(_safe_report(report), sort_keys=True))
    if report.status is RagRunStatus.COMPLETED:
        return 0
    if report.status is RagRunStatus.PARTIAL:
        return 3
    return 2


def main() -> None:
    """Execute the operator command with sanitized errors and documented exits."""

    try:
        exit_code = asyncio.run(_run(_parse_args()))
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
        exit_code = 2
    finally:
        asyncio.run(engine.dispose())
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
