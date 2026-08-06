# Phase 0 Research: Business Audit Log and Recent Academy Activity

**Feature**: 009-business-audit-log  
**Date**: 2026-08-05

## Decision 1: Create an independent business-audit boundary

**Decision**: Add a separate business-audit model, service, schema set, route module, migration, and frontend feature module. Do not extend `AuthAuditLog`, `AuditService`, `/api/v1/auth/audit-log`, or any authentication/security event path.

**Rationale**: The existing audit infrastructure is explicitly security-focused. A separate boundary prevents credentials, sessions, authorization denials, and business activity from being mixed and lets each system evolve independently.

**Alternatives considered**:

- Reusing `AuditService`: rejected because it would blur the security/business boundary and risk exposing security records in the academy feed.
- Adding business event types to `auth_audit_log`: rejected because the schemas, retention semantics, and access surface are different.

## Decision 2: Keep transaction ownership in existing mutation services

**Decision**: Each existing public mutation service method remains responsible for validating the complete mutation, flushing domain rows, invoking the business-audit service once, flushing the audit row, committing once, and rolling back both sides on failure. Route-level mutations that currently bypass a service will be centralized in a user/coach service boundary before adding audit capture.

**Rationale**: The current application services already own domain transaction boundaries, while `get_db()` only yields a session. Adding an event after a service returns would be unsafe because the mutation may already be committed. Staging at the outer service boundary also enforces one event for a composite API mutation.

**Alternatives considered**:

- ORM listeners or lower-level row hooks: rejected because roster replacement, recurrence changes, and assignment replacement would generate duplicates.
- Route-level audit calls after service completion: rejected because the domain mutation may already be committed and actor/target snapshots may be stale or unavailable.
- A request-wide automatic event collector: rejected because it would make action classification and sensitive metadata allowlisting implicit and difficult to test.

## Decision 3: Use an immutable actor context and stored snapshots

**Decision**: Routes pass a small immutable actor context containing actor UUID, display name, role snapshot, and optional request ID to mutation services. The business-audit service accepts that context and explicit target snapshots rather than an ORM `User` object.

**Rationale**: Snapshot values must describe the action at the time it occurred, and the audit writer must not depend on later lazy loads or mutable ORM state. This also keeps the service easy to unit test.

**Alternatives considered**:

- Loading the actor again inside the audit service: rejected because it can create extra queries and can observe a changed role/name.
- Storing only foreign-key references: rejected because historical display must survive rename, deactivation, or deletion.

## Decision 4: Retain historical UUIDs without strict foreign keys

**Decision**: Store `actor_user_id` and polymorphic `target_entity_id` as historical UUID values without strict foreign-key enforcement. Actor ID is nullable for future system-generated events. Target IDs have no direct foreign keys because one column represents several entity types. No user/entity deletion may cascade-delete an audit event; snapshots are authoritative for display.

**Rationale**: Permanent traceability is more important than referential enforcement for an append-only history. This directly implements the clarification and prevents audit history from being deleted with domain data.

**Alternatives considered**:

- Nullable actor foreign key with `ON DELETE SET NULL`: acceptable only if a future requirement prioritizes referential enforcement over retaining the actor UUID; not selected for this feature because the clarified requirement prefers permanent traceability.
- Foreign keys for polymorphic targets: rejected because a single target column cannot safely reference multiple tables.
- Cascading deletes: rejected because audit history must never be removed by domain lifecycle operations.

## Decision 5: One event per externally initiated mutation

**Decision**: Emit exactly one event after each successful externally initiated API mutation. Composite operations use allowlisted metadata to describe affected areas; internal row operations never emit their own events.

**Rationale**: A Head Coach should see one understandable activity item for one action, not a low-level list of deletes/inserts. This is required for roster replacement, recurring-series edits, and coach assignment replacement.

**Alternatives considered**:

- One event per database row: rejected because it creates noisy, duplicate activity and leaks implementation details.
- One event per internal service call: rejected because one API action can invoke multiple internal calls.

## Decision 6: Separate full-log and recent routes over one query service

**Decision**: Expose `GET /api/v1/audit-log` for the paginated Head Coach log and `GET /api/v1/audit-log/recent?limit=4` for the dashboard. Both call the same bounded retrieval service and return the same event representation; the recent route enforces a maximum of four.

**Rationale**: A dedicated recent contract makes the dashboard’s bounded behavior explicit while preserving one retrieval implementation and one source of truth. It also avoids accidentally allowing a dashboard caller to request the full history.

**Alternatives considered**:

- Reusing the full endpoint with `page_size=4`: viable, but a dedicated bounded route is easier to audit and test for the dashboard’s strict limit.
- A separate dashboard activity table: rejected because it duplicates storage and tracking logic.

## Decision 7: Use existing pagination and inclusive academy-local date filters

**Decision**: Use the project’s `page`/`page_size` convention, default page size 20, maximum 100, total counts, and stable `created_at DESC, id DESC` ordering. Filter dates are inclusive `America/Los_Angeles` calendar dates converted to timezone-aware boundaries. Reject `end_date < start_date` and date spans over 366 academy-local dates.

**Rationale**: This matches existing player/team/coach list behavior, gives deterministic pagination, and prevents unbounded history scans while supporting operational review over roughly one year.

**Alternatives considered**:

- `limit`/`offset`: rejected for consistency with existing business-resource APIs.
- Unlimited date ranges: rejected because audit history is append-only and can grow indefinitely.
- Browser-local date interpretation: rejected because the academy has a fixed display timezone and daylight-saving transitions must be consistent.

## Decision 8: Capture request IDs opportunistically, without tracing middleware

**Decision**: Read an existing request/correlation header when available and store it as a nullable value. Do not add tracing middleware or observability infrastructure in this feature.

**Rationale**: The specification makes request IDs optional and keeps full tracing out of scope. Opportunistic capture provides useful context without introducing a new cross-cutting dependency.

**Alternatives considered**:

- Required request IDs: rejected because existing callers and local tests do not guarantee one.
- Full request-ID middleware and distributed tracing: deferred because it materially expands scope.

## Decision 9: Reuse the existing frontend shell and state patterns

**Decision**: Add a `frontend/src/features/business-audit` module with API, types, hooks, components, page, and timestamp utilities. Reuse `apiClient`, `Pagination`, `EmptyState`, existing role/auth context, generalized forbidden behavior, native disclosure controls, `aria-live` patterns, and the current dashboard timeline composition.

**Rationale**: The project already has tested patterns for paginated directories, role-aware navigation, loading/error/empty states, keyboard focus, and responsive layouts. Reuse minimizes dependencies and visual drift.

**Alternatives considered**:

- A dashboard-specific activity implementation: rejected because it would create a second source of truth.
- A new UI component library: rejected by the minimal-dependencies and established-design constraints.

## Decision 10: No new dependencies

**Decision**: Use the existing Python, FastAPI, SQLAlchemy, Alembic, React, TypeScript, Vitest, Testing Library, and Playwright dependencies. Use the standard `Intl.DateTimeFormat` API for academy-local and relative time formatting.

**Rationale**: The repository already supports all required persistence, API, UI, testing, and timezone behavior. No new dependency has a sufficiently strong justification.

## Unresolved clarifications

None. Technical choices that remain implementation details are resolved in this research and do not block Phase 1 design.
