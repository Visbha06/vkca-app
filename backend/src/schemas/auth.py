"""Pydantic request and response schemas for authentication operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.enums import UserRole
from src.schemas.user import EMAIL_PATTERN


class AuthSchema(BaseModel):
    """Reject undeclared authentication input and output fields."""

    model_config = ConfigDict(extra="forbid")


class LoginRequest(AuthSchema):
    """Email and plaintext password credentials supplied during login."""

    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize and validate a login email address."""

        normalized = value.strip().lower()
        if EMAIL_PATTERN.fullmatch(normalized) is None:
            raise ValueError("email must be a valid email address")
        return normalized


class TokenResponse(AuthSchema):
    """Bearer access token returned after login or refresh."""

    access_token: str = Field(min_length=1)
    token_type: Literal["bearer"] = "bearer"


class ProfileUpdate(AuthSchema):
    """Editable profile fields supplied by an authenticated user."""

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)


class CurrentSessionResponse(AuthSchema):
    """Public metadata for the session serving the current request."""

    session_id: UUID
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime


class CurrentUserResponse(AuthSchema):
    """Authenticated account profile plus its current session metadata."""

    id: UUID
    first_name: str
    last_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    session: CurrentSessionResponse
