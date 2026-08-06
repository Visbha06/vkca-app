"""Isolated builders reserved for business-audit unit tests.

Keeping these builders in a feature-specific module prevents the business
audit tests from changing shared security-audit fixtures.
"""

from uuid import UUID, uuid4


def business_audit_ids() -> tuple[UUID, UUID]:
    """Return independent actor and target IDs for a test case."""

    return uuid4(), uuid4()

