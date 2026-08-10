"""Batched projection loading and bounded Data Quality page assembly."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import (
    AuditActionType,
    QualityAction,
    QualityDomain,
    QualitySeverity,
    RecurrenceFrequency,
    RecurrenceTermination,
    UserRole,
)
from src.models.calendar import (
    CalendarEvent,
    OccurrenceException,
    RecurrenceSeries,
)
from src.models.player import Player
from src.models.team import Team
from src.models.team_coach import TeamCoach
from src.models.team_player import TeamPlayer
from src.models.user import User
from src.schemas.data_quality import (
    DataQualityFinding,
    DataQualityPageResponse,
    DataQualityQuery,
    DataQualityRemediationRequest,
    DataQualityRemediationResult,
    DataQualitySummary,
    NormalizeRosterOrderRemediation,
    NormalizeRosterOrderRequest,
    RemoveInactiveAssistantAssignmentRemediation,
    RemoveInactiveAssistantAssignmentRequest,
    RemoveInactivePlayerRemediation,
    RemoveInactivePlayerRequest,
)
from src.services.business_audit_service import AuditActorContext
from src.services.coach_service import CoachService
from src.services.data_quality_rules import (
    CalendarExceptionProjection,
    CalendarSeriesProjection,
    CoachAssignmentProjection,
    CoachProjection,
    EvaluationContext,
    PlayerProjection,
    RosterMembershipProjection,
    TeamProjection,
    evaluate_registered_rules,
    normalize_player_name,
)
from src.services.team_service import TeamService

SEVERITY_ORDER = {
    QualitySeverity.CRITICAL: 0,
    QualitySeverity.WARNING: 1,
    QualitySeverity.INFO: 2,
}
DOMAIN_ORDER = {
    QualityDomain.PLAYERS: 0,
    QualityDomain.TEAMS: 1,
    QualityDomain.ROSTERS: 2,
    QualityDomain.COACHES: 3,
    QualityDomain.CALENDAR: 4,
}


class DataQualityRemediationValidationError(Exception):
    """Raised when a typed command omits an explicit safety precondition."""


class DataQualityRemediationConflictError(Exception):
    """Raised when a referenced finding or target is no longer current."""


class DataQualityService:
    """Evaluate current academy state without persisting scan results."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_findings(
        self,
        query: DataQualityQuery | None = None,
    ) -> DataQualityPageResponse:
        """Load one shared projection snapshot and return a bounded page."""

        context = await self.load_context()
        return self.evaluate(context, query or DataQualityQuery())

    async def get_findings(
        self,
        query: DataQualityQuery | None = None,
    ) -> DataQualityPageResponse:
        """Compatibility name for the current findings read capability."""

        return await self.list_findings(query)

    async def scan(
        self,
        query: DataQualityQuery | None = None,
    ) -> DataQualityPageResponse:
        """Explicit scan name for non-route callers and regression tests."""

        return await self.list_findings(query)

    async def remediate(
        self,
        command: DataQualityRemediationRequest,
        *,
        actor: AuditActorContext,
    ) -> DataQualityRemediationResult:
        """Re-evaluate and dispatch one exact, confirmation-gated correction."""

        if not command.confirmed:
            raise DataQualityRemediationValidationError(
                "Explicit confirmation is required before remediation."
            )

        context = await self.load_context()
        finding = next(
            (
                candidate
                for candidate in evaluate_registered_rules(context)
                if candidate.finding_id == command.finding_id
            ),
            None,
        )
        if finding is None:
            raise DataQualityRemediationConflictError(
                "The referenced finding is no longer current. Refresh the findings."
            )
        self._validate_exact_target(command, finding)

        if isinstance(command, NormalizeRosterOrderRequest):
            await TeamService(self.session).normalize_roster_order(
                command.team_id,
                expected_team_version=command.expected_team_version,
                actor=actor,
            )
            return DataQualityRemediationResult(
                action=command.action,
                message="The roster order was normalized.",
                affected_entity_id=command.team_id,
                audit_action=AuditActionType.ROSTER_REORDERED,
            )
        if isinstance(command, RemoveInactivePlayerRequest):
            await TeamService(self.session).remove_inactive_player(
                command.team_id,
                command.player_id,
                expected_team_version=command.expected_team_version,
                actor=actor,
            )
            return DataQualityRemediationResult(
                action=command.action,
                message="The inactive player was removed from the roster.",
                affected_entity_id=command.player_id,
                audit_action=AuditActionType.ROSTER_REMOVED,
            )

        await CoachService(self.session).remove_inactive_assistant_assignment(
            command.coach_id,
            command.team_id,
            expected_coach_version=command.expected_coach_version,
            actor=actor,
        )
        return DataQualityRemediationResult(
            action=QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT,
            message="The inactive Assistant Coach assignment was removed.",
            affected_entity_id=command.coach_id,
            audit_action=AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED,
        )

    @staticmethod
    def _validate_exact_target(
        command: DataQualityRemediationRequest,
        finding: DataQualityFinding,
    ) -> None:
        """Require command identity and OCC metadata to match current output."""

        remediation = finding.direct_remediation
        matches = False
        if isinstance(command, NormalizeRosterOrderRequest) and isinstance(
            remediation,
            NormalizeRosterOrderRemediation,
        ):
            matches = (
                command.action == remediation.action
                and command.team_id == remediation.team_id
                and command.expected_team_version
                == remediation.expected_team_version
            )
        elif isinstance(command, RemoveInactivePlayerRequest) and isinstance(
            remediation,
            RemoveInactivePlayerRemediation,
        ):
            matches = (
                command.action == remediation.action
                and command.team_id == remediation.team_id
                and command.player_id == remediation.player_id
                and command.expected_team_version
                == remediation.expected_team_version
            )
        elif isinstance(
            command,
            RemoveInactiveAssistantAssignmentRequest,
        ) and isinstance(
            remediation,
            RemoveInactiveAssistantAssignmentRemediation,
        ):
            matches = (
                command.action == remediation.action
                and command.coach_id == remediation.coach_id
                and command.team_id == remediation.team_id
                and command.expected_coach_version
                == remediation.expected_coach_version
            )

        if not matches:
            raise DataQualityRemediationConflictError(
                "The finding target or version changed. Refresh the findings."
            )

    async def load_context(self) -> EvaluationContext:
        """Load five fixed, narrow projections with no per-entity queries."""

        players = await self._load_players()
        teams = await self._load_teams()
        memberships = await self._load_roster_memberships()
        coaches, assignments = await self._load_coaches_and_assignments()
        series, exceptions = await self._load_calendar_series_and_exceptions()
        return EvaluationContext(
            players=players,
            teams=teams,
            roster_memberships=memberships,
            coaches=coaches,
            coach_assignments=assignments,
            calendar_series=series,
            calendar_exceptions=exceptions,
        )

    @staticmethod
    def evaluate(
        context: EvaluationContext,
        query: DataQualityQuery | None = None,
    ) -> DataQualityPageResponse:
        """Evaluate, order, summarize, filter, and paginate one projection set."""

        bounded_query = query or DataQualityQuery()
        findings = sorted(
            evaluate_registered_rules(context),
            key=DataQualityService.finding_sort_key,
        )
        summary = DataQualityService._build_summary(findings)
        filtered = [
            finding
            for finding in findings
            if DataQualityService._matches_filters(finding, bounded_query)
        ]
        total_findings = len(filtered)
        total_pages = (
            total_findings + bounded_query.page_size - 1
        ) // bounded_query.page_size
        offset = (bounded_query.page - 1) * bounded_query.page_size
        page_findings = filtered[offset : offset + bounded_query.page_size]
        return DataQualityPageResponse(
            findings=page_findings,
            summary=summary,
            page=bounded_query.page,
            page_size=bounded_query.page_size,
            total_findings=total_findings,
            total_pages=total_pages,
            has_previous=bounded_query.page > 1,
            has_next=bounded_query.page < total_pages,
        )

    @staticmethod
    def finding_sort_key(finding: DataQualityFinding) -> tuple[object, ...]:
        """Return the documented stable cross-domain finding order."""

        return (
            SEVERITY_ORDER[finding.severity],
            DOMAIN_ORDER[finding.domain],
            normalize_player_name(finding.entity_label),
            finding.rule_id.value,
            finding.finding_id,
        )

    @staticmethod
    def _matches_filters(
        finding: DataQualityFinding,
        query: DataQualityQuery,
    ) -> bool:
        return (
            (query.severity is None or finding.severity == query.severity)
            and (query.domain is None or finding.domain == query.domain)
            and (query.rule_id is None or finding.rule_id == query.rule_id)
        )

    @staticmethod
    def _build_summary(
        findings: list[DataQualityFinding],
    ) -> DataQualitySummary:
        severity_counts = Counter(finding.severity for finding in findings)
        domain_counts = Counter(finding.domain for finding in findings)
        return DataQualitySummary(
            total_findings=len(findings),
            critical_count=severity_counts[QualitySeverity.CRITICAL],
            warning_count=severity_counts[QualitySeverity.WARNING],
            info_count=severity_counts[QualitySeverity.INFO],
            domain_counts={
                domain: domain_counts[domain] for domain in QualityDomain
            },
        )

    async def _load_players(self) -> tuple[PlayerProjection, ...]:
        statement = select(
            Player.id,
            Player.first_name,
            Player.last_name,
            Player.date_of_birth,
            Player.is_active,
        ).order_by(Player.id)
        rows = (await self.session.execute(statement)).all()
        return tuple(
            PlayerProjection(
                player_id=player_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                is_active=is_active,
            )
            for player_id, first_name, last_name, date_of_birth, is_active in rows
        )

    async def _load_teams(self) -> tuple[TeamProjection, ...]:
        statement = select(
            Team.id,
            Team.name,
            Team.age_group,
            Team.version_number,
        ).order_by(Team.id)
        rows = (await self.session.execute(statement)).all()
        return tuple(
            TeamProjection(
                team_id=team_id,
                name=name,
                age_group=age_group,
                version_number=version_number,
            )
            for team_id, name, age_group, version_number in rows
        )

    async def _load_roster_memberships(
        self,
    ) -> tuple[RosterMembershipProjection, ...]:
        statement = select(
            TeamPlayer.team_id,
            TeamPlayer.player_id,
            TeamPlayer.roster_order,
        ).order_by(
            TeamPlayer.team_id,
            TeamPlayer.roster_order,
            TeamPlayer.player_id,
        )
        rows = (await self.session.execute(statement)).all()
        return tuple(
            RosterMembershipProjection(
                team_id=team_id,
                player_id=player_id,
                roster_order=roster_order,
            )
            for team_id, player_id, roster_order in rows
        )

    async def _load_coaches_and_assignments(
        self,
    ) -> tuple[
        tuple[CoachProjection, ...],
        tuple[CoachAssignmentProjection, ...],
    ]:
        statement = (
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.role,
                User.is_active,
                User.version_number,
                TeamCoach.team_id,
            )
            .outerjoin(TeamCoach, TeamCoach.user_id == User.id)
            .order_by(User.id, TeamCoach.team_id)
        )
        rows = (await self.session.execute(statement)).all()
        coaches_by_id: dict[object, CoachProjection] = {}
        assignments: list[CoachAssignmentProjection] = []
        for (
            coach_id,
            first_name,
            last_name,
            role,
            is_active,
            version_number,
            team_id,
        ) in rows:
            coaches_by_id[coach_id] = CoachProjection(
                coach_id=coach_id,
                first_name=first_name,
                last_name=last_name,
                role=UserRole(role),
                is_active=is_active,
                version_number=version_number,
            )
            if team_id is not None:
                assignments.append(
                    CoachAssignmentProjection(
                        coach_id=coach_id,
                        team_id=team_id,
                    )
                )
        return (
            tuple(
                coaches_by_id[coach_id]
                for coach_id in sorted(coaches_by_id, key=str)
            ),
            tuple(assignments),
        )

    async def _load_calendar_series_and_exceptions(
        self,
    ) -> tuple[
        tuple[CalendarSeriesProjection, ...],
        tuple[CalendarExceptionProjection, ...],
    ]:
        statement = (
            select(
                CalendarEvent.id,
                CalendarEvent.name,
                CalendarEvent.first_date,
                RecurrenceSeries.id,
                RecurrenceSeries.frequency,
                RecurrenceSeries.termination,
                RecurrenceSeries.end_date,
                RecurrenceSeries.occurrence_count,
                OccurrenceException.id,
                OccurrenceException.original_date,
            )
            .join(
                RecurrenceSeries,
                RecurrenceSeries.event_id == CalendarEvent.id,
            )
            .outerjoin(
                OccurrenceException,
                OccurrenceException.series_id == RecurrenceSeries.id,
            )
            .order_by(RecurrenceSeries.id, OccurrenceException.id)
        )
        rows = (await self.session.execute(statement)).all()
        series_by_id: dict[object, CalendarSeriesProjection] = {}
        exceptions: list[CalendarExceptionProjection] = []
        for (
            event_id,
            event_name,
            first_date,
            series_id,
            frequency,
            termination,
            end_date,
            occurrence_count,
            exception_id,
            original_date,
        ) in rows:
            series_by_id[series_id] = CalendarSeriesProjection(
                event_id=event_id,
                event_name=event_name,
                first_date=first_date,
                series_id=series_id,
                frequency=RecurrenceFrequency(frequency),
                termination=RecurrenceTermination(termination),
                end_date=end_date,
                occurrence_count=occurrence_count,
            )
            if exception_id is not None and original_date is not None:
                exceptions.append(
                    CalendarExceptionProjection(
                        exception_id=exception_id,
                        series_id=series_id,
                        original_date=original_date,
                    )
                )
        return (
            tuple(
                series_by_id[series_id]
                for series_id in sorted(series_by_id, key=str)
            ),
            tuple(exceptions),
        )
