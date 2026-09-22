"""Read-only scoring consistency reporting coverage."""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.enums import QualityDomain, QualityEntityType, QualityRuleId
from src.models.match import Match
from src.routes.data_quality import router
from src.schemas.data_quality import DataQualityQuery
from src.services.data_quality_rules import (
    RULE_REGISTRY,
    EvaluationContext,
    ScoringQualityProjection,
)
from src.services.data_quality_service import DataQualityService

SCORING_RULE_IDS = tuple(
    rule_id for rule_id in QualityRuleId if rule_id.value.startswith("scoring.")
)


def test_all_scoring_consistency_classes_are_reported_without_remediation(mocker):
    match_id, innings_id = uuid4(), uuid4()
    context = EvaluationContext(
        scoring=(
            ScoringQualityProjection(
                match_id=match_id,
                entity_id=innings_id,
                entity_type=QualityEntityType.INNINGS,
                entity_label="Match innings 1",
                issues=tuple(
                    (rule_id, f"Detected {rule_id.value}")
                    for rule_id in SCORING_RULE_IDS
                ),
            ),
        )
    )
    session = mocker.Mock()

    page = DataQualityService(session).evaluate(
        context,
        DataQualityQuery(domain=QualityDomain.SCORING, page_size=100),
    )

    assert {finding.rule_id for finding in page.findings} == set(SCORING_RULE_IDS)
    assert page.summary.domain_counts[QualityDomain.SCORING] == len(SCORING_RULE_IDS)
    assert all(finding.direct_remediation is None for finding in page.findings)
    assert all(
        finding.related_entities[0].entity_id == match_id for finding in page.findings
    )
    assert session.mock_calls == []


def test_scoring_rules_require_normal_correction_workflow():
    assert SCORING_RULE_IDS
    for rule_id in SCORING_RULE_IDS:
        rule = RULE_REGISTRY[rule_id]
        assert rule.domain is QualityDomain.SCORING
        assert rule.remediation_policy == "manual"
        assert rule.recommended_action


def test_data_quality_exposes_no_public_rerun_or_scoring_repair_endpoint():
    data_quality_paths = {
        route.path
        for route in router.routes
        if getattr(route, "path", "").startswith("/data-quality")
    }

    assert data_quality_paths == {
        "/data-quality",
        "/data-quality/remediations",
    }


@pytest.mark.asyncio
async def test_malformed_scoring_graph_becomes_a_finding_instead_of_failing(mocker):
    match = Match(
        id=uuid4(),
        match_date=date(2026, 9, 10),
        format="T20",
        participant_type="external",
        home_team_id=uuid4(),
        external_opponent_name="Visitors",
        venue="Academy",
        result="Scheduled",
        version_number=1,
    )

    def result(rows):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(rows)))

    session = mocker.Mock()
    session.execute = mocker.AsyncMock(
        side_effect=[result([match]), result([]), result([]), result([])]
    )
    service = DataQualityService(session)
    mocker.patch.object(
        service,
        "_inspect_scoring_match",
        side_effect=ValueError("malformed persisted enum"),
    )

    projections = await service._load_scoring_quality()

    assert len(projections) == 1
    assert projections[0].issues[0][0] is (
        QualityRuleId.SCORING_HISTORICAL_STATE_MALFORMED
    )
