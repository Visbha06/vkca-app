"""Pydantic request and response schemas for authentication operations."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class RefreshRequest(AuthSchema):
    """Validated refresh token extracted from an HttpOnly cookie."""

    refresh_token: str = Field(min_length=1)


class CSRFTokenResponse(AuthSchema):
    """Double-submit CSRF token value exposed to a browser client."""

    csrf_token: str = Field(min_length=1)
