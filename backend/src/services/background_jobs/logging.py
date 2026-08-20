"""Sanitized failure and structured logging helpers."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from src.services.background_jobs.retry import (
    SAFE_FAILURE_MESSAGES,
    FailureCategory,
)

REDACTED: Final = "[REDACTED]"
MAX_LOG_STRING_LENGTH: Final = 500
MAX_LOG_COLLECTION_ITEMS: Final = 100

_SENSITIVE_KEY_PARTS: Final = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "session",
    "csrf",
    "credential",
    "payload",
    "document",
    "vector",
    "embedding",
)
_SENSITIVE_EXACT_KEYS: Final = frozenset(
    {"api_key", "database_url", "redis_url", "provider_response"}
)
_URL_CREDENTIAL_RE = re.compile(
    r"\b(?:postgres(?:ql)?|redis|https?)://[^\s]+",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_ASSIGNMENT_RE = re.compile(
    r"\b(?:password|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SanitizedFailure:
    category: FailureCategory
    message: str


def sanitize_failure(
    category: FailureCategory,
    error: BaseException | None = None,
) -> SanitizedFailure:
    """Map failure state to a fixed operator-safe message."""

    del error
    return SanitizedFailure(category=category, message=SAFE_FAILURE_MESSAGES[category])


def _sensitive_key(key: str) -> bool:
    normalized = key.strip().casefold()
    return normalized in _SENSITIVE_EXACT_KEYS or any(
        part in normalized for part in _SENSITIVE_KEY_PARTS
    )


def _redact_string(value: str) -> str:
    redacted = _URL_CREDENTIAL_RE.sub(REDACTED, value)
    redacted = _BEARER_RE.sub(REDACTED, redacted)
    redacted = _ASSIGNMENT_RE.sub(REDACTED, redacted)
    if len(redacted) > MAX_LOG_STRING_LENGTH:
        return redacted[: MAX_LOG_STRING_LENGTH - 1] + "…"
    return redacted


def _redact_value(value: object, *, depth: int) -> Any:
    if depth > 8:
        return REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_LOG_COLLECTION_ITEMS:
                break
            safe_key = str(key)[:128]
            redacted[safe_key] = (
                REDACTED
                if _sensitive_key(safe_key)
                else _redact_value(item, depth=depth + 1)
            )
        return redacted
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _redact_value(item, depth=depth + 1)
            for item in list(value)[:MAX_LOG_COLLECTION_ITEMS]
        ]
    return _redact_string(str(value))


def redact_structured_fields(fields: Mapping[str, object]) -> dict[str, Any]:
    """Recursively redact and bound values before structured logging."""

    return _redact_value(fields, depth=0)
