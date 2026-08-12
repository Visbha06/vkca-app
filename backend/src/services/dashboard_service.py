"""Bounded, read-time projection for the authenticated role-aware dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.enums import AgeGroup, EventType, ScopeKind, UserRole
from src.models.match import Match
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.schemas.calendar import CalendarEventInstance
from src.schemas.dashboard import (
    MAX_DASHBOARD_COACHES_PER_TEAM,
    MAX_DASHBOARD_CONTEXT_TEAMS,
    MAX_DASHBOARD_UPCOMING_EVENTS,
    DashboardActivePlayerCount,
    DashboardActivityEvent,
    DashboardCalendarEvent,
    DashboardCoachReference,
    DashboardContext,
    DashboardEmptySection,
    DashboardMatch,
    DashboardMyTeams,
    DashboardPlayerSlot,
    DashboardPlayerTeams,
    DashboardReadySection,
    DashboardRecentActivity,
    DashboardResponse,
    DashboardSection,
    DashboardSummary,
    DashboardTeam,
    DashboardUnavailableSection,
    DashboardUnlinkedSection,
    DashboardUpcomingEventList,
    DashboardUser,
)
from src.schemas.match import MatchResponse
from src.services.business_audit_service import BusinessAuditService
from src.services.calendar_recurrence import (
    MAX_CALENDAR_RANGE_DATES,
    academy_today,
)
from src.services.calendar_service import CalendarService

UNLINKED_MESSAGE = (
    "Contact your Head Coach to link your login account to your Player profile."
)


@dataclass(frozen=True, slots=True)
class DashboardScope:
    """Database-derived scope that is never accepted from a client."""

    role: UserRole
    teams: tuple[Team, ...]
    linked_player_id: UUID | None

    @property
    def team_ids(self) -> tuple[UUID, ...]:
        return tuple(team.id for team in self.teams)

    @property
    def age_groups(self) -> frozenset[AgeGroup]:
        return frozenset(AgeGroup(team.age_group) for team in self.teams)

    @property
    def is_unlinked_player(self) -> bool:
        return self.role is UserRole.PLAYER and self.linked_player_id is None


@dataclass(frozen=True, slots=True)
class DashboardCalendarProjection:
    """Effective Calendar instances retained for summary and context reuse."""

    instances: tuple[CalendarEventInstance, ...]

    @property
    def events(self) -> tuple[DashboardCalendarEvent, ...]:
        return tuple(DashboardService._calendar_event(item) for item in self.instances)


class DashboardService:
    """Build one deterministic dashboard without writes or persisted snapshots."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> None:
        self.session = session
        self.now = now

    async def get_dashboard(self, user: User) -> DashboardResponse:
        """Return the current dashboard for the database-authenticated User."""

        scope = await self._resolve_scope(user)
        dashboard_user = DashboardUser(
            id=user.id,
            display_name=f"{user.first_name} {user.last_name}".strip(),
            role=scope.role,
        )
        if scope.is_unlinked_player:
            return self._unlinked_response(dashboard_user)

        today = academy_today(self.now)
        calendar_projection: DashboardCalendarProjection | None = None
        training: DashboardSection[DashboardCalendarEvent]
        upcoming_events: DashboardSection[DashboardUpcomingEventList]
        try:
            calendar_projection = await self._load_calendar_projection(scope)
            training = self._training_section(scope, calendar_projection)
            upcoming_events = self._upcoming_section(calendar_projection)
        except Exception:
            training = DashboardUnavailableSection(
                message="Upcoming training is temporarily unavailable."
            )
            upcoming_events = DashboardUnavailableSection(
                message="Upcoming events are temporarily unavailable."
            )

        next_match: DashboardSection[DashboardMatch]
        if self._requires_team_scope(scope) and not scope.teams:
            next_match = DashboardEmptySection(message=self._no_team_message(scope))
        else:
            try:
                match = await self._load_next_match(scope, today)
                next_match = (
                    DashboardReadySection[DashboardMatch](data=match)
                    if match is not None
                    else DashboardEmptySection(
                        message="No upcoming matches in your scope."
                    )
                )
            except Exception:
                next_match = DashboardUnavailableSection(
                    message="Matches are temporarily unavailable."
                )

        player_slot: DashboardSection[DashboardPlayerSlot]
        if self._requires_team_scope(scope) and not scope.teams:
            player_slot = DashboardEmptySection(
                message=self._no_team_message(scope)
            )
        else:
            try:
                slot = await self._load_player_slot(scope)
                player_slot = DashboardReadySection(data=slot)
            except Exception:
                player_slot = DashboardUnavailableSection(
                    message="Player information is temporarily unavailable."
                )

        context: DashboardSection[DashboardContext]
        if scope.role is not UserRole.HEAD_COACH and not scope.teams:
            context = DashboardEmptySection(message=self._no_team_message(scope))
        else:
            try:
                context_data = await self._load_context(scope, calendar_projection)
                context = DashboardReadySection(data=context_data)
            except Exception:
                context = DashboardUnavailableSection(
                    message="Dashboard context is temporarily unavailable."
                )

        return DashboardResponse(
            user=dashboard_user,
            dashboard_state="ready",
            summary=DashboardSummary(
                training=training,
                next_match=next_match,
                player_slot=player_slot,
            ),
            upcoming_events=upcoming_events,
            context=context,
        )

    async def _resolve_scope(self, user: User) -> DashboardScope:
        """Resolve role and Team scope only from current database relations."""

        role = UserRole(user.role)
        if role is UserRole.HEAD_COACH:
            teams = await self._all_teams()
            return DashboardScope(role=role, teams=teams, linked_player_id=None)

        if role is UserRole.ASSISTANT_COACH:
            result = await self.session.scalars(
                select(Team)
                .join(TeamCoach, TeamCoach.team_id == Team.id)
                .where(TeamCoach.user_id == user.id)
                .order_by(Team.name, Team.id)
            )
            return DashboardScope(
                role=role,
                teams=tuple(result.all()),
                linked_player_id=None,
            )

        player = await self.session.scalar(
            select(Player).where(
                Player.user_id == user.id,
                Player.is_active.is_(True),
            )
        )
        if player is None:
            return DashboardScope(role=role, teams=(), linked_player_id=None)
        result = await self.session.scalars(
            select(Team)
            .join(TeamPlayer, TeamPlayer.team_id == Team.id)
            .where(TeamPlayer.player_id == player.id)
            .order_by(Team.name, Team.id)
        )
        return DashboardScope(
            role=role,
            teams=tuple(result.all()),
            linked_player_id=player.id,
        )

    async def _all_teams(self) -> tuple[Team, ...]:
        result = await self.session.scalars(select(Team).order_by(Team.name, Team.id))
        return tuple(result.all())

    async def _load_calendar_projection(
        self,
        scope: DashboardScope,
    ) -> DashboardCalendarProjection:
        """Reuse Calendar effective occurrences, then apply role audience scope."""

        today = academy_today(self.now)
        range_end = today + timedelta(days=MAX_CALENDAR_RANGE_DATES - 1)
        result = await CalendarService(self.session, now=self.now).get_range(
            today, range_end
        )
        unique: dict[str, CalendarEventInstance] = {}
        for instance in result.events:
            if not self._calendar_instance_is_relevant(instance, scope):
                continue
            unique.setdefault(instance.occurrence_id, instance)
        instances = sorted(unique.values(), key=self._calendar_sort_key)
        return DashboardCalendarProjection(instances=tuple(instances))

    async def _load_next_match(
        self,
        scope: DashboardScope,
        today: date,
    ) -> DashboardMatch | None:
        statement = select(Match).where(Match.match_date >= today)
        if scope.role is not UserRole.HEAD_COACH:
            if not scope.team_ids:
                return None
            statement = statement.where(
                or_(
                    Match.home_team_id.in_(scope.team_ids),
                    Match.away_team_id.in_(scope.team_ids),
                )
            )
        statement = (
            statement.options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
            )
            .order_by(Match.match_date, Match.id)
            .limit(1)
        )
        match = await self.session.scalar(statement)
        if match is None:
            return None
        response = MatchResponse.from_match(match)
        return DashboardMatch(
            id=response.id,
            match_date=response.match_date,
            format=response.format,
            participants=response.participants,
        )

    async def _load_player_slot(
        self,
        scope: DashboardScope,
    ) -> DashboardActivePlayerCount | DashboardPlayerTeams:
        if scope.role is UserRole.PLAYER:
            return DashboardPlayerTeams(
                team_count=len(scope.teams),
                team_names=[
                    team.name
                    for team in scope.teams[:MAX_DASHBOARD_CONTEXT_TEAMS]
                ],
            )

        if scope.role is UserRole.HEAD_COACH:
            count = int(
                await self.session.scalar(
                    select(func.count(Player.id)).where(Player.is_active.is_(True))
                )
                or 0
            )
        else:
            count = int(
                await self.session.scalar(
                    select(func.count(func.distinct(TeamPlayer.player_id)))
                    .join(Player, Player.id == TeamPlayer.player_id)
                    .where(
                        TeamPlayer.team_id.in_(scope.team_ids),
                        Player.is_active.is_(True),
                    )
                )
                or 0
            )
        return DashboardActivePlayerCount(
            count=count,
            team_count=len(scope.teams),
        )

    async def _load_context(
        self,
        scope: DashboardScope,
        calendar_projection: DashboardCalendarProjection | None,
    ) -> DashboardRecentActivity | DashboardMyTeams:
        if scope.role is UserRole.HEAD_COACH:
            recent = await BusinessAuditService(self.session).list_recent(limit=4)
            return DashboardRecentActivity(
                events=[
                    DashboardActivityEvent(
                        id=event.id,
                        actor_display_name=event.actor_display_name,
                        action_type=event.action_type,
                        action_category=event.action_category,
                        target_label=event.target_label,
                        summary=event.summary,
                        created_at=event.created_at,
                    )
                    for event in recent.events
                ]
            )

        displayed_teams = scope.teams[:MAX_DASHBOARD_CONTEXT_TEAMS]
        displayed_ids = tuple(team.id for team in displayed_teams)
        counts: dict[UUID, int] = {}
        if displayed_ids:
            result = await self.session.execute(
                select(
                    TeamPlayer.team_id,
                    func.count(func.distinct(TeamPlayer.player_id)),
                )
                .join(Player, Player.id == TeamPlayer.player_id)
                .where(
                    TeamPlayer.team_id.in_(displayed_ids),
                    Player.is_active.is_(True),
                )
                .group_by(TeamPlayer.team_id)
            )
            counts = {team_id: int(count) for team_id, count in result.all()}

        coaches_by_team: dict[UUID, list[DashboardCoachReference]] = {}
        if scope.role is UserRole.PLAYER and displayed_ids:
            result = await self.session.execute(
                select(
                    TeamCoach.team_id,
                    User.id,
                    User.first_name,
                    User.last_name,
                )
                .join(User, User.id == TeamCoach.user_id)
                .where(
                    TeamCoach.team_id.in_(displayed_ids),
                    User.is_active.is_(True),
                )
                .order_by(
                    TeamCoach.team_id,
                    func.lower(User.first_name),
                    func.lower(User.last_name),
                    User.id,
                )
            )
            for team_id, coach_id, first_name, last_name in result.all():
                team_coaches = coaches_by_team.setdefault(team_id, [])
                if len(team_coaches) < MAX_DASHBOARD_COACHES_PER_TEAM:
                    team_coaches.append(
                        DashboardCoachReference(
                            id=coach_id,
                            display_name=f"{first_name} {last_name}".strip(),
                        )
                    )

        instances = calendar_projection.instances if calendar_projection else ()
        teams = [
            DashboardTeam(
                id=team.id,
                name=team.name,
                age_group=AgeGroup(team.age_group),
                active_player_count=counts.get(team.id, 0),
                coaches=coaches_by_team.get(team.id, []),
                next_event=self._next_team_event(team, instances),
            )
            for team in displayed_teams
        ]
        return DashboardMyTeams(teams=teams)

    def _training_section(
        self,
        scope: DashboardScope,
        projection: DashboardCalendarProjection,
    ) -> DashboardReadySection[DashboardCalendarEvent] | DashboardEmptySection:
        if scope.role is UserRole.ASSISTANT_COACH and not scope.teams:
            return DashboardEmptySection(message=self._no_team_message(scope))
        training = next(
            (
                instance
                for instance in projection.instances
                if instance.event_type is EventType.PRACTICE
            ),
            None,
        )
        if training is None:
            return DashboardEmptySection(
                message="No upcoming training in your scope."
            )
        return DashboardReadySection(data=self._calendar_event(training))

    @staticmethod
    def _upcoming_section(
        projection: DashboardCalendarProjection,
    ) -> DashboardReadySection[list[DashboardCalendarEvent]] | DashboardEmptySection:
        events = list(projection.events[:MAX_DASHBOARD_UPCOMING_EVENTS])
        if not events:
            return DashboardEmptySection(
                message="No upcoming events in your scope."
            )
        return DashboardReadySection(data=events)

    @staticmethod
    def _calendar_instance_is_relevant(
        instance: CalendarEventInstance,
        scope: DashboardScope,
    ) -> bool:
        if scope.role is UserRole.HEAD_COACH:
            return True
        if instance.scope_kind is ScopeKind.ALL_ACADEMY:
            return True
        return bool(scope.age_groups.intersection(instance.age_groups))

    @staticmethod
    def _calendar_event(instance: CalendarEventInstance) -> DashboardCalendarEvent:
        return DashboardCalendarEvent(
            occurrence_id=instance.occurrence_id,
            event_date=instance.event_date,
            start_time=instance.start_time,
            end_time=instance.end_time,
            name=instance.name,
            event_type=instance.event_type,
            age_groups=instance.age_groups,
        )

    @staticmethod
    def _calendar_sort_key(instance: CalendarEventInstance):
        return (
            instance.event_date,
            0 if instance.is_all_day else 1,
            instance.start_time if instance.start_time is not None else time.min,
            instance.occurrence_id,
        )

    @classmethod
    def _next_team_event(
        cls,
        team: Team,
        instances: tuple[CalendarEventInstance, ...],
    ) -> DashboardCalendarEvent | None:
        age_group = AgeGroup(team.age_group)
        instance = next(
            (
                item
                for item in instances
                if item.scope_kind is ScopeKind.ALL_ACADEMY
                or age_group in item.age_groups
            ),
            None,
        )
        return None if instance is None else cls._calendar_event(instance)

    @staticmethod
    def _requires_team_scope(scope: DashboardScope) -> bool:
        return scope.role in {UserRole.ASSISTANT_COACH, UserRole.PLAYER}

    @staticmethod
    def _no_team_message(scope: DashboardScope) -> str:
        if scope.role is UserRole.ASSISTANT_COACH:
            return "No teams are currently assigned to you."
        return "You are not on a team yet."

    @staticmethod
    def _unlinked_response(user: DashboardUser) -> DashboardResponse:
        unlinked = DashboardUnlinkedSection(message=UNLINKED_MESSAGE)
        return DashboardResponse(
            user=user,
            dashboard_state="unlinked",
            summary=DashboardSummary(
                training=unlinked,
                next_match=unlinked,
                player_slot=unlinked,
            ),
            upcoming_events=unlinked,
            context=unlinked,
        )
