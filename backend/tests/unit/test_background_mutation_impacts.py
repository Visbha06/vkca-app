"""Unit coverage for transaction-local domain-to-RAG mutation impacts."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.services.rag.contracts import (
    RagMutationImpact,
    RagMutationOperation,
    RagMutationRef,
    RagMutationSource,
)
from src.services.rag.registry import RagMutationStager, source_registry


def _ref(source: RagMutationSource, source_key: object) -> RagMutationRef:
    return RagMutationRef(source=source, source_key=str(source_key))


def test_domain_impacts_map_to_registered_stable_source_references() -> None:
    player_id = uuid4()
    team_id = uuid4()
    match_id = uuid4()
    impact = RagMutationImpact(
        operation=RagMutationOperation.UPSERT,
        current_refs=(
            _ref(RagMutationSource.PLAYER, player_id),
            _ref(RagMutationSource.TEAM, team_id),
            _ref(RagMutationSource.MATCH, match_id),
        ),
    )

    targets = source_registry.resolve_mutation_impact(impact)

    assert [(target.source_type, target.source_key) for target in targets] == [
        ("match", str(match_id)),
        ("player_profile", str(player_id)),
        ("team", str(team_id)),
    ]


def test_relationship_and_deletion_hints_preserve_old_and_new_references() -> None:
    team_id = uuid4()
    removed_player_id = uuid4()
    added_player_id = uuid4()
    impact = RagMutationImpact(
        operation=RagMutationOperation.RELATIONSHIP,
        current_refs=(
            _ref(RagMutationSource.TEAM, team_id),
            _ref(RagMutationSource.PLAYER, added_player_id),
        ),
        previous_refs=(
            _ref(RagMutationSource.TEAM, team_id),
            _ref(RagMutationSource.PLAYER, removed_player_id),
        ),
        coalescing_ref=_ref(RagMutationSource.TEAM, team_id),
    )

    targets = source_registry.resolve_mutation_impact(impact)

    assert {(target.source_type, target.source_key) for target in targets} == {
        ("team", str(team_id)),
        ("player_profile", str(removed_player_id)),
        ("player_profile", str(added_player_id)),
    }
    assert source_registry.resolve_coalescing_target(impact).source_key == str(team_id)


@pytest.mark.asyncio
async def test_authorization_only_change_is_a_noop_without_side_effects(mocker) -> None:
    outbox = mocker.Mock()
    outbox.stage = mocker.AsyncMock()
    session = mocker.Mock()
    session.commit = mocker.AsyncMock()
    session.rollback = mocker.AsyncMock()
    network = mocker.AsyncMock()
    audit = mocker.AsyncMock()
    stager = RagMutationStager(source_registry, outbox=outbox)
    impact = RagMutationImpact(
        operation=RagMutationOperation.UPSERT,
        current_refs=(),
        semantic_change=False,
    )

    staged = await stager.stage(session, impact)

    assert staged is None
    outbox.stage.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    network.assert_not_awaited()
    audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_staging_uses_bounded_targets_without_commit_network_or_audit(
    mocker,
) -> None:
    player_id = uuid4()
    work_item = object()
    outbox = mocker.Mock()
    outbox.stage = mocker.AsyncMock(return_value=work_item)
    session = mocker.Mock()
    session.commit = mocker.AsyncMock()
    session.rollback = mocker.AsyncMock()
    provider = mocker.AsyncMock()
    redis = mocker.AsyncMock()
    audit = mocker.AsyncMock()
    stager = RagMutationStager(source_registry, outbox=outbox)

    staged = await stager.stage(
        session,
        RagMutationImpact(
            operation=RagMutationOperation.UPSERT,
            current_refs=(_ref(RagMutationSource.PLAYER, player_id),),
        ),
    )

    assert staged is work_item
    outbox.stage.assert_awaited_once()
    call = outbox.stage.await_args
    assert call.args[:2] == (session, "rag_reconciliation")
    assert call.args[2].model_dump(mode="json") == {
        "mode": "targets",
        "reason": "mutation",
        "targets": [{"source_type": "player_profile", "source_key": str(player_id)}],
    }
    assert call.kwargs["coalescing_key"] == f"rag:player_profile:{player_id}"
    assert call.kwargs["source_type"] == "player_profile"
    assert call.kwargs["source_key"] == str(player_id)
    assert call.kwargs["safe_metadata"] == {
        "reason": "mutation",
        "source_count": 1,
    }
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
    provider.assert_not_awaited()
    redis.assert_not_awaited()
    audit.assert_not_awaited()
