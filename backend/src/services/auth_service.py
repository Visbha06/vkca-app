"""Authentication orchestration for login and server-side sessions."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

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


class InvalidSessionError(Exception):
    """Signal an invalid refresh session without exposing the failure reason."""


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

    async def logout(
        self,
        user: User,
        auth_session: AuthSession,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Revoke and audit only the session used for the logout request."""

        auth_session.revoked_at = datetime.now(UTC)
        auth_session.revocation_reason = "logout"
        auth_session.version_number += 1
        await AuditService.log_event(
            self.session,
            "logout",
            user_id=user.id,
            session_id=auth_session.id,
            result="success",
            ip_address=ip_address,
            user_agent=user_agent,
            target_resource="/api/v1/auth/logout",
        )
        await self.session.commit()

    async def revoke_user_sessions(
        self,
        user_id: UUID,
        *,
        reason: str,
        target_resource: str,
    ) -> list[AuthSession]:
        """Revoke every active session for a user in the current transaction."""

        auth_sessions = list(
            (
                await self.session.scalars(
                    select(AuthSession).where(
                        AuthSession.user_id == user_id,
                        AuthSession.revoked_at.is_(None),
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        for auth_session in auth_sessions:
            auth_session.revoked_at = now
            auth_session.revocation_reason = reason
            auth_session.version_number += 1
            await AuditService.log_event(
                self.session,
                "session_revocation",
                user_id=auth_session.user_id,
                session_id=auth_session.id,
                result="success",
                reason=reason,
                target_resource=target_resource,
            )
        return auth_sessions

    async def refresh(
        self,
        refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> tuple[str, str, str]:
        """Rotate one active refresh token and issue a new access token."""

        if not refresh_token:
            raise InvalidSessionError

        token_hash = self.token_service.hash_token(refresh_token)
        auth_session = await self.session.scalar(
            select(AuthSession).where(
                or_(
                    AuthSession.current_token_hash == token_hash,
                    AuthSession.rotated_token_hashes.contains([token_hash]),
                )
            )
        )
        if auth_session is None:
            raise InvalidSessionError

        now = datetime.now(UTC)
        if token_hash in auth_session.rotated_token_hashes:
            await self._reject_token_reuse(
                auth_session,
                now,
                ip_address,
                user_agent,
            )

        settings = get_settings()
        inactivity_cutoff = now - timedelta(days=settings.refresh_inactivity_days)
        if (
            auth_session.revoked_at is not None
            or auth_session.expires_at <= now
            or auth_session.last_used_at <= inactivity_cutoff
        ):
            raise InvalidSessionError

        user = await self.session.scalar(
            select(User).where(User.id == auth_session.user_id)
        )
        if user is None or not user.is_active:
            raise InvalidSessionError

        new_refresh_token = self.token_service.generate_refresh_token()
        new_csrf_token = self.token_service.generate_refresh_token()
        new_token_hash = self.token_service.hash_token(new_refresh_token)
        previous_version = auth_session.version_number
        rotated_token_hashes = [
            *auth_session.rotated_token_hashes,
            auth_session.current_token_hash,
        ]
        rotation = await self.session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == auth_session.id,
                AuthSession.version_number == previous_version,
                AuthSession.current_token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                AuthSession.last_used_at > inactivity_cutoff,
            )
            .values(
                current_token_hash=new_token_hash,
                rotated_token_hashes=rotated_token_hashes,
                last_used_at=now,
                version_number=previous_version + 1,
            )
            .returning(AuthSession.version_number)
            .execution_options(synchronize_session=False)
        )
        new_version = rotation.scalar_one_or_none()
        if new_version is None:
            reused_session_id = await self.session.scalar(
                select(AuthSession.id).where(
                    AuthSession.rotated_token_hashes.contains([token_hash])
                )
            )
            if reused_session_id is not None:
                await self._reject_token_reuse(
                    auth_session,
                    now,
                    ip_address,
                    user_agent,
                )
            raise InvalidSessionError

        set_committed_value(auth_session, "current_token_hash", new_token_hash)
        set_committed_value(
            auth_session,
            "rotated_token_hashes",
            rotated_token_hashes,
        )
        set_committed_value(auth_session, "last_used_at", now)
        set_committed_value(auth_session, "version_number", int(new_version))

        access_token = self.token_service.create_access_token(
            user.id,
            auth_session.id,
            user.role,
        )
        await AuditService.log_event(
            self.session,
            "token_refresh",
            user_id=user.id,
            session_id=auth_session.id,
            result="success",
            ip_address=ip_address,
            user_agent=user_agent,
            target_resource="/api/v1/auth/refresh",
        )
        await self.session.commit()
        return access_token, new_refresh_token, new_csrf_token

    async def _reject_token_reuse(
        self,
        auth_session: AuthSession,
        now: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Revoke a replayed token's family, persist its audit event, and fail."""

        await self.session.execute(
            update(AuthSession)
            .where(AuthSession.token_family_id == auth_session.token_family_id)
            .values(revoked_at=now, revocation_reason="token_reuse")
            .execution_options(synchronize_session=False)
        )
        set_committed_value(auth_session, "revoked_at", now)
        set_committed_value(auth_session, "revocation_reason", "token_reuse")
        await AuditService.log_event(
            self.session,
            "token_reuse",
            user_id=auth_session.user_id,
            session_id=auth_session.id,
            result="failure",
            reason="rotated_token_reuse",
            ip_address=ip_address,
            user_agent=user_agent,
            target_resource="/api/v1/auth/refresh",
        )
        await self.session.commit()
        raise InvalidSessionError

    @staticmethod
    def _failure_reason(user: User | None, password_valid: bool) -> str:
        """Return a credential-free reason for internal audit analysis."""

        if user is None:
            return "unknown_email"
        if not password_valid:
            return "invalid_password"
        return "account_disabled"
