"""Unit tests for Argon2id password hashing and policy validation."""

import pytest

from src.services.password_service import PasswordService

VALID_PASSWORD = "SecureP@ssword1"


def test_hash_password_different_salts() -> None:
    first_hash = PasswordService.hash_password(VALID_PASSWORD)
    second_hash = PasswordService.hash_password(VALID_PASSWORD)

    assert first_hash != second_hash


def test_verify_correct_password() -> None:
    password_hash = PasswordService.hash_password(VALID_PASSWORD)

    assert PasswordService.verify_password(VALID_PASSWORD, password_hash)


def test_verify_wrong_password() -> None:
    password_hash = PasswordService.hash_password(VALID_PASSWORD)

    assert not PasswordService.verify_password("WrongP@ssword1", password_hash)


def test_policy_validation_too_short() -> None:
    with pytest.raises(ValueError, match="at least 12"):
        PasswordService.validate_password_policy("Short1!")


def test_policy_validation_no_uppercase() -> None:
    with pytest.raises(ValueError, match="uppercase"):
        PasswordService.validate_password_policy("lowercase123!")


def test_policy_validation_no_lowercase() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        PasswordService.validate_password_policy("UPPERCASE123!")


def test_policy_validation_no_digit() -> None:
    with pytest.raises(ValueError, match="digit"):
        PasswordService.validate_password_policy("NoDigitsHere!")


def test_policy_validation_no_special() -> None:
    with pytest.raises(ValueError, match="special"):
        PasswordService.validate_password_policy("NoSpecial1234")


def test_policy_validation_too_long() -> None:
    password = "Aa1!" + ("x" * 125)

    with pytest.raises(ValueError, match="at most 128"):
        PasswordService.validate_password_policy(password)


def test_no_truncation_129_chars() -> None:
    password = "Aa1!" + ("x" * 125)

    with pytest.raises(ValueError, match="at most 128"):
        PasswordService.hash_password(password)


def test_argon2id_format() -> None:
    password_hash = PasswordService.hash_password(VALID_PASSWORD)

    assert password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
