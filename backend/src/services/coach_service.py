"""Read-only coach-directory query operations."""

from collections import defaultdict
from typing import Literal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.user import User
from src.schemas.coach import (
    CoachResponse,
    CoachTeamResponse,
    PaginatedCoachResponse,
)

CoachStatus = Literal["active", "inactive", "all"]


class CoachNotFoundError(Exception):
    """Raised when a requested user is not a coach account."""

    def __init__(self) -> None:
        super().__init__("Coach not found")


class CoachService:
    """List coach accounts while preserving a stable, paginated order."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _coach_response(
        rows: list[tuple[User, object | None, str | None]],
    ) -> CoachResponse:
        """Build one coach response from its outer-joined team rows."""

        coach = rows[0][0]
        teams = [
            CoachTeamResponse(id=team_id, name=team_name)
            for _, team_id, team_name in rows
            if team_id is not None and team_name is not None
        ]
        return CoachResponse.model_validate(coach).model_copy(
            update={"teams": teams}
        )

    async def list_coaches(
        self,
        *,
        status: CoachStatus = "active",
        page: int = 1,
        page_size: int = 12,
    ) -> PaginatedCoachResponse:
        """Return one page of coaches and their assigned team names."""

        if status not in {"active", "inactive", "all"}:
            raise ValueError("status must be active, inactive, or all")
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        criteria = [
            User.role.in_([UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH]),
        ]
        if status == "active":
            criteria.append(User.is_active.is_(True))
        elif status == "inactive":
            criteria.append(User.is_active.is_(False))

        total_coaches = int(
            await self.session.scalar(
                select(func.count(User.id)).where(*criteria)
            )
            or 0
        )
        order = (
            case((User.role == UserRole.HEAD_COACH, 0), else_=1),
            User.last_name.asc(),
            User.first_name.asc(),
            User.id.asc(),
        )
        paged_coach_ids = (
            select(User.id)
            .where(*criteria)
            .order_by(*order)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .subquery()
        )
        statement = (
            select(User, Team.id, Team.name)
            .join(paged_coach_ids, User.id == paged_coach_ids.c.id)
            .outerjoin(TeamCoach, TeamCoach.user_id == User.id)
            .outerjoin(Team, Team.id == TeamCoach.team_id)
            .order_by(*order)
        )
        rows = (await self.session.execute(statement)).all()
        teams_by_coach: dict[object, list[CoachTeamResponse]] = defaultdict(list)
        coach_by_id: dict[object, User] = {}
        for coach, team_id, team_name in rows:
            coach_by_id[coach.id] = coach
            if team_id is not None and team_name is not None:
                teams_by_coach[coach.id].append(
                    CoachTeamResponse(id=team_id, name=team_name)
                )

        coaches = [
            CoachResponse.model_validate(coach).model_copy(
                update={"teams": teams_by_coach[coach_id]}
            )
            for coach_id, coach in coach_by_id.items()
        ]
        total_pages = (total_coaches + page_size - 1) // page_size
        return PaginatedCoachResponse(
            coaches=coaches,
            page=page,
            page_size=page_size,
            total_coaches=total_coaches,
            total_pages=total_pages,
            has_previous=page > 1,
            has_next=page < total_pages,
        )

    async def get_coach(self, coach_id: UUID) -> CoachResponse:
        """Return one coach with every assigned team, or a coach-specific 404."""

        statement = (
            select(User, Team.id, Team.name)
            .outerjoin(TeamCoach, TeamCoach.user_id == User.id)
            .outerjoin(Team, Team.id == TeamCoach.team_id)
            .where(
                User.id == coach_id,
                User.role.in_([UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH]),
            )
            .order_by(Team.name.asc(), Team.id.asc())
        )
        rows = (await self.session.execute(statement)).all()
        if not rows:
            raise CoachNotFoundError
        return self._coach_response(rows)
