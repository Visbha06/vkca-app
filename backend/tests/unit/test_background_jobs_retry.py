"""Unit coverage for bounded background-job retry policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.services.background_jobs.retry import (
    FailureCategory,
    RetryDisposition,
    RetryPolicy,
    build_retry_decision,
    classify_failure,
    retry_delay_seconds,
    retry_run_after,
    validate_run_after,
)


@pytest.fixture
def retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=4,
        base_delay_seconds=5,
        max_delay_seconds=20,
        jitter_seconds=3,
        timeout_seconds=30,
    )


@pytest.mark.parametrize(
    ("error", "category", "disposition"),
    [
        (
            TimeoutError("provider token=secret"),
            FailureCategory.TIMEOUT,
            RetryDisposition.RETRY,
        ),
        (
            ConnectionError("redis://user:secret@redis/0"),
            FailureCategory.TRANSIENT_DEPENDENCY_FAILURE,
            RetryDisposition.RETRY,
        ),
        (
            ValueError("invalid stored payload"),
            FailureCategory.INVALID_PAYLOAD,
            RetryDisposition.TERMINAL,
        ),
        (
            RuntimeError("unknown implementation detail"),
            FailureCategory.UNEXPECTED_INTERNAL_ERROR,
            RetryDisposition.RETRY,
        ),
    ],
)
def test_failure_classification_is_explicit_and_safe(
    error: Exception,
    category: FailureCategory,
    disposition: RetryDisposition,
) -> None:
    classification = classify_failure(error)

    assert classification.category is category
    assert classification.disposition is disposition
    assert "secret" not in classification.safe_message


def test_retry_delay_uses_bounded_exponential_backoff_and_injected_jitter(
    retry_policy: RetryPolicy,
) -> None:
    def midpoint(lower: float, upper: float) -> float:
        return (lower + upper) / 2

    assert retry_delay_seconds(1, retry_policy, random_uniform=midpoint) == 6.5
    assert retry_delay_seconds(2, retry_policy, random_uniform=midpoint) == 11.5
    assert retry_delay_seconds(3, retry_policy, random_uniform=midpoint) == 21.5
    assert retry_delay_seconds(8, retry_policy, random_uniform=midpoint) == 21.5


def test_retry_delay_rejects_randomness_outside_jitter_bounds(
    retry_policy: RetryPolicy,
) -> None:
    with pytest.raises(ValueError, match="jitter"):
        retry_delay_seconds(
            1,
            retry_policy,
            random_uniform=lambda _lower, upper: upper + 1,
        )


def test_attempt_exhaustion_becomes_terminal(retry_policy: RetryPolicy) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    retrying = build_retry_decision(
        TimeoutError(),
        attempt_count=3,
        policy=retry_policy,
        now=now,
        random_uniform=lambda _lower, _upper: 0,
    )
    exhausted = build_retry_decision(
        TimeoutError(),
        attempt_count=4,
        policy=retry_policy,
        now=now,
        random_uniform=lambda _lower, _upper: 0,
    )

    assert retrying.disposition is RetryDisposition.RETRY
    assert retrying.run_after == now + timedelta(seconds=20)
    assert exhausted.disposition is RetryDisposition.TERMINAL
    assert exhausted.category is FailureCategory.RETRY_LIMIT_EXHAUSTED
    assert exhausted.run_after is None


def test_retry_run_after_is_timezone_aware_and_in_the_future(
    retry_policy: RetryPolicy,
) -> None:
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)

    run_after = retry_run_after(
        now,
        attempt_count=1,
        policy=retry_policy,
        random_uniform=lambda _lower, _upper: 0,
    )

    assert run_after == now + timedelta(seconds=5)
    assert validate_run_after(run_after, now=now) == run_after
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_run_after(run_after.replace(tzinfo=None), now=now)
    with pytest.raises(ValueError, match="before"):
        validate_run_after(now - timedelta(seconds=1), now=now)


def test_retry_policy_rejects_invalid_or_unbounded_values() -> None:
    with pytest.raises(ValidationError):
        RetryPolicy(
            max_attempts=0,
            base_delay_seconds=10,
            max_delay_seconds=5,
            jitter_seconds=-1,
            timeout_seconds=0,
        )
