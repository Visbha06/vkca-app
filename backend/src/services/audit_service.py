"""Authentication and authorization audit record writer."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.auth_audit_log import AuthAuditLog


class AuditService:
    """Append security events to the current database transaction."""

    @staticmethod
    async def log_event(
        session: AsyncSession,
        event_type: str,
        *,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        result: str,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        target_resource: str | None = None,
    ) -> None:
        """Stage and flush one credential-free audit record without committing."""

        record = AuthAuditLog(
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            result=result,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            target_resource=target_resource,
        )
        session.add(record)
        await session.flush()
