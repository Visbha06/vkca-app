"""Application service for unambiguous cricket Match operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import MatchParticipantType, ScoringAuthority
from src.models.match import Match
from src.models.team import Team
from src.schemas.match import (
    ExternalMatchParticipantRequest,
    MatchCreate,
    MatchParticipantRequest,
    MatchUpdate,
)
from src.schemas.scoring import MatchConfigurationRequest, MatchConfigurationResponse
from src.services.occ import check_and_increment_version
from src.services.rag.contracts import (
    RagMutationImpact,
    RagMutationOperation,
    RagMutationRef,
    RagMutationSource,
)
from src.services.scoring.errors import ScoringAuthorityError


async def _stage_match_impact(session: AsyncSession, match_id: UUID) -> None:
    from src.services.rag.registry import stage_rag_mutation_impact

    reference = RagMutationRef(
        source=RagMutationSource.MATCH,
        source_key=str(match_id),
    )
    await stage_rag_mutation_impact(
        session,
        RagMutationImpact(
            operation=RagMutationOperation.UPSERT,
            current_refs=(reference,),
            coalescing_ref=reference,
        ),
    )


class MatchNotFoundError(Exception):
    """Raised when a Match cannot be updated."""

    def __init__(self) -> None:
        super().__init__("Match not found.")


class TeamNotFoundError(Exception):
    """Raised when a participant references a missing Team."""

    def __init__(self) -> None:
        super().__init__("One or more participant teams do not exist.")


class MatchService:
    """Persist and retrieve participant-safe cricket Matches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_teams(self, team_ids: set[UUID]) -> dict[UUID, Team]:
        """Load all participant Teams in one query and require exact coverage."""

        teams = list(
            (
                await self.session.scalars(
                    select(Team).where(Team.id.in_(team_ids)).order_by(Team.id)
                )
            ).all()
        )
        teams_by_id = {team.id: team for team in teams}
        if set(teams_by_id) != team_ids:
            raise TeamNotFoundError
        return teams_by_id

    async def _participant_columns(
        self, participants: MatchParticipantRequest
    ) -> dict[str, object]:
        """Map exactly one request union variant to persisted Match columns."""

        if isinstance(participants, ExternalMatchParticipantRequest):
            await self._load_teams({participants.academy_team_id})
            return {
                "participant_type": MatchParticipantType.EXTERNAL,
                "home_team_id": (
                    participants.academy_team_id
                    if participants.academy_side == "home"
                    else None
                ),
                "away_team_id": (
                    participants.academy_team_id
                    if participants.academy_side == "away"
                    else None
                ),
                "external_opponent_name": participants.external_opponent_name,
            }

        await self._load_teams({participants.home_team_id, participants.away_team_id})
        return {
            "participant_type": MatchParticipantType.INTERNAL,
            "home_team_id": participants.home_team_id,
            "away_team_id": participants.away_team_id,
            "external_opponent_name": None,
        }

    async def _get_loaded_match(self, match_id: UUID) -> Match:
        """Fetch one Match with both possible Team sides preloaded."""

        statement = (
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.scoring_policy),
                selectinload(Match.scoring_sides),
                selectinload(Match.scoring_participants),
            )
            .where(Match.id == match_id)
        )
        match = (await self.session.scalars(statement)).one_or_none()
        if match is None:
            raise MatchNotFoundError
        return match

    async def create_match(self, payload: MatchCreate) -> Match:
        """Persist a Match after validating every referenced Team in one query."""

        try:
            participant_columns = await self._participant_columns(payload.participants)
            match = Match(
                match_date=payload.match_date,
                format=payload.format,
                venue=payload.venue,
                result=payload.result,
                **participant_columns,
            )
            self.session.add(match)
            await self.session.flush()
            match_id = match.id
            await _stage_match_impact(self.session, match_id)
            await self.session.commit()
            return await self._get_loaded_match(match_id)
        except Exception:
            await self.session.rollback()
            raise

    async def update_match(self, match_id: UUID, payload: MatchUpdate) -> Match:
        """Replace a Match atomically when its optimistic-lock version is current."""

        try:
            match = await self.session.get(Match, match_id)
            if match is None:
                raise MatchNotFoundError
            authority = match.scoring_authority or ScoringAuthority.LEGACY_AGGREGATE
            if ScoringAuthority(authority) is ScoringAuthority.DELIVERY_HISTORY:
                raise ScoringAuthorityError(
                    "A configured scoring Match cannot be replaced through the "
                    "legacy Match update route."
                )
            participant_columns = await self._participant_columns(payload.participants)
            next_version = await check_and_increment_version(
                self.session,
                Match,
                match_id,
                payload.version_number,
            )
            match.match_date = payload.match_date
            match.format = payload.format
            match.venue = payload.venue
            match.result = payload.result
            match.version_number = next_version
            for column, value in participant_columns.items():
                setattr(match, column, value)
            await _stage_match_impact(self.session, match_id)
            await self.session.commit()
            return await self._get_loaded_match(match_id)
        except Exception:
            await self.session.rollback()
            raise

    async def list_matches(self) -> list[Match]:
        """Return all matches in chronological order."""

        statement = (
            select(Match)
            .options(
                selectinload(Match.home_team),
                selectinload(Match.away_team),
                selectinload(Match.scoring_policy),
                selectinload(Match.scoring_sides),
                selectinload(Match.scoring_participants),
            )
            .order_by(Match.match_date, Match.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_match(self, match_id: UUID) -> Match:
        """Return one Match with legacy and locked scoring identities loaded."""

        return await self._get_loaded_match(match_id)

    async def configure_scoring(
        self,
        match_id: UUID,
        payload: MatchConfigurationRequest,
        authenticated_user,
        *,
        request_id: str | None = None,
    ) -> MatchConfigurationResponse:
        """Delegate configuration through the Match aggregate's scoring seam."""

        from src.services.scoring.service import ScoringService

        return await ScoringService(self.session).configure_match(
            match_id,
            payload,
            authenticated_user,
            request_id=request_id,
        )
