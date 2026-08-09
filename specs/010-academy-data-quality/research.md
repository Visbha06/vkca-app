# Academy Data Quality Research

## Scope and source of truth

This design is based on the current repository, `PRODUCT.md`, `DESIGN.md`, and
`.specify/memory/constitution.md`. The relevant implementation patterns are the
existing FastAPI/SQLAlchemy services and routes under `backend/src`, the React
feature/page structure under `frontend/src`, the Head Coach route guard, the
Business Audit Log, optimistic-concurrency helpers, and the existing unit,
integration, Vitest, and Playwright suites.

The clarified specification is the product contract. Repository behavior is
used to choose extension points and to exclude checks that the schema or normal
service validation already makes impossible.

## Decision: Extend the current stack without new dependencies or persistence

**Decision**: Implement the feature with Python 3.12+, FastAPI, async
SQLAlchemy, PostgreSQL, React, TypeScript, Vitest, pytest, and Playwright that
are already present. Do not add a findings table, scan-history table, queue,
worker, scheduler, or third-party dependency.

**Rationale**:

- Findings are explicitly current-state, on-demand results.
- The repository already has typed Pydantic boundaries, async database access,
  pagination conventions, role protection, OCC, and test fixtures.
- No schema migration is needed when findings and remediation commands remain
  transient and existing domain records are unchanged.

**Alternatives considered**:

- Persisted findings would create lifecycle, expiration, and history concerns
  that are out of scope.
- A new query or validation library would add dependency and typing overhead
  without solving a repository gap.

## Decision: Registry-driven evaluator over parallel per-domain endpoints

**Decision**: Add one reusable data-quality service with a stable rule registry.
Rules expose stable IDs, severity, domain, finding construction, and optional
direct-action metadata. The service evaluates all registered rules from a
shared batched `EvaluationContext`, then applies deterministic ordering,
summary aggregation, filters, and pagination.

The initial registry contains these 17 stable rules:

`player.active_unassigned`, `player.inactive_rostered`,
`player.normalized_identity_duplicate`, `team.roster_below_minimum`,
`team.roster_above_maximum`, `roster.order_non_positive`,
`roster.order_duplicate`, `roster.order_gap`, `roster.order_non_contiguous`,
`team.normalized_name_conflict`, `team.no_assigned_coach`,
`coach.sole_head_coach_integrity`, `coach.inactive_assigned`,
`coach.active_assistant_unassigned`, `coach.assignment_invalid_role`,
`calendar.recurrence_end_before_start`, and
`calendar.stale_occurrence_exception`.

**Rationale**:

- A registry makes rule coverage, stable identifiers, severity, and isolated
  unit tests explicit.
- One evaluator keeps summary counts and filtered findings based on the same
  current snapshot.
- A shared context prevents each rule from loading the same teams, players,
  memberships, coaches, or calendar relationships independently.

**Alternatives considered**:

- Separate `/players/quality`, `/teams/quality`, and `/calendar/quality`
  endpoints would duplicate authorization, pagination, summary behavior, and
  frontend state handling.
- A generic SQL rule runner would violate the allowlisted and deterministic
  contract and would make authorization and validation harder to audit.

## Decision: Narrow projections plus set-based and batched evaluation

**Decision**: Build one or a small number of SQL statements per domain that
return only the columns required by the rules. Use joins, grouped aggregates,
outer joins, normalized SQL expressions, and one batched relationship query
where appropriate. Group the resulting projections by IDs in memory rather
than issuing per-entity queries.

Planned query responsibilities:

- Players: active/unassigned and inactive-membership results from a player to
  roster aggregate/join; identity duplicate candidates from normalized identity
  projections rather than full ORM objects.
- Teams and rosters: roster counts, inactive-member counts, team-name conflict
  groups, no-coach counts, and one ordered membership projection for roster
  position diagnostics.
- Coaches: one assignment projection joined to users and teams, grouped
  assignment counts, invalid-role rows, inactive Assistant Coach assignments,
  active unassigned Assistant Coaches, and sole Head Coach coverage.
- Calendar: recurrence series joined to owning event plus exceptions and their
  current rule fields. Use the existing recurrence helper for semantic checks;
  do not expand unbounded series or change timezone behavior.

The evaluator may materialize narrow finding DTOs needed for global sorting and
summary counts, but it must not materialize full ORM tables or perform N+1
lookups. Query-count/regression tests will use realistic seeded projections.

**Rationale**:

- Summary counts and deterministic cross-domain ordering require a common
  candidate set, while narrow projections keep memory use proportional to
  finding inputs rather than full model graphs.
- The repository already uses SQLAlchemy aggregates, joins, stable ordering,
  and bounded pagination in domain services.

**Alternatives considered**:

- Calling existing list services once per rule would cause N+1 behavior and
  would return UI-shaped records that contain unnecessary fields.
- Expanding every calendar series to find stale exceptions would violate the
  existing bounded recurrence semantics.

## Decision: Normalize identities with a shared pure helper

**Decision**: Add a small pure normalization helper for player duplicate
detection that applies Unicode normalization, trimming, whitespace collapsing,
and case-folding to first and last names, while comparing the existing date of
birth value directly. Use the same helper for deterministic labels and tests,
but do not infer nicknames, transliterations, or likely identity.

Team-name conflict detection continues to use the repository’s existing
`lower(trim(name))` semantics within an age group. These two normalization
contracts are intentionally different and must not be conflated.

**Rationale**: The player database uniqueness constraint is exact and can be
bypassed by normalized variants; team services already define the team-name
comparison behavior that the quality rule must explain.

## Decision: Domain-service remediation adapters, not direct join writes

**Decision**: Keep remediation commands allowlisted and route every supported
mutation through a domain service transaction:

- Normalize roster order through a TeamService operation that validates the
  current team version and roster invariants, then produces the existing
  `roster.reordered` audit action.
- Remove one inactive player membership through a TeamService operation that
  checks the exact current membership, active-player roster bounds, and team
  version, then produces `roster.removed`.
- Remove one inactive Assistant Coach assignment through a CoachService
  removal-only operation that validates the inactive Assistant Coach, exact
  assignment, and user version, then produces
  `coach.team_assignments_updated`.

The service operations own the transaction, OCC check, validation, rollback,
and one audit-event staging behavior. The Data Quality route passes a typed
command and does not mutate `TeamPlayer` or `TeamCoach` directly.

The sole Head Coach integrity rule is review-only. No Head Coach assignment
removal command exists, even when the Head Coach is inactive or missing a team.

**Rationale**:

- Existing `TeamService`, `CoachService`, `check_and_increment_version`, and
  `BusinessAuditService` are the repository’s established business boundaries.
- A targeted removal-only CoachService path is required because the current
  normal full-assignment endpoint rejects inactive coaches; extending that
  domain service preserves the business rule without creating a Data Quality
  mutation layer.
- Audit records are staged in the caller’s transaction, so rollback can remove
  both the domain change and its event.

**Alternatives considered**:

- Direct SQL deletes would bypass domain validation, OCC, and audit behavior.
- A generic patch endpoint would expose arbitrary mutation capability.
- Automatic Head Coach reassignment would make a subjective academy decision.

## Decision: One bounded read contract and one typed remediation contract

**Decision**: Add a Head Coach-only `GET /api/v1/data-quality` endpoint with
`page`, `page_size`, `severity`, `domain`, and `rule_id` query filters. The
response includes the bounded page, pagination metadata, and the unfiltered
current summary. Add a Head Coach-only
`POST /api/v1/data-quality/remediations` endpoint with a discriminated,
allowlisted action request.

Use the existing page-size convention: default 20 and maximum 100. Invalid
filters and page values use FastAPI/Pydantic validation; stale or no-longer-
current remediation targets use the repository’s conflict response pattern.

**Rationale**:

- One read contract lets the frontend keep global counts while filtering the
  visible page.
- Typed action variants make arbitrary entity editing impossible at the API
  boundary.
- The endpoints fit the existing `/api/v1` route registration and
  `require_role(UserRole.HEAD_COACH)` pattern.

## Decision: Preserve Head Coach and calendar domain distinctions

**Decision**: Evaluate the academy’s sole Head Coach invariant separately from
`coach.inactive_assigned`. A healthy academy has exactly one active Head Coach
assigned to every current team. A broken invariant yields one Critical
`coach.sole_head_coach_integrity` finding with manual review only. Inactive
Assistant Coach assignments remain Warning findings and are the only inactive
coach assignments eligible for direct removal.

For Calendar, implement only recurrence end-before-start and stale occurrence
exception checks from the clarified catalogue. Do not flag empty scopes because
the current projection treats an empty scope collection as All Academy. Reuse
`calendar_recurrence.py` and existing CalendarService confirmation-aware
exception behavior.

**Rationale**: These distinctions are explicit product decisions and reflect
the current data model and service semantics. Repeating database-protected
constraints would produce noise and false positives.

## Decision: Reuse Head Coach UI, state, and accessibility conventions

**Decision**: Add a `data-quality` frontend feature with a page, typed API
client, hook, filters, summary, finding list, states, and remediation dialog.
Insert the sidebar item immediately after Audit Log and wrap the route in the
existing `HeadCoachRoute`. Reuse `Pagination`, `EmptyState`, existing audit
loading/error patterns, `ModalDialog`, status announcements, focus handling,
and `apiClient` abort/refresh behavior.

Navigate-to-Fix targets the existing `/players`, `/teams`, `/coaches`, or
`/calendar` workflows; no new deep-link selection contract is introduced.

The page uses `PRODUCT.md` and `DESIGN.md` conventions: cool canvas, white
surface, restrained Academy Teal, boundary lines, text severity labels, 44px-
class controls, visible focus, no color-only meaning, and no horizontal
overflow at 320px.

**Alternatives considered**:

- A separate administration shell would conflict with the existing clubhouse
  navigation and role-protection patterns.
- A generic database table/editor would violate the product intent and the
  remediation safety requirements.

## Decision: Automated verification is the performance and usability evidence

**Decision**: Verify bounded pagination, deterministic serialization/order,
efficient query behavior, N+1 avoidance, and realistic seeded scan behavior in
automated backend tests. Treat scan duration as a regression signal. Verify
responsive and accessibility behavior with frontend tests and Playwright at
the supported viewport sizes. Do not add a formal usability study, fixed task-
completion percentage, hard production latency SLA, or dedicated load-testing
infrastructure.

**Rationale**: This matches the clarified success criteria and the constitution’s
mandatory unit, integration where specified, and E2E discipline while keeping
the implementation phase objectively verifiable.

## Resolved planning unknowns

| Planning question | Resolution |
| --- | --- |
| Persist findings or scan history? | No; evaluate current state on demand. |
| Add database tables or migrations? | No initial schema change. |
| Which roles can read or remediate? | Authenticated Head Coaches only; existing 403 behavior for others. |
| What is directly removable? | Roster order, one inactive player membership when valid, one inactive Assistant Coach assignment. |
| Can a Head Coach assignment be removed? | No; sole Head Coach integrity is Critical/manual-review-only. |
| How are calendar scopes handled? | Preserve current empty-scope-as-All-Academy semantics; no empty-scope rule. |
| What is the performance target? | Boundedness and automated query/regression evidence; latency is a regression signal, not an SLA. |
