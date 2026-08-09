"""Strict request and response contracts for Academy Data Quality."""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.enums import (
    AuditActionType,
    QualityAction,
    QualityDomain,
    QualityEntityType,
    QualityRuleId,
    QualitySeverity,
)


class DataQualitySchema(BaseModel):
    """Reject undeclared fields at the Data Quality API boundary."""

    model_config = ConfigDict(extra="forbid")


class DataQualityQuery(DataQualitySchema):
    """One bounded and allowlisted current-state findings query."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    severity: QualitySeverity | None = None
    domain: QualityDomain | None = None
    rule_id: QualityRuleId | None = None


class RelatedQualityEntity(DataQualitySchema):
    """A deterministic related record needed to explain one finding."""

    entity_type: QualityEntityType
    entity_id: UUID
    entity_label: str = Field(min_length=1, max_length=300)


class NormalizeRosterOrderRemediation(DataQualitySchema):
    """Current target metadata for a safe roster-order normalization."""

    action: Literal[QualityAction.NORMALIZE_ROSTER_ORDER] = (
        QualityAction.NORMALIZE_ROSTER_ORDER
    )
    team_id: UUID
    expected_team_version: int = Field(ge=1)
    confirmation_required: Literal[True] = True


class RemoveInactivePlayerRemediation(DataQualitySchema):
    """Current target metadata for removing one inactive membership."""

    action: Literal[QualityAction.REMOVE_INACTIVE_PLAYER] = (
        QualityAction.REMOVE_INACTIVE_PLAYER
    )
    team_id: UUID
    player_id: UUID
    expected_team_version: int = Field(ge=1)
    confirmation_required: Literal[True] = True


class RemoveInactiveAssistantAssignmentRemediation(DataQualitySchema):
    """Current target metadata for removing one Assistant assignment."""

    action: Literal[QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT] = (
        QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT
    )
    coach_id: UUID
    team_id: UUID
    expected_coach_version: int = Field(ge=1)
    confirmation_required: Literal[True] = True


type DirectQualityRemediation = Annotated[
    NormalizeRosterOrderRemediation
    | RemoveInactivePlayerRemediation
    | RemoveInactiveAssistantAssignmentRemediation,
    Field(discriminator="action"),
]


class DataQualityFinding(DataQualitySchema):
    """One non-persisted violation of a registered quality rule."""

    finding_id: str = Field(min_length=1, max_length=500)
    rule_id: QualityRuleId
    severity: QualitySeverity
    domain: QualityDomain
    entity_type: QualityEntityType
    entity_id: UUID | None
    entity_label: str = Field(min_length=1, max_length=300)
    title: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1, max_length=1200)
    recommended_action: str = Field(min_length=1, max_length=800)
    direct_remediation: DirectQualityRemediation | None
    related_entities: list[RelatedQualityEntity] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_direct_action_rule(self) -> Self:
        """Keep direct actions attached only to their allowlisted rule families."""

        if self.direct_remediation is None:
            return self
        allowed_rules = {
            QualityAction.NORMALIZE_ROSTER_ORDER: {
                QualityRuleId.ROSTER_ORDER_NON_POSITIVE,
                QualityRuleId.ROSTER_ORDER_DUPLICATE,
                QualityRuleId.ROSTER_ORDER_GAP,
                QualityRuleId.ROSTER_ORDER_NON_CONTIGUOUS,
            },
            QualityAction.REMOVE_INACTIVE_PLAYER: {
                QualityRuleId.PLAYER_INACTIVE_ROSTERED,
            },
            QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT: {
                QualityRuleId.COACH_INACTIVE_ASSIGNED,
            },
        }
        if self.rule_id not in allowed_rules[self.direct_remediation.action]:
            raise ValueError("direct remediation is not allowed for this rule")
        return self


class DataQualitySummary(DataQualitySchema):
    """Unfiltered counts calculated from the current finding set."""

    total_findings: int = Field(ge=0)
    critical_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    info_count: int = Field(ge=0)
    domain_counts: dict[QualityDomain, int]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Require complete, internally consistent summary metadata."""

        expected_domains = set(QualityDomain)
        if set(self.domain_counts) != expected_domains:
            raise ValueError("domain_counts must contain every quality domain")
        if any(count < 0 for count in self.domain_counts.values()):
            raise ValueError("domain counts must be non-negative")
        if self.critical_count + self.warning_count + self.info_count != (
            self.total_findings
        ):
            raise ValueError("severity counts must equal total_findings")
        if sum(self.domain_counts.values()) != self.total_findings:
            raise ValueError("domain counts must equal total_findings")
        return self


class DataQualityPageResponse(DataQualitySchema):
    """One deterministic and bounded current-state findings page."""

    findings: list[DataQualityFinding] = Field(max_length=100)
    summary: DataQualitySummary
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_findings: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_previous: bool
    has_next: bool

    @model_validator(mode="after")
    def validate_pagination_metadata(self) -> Self:
        """Keep the bounded page and its navigation metadata consistent."""

        expected_pages = (
            self.total_findings + self.page_size - 1
        ) // self.page_size
        if self.total_pages != expected_pages:
            raise ValueError(f"total_pages must equal {expected_pages}")
        if len(self.findings) > self.page_size:
            raise ValueError("findings cannot exceed page_size")
        if len(self.findings) > self.total_findings:
            raise ValueError("findings cannot exceed total_findings")
        if self.total_findings > self.summary.total_findings:
            raise ValueError("filtered findings cannot exceed the global summary")
        if self.has_previous != (self.page > 1):
            raise ValueError("has_previous is inconsistent with page")
        if self.has_next != (self.page < self.total_pages):
            raise ValueError("has_next is inconsistent with total_pages")
        return self


class NormalizeRosterOrderRequest(DataQualitySchema):
    """Confirmation-gated command for one team's current roster order."""

    finding_id: str = Field(min_length=1, max_length=500)
    action: Literal[QualityAction.NORMALIZE_ROSTER_ORDER] = (
        QualityAction.NORMALIZE_ROSTER_ORDER
    )
    team_id: UUID
    expected_team_version: int = Field(ge=1)
    confirmed: Literal[True]


class RemoveInactivePlayerRequest(DataQualitySchema):
    """Confirmation-gated command for exactly one inactive membership."""

    finding_id: str = Field(min_length=1, max_length=500)
    action: Literal[QualityAction.REMOVE_INACTIVE_PLAYER] = (
        QualityAction.REMOVE_INACTIVE_PLAYER
    )
    team_id: UUID
    player_id: UUID
    expected_team_version: int = Field(ge=1)
    confirmed: Literal[True]


class RemoveInactiveAssistantAssignmentRequest(DataQualitySchema):
    """Confirmation-gated command for one inactive Assistant assignment."""

    finding_id: str = Field(min_length=1, max_length=500)
    action: Literal[QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT] = (
        QualityAction.REMOVE_INACTIVE_ASSISTANT_ASSIGNMENT
    )
    coach_id: UUID
    team_id: UUID
    expected_coach_version: int = Field(ge=1)
    confirmed: Literal[True]


type DataQualityRemediationRequest = Annotated[
    NormalizeRosterOrderRequest
    | RemoveInactivePlayerRequest
    | RemoveInactiveAssistantAssignmentRequest,
    Field(discriminator="action"),
]

type DataQualityAuditAction = Literal[
    AuditActionType.ROSTER_REORDERED,
    AuditActionType.ROSTER_REMOVED,
    AuditActionType.COACH_TEAM_ASSIGNMENTS_UPDATED,
]


class DataQualityRemediationResult(DataQualitySchema):
    """User-safe result for one successfully applied domain mutation."""

    status: Literal["applied"] = "applied"
    action: QualityAction
    message: str = Field(min_length=1, max_length=500)
    affected_entity_id: UUID
    audit_action: DataQualityAuditAction
