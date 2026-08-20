"""Sanitized operational schemas for durable background work."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.services.background_jobs.contracts import BackgroundWorkState


class BackgroundJobStatus(BaseModel):
    """Allowlisted status projection that deliberately excludes stored payloads."""

    id: UUID
    job_type: str
    payload_version: int
    state: BackgroundWorkState
    correlation_id: UUID | None
    source_type: str | None
    source_key: str | None
    dispatch_attempt_count: int = Field(ge=0)
    execution_attempt_count: int = Field(ge=0)
    manual_retry_count: int = Field(ge=0)
    run_after: datetime
    last_attempt_at: datetime | None
    dispatched_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    terminal_at: datetime | None
    last_failure_category: str | None
    last_failure_message: str | None
    manual_retry_allowed: bool
    retention_until: datetime | None
    version_number: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True, frozen=True)


class DispatchReport(BaseModel):
    """Bounded, sanitized result of one dispatcher batch."""

    claimed: int = Field(default=0, ge=0, le=500)
    enqueued: int = Field(default=0, ge=0, le=500)
    retrying: int = Field(default=0, ge=0, le=500)
    dead: int = Field(default=0, ge=0, le=500)
    conflicts: int = Field(default=0, ge=0, le=500)
    work_ids: list[UUID] = Field(default_factory=list, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkerExecutionReport(BaseModel):
    """Safe internal outcome used by tests and bounded operator integrations."""

    work_id: UUID
    state: BackgroundWorkState
    failure_category: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class BackgroundJobStatusReport(BaseModel):
    """Bounded status rows plus aggregate state counts without stored payloads."""

    counts: dict[str, int] = Field(default_factory=dict)
    items: list[BackgroundJobStatus] = Field(default_factory=list, max_length=100)
    limit: int = Field(ge=1, le=100)

    model_config = ConfigDict(extra="forbid", frozen=True)


class BackgroundRecoveryReport(BaseModel):
    """Safe outcome of one bounded expired-lease recovery pass."""

    recovered: int = Field(default=0, ge=0, le=500)
    retrying: int = Field(default=0, ge=0, le=500)
    dead: int = Field(default=0, ge=0, le=500)
    conflicts: int = Field(default=0, ge=0, le=500)
    work_ids: list[UUID] = Field(default_factory=list, max_length=500)

    model_config = ConfigDict(extra="forbid", frozen=True)


class BackgroundCommandReport(BaseModel):
    """Minimal output for one approved retry or trigger command."""

    command: str = Field(min_length=1, max_length=40)
    work_id: UUID
    state: BackgroundWorkState

    model_config = ConfigDict(extra="forbid", frozen=True)
