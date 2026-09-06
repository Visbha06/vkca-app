"""Transaction-local work staging and OCC-protected durable transitions."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.background_work_item import BackgroundWorkItem
from src.schemas.background_jobs import (
    BackgroundJobStatus,
    BackgroundJobStatusReport,
    BackgroundRecoveryReport,
)
from src.services.background_jobs.contracts import (
    ACTIVE_COALESCING_STATES,
    DISPATCH_ELIGIBLE_STATES,
    BackgroundPayloadValidationError,
    BackgroundWorkConflictError,
    BackgroundWorkState,
    IncompatiblePayloadVersionError,
    UnregisteredBackgroundJobError,
    validate_json_object,
)
from src.services.background_jobs.logging import sanitize_failure
from src.services.background_jobs.registry import BackgroundJobRegistry
from src.services.background_jobs.retry import FailureCategory, validate_run_after

Clock = Callable[[], datetime]

_IDENTIFIER_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_SAFE_METADATA_KEYS: Final = frozenset(
    {"operation", "reason", "source_count", "trigger", "trigger_kind"}
)
_WORK_IDENTITY_CONSTRAINTS: Final = frozenset(
    {
        "uq_background_work_items_job_idempotency",
        "uq_background_work_items_active_coalescing",
    }
)


class BackgroundWorkNotFoundError(LookupError):
    """Raised when durable background work cannot be found by its UUID."""


class BackgroundWorkTransitionError(ValueError):
    """Raised when a requested state transition violates durable guards."""


class BackgroundCoalescingError(ValueError):
    """Raised when different active payloads have no registered merge strategy."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def _state(value: BackgroundWorkState | str) -> BackgroundWorkState:
    return (
        value if isinstance(value, BackgroundWorkState) else BackgroundWorkState(value)
    )


def _bounded_text(
    value: str | None,
    *,
    name: str,
    max_length: int,
    identifier: bool = False,
) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise BackgroundPayloadValidationError(
            f"{name} must be non-blank and no longer than {max_length} characters."
        )
    if any(ord(character) < 32 for character in normalized):
        raise BackgroundPayloadValidationError(f"{name} contains control characters.")
    if identifier and not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise BackgroundPayloadValidationError(
            f"{name} must be a lowercase bounded identifier."
        )
    return normalized


def _safe_metadata(value: dict[str, object] | None) -> dict[str, Any]:
    metadata = validate_json_object(
        value or {},
        max_serialized_bytes=4_096,
        reject_forbidden_fields=True,
    )
    if set(metadata).difference(_SAFE_METADATA_KEYS):
        raise BackgroundPayloadValidationError(
            "safe_metadata contains fields outside the operational allowlist."
        )
    return metadata


def _identity_conflict(error: IntegrityError) -> bool:
    current: BaseException | None = error.orig
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if getattr(current, "constraint_name", None) in _WORK_IDENTITY_CONSTRAINTS:
            return True
        current = current.__cause__ or current.__context__
    return False


class BackgroundJobOutbox:
    """Stage work in caller transactions and own durable state transitions."""

    def __init__(
        self,
        registry: BackgroundJobRegistry,
        *,
        clock: Clock = utc_now,
        completed_retention_days: int = 7,
        dead_retention_days: int = 30,
    ) -> None:
        if not 1 <= completed_retention_days <= 3_650:
            raise ValueError("completed_retention_days must be between 1 and 3650")
        if not 1 <= dead_retention_days <= 3_650:
            raise ValueError("dead_retention_days must be between 1 and 3650")
        self.registry = registry
        self.clock = clock
        self.completed_retention_days = completed_retention_days
        self.dead_retention_days = dead_retention_days

    async def stage(
        self,
        session: AsyncSession,
        job_type: str,
        payload: object,
        *,
        payload_version: int | None = None,
        idempotency_key: str | None = None,
        coalescing_key: str | None = None,
        correlation_id: UUID | None = None,
        source_type: str | None = None,
        source_key: str | None = None,
        safe_metadata: dict[str, object] | None = None,
        run_after: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Add or coalesce work without committing or contacting a network."""

        now = self._now()
        definition = self.registry.get(job_type, payload_version=payload_version)
        version = (
            definition.payload_version if payload_version is None else payload_version
        )
        typed_payload = definition.payload_adapter.validate(payload)
        normalized_payload = definition.payload_adapter.dump(typed_payload)
        normalized_idempotency = _bounded_text(
            idempotency_key,
            name="idempotency_key",
            max_length=255,
        )
        normalized_coalescing = _bounded_text(
            coalescing_key,
            name="coalescing_key",
            max_length=255,
        )
        normalized_source_type = _bounded_text(
            source_type,
            name="source_type",
            max_length=80,
            identifier=True,
        )
        normalized_source_key = _bounded_text(
            source_key,
            name="source_key",
            max_length=255,
        )
        metadata = _safe_metadata(safe_metadata)
        eligible_at = (
            now if run_after is None else validate_run_after(run_after, now=now)
        )

        if normalized_idempotency is not None:
            existing = await self._find_idempotent(
                session,
                job_type=job_type,
                idempotency_key=normalized_idempotency,
            )
            if existing is not None:
                return existing

        if normalized_coalescing is not None:
            candidate = await self._find_coalescing_candidate(
                session,
                job_type=job_type,
                coalescing_key=normalized_coalescing,
            )
            if (
                candidate is not None
                and _state(candidate.state) in ACTIVE_COALESCING_STATES
            ):
                return await self._coalesce(
                    session,
                    candidate,
                    typed_payload,
                    eligible_at=eligible_at,
                    now=now,
                )
            # Running work deliberately receives a new active successor. Terminal
            # rows likewise do not consume a future logical intent.

        state = (
            BackgroundWorkState.SCHEDULED
            if eligible_at > now
            else BackgroundWorkState.PENDING
        )
        item = BackgroundWorkItem(
            job_type=job_type,
            payload_version=version,
            payload=normalized_payload,
            state=state,
            idempotency_key=normalized_idempotency,
            coalescing_key=normalized_coalescing,
            correlation_id=correlation_id,
            source_type=normalized_source_type,
            source_key=normalized_source_key,
            safe_metadata=metadata,
            run_after=eligible_at,
            dispatch_attempt_count=0,
            execution_attempt_count=0,
            manual_retry_count=0,
            manual_retry_allowed=definition.manual_retry_allowed,
            version_number=1,
        )
        return await self._insert_or_resolve(
            session,
            item,
            typed_payload=typed_payload,
            eligible_at=eligible_at,
            now=now,
        )

    async def stage_manual_trigger(
        self,
        session: AsyncSession,
        trigger: str,
        payload: object,
        **stage_options: Any,
    ) -> BackgroundWorkItem:
        """Stage an allowlisted operator trigger through normal validation.

        The caller still provides a typed payload assembled by that trigger's
        fixed CLI shape.  This method deliberately accepts no arbitrary job
        type, keeping manual work on the same registry/outbox boundary as
        automatic staging.
        """

        definition = self.registry.get_manual_trigger(trigger)
        return await self.stage(
            session,
            definition.job_type,
            payload,
            payload_version=definition.payload_version,
            **stage_options,
        )

    async def reload(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        for_update: bool = False,
    ) -> BackgroundWorkItem | None:
        """Reload current work state after an OCC outcome."""

        statement = select(BackgroundWorkItem).where(BackgroundWorkItem.id == work_id)
        if for_update:
            statement = statement.with_for_update()
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    async def claim_dispatch_batch(
        self,
        session: AsyncSession,
        *,
        lease_owner: str,
        lease_seconds: int,
        limit: int,
        now: datetime | None = None,
    ) -> list[BackgroundWorkItem]:
        """Claim a bounded due batch with row locking plus version predicates."""

        reference = self._reference(now)
        owner = _bounded_text(
            lease_owner,
            name="lease_owner",
            max_length=128,
        )
        if not 1 <= lease_seconds <= 3_600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        statement = (
            select(BackgroundWorkItem)
            .where(
                BackgroundWorkItem.state.in_(DISPATCH_ELIGIBLE_STATES),
                BackgroundWorkItem.run_after <= reference,
            )
            .order_by(BackgroundWorkItem.run_after, BackgroundWorkItem.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        candidates = list((await session.execute(statement)).scalars().all())
        claimed: list[BackgroundWorkItem] = []
        for candidate in candidates:
            try:
                claimed.append(
                    await self._transition(
                        session,
                        candidate.id,
                        expected_version=candidate.version_number,
                        expected_states=tuple(DISPATCH_ELIGIBLE_STATES),
                        now=reference,
                        values={
                            "state": BackgroundWorkState.DISPATCHING,
                            "lease_owner": owner,
                            "lease_expires_at": reference
                            + timedelta(seconds=lease_seconds),
                            "dispatch_attempt_count": (
                                candidate.dispatch_attempt_count + 1
                            ),
                            "last_attempt_at": reference,
                        },
                    )
                )
            except BackgroundWorkConflictError:
                continue
        return claimed

    async def mark_dispatched(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        lease_owner: str,
        arq_job_id: str,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Record successful broker handoff with the dispatch lease predicate."""

        reference = self._reference(now)
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(BackgroundWorkState.DISPATCHING,),
            expected_lease_owner=lease_owner,
            require_live_lease=True,
            now=reference,
            values={
                "state": BackgroundWorkState.DISPATCHED,
                "arq_job_id": _bounded_text(
                    arq_job_id,
                    name="arq_job_id",
                    max_length=255,
                ),
                "dispatched_at": reference,
                "last_failure_category": None,
                "last_failure_message": None,
            },
        )

    async def renew_execution_lease(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        lease_owner: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Extend one live running lease before bounded handler execution."""

        if not 1 <= lease_seconds <= 7_200:
            raise ValueError("lease_seconds must be between 1 and 7200")
        reference = self._reference(now)
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(BackgroundWorkState.RUNNING,),
            expected_lease_owner=lease_owner,
            require_live_lease=True,
            now=reference,
            values={
                "lease_expires_at": reference + timedelta(seconds=lease_seconds),
            },
        )

    async def mark_dispatch_failure(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        lease_owner: str,
        category: FailureCategory,
        run_after: datetime,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Persist a broker failure while retaining durable eligible work."""

        reference = self._reference(now)
        safe_failure = sanitize_failure(category)
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(BackgroundWorkState.DISPATCHING,),
            expected_lease_owner=lease_owner,
            require_live_lease=True,
            now=reference,
            values={
                "state": BackgroundWorkState.RETRYING,
                "run_after": validate_run_after(run_after, now=reference),
                "lease_owner": None,
                "lease_expires_at": None,
                "last_failure_category": safe_failure.category.value,
                "last_failure_message": safe_failure.message,
            },
        )

    async def claim_for_execution(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        lease_owner: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Claim dispatched or due retrying work for one generic worker."""

        reference = self._reference(now)
        if not 1 <= lease_seconds <= 3_600:
            raise ValueError("lease_seconds must be between 1 and 3600")
        current = await self.reload(session, work_id)
        if current is None:
            raise BackgroundWorkNotFoundError(
                f"Background work {work_id} was not found."
            )
        if current.version_number != expected_version:
            raise BackgroundWorkConflictError(
                work_id,
                expected_version,
                current=current,
            )
        if _state(current.state) not in {
            BackgroundWorkState.DISPATCHED,
            BackgroundWorkState.RETRYING,
        }:
            raise BackgroundWorkTransitionError(
                "Only dispatched or retrying work can be executed."
            )
        if current.run_after > reference:
            raise BackgroundWorkTransitionError("Background work is not due yet.")
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(
                BackgroundWorkState.DISPATCHED,
                BackgroundWorkState.RETRYING,
            ),
            now=reference,
            values={
                "state": BackgroundWorkState.RUNNING,
                "lease_owner": _bounded_text(
                    lease_owner,
                    name="lease_owner",
                    max_length=128,
                ),
                "lease_expires_at": reference + timedelta(seconds=lease_seconds),
                "execution_attempt_count": current.execution_attempt_count + 1,
                "last_attempt_at": reference,
                "started_at": reference,
            },
        )

    async def mark_completed(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        lease_owner: str,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Complete running work only for the matching live worker lease."""

        reference = self._reference(now)
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(BackgroundWorkState.RUNNING,),
            expected_lease_owner=lease_owner,
            require_live_lease=True,
            now=reference,
            values={
                "state": BackgroundWorkState.COMPLETED,
                "lease_owner": None,
                "lease_expires_at": None,
                "completed_at": reference,
                "terminal_at": None,
                "retention_until": reference
                + timedelta(days=self.completed_retention_days),
                "last_failure_category": None,
                "last_failure_message": None,
            },
        )

    async def mark_retrying(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        lease_owner: str,
        category: FailureCategory,
        run_after: datetime,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Persist an execution retry with matching version and worker lease."""

        reference = self._reference(now)
        failure = sanitize_failure(category)
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(BackgroundWorkState.RUNNING,),
            expected_lease_owner=lease_owner,
            require_live_lease=lease_owner is not None,
            now=reference,
            values={
                "state": BackgroundWorkState.RETRYING,
                "run_after": validate_run_after(run_after, now=reference),
                "lease_owner": None,
                "lease_expires_at": None,
                "last_failure_category": failure.category.value,
                "last_failure_message": failure.message,
            },
        )

    async def mark_dead(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        category: FailureCategory,
        lease_owner: str | None = None,
        expected_states: Sequence[BackgroundWorkState] = (BackgroundWorkState.RUNNING,),
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Persist a terminal sanitized failure without retaining exceptions."""

        reference = self._reference(now)
        failure = sanitize_failure(category)
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=expected_states,
            expected_lease_owner=lease_owner,
            require_live_lease=lease_owner is not None,
            now=reference,
            values={
                "state": BackgroundWorkState.DEAD,
                "lease_owner": None,
                "lease_expires_at": None,
                "terminal_at": reference,
                "retention_until": reference + timedelta(days=self.dead_retention_days),
                "last_failure_category": failure.category.value,
                "last_failure_message": failure.message,
            },
        )

    async def manual_requeue(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        max_manual_retries: int,
        now: datetime | None = None,
    ) -> BackgroundWorkItem:
        """Requeue one approved dead item with finite manual retry bounds."""

        if not 1 <= max_manual_retries <= 20:
            raise ValueError("max_manual_retries must be between 1 and 20")
        reference = self._reference(now)
        current = await self.reload(session, work_id)
        if current is None:
            raise BackgroundWorkNotFoundError(
                f"Background work {work_id} was not found."
            )
        if current.version_number != expected_version:
            raise BackgroundWorkConflictError(
                work_id,
                expected_version,
                current=current,
            )
        if _state(current.state) is not BackgroundWorkState.DEAD:
            raise BackgroundWorkTransitionError(
                "Only dead work can be manually requeued."
            )
        definition = self.registry.get(
            current.job_type,
            payload_version=current.payload_version,
        )
        if not current.manual_retry_allowed or not definition.manual_retry_allowed:
            raise BackgroundWorkTransitionError(
                "This registered job does not permit manual retry."
            )
        if current.manual_retry_count >= max_manual_retries:
            raise BackgroundWorkTransitionError("Manual retry limit is exhausted.")
        return await self._transition(
            session,
            work_id,
            expected_version=expected_version,
            expected_states=(BackgroundWorkState.DEAD,),
            now=reference,
            values={
                "state": BackgroundWorkState.PENDING,
                "run_after": reference,
                "manual_retry_count": current.manual_retry_count + 1,
                "dispatch_attempt_count": 0,
                "execution_attempt_count": 0,
                "arq_job_id": None,
                "terminal_at": None,
                "retention_until": None,
                "last_failure_category": None,
                "last_failure_message": None,
            },
        )

    async def recover_expired_leases(
        self,
        session: AsyncSession,
        *,
        limit: int,
        now: datetime | None = None,
    ) -> BackgroundRecoveryReport:
        """Make expired dispatcher/worker claims eligible again in a bounded batch."""

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        reference = self._reference(now)
        statement = (
            select(BackgroundWorkItem)
            .where(
                BackgroundWorkItem.state.in_(
                    (
                        BackgroundWorkState.DISPATCHING,
                        BackgroundWorkState.DISPATCHED,
                        BackgroundWorkState.RUNNING,
                    )
                ),
                BackgroundWorkItem.lease_expires_at <= reference,
            )
            .order_by(BackgroundWorkItem.lease_expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        candidates = list((await session.execute(statement)).scalars().all())
        recovered: list[BackgroundWorkItem] = []
        retrying = 0
        dead = 0
        conflicts = 0
        for candidate in candidates:
            try:
                state = _state(candidate.state)
                try:
                    definition = self.registry.get(
                        candidate.job_type,
                        payload_version=candidate.payload_version,
                    )
                except UnregisteredBackgroundJobError:
                    category = FailureCategory.UNREGISTERED_JOB
                    exhausted = True
                except IncompatiblePayloadVersionError:
                    category = FailureCategory.INCOMPATIBLE_PAYLOAD_VERSION
                    exhausted = True
                else:
                    attempt_count = (
                        candidate.execution_attempt_count
                        if state is BackgroundWorkState.RUNNING
                        else candidate.dispatch_attempt_count
                    )
                    exhausted = attempt_count >= definition.retry_policy.max_attempts
                    category = (
                        FailureCategory.RETRY_LIMIT_EXHAUSTED
                        if exhausted
                        else FailureCategory.TIMEOUT
                    )
                failure = sanitize_failure(category)
                values: dict[str, object] = {
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "last_failure_category": failure.category.value,
                    "last_failure_message": failure.message,
                }
                if exhausted:
                    values.update(
                        state=BackgroundWorkState.DEAD,
                        terminal_at=reference,
                        retention_until=reference
                        + timedelta(days=self.dead_retention_days),
                    )
                else:
                    values.update(
                        state=BackgroundWorkState.RETRYING,
                        run_after=reference,
                    )
                recovered_item = await self._transition(
                    session,
                    candidate.id,
                    expected_version=candidate.version_number,
                    expected_states=(state,),
                    expected_lease_owner=candidate.lease_owner,
                    require_expired_lease=True,
                    now=reference,
                    values=values,
                )
                recovered.append(recovered_item)
                if exhausted:
                    dead += 1
                else:
                    retrying += 1
            except BackgroundWorkConflictError:
                conflicts += 1
                continue
        return BackgroundRecoveryReport(
            recovered=len(recovered),
            retrying=retrying,
            dead=dead,
            conflicts=conflicts,
            work_ids=[item.id for item in recovered],
        )

    async def inspect_status(
        self,
        session: AsyncSession,
        *,
        states: Sequence[BackgroundWorkState] | None = None,
        limit: int = 50,
    ) -> BackgroundJobStatusReport:
        """Return aggregate state counts and bounded allowlisted row projections."""

        if not 1 <= limit <= 100:
            raise ValueError("status limit must be between 1 and 100")
        selected_states = tuple(states or ())
        if len(selected_states) != len(set(selected_states)):
            raise ValueError("status state filters must be unique")
        count_rows = (
            await session.execute(
                select(BackgroundWorkItem.state, func.count(BackgroundWorkItem.id))
                .group_by(BackgroundWorkItem.state)
                .order_by(BackgroundWorkItem.state)
            )
        ).all()
        statement = select(BackgroundWorkItem)
        if selected_states:
            statement = statement.where(BackgroundWorkItem.state.in_(selected_states))
        statement = statement.order_by(
            BackgroundWorkItem.created_at.desc(),
            BackgroundWorkItem.id,
        ).limit(limit)
        items = tuple((await session.scalars(statement)).all())
        return BackgroundJobStatusReport(
            counts={str(state): int(count) for state, count in count_rows},
            items=[self.project_status(item) for item in items],
            limit=limit,
        )

    async def retention_eligible(
        self,
        session: AsyncSession,
        *,
        limit: int,
        now: datetime | None = None,
    ) -> list[BackgroundWorkItem]:
        """Return only bounded terminal rows whose retention period elapsed."""

        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        reference = self._reference(now)
        statement = (
            select(BackgroundWorkItem)
            .where(
                BackgroundWorkItem.state.in_(
                    (BackgroundWorkState.COMPLETED, BackgroundWorkState.DEAD)
                ),
                BackgroundWorkItem.retention_until <= reference,
            )
            .order_by(BackgroundWorkItem.retention_until)
            .limit(limit)
        )
        return list((await session.execute(statement)).scalars().all())

    def project_status(self, item: BackgroundWorkItem) -> BackgroundJobStatus:
        """Build the allowlisted operator projection for one durable row."""

        return BackgroundJobStatus.model_validate(item)

    async def _insert_or_resolve(
        self,
        session: AsyncSession,
        item: BackgroundWorkItem,
        *,
        typed_payload: object,
        eligible_at: datetime,
        now: datetime,
    ) -> BackgroundWorkItem:
        """Insert under a savepoint and resolve a concurrent uniqueness winner."""

        uses_unique_identity = (
            item.idempotency_key is not None or item.coalescing_key is not None
        )
        try:
            if uses_unique_identity:
                async with session.begin_nested():
                    session.add(item)
                    await session.flush()
            else:
                session.add(item)
                await session.flush()
            return item
        except IntegrityError as exc:
            if not _identity_conflict(exc):
                raise
            if item.idempotency_key is not None:
                existing = await self._find_idempotent(
                    session,
                    job_type=item.job_type,
                    idempotency_key=item.idempotency_key,
                )
                if existing is not None:
                    return existing
            if item.coalescing_key is not None:
                candidate = await self._find_coalescing_candidate(
                    session,
                    job_type=item.job_type,
                    coalescing_key=item.coalescing_key,
                )
                if (
                    candidate is not None
                    and _state(candidate.state) in ACTIVE_COALESCING_STATES
                ):
                    return await self._coalesce(
                        session,
                        candidate,
                        typed_payload,
                        eligible_at=eligible_at,
                        now=now,
                    )
            raise BackgroundCoalescingError(
                "Concurrent background-work identity could not be resolved."
            ) from exc

    async def _find_idempotent(
        self,
        session: AsyncSession,
        *,
        job_type: str,
        idempotency_key: str,
    ) -> BackgroundWorkItem | None:
        result = await session.execute(
            select(BackgroundWorkItem)
            .where(
                BackgroundWorkItem.job_type == job_type,
                BackgroundWorkItem.idempotency_key == idempotency_key,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_coalescing_candidate(
        self,
        session: AsyncSession,
        *,
        job_type: str,
        coalescing_key: str,
    ) -> BackgroundWorkItem | None:
        # Prefer mergeable active work. If only running work exists, returning it
        # causes stage() to create the required successor.
        result = await session.execute(
            select(BackgroundWorkItem)
            .where(
                BackgroundWorkItem.job_type == job_type,
                BackgroundWorkItem.coalescing_key == coalescing_key,
                BackgroundWorkItem.state.notin_(
                    (BackgroundWorkState.COMPLETED, BackgroundWorkState.DEAD)
                ),
            )
            .order_by(
                case(
                    (BackgroundWorkItem.state == BackgroundWorkState.RUNNING, 1),
                    else_=0,
                ),
                BackgroundWorkItem.created_at.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _coalesce(
        self,
        session: AsyncSession,
        existing: BackgroundWorkItem,
        incoming_payload: object,
        *,
        eligible_at: datetime,
        now: datetime,
    ) -> BackgroundWorkItem:
        definition = self.registry.get(
            existing.job_type,
            payload_version=existing.payload_version,
        )
        current_typed = definition.payload_adapter.validate(existing.payload)
        incoming_typed = definition.payload_adapter.validate(incoming_payload)
        if definition.coalescer is None:
            if current_typed != incoming_typed:
                raise BackgroundCoalescingError(
                    "Registered job has no bounded payload coalescer."
                )
            return existing
        merged = definition.coalescer(current_typed, incoming_typed)
        merged_payload = definition.payload_adapter.dump(merged)
        next_run_after = min(existing.run_after, eligible_at)
        existing_state = _state(existing.state)
        next_state = (
            BackgroundWorkState.PENDING
            if existing_state is BackgroundWorkState.SCHEDULED and next_run_after <= now
            else existing_state
        )
        return await self._transition(
            session,
            existing.id,
            expected_version=existing.version_number,
            expected_states=(existing_state,),
            now=now,
            values={
                "payload": merged_payload,
                "run_after": next_run_after,
                "state": next_state,
            },
        )

    async def _transition(
        self,
        session: AsyncSession,
        work_id: UUID,
        *,
        expected_version: int,
        expected_states: Sequence[BackgroundWorkState],
        values: dict[str, object],
        now: datetime,
        expected_lease_owner: str | None = None,
        require_live_lease: bool = False,
        require_expired_lease: bool = False,
    ) -> BackgroundWorkItem:
        predicates = [
            BackgroundWorkItem.id == work_id,
            BackgroundWorkItem.version_number == expected_version,
            BackgroundWorkItem.state.in_(expected_states),
        ]
        if expected_lease_owner is not None:
            predicates.append(BackgroundWorkItem.lease_owner == expected_lease_owner)
        if require_live_lease:
            predicates.append(BackgroundWorkItem.lease_expires_at > now)
        if require_expired_lease:
            predicates.append(BackgroundWorkItem.lease_expires_at <= now)
        statement = (
            update(BackgroundWorkItem)
            .where(*predicates)
            .values(
                **values,
                version_number=expected_version + 1,
                updated_at=func.now(),
            )
            .returning(BackgroundWorkItem)
        )
        updated = (await session.execute(statement)).scalar_one_or_none()
        if updated is not None:
            return updated
        current = await self.reload(session, work_id)
        raise BackgroundWorkConflictError(
            work_id,
            expected_version,
            current=current,
        )

    def _now(self) -> datetime:
        return self._reference(self.clock())

    @staticmethod
    def _reference(value: datetime | None) -> datetime:
        reference = value or utc_now()
        if reference.tzinfo is None or reference.utcoffset() is None:
            raise ValueError("Background processing clocks must be timezone-aware")
        return reference


async def stage_background_work(
    session: AsyncSession,
    outbox: BackgroundJobOutbox,
    job_type: str,
    payload: object,
    *,
    payload_version: int | None = None,
    idempotency_key: str | None = None,
    coalescing_key: str | None = None,
    correlation_id: UUID | None = None,
    source_type: str | None = None,
    source_key: str | None = None,
    safe_metadata: dict[str, object] | None = None,
    run_after: datetime | None = None,
) -> BackgroundWorkItem:
    """Functional staging facade for application-service transaction boundaries."""

    return await outbox.stage(
        session,
        job_type,
        payload,
        payload_version=payload_version,
        idempotency_key=idempotency_key,
        coalescing_key=coalescing_key,
        correlation_id=correlation_id,
        source_type=source_type,
        source_key=source_key,
        safe_metadata=safe_metadata,
        run_after=run_after,
    )


async def stage_scoring_refresh(
    session: AsyncSession,
    *,
    match_id: UUID,
    innings_id: UUID,
    projection_revision: int,
    reason: Literal["completion", "correction"],
) -> BackgroundWorkItem:
    """Stage the shared completion/correction refresh through the existing outbox."""
    from src.services.rag.contracts import (
        RagReconciliationPayloadV1,
        RagTargetRef,
        ScoringRefreshRef,
    )
    from src.services.rag.registry import get_rag_mutation_stager

    payload = RagReconciliationPayloadV1(
        targets=(RagTargetRef(source_type="match", source_key=str(match_id)),),
        scoring_refresh=ScoringRefreshRef(
            match_id=match_id,
            innings_id=innings_id,
            projection_revision=projection_revision,
            reason=reason,
        ),
    )
    return await get_rag_mutation_stager().outbox.stage(
        session,
        "rag_reconciliation",
        payload,
        idempotency_key=f"scoring:{match_id}:{innings_id}:{projection_revision}",
        coalescing_key=f"rag:match:{match_id}",
        source_type="match",
        source_key=str(match_id),
        safe_metadata={"reason": reason, "source_count": 1},
    )
