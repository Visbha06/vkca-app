"""Batched projection loading and bounded Data Quality page assembly."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import (
    AuditActionType,
    DeliveryRevisionState,
    FielderRole,
    InningsLifecycleState,
    MatchLifecycleState,
    MatchResultCode,
    QualityAction,
    QualityDomain,
    QualityEntityType,
    QualityRuleId,
    QualitySeverity,
    RecurrenceFrequency,
    RecurrenceTermination,
    ScoringAuthority,
    ScoringDismissalType,
    UserRole,
)
from src.models.calendar import (
    CalendarEvent,
    OccurrenceException,
    RecurrenceSeries,
)
from src.models.match import Match
from src.models.match_batting_performance import MatchBattingPerformance
from src.models.match_bowling_performance import MatchBowlingPerformance
from src.models.match_fielding_performance import MatchFieldingPerformance
from src.models.player import Player
from src.models.scoring.delivery import Delivery
from src.models.scoring.delivery_revision import DeliveryRevision
from src.models.scoring.innings import Innings
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
    ScoringQualityProjection,
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
    QualityDomain.SCORING: 5,
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
                and command.expected_team_version == remediation.expected_team_version
            )
        elif isinstance(command, RemoveInactivePlayerRequest) and isinstance(
            remediation,
            RemoveInactivePlayerRemediation,
        ):
            matches = (
                command.action == remediation.action
                and command.team_id == remediation.team_id
                and command.player_id == remediation.player_id
                and command.expected_team_version == remediation.expected_team_version
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
                and command.expected_coach_version == remediation.expected_coach_version
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
        scoring = await self._load_scoring_quality()
        return EvaluationContext(
            players=players,
            teams=teams,
            roster_memberships=memberships,
            coaches=coaches,
            coach_assignments=assignments,
            calendar_series=series,
            calendar_exceptions=exceptions,
            scoring=scoring,
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
            domain_counts={domain: domain_counts[domain] for domain in QualityDomain},
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
                coaches_by_id[coach_id] for coach_id in sorted(coaches_by_id, key=str)
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
                series_by_id[series_id] for series_id in sorted(series_by_id, key=str)
            ),
            tuple(exceptions),
        )

    async def _load_scoring_quality(self) -> tuple[ScoringQualityProjection, ...]:
        """Load scoring graphs in a fixed set of queries and report without repair."""

        statement = (
            select(Match)
            .options(
                selectinload(Match.scoring_policy),
                selectinload(Match.scoring_sides),
                selectinload(Match.scoring_participants),
                selectinload(Match.scoring_performances),
                selectinload(Match.scoring_innings).selectinload(
                    Innings.batting_entries
                ),
                selectinload(Match.scoring_innings).selectinload(Innings.overs),
                selectinload(Match.scoring_innings).selectinload(
                    Innings.participant_summaries
                ),
                selectinload(Match.scoring_innings)
                .selectinload(Innings.deliveries)
                .selectinload(Delivery.revisions)
                .selectinload(DeliveryRevision.wicket_event),
                selectinload(Match.scoring_innings)
                .selectinload(Innings.deliveries)
                .selectinload(Delivery.revisions)
                .selectinload(DeliveryRevision.fielders),
                selectinload(Match.scoring_innings).selectinload(
                    Innings.transition_events
                ),
            )
            .order_by(Match.id)
            .execution_options(populate_existing=True)
        )
        matches = list((await self.session.execute(statement)).scalars().all())
        batting = list(
            (await self.session.execute(select(MatchBattingPerformance)))
            .scalars()
            .all()
        )
        bowling = list(
            (await self.session.execute(select(MatchBowlingPerformance)))
            .scalars()
            .all()
        )
        fielding = list(
            (await self.session.execute(select(MatchFieldingPerformance)))
            .scalars()
            .all()
        )
        legacy_rows = {
            match_id: tuple(rows)
            for match_id, rows in self._group_legacy_rows(
                (*batting, *bowling, *fielding)
            ).items()
        }
        projections: list[ScoringQualityProjection] = []
        for match in matches:
            try:
                projections.extend(
                    self._inspect_scoring_match(match, legacy_rows.get(match.id, ()))
                )
            except (ValueError, LookupError, TypeError, AttributeError):
                projections.append(
                    ScoringQualityProjection(
                        match_id=match.id,
                        entity_id=match.id,
                        entity_type=QualityEntityType.MATCH,
                        entity_label=f"Match {match.id}",
                        issues=(
                            (
                                QualityRuleId.SCORING_HISTORICAL_STATE_MALFORMED,
                                "The persisted scoring graph cannot be inspected "
                                "safely.",
                            ),
                        ),
                    )
                )
        return tuple(projections)

    @staticmethod
    def _group_legacy_rows(rows):
        grouped: dict[object, list[object]] = {}
        for row in rows:
            grouped.setdefault(row.match_id, []).append(row)
        return grouped

    @staticmethod
    def _inspect_scoring_match(
        match: Match,
        legacy_rows: tuple[object, ...],
    ) -> list[ScoringQualityProjection]:
        from src.services.scoring.errors import ScoringDomainError
        from src.services.scoring.policy import capability_from_locked_policy
        from src.services.scoring.projections import (
            build_innings_projection,
            innings_projection_matches,
        )
        from src.services.scoring.service import ScoringService

        findings: list[ScoringQualityProjection] = []
        match_issues: list[tuple[QualityRuleId, str]] = []
        authority = ScoringAuthority(match.scoring_authority)
        lifecycle = MatchLifecycleState(match.lifecycle_state)
        result = MatchResultCode(match.result_code)
        if authority is ScoringAuthority.LEGACY_AGGREGATE:
            if match.scoring_policy is not None or match.scoring_innings:
                match_issues.append(
                    (
                        QualityRuleId.SCORING_HISTORICAL_STATE_MALFORMED,
                        "A legacy-authority Match contains authoritative "
                        "scoring state.",
                    )
                )
        elif match.scoring_policy is None:
            match_issues.append(
                (
                    QualityRuleId.SCORING_HISTORICAL_STATE_MALFORMED,
                    "A delivery-history Match has no locked scoring policy.",
                )
            )
        if (
            (
                lifecycle is MatchLifecycleState.COMPLETED
                and result is MatchResultCode.PENDING
            )
            or (
                lifecycle is MatchLifecycleState.ABANDONED
                and result is not MatchResultCode.NO_RESULT
            )
            or (
                lifecycle
                in {MatchLifecycleState.SCHEDULED, MatchLifecycleState.IN_PROGRESS}
                and result is not MatchResultCode.PENDING
            )
            or lifecycle is MatchLifecycleState.CORRECTION_REPROCESSING
        ):
            match_issues.append(
                (
                    QualityRuleId.SCORING_LIFECYCLE_INVALID,
                    "The persisted Match lifecycle and result code disagree.",
                )
            )
        innings_numbers = [item.innings_number for item in match.scoring_innings]
        if len(innings_numbers) != len(set(innings_numbers)) or sorted(
            innings_numbers
        ) != list(range(1, len(innings_numbers) + 1)):
            match_issues.append(
                (
                    QualityRuleId.SCORING_SEQUENCE_CONFLICT,
                    "The Match innings sequence contains a duplicate or a gap.",
                )
            )
        if authority is ScoringAuthority.DELIVERY_HISTORY:
            internal_player_ids = {
                participant.player_id
                for participant in match.scoring_participants
                if participant.player_id is not None
            }
            legacy_player_ids = {
                getattr(row, "player_id", None)
                for row in legacy_rows
                if str(getattr(row, "notes", "") or "").startswith("[delivery_derived]")
            }
            if match.scoring_performances and not internal_player_ids.issubset(
                legacy_player_ids
            ):
                match_issues.append(
                    (
                        QualityRuleId.SCORING_LEGACY_DIVERGENCE,
                        "Academy compatibility rows are missing or lack "
                        "derived provenance.",
                    )
                )
        if match_issues:
            findings.append(
                ScoringQualityProjection(
                    match_id=match.id,
                    entity_id=match.id,
                    entity_type=QualityEntityType.MATCH,
                    entity_label=f"Match {match.id}",
                    issues=tuple(match_issues),
                )
            )

        participant_by_id = {
            participant.id: participant for participant in match.scoring_participants
        }
        capability = (
            capability_from_locked_policy(match.scoring_policy)
            if match.scoring_policy is not None
            else None
        )
        for innings in sorted(
            match.scoring_innings, key=lambda value: value.innings_number
        ):
            issues: list[tuple[QualityRuleId, str]] = []
            sequences = [delivery.attempted_sequence for delivery in innings.deliveries]
            if len(sequences) != len(set(sequences)) or sorted(sequences) != list(
                range(1, len(sequences) + 1)
            ):
                issues.append(
                    (
                        QualityRuleId.SCORING_SEQUENCE_CONFLICT,
                        "Attempted delivery sequence contains a duplicate or a gap.",
                    )
                )
            active_revisions = []
            active_conflict = False
            for delivery in innings.deliveries:
                active = [
                    revision
                    for revision in delivery.revisions
                    if DeliveryRevisionState(revision.revision_state)
                    is DeliveryRevisionState.ACTIVE
                ]
                if len(active) != 1:
                    active_conflict = True
                elif active:
                    active_revisions.append(active[0])
            if active_conflict:
                issues.append(
                    (
                        QualityRuleId.SCORING_ACTIVE_REVISION_CONFLICT,
                        "At least one delivery does not have exactly one "
                        "active revision.",
                    )
                )
            invalid_identity = False
            invalid_wicket = False
            zero_fielder_dismissals = {
                ScoringDismissalType.BOWLED,
                ScoringDismissalType.LBW,
                ScoringDismissalType.HIT_WICKET,
                ScoringDismissalType.RETIRED_OUT,
            }
            one_fielder_roles = {
                ScoringDismissalType.CAUGHT: FielderRole.CATCHER,
                ScoringDismissalType.CAUGHT_AND_BOWLED: FielderRole.BOWLER,
                ScoringDismissalType.STUMPED: FielderRole.KEEPER,
            }
            for revision in active_revisions:
                striker = participant_by_id.get(revision.striker_participant_id)
                non_striker = participant_by_id.get(revision.non_striker_participant_id)
                bowler = participant_by_id.get(revision.bowler_participant_id)
                if (
                    striker is None
                    or non_striker is None
                    or bowler is None
                    or striker.side_id != innings.batting_side_id
                    or non_striker.side_id != innings.batting_side_id
                    or bowler.side_id != innings.fielding_side_id
                    or any(
                        participant_by_id.get(fielder.participant_id) is None
                        or participant_by_id[fielder.participant_id].side_id
                        != innings.fielding_side_id
                        for fielder in revision.fielders
                    )
                ):
                    invalid_identity = True
                wicket = revision.wicket_event
                fielders = sorted(revision.fielders, key=lambda value: value.ordinal)
                if wicket is None:
                    invalid_wicket = invalid_wicket or bool(fielders)
                    continue
                dismissal = ScoringDismissalType(wicket.dismissal_type)
                if wicket.dismissed_participant_id not in {
                    revision.striker_participant_id,
                    revision.non_striker_participant_id,
                }:
                    invalid_identity = True
                if dismissal in zero_fielder_dismissals and fielders:
                    invalid_wicket = True
                if dismissal in one_fielder_roles and (
                    len(fielders) != 1
                    or FielderRole(fielders[0].role) is not one_fielder_roles[dismissal]
                ):
                    invalid_wicket = True
                if dismissal is ScoringDismissalType.RUN_OUT and not fielders:
                    invalid_wicket = True
                ordinals = [fielder.ordinal for fielder in fielders]
                if ordinals != list(range(1, len(ordinals) + 1)):
                    invalid_wicket = True
            if invalid_identity:
                issues.append(
                    (
                        QualityRuleId.SCORING_PARTICIPANT_IDENTITY_INVALID,
                        "A scoring event references a participant outside "
                        "its fixed side.",
                    )
                )
            if invalid_wicket:
                issues.append(
                    (
                        QualityRuleId.SCORING_WICKET_CARDINALITY_INVALID,
                        "A wicket has invalid ordered fielder cardinality or roles.",
                    )
                )
            innings_lifecycle = InningsLifecycleState(innings.lifecycle_state)
            if innings_lifecycle is InningsLifecycleState.RECONCILIATION_REQUIRED:
                issues.append(
                    (
                        QualityRuleId.SCORING_RECONCILIATION_REQUIRED,
                        "The Innings lifecycle is reconciliation_required.",
                    )
                )
            if (innings_lifecycle is InningsLifecycleState.COMPLETED) != (
                innings.completion_reason is not None
            ):
                issues.append(
                    (
                        QualityRuleId.SCORING_LIFECYCLE_INVALID,
                        "The Innings lifecycle and completion reason disagree.",
                    )
                )
            if capability is not None:
                quota = capability.bowler_quota_legal_balls
                if (
                    sum(over.legal_ball_count for over in innings.overs)
                    != innings.legal_balls
                    or any(
                        over.legal_ball_count > capability.over_length_legal_balls
                        or (
                            over.is_complete
                            and over.legal_ball_count
                            != capability.over_length_legal_balls
                        )
                        for over in innings.overs
                    )
                    or (
                        quota is not None
                        and any(
                            summary.bowling_legal_balls > quota
                            for summary in innings.participant_summaries
                        )
                    )
                ):
                    issues.append(
                        (
                            QualityRuleId.SCORING_OVER_QUOTA_INVALID,
                            "Persisted over or bowler legal-ball totals "
                            "violate policy.",
                        )
                    )
            if (
                capability is not None
                and not active_conflict
                and innings_lifecycle
                is not InningsLifecycleState.RECONCILIATION_REQUIRED
            ):
                try:
                    state = ScoringService._replay_orm(match, innings)
                    projection = build_innings_projection(
                        state,
                        over_length_legal_balls=capability.over_length_legal_balls,
                    )
                    if not innings_projection_matches(innings, projection):
                        issues.append(
                            (
                                QualityRuleId.SCORING_PROJECTION_MISMATCH,
                                "Persisted Innings totals or summaries differ "
                                "from replay.",
                            )
                        )
                except (ScoringDomainError, ValueError, LookupError, RuntimeError):
                    issues.append(
                        (
                            QualityRuleId.SCORING_HISTORICAL_STATE_MALFORMED,
                            "The active scoring history cannot be replayed safely.",
                        )
                    )
            if issues:
                findings.append(
                    ScoringQualityProjection(
                        match_id=match.id,
                        entity_id=innings.id,
                        entity_type=QualityEntityType.INNINGS,
                        entity_label=(
                            f"Match {match.id} innings {innings.innings_number}"
                        ),
                        issues=tuple(dict.fromkeys(issues)),
                    )
                )
        return findings
