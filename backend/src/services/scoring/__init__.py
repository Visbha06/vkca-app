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
    capability_from_locked_policy,
    resolve_capability_profile,
    resolve_format_capability,
)
from src.services.scoring.service import (
    ScoringService,
    append_delivery,
    configure_match,
    configure_scoring,
    retire_hurt,
    retired_hurt_return,
    select_next_batter,
    start_innings,
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
    "append_delivery",
    "capability_from_locked_policy",
    "configure_match",
    "configure_scoring",
    "FormatCapability",
    "load_scoring_command_context",
    "resolve_capability_profile",
    "resolve_format_capability",
    "retire_hurt",
    "retired_hurt_return",
    "select_next_batter",
    "start_innings",
]
