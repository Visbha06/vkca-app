"""Deterministic builders shared by role-aware dashboard integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID, uuid5

from src.enums import (
    AuditActionCategory,
    AuditActionType,
    AuditEntityType,
    MatchParticipantType,
    UserRole,
)
from src.models.auth_session import AuthSession
from src.models.business_audit_event import BusinessAuditEvent
from src.models.calendar import CalendarEvent, CalendarEventScope
from src.models.match import Match
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User

ROLE_AWARE_NAMESPACE = UUID("2a7f24a4-3d90-4a4a-8f02-011013000001")
ROLE_AWARE_REFERENCE_DATE = date(2026, 8, 10)


def deterministic_id(label: str) -> UUID:
    """Return a stable ID for a named fixture record."""

    return uuid5(ROLE_AWARE_NAMESPACE, label)


def build_role_aware_team(
    *, name: str = "U15 Falcons", age_group: str = "U15"
) -> Team:
    """Build a deterministic dashboard team."""

    return Team(
        id=deterministic_id(f"team:{name}"),
        name=name,
        age_group=age_group,
        version_number=1,
    )


def build_role_aware_player(*, label: str = "asha") -> Player:
    """Build a deterministic dashboard player using existing required fields."""

    from tests.data_quality_builders import build_quality_player

    return build_quality_player(
        player_id=deterministic_id(f"player:{label}"),
        first_name="Asha",
        last_name="Player",
    )


def build_role_aware_membership(
    *, team: Team | None = None, player: Player | None = None, roster_order: int = 1
) -> TeamPlayer:
    """Build one deterministic current roster membership."""

    resolved_team = team or build_role_aware_team()
    resolved_player = player or build_role_aware_player()
    return TeamPlayer(
        team_id=resolved_team.id,
        player_id=resolved_player.id,
        roster_order=roster_order,
        version_number=1,
    )


def build_role_aware_coach_assignment(
    *, team: Team | None = None, user_id: UUID | None = None
) -> TeamCoach:
    """Build one deterministic Assistant Coach assignment."""

    resolved_team = team or build_role_aware_team()
    return TeamCoach(
        team_id=resolved_team.id,
        user_id=user_id or deterministic_id("user:assistant-coach"),
        version_number=1,
    )


def build_role_aware_calendar_occurrence(
    *, event_id: UUID | None = None, event_date: date = ROLE_AWARE_REFERENCE_DATE
) -> CalendarEvent:
    """Build an effective-occurrence source event for dashboard tests."""

    return CalendarEvent(
        id=event_id or deterministic_id(f"event:{event_date.isoformat()}"),
        event_type="practice",
        name="Batting fundamentals",
        first_date=event_date,
        is_all_day=False,
        start_time=time(17, 0),
        end_time=time(18, 30),
        version_number=1,
    )


def build_role_aware_calendar_scope(
    *, event: CalendarEvent, age_group: str = "U15"
) -> CalendarEventScope:
    """Build an age-group scope row for a calendar source event."""

    return CalendarEventScope(
        id=deterministic_id(f"scope:{event.id}:{age_group}"),
        event_id=event.id,
        scope_kind="age_group",
        age_group=age_group,
    )


def build_role_aware_match(
    *,
    match_date: date = ROLE_AWARE_REFERENCE_DATE + timedelta(days=5),
    opponent: str = "Northside CC",
    academy_team_id: UUID | None = None,
    academy_side: Literal["home", "away"] = "home",
) -> Match:
    """Build one deterministic external Match with explicit academy side."""

    resolved_team_id = academy_team_id or deterministic_id("team:U15 Falcons")

    return Match(
        id=deterministic_id(
            f"match:{match_date.isoformat()}:{opponent}:{academy_side}"
        ),
        match_date=match_date,
        format="T20",
        participant_type=MatchParticipantType.EXTERNAL,
        home_team_id=resolved_team_id if academy_side == "home" else None,
        away_team_id=resolved_team_id if academy_side == "away" else None,
        external_opponent_name=opponent,
        venue="Academy Ground",
        result="scheduled",
        version_number=1,
    )


def build_role_aware_internal_match(
    *,
    match_date: date = ROLE_AWARE_REFERENCE_DATE + timedelta(days=6),
    home_team_id: UUID | None = None,
    away_team_id: UUID | None = None,
) -> Match:
    """Build one deterministic internal Match between different Teams."""

    resolved_home_id = home_team_id or deterministic_id("team:U13 Falcons")
    resolved_away_id = away_team_id or deterministic_id("team:U15 Falcons")
    return Match(
        id=deterministic_id(
            f"match:{match_date.isoformat()}:{resolved_home_id}:{resolved_away_id}"
        ),
        match_date=match_date,
        format="T20",
        participant_type=MatchParticipantType.INTERNAL,
        home_team_id=resolved_home_id,
        away_team_id=resolved_away_id,
        external_opponent_name=None,
        venue="Academy Ground",
        result="scheduled",
        version_number=1,
    )


def build_role_aware_audit_event(
    *, event_id: UUID | None = None, actor_user_id: UUID | None = None
) -> BusinessAuditEvent:
    """Build one deterministic, immutable activity snapshot."""

    return BusinessAuditEvent(
        id=event_id or deterministic_id("audit:player-linked"),
        actor_user_id=actor_user_id or deterministic_id("user:head-coach"),
        actor_display_name="Asha Coach",
        actor_role=UserRole.HEAD_COACH.value,
        action_type=AuditActionType.PLAYER_CREATED.value,
        action_category=AuditActionCategory.PLAYER.value,
        target_entity_type=AuditEntityType.PLAYER.value,
        target_entity_id=deterministic_id("player:asha"),
        target_label="Asha Player",
        summary="Asha Coach changed Asha Player",
        event_metadata={},
        created_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
        request_id="role-aware-dashboard-fixture",
    )


def build_role_aware_linked_account(
    *, label: str = "asha"
) -> tuple[Player, User]:
    """Build a Player explicitly linked to one Player-role User."""

    player = build_role_aware_player(label=label)
    user_id = deterministic_id(f"user:player:{label}")
    player.user_id = user_id
    user = User(
        id=user_id,
        first_name="Asha",
        last_name="Account",
        email=f"{label}.player@example.com",
        hashed_password="$argon2id$role-aware-dashboard-fixture",
        role=UserRole.PLAYER,
        is_active=True,
        version_number=1,
    )
    return player, user


def build_role_aware_isolated_session(
    *, user_id: UUID | None = None, now: datetime | None = None
) -> AuthSession:
    """Build a deterministic active session for isolated auth tests."""

    current = now or datetime(2026, 8, 10, 12, tzinfo=UTC)
    return AuthSession(
        id=deterministic_id("session:player"),
        user_id=user_id or deterministic_id("user:player:asha"),
        token_family_id=deterministic_id("token-family:player"),
        current_token_hash="role-aware-dashboard-token",
        rotated_token_hashes=[],
        created_at=current,
        last_used_at=current,
        expires_at=current + timedelta(days=7),
        revoked_at=None,
        revocation_reason=None,
        ip_address="127.0.0.1",
        user_agent="role-aware-dashboard-fixture",
        version_number=1,
    )


@dataclass(slots=True)
class RoleAwareDashboardSeed:
    """A small deterministic set of records for projection tests."""

    team: Team
    player: Player
    membership: TeamPlayer
    event: CalendarEvent
    event_scope: CalendarEventScope
    match: Match
    audit_event: BusinessAuditEvent
    linked_account: tuple[Player, User]
    session: AuthSession


def build_role_aware_dashboard_seed() -> RoleAwareDashboardSeed:
    """Return related records with stable IDs and no database side effects."""

    team = build_role_aware_team()
    player = build_role_aware_player()
    linked_account = build_role_aware_linked_account()
    event = build_role_aware_calendar_occurrence()
    return RoleAwareDashboardSeed(
        team=team,
        player=player,
        membership=build_role_aware_membership(team=team, player=player),
        event=event,
        event_scope=build_role_aware_calendar_scope(event=event),
        match=build_role_aware_match(),
        audit_event=build_role_aware_audit_event(),
        linked_account=linked_account,
        session=build_role_aware_isolated_session(user_id=linked_account[1].id),
    )
