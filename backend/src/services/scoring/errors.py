"""Typed scoring-domain failures translated by the global API seam."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoringFieldViolation:
    """One bounded request-field explanation safe for an API response."""

    field: str
    message: str


class ScoringDomainError(Exception):
    """Base failure carrying a stable response code and HTTP classification."""

    status_code = 409
    code = "scoring_conflict"

    def __init__(
        self,
        detail: str,
        *,
        field_errors: tuple[ScoringFieldViolation, ...] = (),
    ) -> None:
        self.detail = detail[:500]
        self.field_errors = field_errors[:50]
        super().__init__(self.detail)


class ScoringAuthenticationError(ScoringDomainError):
    """The current database account cannot authenticate a scoring request."""

    status_code = 401
    code = "scoring_authentication_required"


class ScoringAuthorizationError(ScoringDomainError):
    """The current role or Team scope cannot perform a scoring command."""

    status_code = 403
    code = "scoring_forbidden"


class ScoringVisibilityError(ScoringDomainError):
    """A scoring resource is absent or concealed from the current scope."""

    status_code = 404
    code = "scoring_not_found"


class ScoringValidationError(ScoringDomainError):
    """Observed facts or a cross-field rule failed strict validation."""

    status_code = 422
    code = "scoring_validation_failed"


class ScoringLifecycleError(ScoringDomainError):
    """A command conflicts with the authoritative Match/Innings lifecycle."""

    status_code = 409
    code = "scoring_lifecycle_conflict"


class ScoringRevisionError(ScoringDomainError):
    """A correction targets a stale or conflicting delivery revision."""

    status_code = 409
    code = "scoring_revision_conflict"


class ScoringReconciliationError(ScoringDomainError):
    """Authoritative Innings reconciliation blocks the requested operation."""

    status_code = 409
    code = "scoring_reconciliation_conflict"


class ScoringAuthorityError(ScoringDomainError):
    """A write attempts to bypass the Match's locked scoring authority."""

    status_code = 409
    code = "scoring_authority_conflict"


class ScoringSequenceError(ScoringDomainError):
    """An attempted delivery or innings sequence conflicts with persisted order."""

    status_code = 409
    code = "scoring_sequence_conflict"


class ScoringConflictError(ScoringDomainError):
    """A generic scoring conflict not covered by a narrower category."""


ScoringNotFoundError = ScoringVisibilityError
