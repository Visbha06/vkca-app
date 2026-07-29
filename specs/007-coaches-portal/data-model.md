# Data Model: Coaches Portal

**Feature**: 007-coaches-portal
**Date**: 2026-07-28

## New Entities

### TeamCoach

Many-to-many join table linking teams to coach users.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `team_id` | `UUID` | PK, FK → `teams.id` | Team reference |
| `user_id` | `UUID` | PK, FK → `users.id` | Coach user reference |
| `created_at` | `timestamp(tz)` | NOT NULL, server default `now()` | From TimestampMixin |
| `updated_at` | `timestamp(tz)` | NOT NULL, server default `now()`, on update `now()` | From TimestampMixin |
| `version_number` | `integer` | NOT NULL, default 1 | From VersionMixin |

**Unique constraint**: `(team_id, user_id)` — prevents duplicate coach-team assignments.

**Table name**: `team_coaches`

**Indexes**: Implicit index on the composite primary key. No additional indexes needed at academy scale.

**Lifecycle**: Rows are created when a coach is assigned to a team (via Add Coach or Edit Assignments). Rows are deleted when assignments are removed. No soft-delete — the complete desired assignment set replaces the previous set atomically.

## Modified / Extended Entities

### User (Coach Role Subset)

No schema changes to the `users` table. The existing `role` column with `'head coach'` and `'assistant coach'` values already supports coach identification. The existing `is_active` and `version_number` columns are reused for coach status management and OCC.

**Coach-specific query filters**:

- `role IN ('head coach', 'assistant coach')` — excludes player accounts from coach listings
- `is_active = true/false` — status filtering
- `ORDER BY CASE role WHEN 'head coach' THEN 0 ELSE 1 END, last_name ASC, first_name ASC, id ASC` — stable ordering

**New endpoint impact on User entity**:

- `POST /users/{id}/reactivate` — sets `is_active = true`, increments `version_number`
- `POST /users/{id}/disable` (existing) — already sets `is_active = false` and revokes sessions; must now do both atomically per FR-040

### AuthSession (Existing)

No changes. The existing `revoke_user_sessions` method in `AuthService` is reused for deactivation. The `AuthSession` model's `revoked_at` and `revocation_reason` columns capture the deactivation context.

### Team (Existing)

No changes to the `teams` table. `TeamCoach` references `teams.id` via foreign key. Existing team endpoints (`GET /teams`, `GET /teams/{id}`) are reused by the Team Assignments modal to populate available-teams lists.

## Entity Relationships

```
┌──────────┐         ┌──────────────┐         ┌──────────┐
│   User   │────────<│  TeamCoach   │>────────│   Team   │
│ (coach)  │  user_id│              │team_id  │          │
└──────────┘         └──────────────┘         └──────────┘
       │                                             │
       │ 1:N (sessions)                              │ 1:N (roster)
       ▼                                             ▼
┌──────────────┐                           ┌──────────────┐
│ AuthSession  │                           │  TeamPlayer  │
└──────────────┘                           └──────────────┘
```

- A coach (User with role 'head coach' or 'assistant coach') can be assigned to 0..N teams through `TeamCoach`.
- A Team can have 0..N coaches through `TeamCoach`.
- Deactivation preserves `TeamCoach` rows — the relationship survives status changes.
- The existing `TeamPlayer` relationship (team ↔ player) is independent and unaffected.

## State Transitions

### Coach Account Status

```
                    ┌─────────┐
          create    │ ACTIVE  │    reactivate
        ──────────▶│         │◀────────────
                   └────┬─────┘
                        │ deactivate
                        ▼
                   ┌─────────┐
                   │INACTIVE │
                   └─────────┘
```

- **ACTIVE → INACTIVE** (deactivate): Sets `is_active = false`, revokes all `AuthSession` rows (sets `revoked_at`), increments `version_number`. Atomic per FR-040.
- **INACTIVE → ACTIVE** (reactivate): Sets `is_active = true`, increments `version_number`. Does NOT restore sessions (FR-041).
- Self-deactivation rejected both frontend and backend (FR-042).

### Team Assignments

Assignment updates replace the complete set of `TeamCoach` rows for a coach:

1. Delete all existing `TeamCoach` rows for `user_id`.
2. Insert new `TeamCoach` rows for each `team_id` in the submitted set.
3. Increment the coach user's `version_number` (FR-036).

The operation is atomic — if any step fails, the transaction rolls back (FR-036, SC-008). OCC via `version_number` prevents stale writes (FR-038).

## Validation Rules

| Rule | Source | Enforcement |
|------|--------|-------------|
| Email unique (case-insensitive normalized) | FR-030 | `UserService.create_user` with `UserAlreadyExistsError` |
| Role fixed to "assistant coach" on creation | FR-025 | Backend ignores/sets role in request |
| Temporary password satisfies policy | FR-026 | `PasswordService.validate_password_policy` |
| Password never returned outside creation response | FR-026, FR-028 | Frontend does not persist; backend only returns in `POST /coaches` 201 |
| Team IDs must reference existing teams | FR-029 | Foreign key validation; backend checks all IDs before insert |
| Duplicate team assignments rejected | FR-032 | Unique constraint on `team_coaches(team_id, user_id)` |
| Active coach required for assignment edits | FR-033 | Backend checks `is_active` before processing assignment update |
| Current user cannot self-deactivate | FR-042 | Backend checks `user_id != current_user.id` |
| Stale `version_number` rejected (409) | FR-038 | `check_and_increment_version` from OCC module |
