# Data Model: Dynamic Role-Aware Dashboard

This feature adds durable Player account linkage and Match participant
semantics. The dashboard itself remains a read-time projection and has no
database table.

## Existing entities used by the projection

| Entity | Existing fields used | Relationship used by dashboard |
|---|---|---|
| `User` | `id`, names, `role`, `is_active`, `version_number` | Authenticated actor and role source; Player accounts link to `Player`. |
| `Player` | identity, `is_active`, `version_number` | Account-linked profile and active-player count source. |
| `Team` | `id`, `name`, `age_group`, `version_number` | Team scope, labels, and My Teams rows. |
| `TeamPlayer` | `team_id`, `player_id`, roster timestamps/order | Current Player membership and distinct roster counts. |
| `TeamCoach` | `team_id`, `user_id` | Assistant Coach scope and assigned coach display. |
| `CalendarEvent` and effective occurrence models | type, name, date/time, scope, recurrence/exception data | Upcoming Training and Upcoming Events; effective identity is preserved. |
| `Match` | date, format, venue, result, version | Next Match and role-scoped fixture relevance. |
| `BusinessAuditEvent` | immutable snapshots and registered action | Head Coach-only Recent Academy Activity. |
| `AuthSession` | user, token family, revocation fields | Inactive linked Player session revocation. |

## Player account association

### Durable fields

Add to `players`:

| Field | Type/constraint | Meaning |
|---|---|---|
| `user_id` | nullable PostgreSQL UUID FK to `users.id`, `ON DELETE SET NULL` | Explicit account associated with this profile. |
| unique index | unique on non-null `user_id` | One Player-role account can link to at most one Player profile. |

The nullable Player-side reference preserves existing account-less profiles.
The ORM relationship is one-to-one from `Player` to `User`; it must not infer
identity from names, email, date of birth, or metadata. General `PlayerResponse`
does not include account credentials or account details. Protected account
linking responses expose only the safe account snapshot required by the Head
Coach flow.

### Association invariants

1. A link target must exist and have `UserRole.PLAYER`.
2. The target User must not already be linked to a different Player.
3. The Player must exist and must not already be linked to a different User.
4. The mutation actor must be a Head Coach; Assistant Coaches and Players are
   rejected at the route dependency before service mutation.
5. Player `version_number` is required for link, unlink, and reassignment.
6. The database unique index remains authoritative for concurrent link races;
   its integrity error maps to the existing conflict response.
7. Every committed mutation stages exactly one matching Business Audit event.
8. A rejected, stale, unauthorized, integrity-failed, or rolled-back mutation
   leaves both association and Business Audit state unchanged.

### Association transitions

```text
No account
  ├─ link(target Player User, current Player version) ─> Linked(target)
  └─ link rejected if target/profile is already associated or stale

Linked(old account)
  ├─ unlink(current version) ─> No account
  ├─ reassign(expected old, target new, current version) ─> Linked(new account)
  └─ stale/mismatched old account ─> 409, unchanged
```

Reassignment is one domain mutation and one audit event, not an unlink event
plus a link event. A no-op reassignment to the same account is rejected as an
invalid correction rather than audited as a successful change.

## Player-profile activity and authentication state

`Player.is_active` remains the profile lifecycle field. When a linked profile
transitions from active to inactive:

1. the Player update and `AuthService.revoke_user_sessions` run in the same
   transaction;
2. every active `AuthSession` for the linked Player-role User receives the
   existing revocation timestamp/reason and version increment;
3. bearer authentication rejects the User because the linked profile is
   inactive, even if a stale token is presented;
4. login and refresh reject the account while the profile remains inactive;
5. reactivation removes the profile gate but does not restore revoked sessions;
   the User must establish a new session; and
6. independent User deactivation remains authoritative and is never
   auto-reversed by Player-profile reactivation.

This is an authentication/session invariant, not a dashboard response state.
The dashboard only needs to handle the existing 401/session-expiry behavior.

## Match participant model

### Durable fields

The final `matches` shape preserves existing match metadata and replaces the
opponent-only participant representation with:

| Field | Type/constraint | Meaning |
|---|---|---|
| `participant_type` | non-null string constrained to `external`/`internal` | Discriminator for the one allowed participant structure. |
| `home_team_id` | nullable UUID FK to `teams.id` | Academy home Team, or null when an external opponent is home. |
| `away_team_id` | nullable UUID FK to `teams.id` | Academy away Team, or null when an external opponent is away. |
| `external_opponent_name` | nullable string, max 200 | Nonblank outside opponent for external Matches only. |

`match_date`, `format`, `venue`, `result`, timestamps, and
`version_number` remain. The old `opponent_name` column is removed or renamed
as part of the final migration; no temporary legacy compatibility period is
needed because the repository contains no meaningful Match data.

### Participant invariants

The database check constraint and Pydantic discriminated union enforce the same
rules:

```text
external:
  external_opponent_name is nonblank
  exactly one of home_team_id / away_team_id is non-null

internal:
  external_opponent_name is null
  home_team_id and away_team_id are both non-null
  home_team_id != away_team_id
```

Every non-null Team FK points to an academy Team. The API response expands the
stored shape into a typed participant union:

```text
ExternalMatchParticipant {
  kind: "external"
  academy_team: TeamRef
  opponent_name: string
  academy_side: "home" | "away"
}

InternalMatchParticipant {
  kind: "internal"
  home_team: TeamRef
  away_team: TeamRef
}
```

No internal response includes an external opponent. No external response
includes both academy sides. Dashboard matching uses one OR predicate across
`home_team_id` and `away_team_id`, so a Match relevant through both sides is
returned once.

### Match indexes and concurrency

Add indexes supporting date-ordered role lookup, such as `(match_date,
home_team_id, id)` and `(match_date, away_team_id, id)`, or the equivalent
repository-approved index pair. Match updates carry `version_number`, use the
existing OCC helper, and return `409` without an audit event when stale.

Match creation/update remains backend/domain support only. No Match page, modal,
dashboard-created route, or frontend Match entry workflow is part of this
feature.

## Dashboard projection (non-persisted)

The service builds the following response-only structures at read time. These
are API contract types, not ORM entities or stored snapshots.

### Scope context

```text
DashboardScope {
  role: "head coach" | "assistant coach" | "player"
  team_ids: UUID[]              # derived server-side; not request input
  age_groups: AgeGroup[]        # derived from scoped Teams
  linked_player_id: UUID | null # only for Player role
}
```

Head Coaches use academy scope. Assistant Coaches use active `TeamCoach` rows.
Players use the explicit User-to-Player-to-TeamPlayer chain. An unlinked Player
has no team or age-group scope and receives only the typed unlinked state.

### Section state

Each independent section uses a discriminated state rather than ambiguous
nulls:

```text
ready   { status: "ready", data: T }
empty   { status: "empty", message: string }
unlinked { status: "unlinked", message: string }  # Player dashboard only
unavailable { status: "unavailable", message: string, retryable: boolean }
```

The API does not include client-selected scope values. Stable ordering and
limits are applied before serialization.

### Summary and panels

- `training`: nearest Practice effective occurrence in the current 45-day
  window, or explicit empty state.
- `next_match`: nearest Match with `match_date >= academy_today`, ordered by
  date then Match ID, or explicit empty state.
- `active_players`: academy count for Head Coach, distinct active Player count
  across Assistant Coach teams, or a Player team-label summary instead of an
  academy count.
- `upcoming_events`: at most five effective Calendar occurrences, filtered by
  role scope and deduplicated by `occurrence_id`; location/venue omitted.
- `recent_activity`: at most four Business Audit snapshots for Head Coaches
  only, ordered by `created_at DESC, id DESC`.
- `my_teams`: at most twelve deterministic Team rows for Assistant Coaches and
  linked Players, with active-player count and next relevant event; Player rows
  include permitted coach context.

## Migration 013 outline

Upgrade:

1. Add nullable `players.user_id`, FK, and unique non-null index.
2. Add Match participant columns and temporary validation-safe nullability.
3. Assert the repository's no-meaningful-Match-data assumption before removing
   the opponent-only column; do not silently guess participant sides.
4. Apply final Match checks, non-null discriminator, participant indexes, and
   final ORM-compatible constraints.
5. Drop temporary defaults and legacy participant column state.

Downgrade reverses the indexes, checks, FKs, Player association, and Match
participant columns. The old opponent-only shape cannot faithfully represent a
new internal Match; as with the repository's stated no-meaningful-data
assumption, downgrade is structurally reversible but cannot preserve internal
participant semantics in the legacy column.
