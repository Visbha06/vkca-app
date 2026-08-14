"""Unit coverage for safe failure and structured-log projections."""

from __future__ import annotations

from src.services.background_jobs.logging import (
    REDACTED,
    redact_structured_fields,
    sanitize_failure,
)
from src.services.background_jobs.retry import FailureCategory


def test_failure_mapping_uses_category_message_not_raw_exception() -> None:
    failure = sanitize_failure(
        FailureCategory.TRANSIENT_DEPENDENCY_FAILURE,
        RuntimeError(
            "provider response token=top-secret "
            "redis://operator:password@localhost:6379/0"
        ),
    )

    assert failure.category is FailureCategory.TRANSIENT_DEPENDENCY_FAILURE
    assert failure.message == "A temporary dependency failure interrupted the job."
    assert "top-secret" not in failure.message
    assert "redis://" not in failure.message


def test_structured_log_redaction_masks_sensitive_keys_recursively() -> None:
    fields = redact_structured_fields(
        {
            "event": "background_job_retrying",
            "work_id": "00000000-0000-4000-8000-000000000000",
            "attempt": 2,
            "payload": {"source_key": "player:1"},
            "nested": {
                "access_token": "bearer-secret",
                "password": "hunter2",
                "vector": [0.1, 0.2],
            },
        }
    )

    assert fields["event"] == "background_job_retrying"
    assert fields["work_id"] == "00000000-0000-4000-8000-000000000000"
    assert fields["attempt"] == 2
    assert fields["payload"] == REDACTED
    assert fields["nested"]["access_token"] == REDACTED
    assert fields["nested"]["password"] == REDACTED
    assert fields["nested"]["vector"] == REDACTED


def test_structured_log_redaction_masks_credentials_inside_safe_key_strings() -> None:
    fields = redact_structured_fields(
        {
            "event": "dependency_failed",
            "message": (
                "Authorization: Bearer abc.def.ghi at "
                "postgresql://worker:db-secret@db/background_test"
            ),
        }
    )

    rendered = str(fields)
    assert "abc.def.ghi" not in rendered
    assert "db-secret" not in rendered
    assert "postgresql://worker" not in rendered


def test_structured_log_values_are_bounded() -> None:
    fields = redact_structured_fields({"message": "x" * 2_000})

    assert len(fields["message"]) <= 500
