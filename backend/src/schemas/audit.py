"""Credential-free response schemas for authentication audit records."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    """Public audit metadata available to authenticated head coaches."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    user_id: UUID | None
    session_id: UUID | None
    result: str
    reason: str | None
    ip_address: str | None
    user_agent: str | None
    target_resource: str | None
    event_timestamp: datetime
