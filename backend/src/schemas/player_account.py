"""Protected schemas for explicit Player-to-User account association."""

from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.enums import UserRole


class PlayerAccountLookupQuery(BaseModel):
    """Bounded eligible-account search supplied by a Head Coach."""

    model_config = ConfigDict(extra="forbid")

    search: str | None = Field(default=None, max_length=255)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("search")
    @classmethod
    def normalize_search(cls, value: str | None) -> str | None:
        """Trim optional search text and treat whitespace as no filter."""

        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PlayerAccountSnapshot(BaseModel):
    """Allowlisted account fields safe for the protected linking flow."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str = Field(min_length=1, max_length=201)
    email: str = Field(min_length=1, max_length=255)
    role: Literal[UserRole.PLAYER]
    is_active: bool


class PaginatedPlayerAccountResponse(BaseModel):
    """One bounded page of eligible, unlinked Player-role accounts."""

    users: list[PlayerAccountSnapshot] = Field(max_length=100)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_users: int = Field(ge=0)
    total_pages: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_pagination_metadata(self) -> Self:
        """Keep total-page metadata consistent with the bounded result."""

        expected_pages = (self.total_users + self.page_size - 1) // self.page_size
        if self.total_pages != expected_pages:
            raise ValueError(f"total_pages must equal {expected_pages}")
        if len(self.users) > self.page_size:
            raise ValueError("users cannot exceed page_size")
        return self


class PlayerAccountLinkRequest(BaseModel):
    """Associate one eligible account at the current Player version."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    version_number: int = Field(ge=1)


class PlayerAccountUnlinkRequest(BaseModel):
    """Remove one association at the current Player version."""

    model_config = ConfigDict(extra="forbid")

    version_number: int = Field(ge=1)


class PlayerAccountReassignRequest(BaseModel):
    """Replace an expected association with one eligible account."""

    model_config = ConfigDict(extra="forbid")

    expected_user_id: UUID
    new_user_id: UUID
    version_number: int = Field(ge=1)


class PlayerAccountAssociationResponse(BaseModel):
    """Safe result shared by link, unlink, and reassignment mutations."""

    player_id: UUID
    account: PlayerAccountSnapshot | None
    player_version_number: int = Field(ge=1)


EligiblePlayerAccountResponse = PlayerAccountSnapshot
PlayerAccountLookupResponse = PaginatedPlayerAccountResponse
PlayerAccountLinkResponse = PlayerAccountAssociationResponse
PlayerAccountUnlinkResponse = PlayerAccountAssociationResponse
PlayerAccountReassignResponse = PlayerAccountAssociationResponse
