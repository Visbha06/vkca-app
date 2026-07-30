"""Coach-directory query and account-management operations."""

import secrets
from collections import defaultdict
from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import UserRole
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.user import User
from src.schemas.coach import (
    CoachCreate,
    CoachResponse,
    CoachTeamResponse,
    CoachTeamUpdate,
    PaginatedCoachResponse,
)
from src.services.auth_service import AuthService
from src.services.occ import check_and_increment_version
from src.services.password_service import PasswordService

CoachStatus = Literal["active", "inactive", "all"]


class CoachNotFoundError(Exception):
    """Raised when a requested user is not a coach account."""

    def __init__(self) -> None:
        super().__init__("Coach not found")


class CoachAlreadyExistsError(Exception):
    """Raised when an email address already belongs to an account."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"A user with email '{email}' already exists.")


class CoachTeamValidationError(Exception):
    """Raised when an assignment set is invalid."""

    def __init__(
        self,
        message: str = "team_ids: one or more teams do not exist",
    ) -> None:
        super().__init__(message)


class CoachInactiveError(Exception):
    """Raised when assignments are edited for an inactive coach."""

    def __init__(self) -> None:
        super().__init__("Not authorized")


class CoachService:
    """Query and manage coach accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _coach_response(
        rows: Sequence[Row[tuple[User, UUID, str]]],
    ) -> CoachResponse:
        """Build one coach response from its outer-joined team rows."""

        coach = rows[0][0]
        teams = [
            CoachTeamResponse(id=team_id, name=team_name)
            for _, team_id, team_name in rows
            if team_id is not None and team_name is not None
        ]
        return CoachResponse.model_validate(coach).model_copy(update={"teams": teams})

    @staticmethod
    def generate_temporary_password() -> str:
        """Return a secure one-time password that always satisfies policy."""

        password = f"Aa1!{secrets.token_urlsafe(16)}"
        PasswordService.validate_password_policy(password)
        return password

    async def create_coach(
        self,
        payload: CoachCreate,
    ) -> tuple[CoachResponse, str]:
        """Atomically create an Assistant Coach and initial assignments."""

        normalized_email = payload.email.strip().lower()
        duplicate = await self.session.scalar(
            select(User.id).where(func.lower(User.email) == normalized_email)
        )
        if duplicate is not None:
            raise CoachAlreadyExistsError(normalized_email)

        teams: list[Team] = []
        if payload.team_ids:
            team_result = await self.session.scalars(
                select(Team)
                .where(Team.id.in_(payload.team_ids))
                .order_by(Team.name, Team.id)
            )
            teams = list(team_result.all())
            if {team.id for team in teams} != set(payload.team_ids):
                raise CoachTeamValidationError

        temporary_password = self.generate_temporary_password()
        coach = User(
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=normalized_email,
            hashed_password=PasswordService.hash_password(temporary_password),
            role=UserRole.ASSISTANT_COACH,
            is_active=True,
        )
        self.session.add(coach)
        try:
            await self.session.flush()
            self.session.add_all(
                [TeamCoach(team_id=team.id, user_id=coach.id) for team in teams]
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise CoachAlreadyExistsError(normalized_email) from exc
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(coach)
        response = CoachResponse.model_validate(coach).model_copy(
            update={
                "teams": [
                    CoachTeamResponse(id=team.id, name=team.name) for team in teams
                ]
            }
        )
        return response, temporary_password

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
            await self.session.scalar(select(func.count(User.id)).where(*criteria)) or 0
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

    async def toggle_coach_status(
        self,
        coach_id: UUID,
        *,
        is_active: bool,
        version_number: int,
    ) -> CoachResponse:
        """Change coach status with OCC and atomic session revocation."""

        coach = await self.session.get(User, coach_id)
        if coach is None or coach.role not in {
            UserRole.HEAD_COACH,
            UserRole.ASSISTANT_COACH,
        }:
            raise CoachNotFoundError

        try:
            coach.version_number = await check_and_increment_version(
                self.session,
                User,
                coach_id,
                version_number,
            )
            coach.is_active = is_active
            if not is_active:
                await AuthService(self.session).revoke_user_sessions(
                    coach.id,
                    reason="user_disabled",
                    target_resource=f"/api/v1/users/{coach.id}/disable",
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return await self.get_coach(coach_id)

    async def update_team_assignments(
        self,
        coach_id: UUID,
        payload: CoachTeamUpdate,
    ) -> CoachResponse:
        """Atomically replace an active coach's complete assignment set."""

        coach = await self.session.get(User, coach_id)
        if coach is None or coach.role not in {
            UserRole.HEAD_COACH,
            UserRole.ASSISTANT_COACH,
        }:
            raise CoachNotFoundError
        if not coach.is_active:
            raise CoachInactiveError
        if len(set(payload.team_ids)) != len(payload.team_ids):
            raise CoachTeamValidationError(
                "team_ids: assignments must not contain duplicates"
            )

        if payload.team_ids:
            team_result = await self.session.scalars(
                select(Team)
                .where(Team.id.in_(payload.team_ids))
                .order_by(Team.name, Team.id)
            )
            teams = list(team_result.all())
            if {team.id for team in teams} != set(payload.team_ids):
                raise CoachTeamValidationError

        try:
            coach.version_number = await check_and_increment_version(
                self.session,
                User,
                coach_id,
                payload.version_number,
            )
            await self.session.execute(
                delete(TeamCoach).where(TeamCoach.user_id == coach_id)
            )
            self.session.add_all(
                [
                    TeamCoach(team_id=team_id, user_id=coach_id)
                    for team_id in payload.team_ids
                ]
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return await self.get_coach(coach_id)
