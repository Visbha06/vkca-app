"""Authentication orchestration for login and server-side sessions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.auth_session import AuthSession
from src.models.user import User
from src.services.audit_service import AuditService
from src.services.password_service import PasswordService
from src.services.token_service import TokenService

DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$M1GdDsvF79kBofj4RwGr+g$"
    "wzgw0TMYLKtFni5U28a1DNG2GNSA8JY3DofEL0s8UY4"
)


class InvalidCredentialsError(Exception):
    """Signal an intentionally indistinguishable login failure."""


class AuthService:
    """Authenticate credentials and establish independently revocable sessions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        token_service: TokenService | None = None,
    ) -> None:
        self.session = session
        self.token_service = token_service or TokenService()

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[User, AuthSession, str, str, str]:
        """Validate credentials, persist a session, and issue browser tokens."""

        normalized_email = email.strip().lower()
        user = await self.session.scalar(
            select(User).where(User.email == normalized_email)
        )
        password_hash = (
            user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
        )
        password_valid = PasswordService.verify_password(password, password_hash)

        if user is None or not password_valid or not user.is_active:
            reason = self._failure_reason(user, password_valid)
            await AuditService.log_event(
                self.session,
                "failed_login",
                user_id=user.id if user is not None else None,
                result="failure",
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                target_resource="/api/v1/auth/login",
            )
            await self.session.commit()
            raise InvalidCredentialsError

        now = datetime.now(UTC)
        refresh_token = self.token_service.generate_refresh_token()
        csrf_token = self.token_service.generate_refresh_token()
        settings = get_settings()
        auth_session = AuthSession(
            id=uuid4(),
            user_id=user.id,
            token_family_id=uuid4(),
            current_token_hash=self.token_service.hash_token(refresh_token),
            rotated_token_hashes=[],
            last_used_at=now,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(auth_session)
        await self.session.flush()

        access_token = self.token_service.create_access_token(
            user.id,
            auth_session.id,
            user.role,
        )
        await AuditService.log_event(
            self.session,
            "login",
            user_id=user.id,
            session_id=auth_session.id,
            result="success",
            ip_address=ip_address,
            user_agent=user_agent,
            target_resource="/api/v1/auth/login",
        )
        await self.session.commit()
        return user, auth_session, access_token, refresh_token, csrf_token

    @staticmethod
    def _failure_reason(user: User | None, password_valid: bool) -> str:
        """Return a credential-free reason for internal audit analysis."""

        if user is None:
            return "unknown_email"
        if not password_valid:
            return "invalid_password"
        return "account_disabled"
