"""Explicit allowlist of typed background-job definitions."""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from pydantic import BaseModel

from src.services.background_jobs.contracts import (
    IncompatiblePayloadVersionError,
    UnregisteredBackgroundJobError,
    VersionedPayloadAdapter,
)
from src.services.background_jobs.retry import (
    FailureClassification,
    RetryPolicy,
    classify_failure,
)

type JobHandler = Callable[[object, BaseModel], Awaitable[object | None]]
type PayloadCoalescer = Callable[[BaseModel, BaseModel], BaseModel | object]
type RetryClassifier = Callable[[BaseException], FailureClassification]

_JOB_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_MANUAL_TRIGGER_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,79}$")


class BackgroundJobRegistryError(ValueError):
    """Base class for safe registry configuration errors."""


class DuplicateBackgroundJobError(BackgroundJobRegistryError):
    """Raised when a stable job type is registered more than once."""


class HandlerNotAllowedError(BackgroundJobRegistryError):
    """Raised when a definition references an unapproved handler."""


class InvalidBackgroundJobDefinitionError(BackgroundJobRegistryError):
    """Raised when definition metadata is invalid or unbounded."""


@dataclass(frozen=True, slots=True)
class ResourceBounds:
    """Declared finite concurrency and batch bounds for one handler."""

    max_concurrency: int
    max_batch_size: int


@dataclass(frozen=True, slots=True)
class BackgroundJobDefinition:
    """One immutable registry entry for an executable typed job."""

    job_type: str
    payload_version: int
    payload_model: type[BaseModel]
    handler: JobHandler
    retry_policy: RetryPolicy
    idempotency_strategy: str
    resource_bounds: ResourceBounds
    manual_retry_allowed: bool = False
    coalescer: PayloadCoalescer | None = None
    retry_classifier: RetryClassifier = classify_failure
    concurrency_key: str | None = None
    manual_trigger: str | None = None

    @property
    def payload_adapter(self) -> VersionedPayloadAdapter[BaseModel]:
        return VersionedPayloadAdapter(
            version=self.payload_version,
            payload_model=self.payload_model,
        )

    @property
    def timeout_seconds(self) -> float:
        return self.retry_policy.timeout_seconds


class BackgroundJobRegistry:
    """Register and resolve only explicitly approved job definitions."""

    def __init__(self, *, allowed_handlers: Iterable[JobHandler] = ()) -> None:
        self._allowed_handlers = frozenset(allowed_handlers)
        self._definitions: dict[str, BackgroundJobDefinition] = {}

    @property
    def definitions(self) -> Mapping[str, BackgroundJobDefinition]:
        return MappingProxyType(self._definitions)

    def register(self, definition: BackgroundJobDefinition) -> BackgroundJobDefinition:
        """Validate and register one stable job type."""

        self._validate_definition(definition)
        if definition.job_type in self._definitions:
            raise DuplicateBackgroundJobError(
                f"Background job type '{definition.job_type}' is already registered."
            )
        self._definitions[definition.job_type] = definition
        return definition

    def get(
        self,
        job_type: str,
        *,
        payload_version: int | None = None,
    ) -> BackgroundJobDefinition:
        """Resolve one registered type/version without dynamic imports."""

        definition = self._definitions.get(job_type)
        if definition is None:
            raise UnregisteredBackgroundJobError(
                f"Background job type '{job_type}' is not registered."
            )
        if (
            payload_version is not None
            and payload_version != definition.payload_version
        ):
            raise IncompatiblePayloadVersionError(
                f"Background job type '{job_type}' does not support payload "
                f"version {payload_version}."
            )
        return definition

    def get_manual_trigger(self, trigger: str) -> BackgroundJobDefinition:
        """Resolve one explicitly registered operator trigger.

        Trigger names are registry metadata rather than client-selected job
        types, so an operator command cannot become an arbitrary execution
        path merely by supplying a different string.
        """

        normalized = trigger.strip()
        for definition in self._definitions.values():
            if definition.manual_trigger == normalized:
                return definition
        raise UnregisteredBackgroundJobError(
            f"Background manual trigger '{normalized}' is not registered."
        )

    def validate_payload(
        self,
        job_type: str,
        payload_version: int,
        payload: object,
    ) -> BaseModel:
        """Validate a durable payload through its registered version adapter."""

        definition = self.get(job_type, payload_version=payload_version)
        return definition.payload_adapter.validate(payload)

    def _validate_definition(self, definition: BackgroundJobDefinition) -> None:
        if not isinstance(definition, BackgroundJobDefinition):
            raise InvalidBackgroundJobDefinitionError(
                "Registry entries must be BackgroundJobDefinition values."
            )
        if not _JOB_TYPE_PATTERN.fullmatch(definition.job_type):
            raise InvalidBackgroundJobDefinitionError(
                "job_type must be a bounded lowercase identifier."
            )
        if not 1 <= definition.payload_version <= 32_767:
            raise InvalidBackgroundJobDefinitionError(
                "payload_version must be between 1 and 32767."
            )
        if not isinstance(definition.payload_model, type) or not issubclass(
            definition.payload_model, BaseModel
        ):
            raise InvalidBackgroundJobDefinitionError(
                "payload_model must be a Pydantic BaseModel type."
            )
        if definition.handler not in self._allowed_handlers:
            raise HandlerNotAllowedError(
                "Background job handler is not present in the explicit allowlist."
            )
        if not inspect.iscoroutinefunction(definition.handler):
            raise InvalidBackgroundJobDefinitionError(
                "Background job handlers must be async functions."
            )
        if definition.coalescer is not None and inspect.iscoroutinefunction(
            definition.coalescer
        ):
            raise InvalidBackgroundJobDefinitionError(
                "Payload coalescers must be synchronous and transaction-local."
            )
        if not callable(definition.retry_classifier):
            raise InvalidBackgroundJobDefinitionError(
                "retry_classifier must be callable."
            )
        strategy = definition.idempotency_strategy.strip()
        if not strategy or len(strategy) > 500:
            raise InvalidBackgroundJobDefinitionError(
                "idempotency_strategy must be non-blank and bounded."
            )
        bounds = definition.resource_bounds
        if not 1 <= bounds.max_concurrency <= 64:
            raise InvalidBackgroundJobDefinitionError(
                "max_concurrency must be between 1 and 64."
            )
        if not 1 <= bounds.max_batch_size <= 1_000:
            raise InvalidBackgroundJobDefinitionError(
                "max_batch_size must be between 1 and 1000."
            )
        if definition.concurrency_key is not None and not (
            1 <= len(definition.concurrency_key.strip()) <= 80
        ):
            raise InvalidBackgroundJobDefinitionError(
                "concurrency_key must be non-blank and bounded when provided."
            )
        if (
            definition.manual_trigger is not None
            and not _MANUAL_TRIGGER_PATTERN.fullmatch(definition.manual_trigger)
        ):
            raise InvalidBackgroundJobDefinitionError(
                "manual_trigger must be a bounded lowercase command identifier."
            )
        if definition.manual_trigger is not None and any(
            registered.manual_trigger == definition.manual_trigger
            for registered in self._definitions.values()
        ):
            raise DuplicateBackgroundJobError(
                f"Background manual trigger '{definition.manual_trigger}' is "
                "already registered."
            )


def build_background_job_registry(
    definitions: Iterable[BackgroundJobDefinition] = (),
    *,
    allowed_handlers: Iterable[JobHandler] = (),
    settings: object | None = None,
) -> BackgroundJobRegistry:
    """Build the application registry without creating provider/network resources."""

    from src.config import get_settings
    from src.services.background_jobs.handlers.rag_reconciliation import (
        classify_rag_reconciliation_failure,
        coalesce_rag_reconciliation_payloads,
        rag_reconciliation_handler,
    )
    from src.services.rag.contracts import (
        MAX_RAG_MUTATION_TARGETS,
        RagReconciliationPayloadV1,
    )

    selected_settings = cast(Any, settings or get_settings())
    application_definition = BackgroundJobDefinition(
        job_type="rag_reconciliation",
        payload_version=1,
        payload_model=RagReconciliationPayloadV1,
        handler=rag_reconciliation_handler,
        retry_policy=RetryPolicy(
            max_attempts=int(selected_settings.background_max_attempts),
            base_delay_seconds=float(selected_settings.background_retry_base_seconds),
            max_delay_seconds=float(selected_settings.background_retry_max_seconds),
            jitter_seconds=float(selected_settings.background_retry_jitter_seconds),
            timeout_seconds=float(selected_settings.background_job_timeout_seconds),
        ),
        idempotency_strategy=(
            "Reload current registered source truth and reconcile stable targets."
        ),
        resource_bounds=ResourceBounds(
            max_concurrency=int(selected_settings.background_worker_max_jobs),
            max_batch_size=MAX_RAG_MUTATION_TARGETS,
        ),
        manual_retry_allowed=True,
        coalescer=coalesce_rag_reconciliation_payloads,
        retry_classifier=classify_rag_reconciliation_failure,
        concurrency_key="rag-indexing",
        manual_trigger="trigger-rag",
    )
    configured_definitions = (application_definition, *tuple(definitions))
    registry = BackgroundJobRegistry(
        allowed_handlers={rag_reconciliation_handler, *tuple(allowed_handlers)}
    )
    for definition in configured_definitions:
        registry.register(definition)
    return registry
