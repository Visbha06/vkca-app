"""Argon2id password hashing and password-policy enforcement."""

import re

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^A-Za-z0-9]")


class PasswordService:
    """Hash and verify passwords using the application's Argon2id profile."""

    _hasher = PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )

    @classmethod
    def hash_password(cls, plaintext: str) -> str:
        """Validate and hash a plaintext password with a fresh random salt."""

        cls.validate_password_policy(plaintext)
        return cls._hasher.hash(plaintext)

    @classmethod
    def verify_password(cls, plaintext: str, password_hash: str) -> bool:
        """Return whether plaintext matches an Argon2 hash without leaking errors."""

        try:
            return cls._hasher.verify(password_hash, plaintext)
        except (VerificationError, ValueError):
            return False

    @staticmethod
    def validate_password_policy(password: str) -> None:
        """Raise ``ValueError`` when a password violates the required policy."""

        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"password must be at least {PASSWORD_MIN_LENGTH} characters"
            )
        if len(password) > PASSWORD_MAX_LENGTH:
            raise ValueError(
                f"password must be at most {PASSWORD_MAX_LENGTH} characters"
            )
        if not any(character.isupper() for character in password):
            raise ValueError("password must contain an uppercase letter")
        if not any(character.islower() for character in password):
            raise ValueError("password must contain a lowercase letter")
        if not any(character.isdigit() for character in password):
            raise ValueError("password must contain a digit")
        if SPECIAL_CHARACTER_PATTERN.search(password) is None:
            raise ValueError("password must contain a special character")
