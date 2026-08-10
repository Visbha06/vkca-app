# Phase 0 Research: Dynamic Role-Aware Dashboard

## Repository baseline

Decision: Extend the existing two-part web application in place: the async
FastAPI/SQLAlchemy backend under `backend/src` and the React/TypeScript
frontend under `frontend/src`.

Rationale: The repository already provides the authentication/session
middleware, role dependency, Calendar recurrence projection, TeamCoach and
TeamPlayer joins, Match routes, Business Audit registry, OCC helpers, and the
current static dashboard. Reusing those seams satisfies the feature's
no-parallel-abstraction requirement and avoids introducing a second identity,
calendar, or audit system.

Alternatives considered: A new dashboard-specific persistence table, cached
summary job, or separate Match-management module. These are explicitly outside
the feature and would violate the read-time projection and Match UI scope.

## Dashboard endpoint and projection

Decision: Add an authenticated `GET /api/v1/dashboard` capability backed by a
read-time `DashboardService`. The response contains typed summary slots,
bounded Upcoming Events, and one role-specific contextual panel. Each major
section carries an explicit `ready`, `empty`, `unlinked`, or `unavailable`
state so the frontend never substitutes sample data.

Rationale: The server can derive scope from the database-loaded authenticated
`User`, while one stable response gives the frontend a strongly typed boundary.
Section state makes isolated failures observable without ambiguous nulls and
allows populated sections to remain visible during retries.

Alternatives considered: Client-supplied user/team IDs, multiple client-side
queries that reconstruct scope, persisted dashboard snapshots, and background
aggregation. These would weaken authorization or add infrastructure rejected by
FR-005 through FR-008.

## Role scope and Assistant Coach actions

Decision: Resolve scope server-side as follows:

- Head Coach: academy-wide active Teams, Players, valid Matches, Calendar
  occurrences, and bounded Business Audit activity.
- Assistant Coach: active `TeamCoach` assignments plus explicitly
  `all_academy` Calendar occurrences. Existing repository permissions allow
  player/team/calendar/match mutations, but the frontend exposes only existing
  usable workflows: Add player and Schedule event. No Match quick action is
  shown because the current `/teams` destination is not a Match entry flow.
- Player: `User -> Player.user_id -> TeamPlayer -> Team`, with active profile
  and current membership checks. No profile produces the typed unlinked state.

Rationale: The current routes use `require_role` and database-loaded role
  checks. Existing Assistant Coach permissions are not expanded; dashboard
  visibility mirrors actual route capability and available UI workflow.

Alternatives considered: Showing the old Create match action, inventing a new
route, or adding Assistant Coach permissions solely for dashboard symmetry.

## Match participant representation

Decision: Replace the opponent-only persistence shape with one discriminated
participant structure represented by:

- `participant_type`: `external` or `internal`;
- `home_team_id`: nullable FK to `teams.id`;
- `away_team_id`: nullable FK to `teams.id`; and
- `external_opponent_name`: nullable, nonblank for external Matches only.

External Matches set exactly one of `home_team_id` or `away_team_id` to the
academy Team and use the missing side for the external opponent. Internal
Matches set both team IDs to different academy Teams and leave the external
opponent null. A database check constraint and Pydantic model validator enforce
the same invariant before persistence.

Rationale: The shape preserves home/away semantics without a second Match-to-
Team relationship, supports one-sided external fixtures and two-sided internal
fixtures, and gives dashboard queries direct indexed team columns.

Alternatives considered: Keeping a required free-text opponent, adding a
separate MatchParticipant table for this release, or storing both an academy
team ID and home/away IDs. Those options either permit ambiguity or duplicate
the relationship needed by future performance workflows.

## Player account linking

Decision: Add nullable unique `players.user_id` with a foreign key to `users.id`.
Expose a Head Coach-only eligible Player-account lookup and explicit link,
unlink, and reassignment mutations from the existing Player Directory flow.
Keep account details out of the general Player response; return safe account
snapshots only from the protected linking capability.

Rationale: The Player-side nullable reference matches the specification,
preserves account-less profiles, and prevents normal Player reads from leaking
another account's details. Player version checks plus the database unique index
cover stale edits and concurrent attempts.

Alternatives considered: Name/email matching, Player self-claiming, a new
user-management page, or embedding all User fields in `PlayerResponse`.

## Business Audit actions and transaction boundary

Decision: Extend `AuditActionType` and `ACTION_REGISTRY` only when an existing
action is not semantically accurate. The explicit fallback actions are
`player.account_linked`, `player.account_unlinked`, and
`player.account_reassigned`; each successful external mutation stages exactly
one Business Audit event through `BusinessAuditService.record` before the
outer transaction commits.

Rationale: The registry already enforces target types and metadata allowlists,
and `record` intentionally does not commit independently. Rejected,
unauthorized, stale, integrity-failed, or rolled-back mutations therefore
produce no successful event.

Alternatives considered: Reusing `player.updated` for all associations,
emitting separate unlink/link events for reassignment, or writing audit rows
from a lower-level helper. These would misdescribe mutations or violate the
exactly-one event requirement.

## Inactive linked Player authentication

Decision: Treat linked Player activity as an authentication/session invariant.
When a linked Player transitions to inactive, revoke every active `AuthSession`
for the linked Player-role User in the same transaction. The access-token
dependency, login, and refresh paths all reject a Player account whose linked
profile is inactive. Profile reactivation removes this gate but never restores
revoked sessions and never auto-reactivates a User independently disabled by a
Head Coach.

Rationale: The repository already rejects inactive Users in bearer, login, and
refresh paths and uses `AuthService.revoke_user_sessions` for deactivation.
Checking the linked profile as an additional gate gives the same security
effect without losing the distinction between profile status and an
independent account disablement.

Alternatives considered: Adding an inactive dashboard state, relying only on
frontend logout, or automatically toggling `User.is_active` back to true on
Player reactivation. Each would either permit stale sessions, expose a state
the specification forbids, or accidentally restore an independently disabled
account.

## Calendar and bounded projection

Decision: Reuse `CalendarService`'s effective occurrence algorithm and its
`MAX_CALENDAR_RANGE_DATES = 45` bound for a dashboard window beginning on the
academy-local current date. Add a scoped projection/query path that filters
all-academy or relevant age-group scopes while preserving moved, deleted,
replaced, recurring, daylight-saving, and stable occurrence identities.

Rationale: The existing service already owns `America/Los_Angeles` date
handling, recurrence expansion, exception semantics, and deterministic sorting.
The 45-day limit keeps dashboard reads bounded and avoids a second recurrence
engine. If no eligible event exists in that bounded operational window, the
response uses the explicit empty state.

Alternatives considered: Expanding recurrence in the frontend, querying an
unbounded future, or changing the calendar range limit globally. Those choices
would duplicate semantics, risk unbounded work, or alter unrelated Calendar
behavior.

## API-to-TypeScript contract generation

Decision: Add a repeatable OpenAPI export/generation/check path for the new
dashboard, Match participant, and Player account-linking contracts, following
the repository's existing `openapi-typescript` Data Quality workflow. Generated
types are the frontend source of truth; feature-local UI state types may wrap
them but may not duplicate response shapes.

Rationale: The repository has `openapi-typescript` installed and already proves
the export/check pattern for Data Quality, while the rest of the frontend still
uses hand-maintained types. Extending the established pattern satisfies the
strongly typed boundary and gives CI a repeatable drift check.

Alternatives considered: Hand-maintained parallel dashboard/match/linking
interfaces or generating types from an ad hoc frontend fixture.

## Migration and test baseline

Decision: Add a new reversible Alembic revision `013` after the repository's
current `012_create_business_audit_events` head. Validate upgrade/downgrade on
the existing PostgreSQL test setup and add the required quickstart at
`backend/tests/integration/quickstart/test_011_quickstart_flow.py`.

Rationale: The specification's reference to revision `012` is the baseline
revision in this repository; it is not the new migration number. Existing
integration fixtures use rollback-only transactions, ASGI HTTP clients, and
query counters that can be reused for role isolation, audit cardinality,
participant invariants, and no-N+1 checks.

Alternatives considered: Editing an existing migration, adding manual schema
edits, or creating a second migration branch.
