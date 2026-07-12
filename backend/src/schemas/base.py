"""Shared Pydantic request schema configuration."""

from pydantic import BaseModel, ConfigDict


class BaseRequestSchema(BaseModel):
    """Ignore server-managed fields supplied by API clients.

    Request subclasses intentionally do not declare ``created_at``, ``updated_at``,
    or ``version_number``. Pydantic therefore drops those extra input keys.
    """

    model_config = ConfigDict(extra="ignore")
