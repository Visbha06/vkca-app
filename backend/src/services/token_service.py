"""JWT, refresh-token, token-hashing, and CSRF helpers."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt  # type: ignore[import-untyped]

from src.config import get_settings
from src.enums import UserRole

REQUIRED_ACCESS_TOKEN_CLAIMS = frozenset(
    {"sub", "sid", "role", "jti", "iat", "exp"}
)


class TokenService:
    """Create and validate access, refresh, and CSRF token values."""

    def __init__(
        self,
        jwt_secret: str | None = None,
        jwt_algorithm: str | None = None,
        access_token_expire_minutes: int | None = None,
    ) -> None:
        if (
            jwt_secret is None
            or jwt_algorithm is None
            or access_token_expire_minutes is None
        ):
            settings = get_settings()
            if jwt_secret is None:
                jwt_secret = settings.jwt_secret
            if jwt_algorithm is None:
                jwt_algorithm = settings.jwt_algorithm
            if access_token_expire_minutes is None:
                access_token_expire_minutes = settings.access_token_expire_minutes

        if jwt_secret is None or jwt_algorithm is None:
            raise ValueError("JWT signing configuration is incomplete")
        if access_token_expire_minutes is None:
            raise ValueError("access-token expiration is not configured")

        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.access_token_expire_minutes = access_token_expire_minutes

    def create_access_token(
        self,
        user_id: UUID | str,
        session_id: UUID | str,
        role: UserRole | str,
    ) -> str:
        """Return a signed short-lived JWT containing all required claims."""

        issued_at = datetime.now(UTC)
        role_value = role.value if isinstance(role, UserRole) else role
        claims = {
            "sub": str(user_id),
            "sid": str(session_id),
            "role": role_value,
            "jti": str(uuid4()),
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=self.access_token_expire_minutes),
        }
        return jwt.encode(
            claims,
            self.jwt_secret,
            algorithm=self.jwt_algorithm,
        )

    def decode_and_verify_access_token(self, token: str) -> dict[str, Any]:
        """Decode a correctly signed, unexpired JWT with all required claims."""

        claims = jwt.decode(
            token,
            self.jwt_secret,
            algorithms=[self.jwt_algorithm],
            options={
                "require_sub": True,
                "require_exp": True,
                "require_iat": True,
                "require_jti": True,
            },
        )
        missing_claims = REQUIRED_ACCESS_TOKEN_CLAIMS.difference(claims)
        if missing_claims:
            names = ", ".join(sorted(missing_claims))
            raise JWTError(f"access token is missing required claims: {names}")
        return claims

    @staticmethod
    def generate_refresh_token() -> str:
        """Return a 256-bit random, URL-safe opaque refresh token."""

        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """Return the SHA-256 hexadecimal digest used for token persistence."""

        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_csrf_token(
        header_value: str | None,
        cookie_value: str | None,
    ) -> bool:
        """Safely compare non-empty double-submit CSRF token values."""

        if not header_value or not cookie_value:
            return False
        return secrets.compare_digest(header_value, cookie_value)
