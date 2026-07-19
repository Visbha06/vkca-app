"""Unit tests for user account request and response schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.enums import UserRole
from src.schemas.user import UserCreate, UserResponse


def test_user_create_validates_fields_and_ignores_server_managed_values() -> None:
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "password": "SecureP@ssword1",
        "role": "head coach",
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "version_number": 99,
        "is_active": False,
    }

    user = UserCreate.model_validate(payload)

    assert user.first_name == "John"
    assert user.email == "john.doe@example.com"
    assert user.role is UserRole.HEAD_COACH
    assert "created_at" not in user.model_fields_set
    assert "updated_at" not in user.model_fields_set
    assert "version_number" not in user.model_fields_set
    assert "is_active" not in user.model_fields_set


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("first_name", ""),
        ("last_name", ""),
        ("email", "not-an-email"),
        ("password", ""),
    ],
)
def test_user_create_rejects_invalid_required_fields(field: str, value: str) -> None:
    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "password": "SecureP@ssword1",
        "role": "player",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        UserCreate.model_validate(payload)


def test_password_field_accepted() -> None:
    user = UserCreate.model_validate(
        {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "SecureP@ssword1",
            "role": "player",
        }
    )

    assert user.password == "SecureP@ssword1"
    assert "hashed_password" not in UserCreate.model_fields


def test_hashed_password_field_rejected() -> None:
    with pytest.raises(ValidationError, match="hashed_password must not be submitted"):
        UserCreate.model_validate(
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "password": "SecureP@ssword1",
                "hashed_password": "$argon2id$client-supplied",
                "role": "player",
            }
        )


@pytest.mark.parametrize(
    "password",
    [
        "Short1!",
        "lowercase123!",
        "UPPERCASE123!",
        "NoDigitsHere!",
        "NoSpecial1234",
    ],
)
def test_password_policy_enforced(password: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "password": password,
                "role": "player",
            }
        )


def test_user_response_never_exposes_hashed_password() -> None:
    now = datetime.now(UTC)
    response = UserResponse.model_validate(
        {
            "id": uuid4(),
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "hashed_password": "must-not-leak",
            "role": UserRole.HEAD_COACH,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "version_number": 1,
        }
    )

    assert "hashed_password" not in UserResponse.model_fields
    assert "hashed_password" not in response.model_dump(mode="json")
