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
from src.services.scoring.policy import (
    FormatCapability,
    resolve_capability_profile,
    resolve_format_capability,
)
from src.services.scoring.service import (
    ScoringService,
    configure_match,
    configure_scoring,
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
    "ScoringService",
    "configure_match",
    "configure_scoring",
    "FormatCapability",
    "load_scoring_command_context",
    "resolve_capability_profile",
    "resolve_format_capability",
]
