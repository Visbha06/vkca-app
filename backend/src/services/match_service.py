"""Application service for cricket match operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.match import Match
from src.schemas.match import MatchCreate


class MatchService:
    """Create and list cricket matches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_match(self, payload: MatchCreate) -> Match:
        """Persist a match record."""

        match = Match(**payload.model_dump())
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def list_matches(self) -> list[Match]:
        """Return all matches in chronological order."""

        statement = select(Match).order_by(Match.match_date, Match.id)
        return list((await self.session.scalars(statement)).all())
