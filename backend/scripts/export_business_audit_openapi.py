"""Export the production business-audit routes for frontend contract types."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402

from src.routes.business_audit import router as business_audit_router  # noqa: E402


def business_audit_openapi() -> dict[str, object]:
    """Build OpenAPI from the feature's registered production routes."""

    contract_app = FastAPI(title="VKCA Business Audit Contract")
    contract_app.include_router(business_audit_router, prefix="/api/v1")
    return contract_app.openapi()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    """Write stable, sorted JSON for openapi-typescript."""

    args = _parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(business_audit_openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
