"""Pydantic schemas for user account requests and responses."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.enums import UserRole
from src.schemas.base import BaseRequestSchema

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserCreate(BaseRequestSchema):
    """Payload for creating a user account."""

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    hashed_password: str = Field(min_length=1, max_length=255)
    role: UserRole

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Reject values that do not have a conventional email structure."""

        if EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("email must be a valid email address")
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
