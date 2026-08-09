"""Export the OpenAPI contract used for frontend Data Quality types."""

import argparse
import json
import sys
from pathlib import Path
from typing import Annotated

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, Query  # noqa: E402

from src.enums import QualityDomain, QualityRuleId, QualitySeverity  # noqa: E402
from src.schemas.data_quality import (  # noqa: E402
    DataQualityPageResponse,
    DataQualityRemediationRequest,
    DataQualityRemediationResult,
)

READ_PATH = "/api/v1/data-quality"
REMEDIATION_PATH = "/api/v1/data-quality/remediations"


def _contract_app() -> FastAPI:
    """Build contract-only routes until their production routes are registered."""

    contract_app = FastAPI(title="VKCA Data Quality Contract")

    @contract_app.get(
        READ_PATH,
        response_model=DataQualityPageResponse,
        operation_id="get_data_quality",
    )
    async def get_data_quality(
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
        severity: QualitySeverity | None = None,
        domain: QualityDomain | None = None,
        rule_id: QualityRuleId | None = None,
    ) -> DataQualityPageResponse:
        raise NotImplementedError

    @contract_app.post(
        REMEDIATION_PATH,
        response_model=DataQualityRemediationResult,
        operation_id="apply_data_quality_remediation",
    )
    async def apply_data_quality_remediation(
        command: DataQualityRemediationRequest,
    ) -> DataQualityRemediationResult:
        raise NotImplementedError

    return contract_app


def data_quality_openapi() -> dict[str, object]:
    """Prefer registered production operations and fill only missing routes."""

    schema = _contract_app().openapi()
    try:
        from src.main import app

        application_schema = app.openapi()
    except Exception:
        return schema

    contract_paths = schema.setdefault("paths", {})
    application_paths = application_schema.get("paths", {})
    uses_application_components = False
    if isinstance(contract_paths, dict) and isinstance(application_paths, dict):
        for path in (READ_PATH, REMEDIATION_PATH):
            if path in application_paths:
                contract_paths[path] = application_paths[path]
                uses_application_components = True

    contract_components = schema.setdefault("components", {})
    application_components = application_schema.get("components", {})
    if (
        uses_application_components
        and isinstance(contract_components, dict)
        and isinstance(application_components, dict)
    ):
        for component_kind, values in application_components.items():
            if not isinstance(values, dict):
                continue
            existing = contract_components.setdefault(component_kind, {})
            if isinstance(existing, dict):
                existing.update(values)
    return schema


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    """Write a stable JSON document for openapi-typescript."""

    args = _parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data_quality_openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
