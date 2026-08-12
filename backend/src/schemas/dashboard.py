"""Strongly typed response boundary for the role-aware dashboard."""

from datetime import date, datetime, time
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.enums import (
    AgeGroup,
    AuditActionCategory,
    AuditActionType,
    EventType,
    MatchFormat,
    UserRole,
)
from src.schemas.match import MatchParticipantResponse

MAX_DASHBOARD_UPCOMING_EVENTS = 5
MAX_DASHBOARD_CONTEXT_TEAMS = 12
MAX_DASHBOARD_RECENT_ACTIVITY = 4
MAX_DASHBOARD_COACHES_PER_TEAM = 12


class RoleAwareApiErrorResponse(BaseModel):
    """Existing non-sensitive API error envelope used by feature operations."""

    detail: str = Field(min_length=1, max_length=500)


class DashboardReadySection[SectionData](BaseModel):
    """A dashboard section containing usable data."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    data: SectionData


class DashboardEmptySection(BaseModel):
    """A dashboard section with no eligible source records."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["empty"] = "empty"
    message: str = Field(min_length=1, max_length=500)


class DashboardUnlinkedSection(BaseModel):
    """A Player section withheld until an explicit profile link exists."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["unlinked"] = "unlinked"
    message: str = Field(min_length=1, max_length=500)


class DashboardUnavailableSection(BaseModel):
    """An independently failed section with explicit retry behavior."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["unavailable"] = "unavailable"
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = True


type DashboardSection[SectionData] = Annotated[
    DashboardReadySection[SectionData]
    | DashboardEmptySection
    | DashboardUnlinkedSection
    | DashboardUnavailableSection,
    Field(discriminator="status"),
]


class DashboardUser(BaseModel):
    """Authenticated account identity displayed in the briefing."""

    id: UUID
    display_name: str = Field(min_length=1, max_length=201)
    role: UserRole


class DashboardCalendarEvent(BaseModel):
    """Useful Calendar occurrence fields without location or venue."""

    occurrence_id: str = Field(min_length=1, max_length=255)
    event_date: date
    start_time: time | None
    end_time: time | None
    name: str = Field(min_length=1, max_length=200)
    event_type: EventType
    age_groups: list[AgeGroup] = Field(max_length=len(AgeGroup))


class DashboardMatch(BaseModel):
    """Date-based Match summary with expanded participant labels."""

    id: UUID
    match_date: date
    format: MatchFormat
    participants: MatchParticipantResponse


class DashboardActivePlayerCount(BaseModel):
    """Academy or assigned-Team active Player count."""

    kind: Literal["active_player_count"] = "active_player_count"
    count: int = Field(ge=0)
    team_count: int = Field(ge=0)


class DashboardPlayerTeams(BaseModel):
    """Concise Player summary for one or more current memberships."""

    kind: Literal["player_teams"] = "player_teams"
    team_count: int = Field(ge=0)
    team_names: list[str] = Field(max_length=MAX_DASHBOARD_CONTEXT_TEAMS)

    @model_validator(mode="after")
    def validate_team_names(self) -> Self:
        """Keep the displayed bounded subset within the actual membership count."""

        if len(self.team_names) > self.team_count:
            raise ValueError("team_names cannot exceed team_count")
        return self


type DashboardPlayerSlot = Annotated[
    DashboardActivePlayerCount | DashboardPlayerTeams,
    Field(discriminator="kind"),
]

type DashboardUpcomingEventList = Annotated[
    list[DashboardCalendarEvent],
    Field(max_length=MAX_DASHBOARD_UPCOMING_EVENTS),
]


class DashboardSummary(BaseModel):
    """The three stable summary slots on the shared surface."""

    training: DashboardSection[DashboardCalendarEvent]
    next_match: DashboardSection[DashboardMatch]
    player_slot: DashboardSection[DashboardPlayerSlot]


class DashboardActivityEvent(BaseModel):
    """Allowlisted Business Audit snapshot for Head Coach activity."""

    id: UUID
    actor_display_name: str | None
    action_type: AuditActionType
    action_category: AuditActionCategory
    target_label: str | None
    summary: str = Field(min_length=1, max_length=500)
    created_at: datetime


class DashboardRecentActivity(BaseModel):
    """Bounded Head Coach-only context panel data."""

    kind: Literal["recent_activity"] = "recent_activity"
    events: list[DashboardActivityEvent] = Field(
        max_length=MAX_DASHBOARD_RECENT_ACTIVITY
    )
    view_all_path: Literal["/audit-log"] = "/audit-log"


class DashboardCoachReference(BaseModel):
    """Permitted coach identity shown in a Player's Team context."""

    id: UUID
    display_name: str = Field(min_length=1, max_length=201)


class DashboardTeam(BaseModel):
    """One scoped Team row in an Assistant Coach or Player panel."""

    id: UUID
    name: str = Field(min_length=1, max_length=200)
    age_group: AgeGroup
    active_player_count: int = Field(ge=0)
    coaches: list[DashboardCoachReference] = Field(
        default_factory=list,
        max_length=MAX_DASHBOARD_COACHES_PER_TEAM,
    )
    next_event: DashboardCalendarEvent | None


class DashboardMyTeams(BaseModel):
    """Bounded role-scoped Team context."""

    kind: Literal["my_teams"] = "my_teams"
    teams: list[DashboardTeam] = Field(max_length=MAX_DASHBOARD_CONTEXT_TEAMS)
    view_all_path: Literal["/teams"] = "/teams"


type DashboardContext = Annotated[
    DashboardRecentActivity | DashboardMyTeams,
    Field(discriminator="kind"),
]


class DashboardResponse(BaseModel):
    """One bounded, server-authorized dashboard briefing."""

    model_config = ConfigDict(extra="forbid")

    user: DashboardUser
    dashboard_state: Literal["ready", "unlinked"]
    summary: DashboardSummary
    upcoming_events: DashboardSection[DashboardUpcomingEventList]
    context: DashboardSection[DashboardContext]

    @model_validator(mode="after")
    def validate_role_state(self) -> Self:
        """Prevent role-incompatible or academy-leaking response combinations."""

        sections = (
            self.summary.training,
            self.summary.next_match,
            self.summary.player_slot,
            self.upcoming_events,
            self.context,
        )
        if self.dashboard_state == "unlinked":
            if self.user.role is not UserRole.PLAYER:
                raise ValueError("Only a Player dashboard can be unlinked")
            if any(section.status != "unlinked" for section in sections):
                raise ValueError("An unlinked dashboard cannot expose scoped data")
            return self

        if any(section.status == "unlinked" for section in sections):
            raise ValueError("A ready dashboard cannot contain unlinked sections")
        if self.summary.player_slot.status == "ready":
            expected_kind = (
                "player_teams"
                if self.user.role is UserRole.PLAYER
                else "active_player_count"
            )
            if self.summary.player_slot.data.kind != expected_kind:
                raise ValueError("Player summary kind is incompatible with User role")
        if self.context.status == "ready":
            expected_context = (
                "recent_activity"
                if self.user.role is UserRole.HEAD_COACH
                else "my_teams"
            )
            if self.context.data.kind != expected_context:
                raise ValueError("Dashboard context is incompatible with User role")
        return self
