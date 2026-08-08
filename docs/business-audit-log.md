# Business Audit Log

The Business Audit Log records successful academy administration separately
from authentication and security monitoring. It covers coach, player, team,
roster, and calendar mutations and gives Head Coaches a filterable history plus
the four newest events on the dashboard.

## Business and security boundary

Business events are stored in `business_audit_events` and exposed under
`/api/v1/audit-log`. Login, logout, token, session, authorization-denial, and
other security events remain in `auth_audit_log` and the existing
`/api/v1/auth/audit-log` API. Neither service writes to, queries, or presents
the other service's records.

Only authenticated Head Coaches can read business audit events or actor
options. Assistant Coaches and Players receive the standard `403 Not
authorized` response. Coaches may still create events when they perform an
existing mutation their role permits; read access remains Head Coach-only.

Match, performance, and player-statistics activity is not recorded in this
release.

## Recorded actions

The initial action catalogue is:

| Category | Actions |
|---|---|
| Coach | `coach.created`, `coach.activated`, `coach.deactivated`, `coach.team_assignments_updated` |
| Player | `player.created`, `player.updated` |
| Team | `team.created`, `team.updated` |
| Roster | `roster.added`, `roster.removed`, `roster.reordered` |
| Calendar | `calendar.standalone_created`, `calendar.standalone_updated`, `calendar.standalone_deleted`, `calendar.series_created`, `calendar.series_updated`, `calendar.series_deleted`, `calendar.occurrence_updated`, `calendar.occurrence_moved`, `calendar.occurrence_deleted` |

Each externally initiated mutation creates exactly one event. Composite team,
roster, coach-assignment, and recurring-calendar operations describe the whole
operation in one record instead of emitting lower-level row events.

## Transaction contract

The domain service owns the transaction. It validates and flushes the complete
domain change, snapshots the actor and target, stages and flushes one business
event, and then commits both together. The audit writer accepts the caller's
SQLAlchemy session and never commits independently. A domain error, stale
version, authorization failure, or audit persistence error rolls back both the
domain change and its event.

Business events are append-only. The application exposes no update or delete
method or route for them.

## Safe metadata and summaries

Summaries are built from registered templates and stored actor/target labels.
Metadata is retained only when its key is allowlisted for the action, and
values are reduced to bounded JSON-safe scalars or scalar lists.

The allowlisted fields are:

| Area | Fields |
|---|---|
| Coach | `assigned_team_ids`, `assigned_team_count`, `changed_fields`, `added_team_ids`, `removed_team_ids`, `added_count`, `removed_count` |
| Player | `changed_fields` |
| Team and roster | `age_group`, `roster_count`, `roster_replaced`, `changed_fields`, `added_player_ids`, `removed_player_ids`, `reordered_player_ids`, `player_id`, `new_roster_position`, `prior_roster_position`, `affected_player_ids`, `affected_count`, `changed_positions` |
| Calendar | `event_type`, `scope`, `schedule_label`, `frequency`, `exception_count`, `original_date`, `replacement_date`, `changed_fields` |

Passwords, password hashes, access or refresh tokens, CSRF values, secrets,
environment values, raw requests or responses, unrestricted object snapshots,
stack traces, and raw exception messages are never permitted.

## Historical snapshots and identifiers

Every event stores the actor display name and role at the time of the action,
plus a target label. Actor and polymorphic target UUIDs are historical values
without foreign keys. Renaming, deactivating, or deleting a current actor or
target therefore does not rewrite or cascade-delete its audit history. Feed
rendering uses stored snapshots and does not require linked-record lookups.

`created_at` is a timezone-aware, creation-only database timestamp. The UI
formats stored ISO timestamps in `America/Los_Angeles`, including daylight
saving transitions.

## API surface

| Method | Path | Purpose and bounds |
|---|---|---|
| `GET` | `/api/v1/audit-log` | Newest-first page; default 20 and maximum 100 events |
| `GET` | `/api/v1/audit-log/recent?limit=4` | Latest one to four events for the dashboard |
| `GET` | `/api/v1/audit-log/actors` | At most 100 distinct, alphabetized historical actor snapshots |

The full list supports actor UUID, category, action, entity type, target UUID,
and inclusive academy-local start/end date filters. Filters combine with AND.
Date ranges may span at most 366 inclusive dates. Ordering is stable by
`created_at DESC, id DESC`.

## User interface

Head Coaches see **Audit Log** immediately below Calendar in the application
navigation. The `/audit-log` page provides labeled filters, result
announcements, newest-first events, safe native disclosures, and server-side
pagination. It distinguishes loading, initial empty history, filtered no
results, forbidden access, and retryable errors. Controls wrap without page
overflow from 320 px through desktop widths and remain keyboard operable.

The Head Coach dashboard's **Recent academy activity** section uses the same
retrieval service, displays at most four events, and links to the full log. Its
empty or retryable error state does not block the rest of the dashboard.
Assistant Coaches and Players neither render the section nor request the
recent endpoint.

## Retention and operations

Business audit history is currently retained indefinitely. There is no
automatic cleanup, export, restore, or undo workflow. A future retention policy
must be explicitly approved, documented, and implemented with preservation and
compliance requirements before any deletion mechanism is introduced.

No new environment variables or runtime dependencies are required. Apply the
normal Alembic migration chain through revision `012` before deploying the
feature. The executable validation flow and commands are documented in
`specs/009-business-audit-log/quickstart.md`.
