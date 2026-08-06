"""Typed request, filter, and response contracts for business activity."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.enums import AuditActionCategory, AuditActionType, AuditEntityType

ACADEMY_TIMEZONE = ZoneInfo("America/Los_Angeles")
MAX_AUDIT_DATE_RANGE_DAYS = 366

type BusinessAuditMetadataScalar = str | int | float | bool | None
type BusinessAuditMetadataValue = (
    BusinessAuditMetadataScalar | list[BusinessAuditMetadataScalar]
)


class BusinessAuditQuery(BaseModel):
    """One bounded, validated full-history query."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    actor_user_id: UUID | None = None
    action_category: AuditActionCategory | None = None
    action_type: AuditActionType | None = None
    entity_type: AuditEntityType | None = None
    target_entity_id: UUID | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        """Reject inverted or excessive academy-local ranges before querying."""

        if self.start_date is None or self.end_date is None:
            return self
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        inclusive_days = (self.end_date - self.start_date).days + 1
        if inclusive_days > MAX_AUDIT_DATE_RANGE_DAYS:
            raise ValueError("date range must not exceed 366 inclusive dates")
        return self

    def utc_date_bounds(self) -> tuple[datetime | None, datetime | None]:
        """Convert inclusive academy dates to a UTC half-open interval."""

        lower = (
            datetime.combine(
                self.start_date, time.min, tzinfo=ACADEMY_TIMEZONE
            ).astimezone(UTC)
            if self.start_date is not None
            else None
        )
        upper = (
            datetime.combine(
                self.end_date + timedelta(days=1),
                time.min,
                tzinfo=ACADEMY_TIMEZONE,
            ).astimezone(UTC)
            if self.end_date is not None
            else None
        )
        return lower, upper


class BusinessAuditRecentQuery(BaseModel):
    """Strictly bounded dashboard recent-activity request."""

    limit: int = Field(default=4, ge=1, le=4)


class BusinessAuditEventResponse(BaseModel):
    """Stored snapshots and allowlisted detail exposed by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    actor_display_name: str | None
    actor_role: str | None
    action_type: AuditActionType
    action_category: AuditActionCategory
    target_entity_type: AuditEntityType
    target_entity_id: UUID | None
    target_label: str | None
    summary: str
    metadata: dict[str, BusinessAuditMetadataValue]
    created_at: datetime
    request_id: str | None


class BusinessAuditPageResponse(BaseModel):
    """One stable server-paginated business-audit page."""

    events: list[BusinessAuditEventResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_events: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    has_previous: bool
    has_next: bool

    @model_validator(mode="after")
    def validate_pagination_metadata(self) -> Self:
        """Keep navigation metadata consistent with the bounded total."""

        expected_pages = (self.total_events + self.page_size - 1) // self.page_size
        if self.total_pages != expected_pages:
            raise ValueError(f"total_pages must equal {expected_pages}")
        if self.has_previous != (self.page > 1):
            raise ValueError("has_previous is inconsistent with page")
        if self.has_next != (self.page < self.total_pages):
            raise ValueError("has_next is inconsistent with total_pages")
        return self


class RecentBusinessAuditResponse(BaseModel):
    """At most four events for Head Coach dashboard activity."""

    events: list[BusinessAuditEventResponse] = Field(max_length=4)


class BusinessAuditActorOption(BaseModel):
    """One historical actor snapshot available as a bounded filter option."""

    actor_user_id: UUID
    actor_display_name: str
    actor_role: str | None


class BusinessAuditActorOptionsResponse(BaseModel):
    """At most 100 distinct actor snapshots."""

    actors: list[BusinessAuditActorOption] = Field(max_length=100)
