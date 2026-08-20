"""Unit coverage for Data Quality page assembly."""

from datetime import date
from uuid import uuid4

import pytest

from src.enums import QualityDomain, QualitySeverity
from src.schemas.data_quality import DataQualityQuery
from src.services.data_quality_rules import EvaluationContext, PlayerProjection
from src.services.data_quality_service import DataQualityService


def _context() -> EvaluationContext:
    return EvaluationContext(
        players=(
            PlayerProjection(uuid4(), "Zoe", "Player", date(2013, 1, 1), True),
            PlayerProjection(uuid4(), "Ada", "Player", date(2013, 1, 2), True),
        )
    )


def test_evaluation_is_deterministic_and_summary_remains_global_when_filtered() -> None:
    context = _context()
    page = DataQualityService.evaluate(context)
    filtered = DataQualityService.evaluate(
        context,
        DataQualityQuery(
            severity=QualitySeverity.WARNING, domain=QualityDomain.PLAYERS, page_size=1
        ),
    )

    assert [finding.entity_label for finding in page.findings] == [
        "Academy Head Coach coverage",
        "Ada Player",
        "Zoe Player",
    ]
    assert (
        page.summary.total_findings == 3
    )  # active players plus academy Head Coach integrity
    assert filtered.total_findings == 2
    assert filtered.summary == page.summary
    assert filtered.total_pages == 2 and filtered.has_next


@pytest.mark.asyncio
async def test_projection_loading_uses_a_fixed_query_budget(
    quality_projection_session_builder,
    projection_query_count_assertion,
    mocker,
) -> None:
    background_staging = mocker.patch(
        "src.services.rag.registry.stage_rag_mutation_impact"
    )
    session = quality_projection_session_builder([], [], [], [], [])

    context = await DataQualityService(session).load_context()

    assert context == EvaluationContext()
    projection_query_count_assertion(session)
    background_staging.assert_not_called()
