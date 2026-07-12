"""Pydantic schemas for user account requests and responses."""

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.enums import UserRole
from src.schemas.base import BaseRequestSchema
from src.services.password_service import PasswordService

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserCreate(BaseRequestSchema):
    """Payload for creating a user account."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    role: UserRole

    @model_validator(mode="before")
    @classmethod
    def reject_client_password_hash(cls, value: Any) -> Any:
        """Reject client-submitted password hashes even when password is present."""

        if isinstance(value, Mapping) and "hashed_password" in value:
            raise ValueError("hashed_password must not be submitted")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Reject values that do not have a conventional email structure."""

        if EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("email must be a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        """Enforce the server-side password composition policy."""

        PasswordService.validate_password_policy(value)
        return value


class UserResponse(BaseModel):
    """Public account representation, intentionally excluding the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version_number: int
