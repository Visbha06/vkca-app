"""Failure classification and finite retry/backoff policy."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.services.background_jobs.contracts import (
    BackgroundPayloadValidationError,
    IncompatiblePayloadVersionError,
    UnregisteredBackgroundJobError,
)

RandomUniform = Callable[[float, float], float]


class FailureCategory(StrEnum):
    """Sanitized durable categories for background-processing failures."""

    TRANSIENT_DEPENDENCY_FAILURE = "transient_dependency_failure"
    TIMEOUT = "timeout"
    REDIS_UNAVAILABLE = "redis_unavailable"
    DATABASE_UNAVAILABLE = "database_unavailable"
    INVALID_PAYLOAD = "invalid_payload"
    UNREGISTERED_JOB = "unregistered_job"
    INCOMPATIBLE_PAYLOAD_VERSION = "incompatible_payload_version"
    PERMANENT_DOMAIN_SOURCE_FAILURE = "permanent_domain_source_failure"
    UNEXPECTED_INTERNAL_ERROR = "unexpected_internal_error"
    RETRY_LIMIT_EXHAUSTED = "retry_limit_exhausted"


class RetryDisposition(StrEnum):
    """Action requested by a failure classification."""

    RETRY = "retry"
    TERMINAL = "terminal"
    SAFE_NOOP = "safe_noop"


SAFE_FAILURE_MESSAGES: dict[FailureCategory, str] = {
    FailureCategory.TRANSIENT_DEPENDENCY_FAILURE: (
        "A temporary dependency failure interrupted the job."
    ),
    FailureCategory.TIMEOUT: "The job exceeded its bounded execution time.",
    FailureCategory.REDIS_UNAVAILABLE: "Redis is temporarily unavailable.",
    FailureCategory.DATABASE_UNAVAILABLE: "The database is temporarily unavailable.",
    FailureCategory.INVALID_PAYLOAD: "The stored job payload is invalid.",
    FailureCategory.UNREGISTERED_JOB: "The stored job type is not registered.",
    FailureCategory.INCOMPATIBLE_PAYLOAD_VERSION: (
        "The stored payload version is not supported."
    ),
    FailureCategory.PERMANENT_DOMAIN_SOURCE_FAILURE: (
        "The authoritative source cannot be processed."
    ),
    FailureCategory.UNEXPECTED_INTERNAL_ERROR: (
        "An unexpected internal error interrupted the job."
    ),
    FailureCategory.RETRY_LIMIT_EXHAUSTED: (
        "The job exhausted its configured retry attempts."
    ),
}


class RetryPolicy(BaseModel):
    """Validated finite execution and delay bounds for one job definition."""

    max_attempts: int = Field(ge=1, le=20)
    base_delay_seconds: float = Field(gt=0, le=3_600)
    max_delay_seconds: float = Field(gt=0, le=86_400)
    jitter_seconds: float = Field(ge=0, le=60)
    timeout_seconds: float = Field(gt=0, le=3_600)

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> RetryPolicy:
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must not be below base_delay_seconds")
        return self


@dataclass(frozen=True, slots=True)
class FailureClassification:
    category: FailureCategory
    disposition: RetryDisposition
    safe_message: str


@dataclass(frozen=True, slots=True)
class RetryDecision:
    category: FailureCategory
    disposition: RetryDisposition
    safe_message: str
    run_after: datetime | None
    delay_seconds: float | None


def classify_failure(error: BaseException) -> FailureClassification:
    """Map an exception to an explicit category without retaining its message."""

    if isinstance(error, UnregisteredBackgroundJobError):
        category = FailureCategory.UNREGISTERED_JOB
        disposition = RetryDisposition.TERMINAL
    elif isinstance(error, IncompatiblePayloadVersionError):
        category = FailureCategory.INCOMPATIBLE_PAYLOAD_VERSION
        disposition = RetryDisposition.TERMINAL
    elif isinstance(error, (BackgroundPayloadValidationError, ValueError, TypeError)):
        category = FailureCategory.INVALID_PAYLOAD
        disposition = RetryDisposition.TERMINAL
    elif isinstance(error, TimeoutError):
        category = FailureCategory.TIMEOUT
        disposition = RetryDisposition.RETRY
    elif isinstance(error, (ConnectionError, OSError)):
        category = FailureCategory.TRANSIENT_DEPENDENCY_FAILURE
        disposition = RetryDisposition.RETRY
    else:
        category = FailureCategory.UNEXPECTED_INTERNAL_ERROR
        disposition = RetryDisposition.RETRY
    return FailureClassification(
        category=category,
        disposition=disposition,
        safe_message=SAFE_FAILURE_MESSAGES[category],
    )


def retry_delay_seconds(
    attempt_count: int,
    policy: RetryPolicy,
    *,
    random_uniform: RandomUniform = random.uniform,
) -> float:
    """Calculate capped exponential delay plus validated bounded jitter."""

    if attempt_count < 1:
        raise ValueError("attempt_count must be positive")
    exponent = min(attempt_count - 1, 63)
    base_delay = min(
        policy.max_delay_seconds,
        policy.base_delay_seconds * (2**exponent),
    )
    jitter = (
        random_uniform(0.0, policy.jitter_seconds) if policy.jitter_seconds > 0 else 0.0
    )
    if not math.isfinite(jitter) or not 0 <= jitter <= policy.jitter_seconds:
        raise ValueError("Injected retry jitter is outside the configured bounds")
    return float(base_delay + jitter)


def validate_run_after(
    run_after: datetime,
    *,
    now: datetime | None = None,
) -> datetime:
    """Require a timezone-aware delayed eligibility timestamp."""

    reference = now or datetime.now(UTC)
    if run_after.tzinfo is None or run_after.utcoffset() is None:
        raise ValueError("run_after must be timezone-aware")
    if reference.tzinfo is None or reference.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if run_after < reference:
        raise ValueError("run_after must not be before the current time")
    return run_after


def retry_run_after(
    now: datetime,
    *,
    attempt_count: int,
    policy: RetryPolicy,
    random_uniform: RandomUniform = random.uniform,
) -> datetime:
    """Return the validated durable eligibility time for a retry."""

    delay = retry_delay_seconds(
        attempt_count,
        policy,
        random_uniform=random_uniform,
    )
    return validate_run_after(now + timedelta(seconds=delay), now=now)


def build_retry_decision(
    error: BaseException,
    *,
    attempt_count: int,
    policy: RetryPolicy,
    now: datetime | None = None,
    random_uniform: RandomUniform = random.uniform,
    classifier: Callable[[BaseException], FailureClassification] = classify_failure,
) -> RetryDecision:
    """Classify one failure and apply the finite attempt policy."""

    if attempt_count < 1:
        raise ValueError("attempt_count must be positive")
    reference = now or datetime.now(UTC)
    classification = classifier(error)
    if classification.disposition is not RetryDisposition.RETRY:
        return RetryDecision(
            category=classification.category,
            disposition=classification.disposition,
            safe_message=classification.safe_message,
            run_after=None,
            delay_seconds=None,
        )
    if attempt_count >= policy.max_attempts:
        category = FailureCategory.RETRY_LIMIT_EXHAUSTED
        return RetryDecision(
            category=category,
            disposition=RetryDisposition.TERMINAL,
            safe_message=SAFE_FAILURE_MESSAGES[category],
            run_after=None,
            delay_seconds=None,
        )
    delay = retry_delay_seconds(
        attempt_count,
        policy,
        random_uniform=random_uniform,
    )
    return RetryDecision(
        category=classification.category,
        disposition=RetryDisposition.RETRY,
        safe_message=classification.safe_message,
        run_after=validate_run_after(
            reference + timedelta(seconds=delay),
            now=reference,
        ),
        delay_seconds=delay,
    )
