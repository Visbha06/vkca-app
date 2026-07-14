"""Unit tests for JWT, refresh-token, and token-hashing helpers."""

from uuid import uuid4

import pytest
from jose import JWTError
from jose.exceptions import ExpiredSignatureError

from src.enums import UserRole
from src.services.token_service import TokenService

JWT_SECRET = "unit-test-secret-that-is-not-for-production"


@pytest.fixture
def token_service() -> TokenService:
    return TokenService(
        jwt_secret=JWT_SECRET,
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
    )


def test_create_access_token_has_required_claims(
    token_service: TokenService,
) -> None:
    user_id = uuid4()
    session_id = uuid4()

    token = token_service.create_access_token(
        user_id,
        session_id,
        UserRole.HEAD_COACH,
    )
    claims = token_service.decode_and_verify_access_token(token)

    assert claims["sub"] == str(user_id)
    assert claims["sid"] == str(session_id)
    assert claims["role"] == UserRole.HEAD_COACH.value
    assert {"jti", "iat", "exp"}.issubset(claims)
    assert claims["exp"] - claims["iat"] == 30 * 60


def test_decode_valid_token(token_service: TokenService) -> None:
    token = token_service.create_access_token(uuid4(), uuid4(), UserRole.STAFF)

    claims = token_service.decode_and_verify_access_token(token)

    assert claims["role"] == UserRole.STAFF.value


def test_reject_expired_token() -> None:
    service = TokenService(
        jwt_secret=JWT_SECRET,
        jwt_algorithm="HS256",
        access_token_expire_minutes=-1,
    )
    token = service.create_access_token(uuid4(), uuid4(), UserRole.STAFF)

    with pytest.raises(ExpiredSignatureError):
        service.decode_and_verify_access_token(token)


def test_reject_malformed_token(token_service: TokenService) -> None:
    with pytest.raises(JWTError):
        token_service.decode_and_verify_access_token("not-a-jwt")


def test_reject_wrong_signature(token_service: TokenService) -> None:
    other_service = TokenService(
        jwt_secret="a-different-unit-test-signing-secret",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
    )
    token = other_service.create_access_token(uuid4(), uuid4(), UserRole.STAFF)

    with pytest.raises(JWTError):
        token_service.decode_and_verify_access_token(token)


def test_refresh_token_length_43(token_service: TokenService) -> None:
    assert len(token_service.generate_refresh_token()) == 43


def test_refresh_token_uniqueness(token_service: TokenService) -> None:
    tokens = {token_service.generate_refresh_token() for _ in range(100)}

    assert len(tokens) == 100


def test_hash_token_deterministic(token_service: TokenService) -> None:
    token = token_service.generate_refresh_token()

    assert token_service.hash_token(token) == token_service.hash_token(token)


def test_hash_token_not_reversible(token_service: TokenService) -> None:
    token = token_service.generate_refresh_token()
    token_hash = token_service.hash_token(token)

    assert token_hash != token
    assert token not in token_hash
    assert len(token_hash) == 64
