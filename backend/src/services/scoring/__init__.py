"""Explicit application-service boundary for Match-scoped scoring."""

from src.services.scoring.authorization import (
    ScoringAuthorizationAdapter,
    ScoringCommandContext,
    load_scoring_command_context,
)
from src.services.scoring.errors import (
    ScoringAuthenticationError,
    ScoringAuthorityError,
    ScoringAuthorizationError,
    ScoringConflictError,
    ScoringDomainError,
    ScoringLifecycleError,
    ScoringReconciliationError,
    ScoringRevisionError,
    ScoringSequenceError,
    ScoringValidationError,
    ScoringVisibilityError,
)

__all__ = [
    "ScoringAuthenticationError",
    "ScoringAuthorityError",
    "ScoringAuthorizationAdapter",
    "ScoringAuthorizationError",
    "ScoringCommandContext",
    "ScoringConflictError",
    "ScoringDomainError",
    "ScoringLifecycleError",
    "ScoringReconciliationError",
    "ScoringRevisionError",
    "ScoringSequenceError",
    "ScoringValidationError",
    "ScoringVisibilityError",
    "load_scoring_command_context",
]
