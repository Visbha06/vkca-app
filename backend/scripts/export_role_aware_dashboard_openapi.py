"""Export OpenAPI contracts for the role-aware dashboard feature boundary."""

import argparse
import json
import sys
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, Query, status  # noqa: E402

from src.schemas.dashboard import (  # noqa: E402
    DashboardResponse,
    RoleAwareApiErrorResponse,
)
from src.schemas.match import MatchCreate, MatchResponse, MatchUpdate  # noqa: E402
from src.schemas.player_account import (  # noqa: E402
    PaginatedPlayerAccountResponse,
    PlayerAccountAssociationResponse,
    PlayerAccountLinkRequest,
    PlayerAccountReassignRequest,
    PlayerAccountUnlinkRequest,
)

DASHBOARD_PATH = "/api/v1/dashboard"
MATCH_COLLECTION_PATH = "/api/v1/matches"
MATCH_DETAIL_PATH = "/api/v1/matches/{match_id}"
ACCOUNT_LOOKUP_PATH = "/api/v1/players/account-linking/users"
ACCOUNT_ASSOCIATION_PATH = "/api/v1/players/{player_id}/account"
ACCOUNT_REASSIGN_PATH = "/api/v1/players/{player_id}/account/reassign"
HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
)


def _error_responses(
    *status_codes: int,
) -> dict[int | str, dict[str, Any]]:
    """Return the feature's existing non-sensitive error envelope metadata."""

    return {
        status_code: {
            "model": RoleAwareApiErrorResponse,
            "description": "Request could not be completed.",
        }
        for status_code in status_codes
    }


def _contract_app() -> FastAPI:
    """Build contract operations until their production routes are complete."""

    contract_app = FastAPI(title="VKCA Role-Aware Dashboard Contract")

    @contract_app.get(
        DASHBOARD_PATH,
        response_model=DashboardResponse,
        operation_id="get_role_aware_dashboard",
        responses=_error_responses(401, 403, 500),
    )
    async def get_role_aware_dashboard() -> DashboardResponse:
        raise NotImplementedError

    @contract_app.get(
        MATCH_COLLECTION_PATH,
        response_model=list[MatchResponse],
        operation_id="list_matches",
        responses=_error_responses(401, 403),
    )
    async def list_matches() -> list[MatchResponse]:
        raise NotImplementedError

    @contract_app.post(
        MATCH_COLLECTION_PATH,
        response_model=MatchResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="create_match",
        responses=_error_responses(401, 403, 409, 422),
    )
    async def create_match(payload: MatchCreate) -> MatchResponse:
        raise NotImplementedError

    @contract_app.put(
        MATCH_DETAIL_PATH,
        response_model=MatchResponse,
        operation_id="update_match",
        responses=_error_responses(401, 403, 404, 409, 422),
    )
    async def update_match(match_id: UUID, payload: MatchUpdate) -> MatchResponse:
        raise NotImplementedError

    @contract_app.get(
        ACCOUNT_LOOKUP_PATH,
        response_model=PaginatedPlayerAccountResponse,
        operation_id="list_eligible_player_accounts",
        responses=_error_responses(401, 403, 422),
    )
    async def list_eligible_player_accounts(
        search: Annotated[str | None, Query(max_length=255)] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> PaginatedPlayerAccountResponse:
        raise NotImplementedError

    @contract_app.put(
        ACCOUNT_ASSOCIATION_PATH,
        response_model=PlayerAccountAssociationResponse,
        operation_id="link_player_account",
        responses=_error_responses(401, 403, 404, 409, 422),
    )
    async def link_player_account(
        player_id: UUID,
        payload: PlayerAccountLinkRequest,
    ) -> PlayerAccountAssociationResponse:
        raise NotImplementedError

    @contract_app.delete(
        ACCOUNT_ASSOCIATION_PATH,
        response_model=PlayerAccountAssociationResponse,
        operation_id="unlink_player_account",
        responses=_error_responses(401, 403, 404, 409, 422),
    )
    async def unlink_player_account(
        player_id: UUID,
        payload: PlayerAccountUnlinkRequest,
    ) -> PlayerAccountAssociationResponse:
        raise NotImplementedError

    @contract_app.post(
        ACCOUNT_REASSIGN_PATH,
        response_model=PlayerAccountAssociationResponse,
        operation_id="reassign_player_account",
        responses=_error_responses(401, 403, 404, 409, 422),
    )
    async def reassign_player_account(
        player_id: UUID,
        payload: PlayerAccountReassignRequest,
    ) -> PlayerAccountAssociationResponse:
        raise NotImplementedError

    return contract_app


def _production_path_is_complete(
    contract_path: object,
    application_path: object,
) -> bool:
    """Use production operations only when every contract method is registered."""

    if not isinstance(contract_path, dict) or not isinstance(application_path, dict):
        return False
    required_methods = set(contract_path).intersection(HTTP_METHODS)
    return required_methods.issubset(application_path)


def role_aware_dashboard_openapi() -> dict[str, object]:
    """Prefer complete production paths and retain contract-only operations."""

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
        for path, contract_path in tuple(contract_paths.items()):
            application_path = application_paths.get(path)
            if _production_path_is_complete(contract_path, application_path):
                contract_paths[path] = application_path
                uses_application_components = True

    if uses_application_components:
        contract_components = schema.setdefault("components", {})
        application_components = application_schema.get("components", {})
        if isinstance(contract_components, dict) and isinstance(
            application_components, dict
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
    """Write stable, sorted JSON for openapi-typescript."""

    args = _parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(role_aware_dashboard_openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
