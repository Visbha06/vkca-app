"""PostgreSQL integration coverage for Match participant invariants."""

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionFactory
from src.enums import MatchFormat, MatchParticipantType
from src.models.business_audit_event import BusinessAuditEvent
from src.models.match import Match
from src.models.team import Team
from src.schemas.match import MatchCreate
from src.services.match_service import MatchService, TeamNotFoundError


@pytest_asyncio.fixture(loop_scope="session")
async def db_session() -> AsyncSession:
    """Provide an integration session enclosed by the shared rollback fixture."""

    async with AsyncSessionFactory() as session:
        yield session
        await session.rollback()


async def add_team(session: AsyncSession, name: str) -> Team:
    """Insert a Team usable by Match foreign keys."""

    team = Team(name=f"{name}-{uuid4()}", age_group="U15")
    session.add(team)
    await session.flush()
    return team


@pytest.mark.asyncio(loop_scope="session")
async def test_participant_constraints_and_rejected_mutations_do_not_audit(
    db_session: AsyncSession,
) -> None:
    home_team = await add_team(db_session, "Home")
    away_team = await add_team(db_session, "Away")
    audits_before = int(
        await db_session.scalar(select(func.count(BusinessAuditEvent.id))) or 0
    )
    invalid = Match(
        match_date=date(2026, 7, 1),
        format=MatchFormat.T20,
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=home_team.id,
        away_team_id=away_team.id,
        external_opponent_name="Should fail",
        venue="Main Ground",
        result="Scheduled",
    )
    db_session.add(invalid)

    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    invalid_payload = MatchCreate.model_validate(
        {
            "match_date": "2026-07-01",
            "format": "T20",
            "venue": "Main Ground",
            "result": "Scheduled",
            "participants": {
                "participant_type": "external",
                "academy_team_id": str(uuid4()),
                "external_opponent_name": "Northside CC",
                "academy_side": "home",
            },
        }
    )
    with pytest.raises(TeamNotFoundError):
        await MatchService(db_session).create_match(invalid_payload)

    audits_after = int(
        await db_session.scalar(select(func.count(BusinessAuditEvent.id))) or 0
    )
    assert audits_after == audits_before
