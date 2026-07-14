"""Unit tests for authentication request and response schemas."""

import pytest
from pydantic import ValidationError

from src.schemas.auth import LoginRequest, TokenResponse


def test_login_request_validation() -> None:
    request = LoginRequest(
        email="  Coach@Example.COM ",
        password="wrong",
    )

    assert request.email == "coach@example.com"
    assert request.password == "wrong"

    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="wrong")


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "SecureP@ssword1"},
        {"email": "coach@example.com"},
    ],
)
def test_login_request_missing_fields(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        LoginRequest.model_validate(payload)


def test_token_response_structure() -> None:
    response = TokenResponse(access_token="signed.jwt.value")

    assert response.model_dump() == {
        "access_token": "signed.jwt.value",
        "token_type": "bearer",
    }

    with pytest.raises(ValidationError):
        TokenResponse(access_token="signed.jwt.value", token_type="basic")
