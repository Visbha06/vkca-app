# Research: Coaches Portal

**Feature**: 007-coaches-portal
**Date**: 2026-07-28

## Decision Log

### 1. Temporary Password Generation Strategy

**Decision**: Use `secrets.token_urlsafe(16)` from the Python standard library to generate a 16-byte cryptographically secure random token, then prepend a fixed prefix character (e.g., uppercase letter and digit) to guarantee password policy compliance, producing a ~24-character plaintext password.

**Rationale**: The existing `PasswordService.validate_password_policy` requires an uppercase letter, lowercase letter, digit, and special character. `token_urlsafe` produces URL-safe base64 (A-Z, a-z, 0-9, `-`, `_`), which satisfies all categories except the special-character requirement (since `-` and `_` count as special chars). The generated plaintext is hashed via `PasswordService.hash_password` before storage, matching the existing flow in `UserService.create_user`. The `secrets` module is stdlib — no new dependency.

**Alternatives considered**:
- `uuid.uuid4().hex` — lacks special characters; would require deterministic post-processing.
- Third-party password-generation library — unnecessary dependency for one-off generation (Constitution IV).

### 2. TeamCoach Join Table Model

**Decision**: Model `TeamCoach` after the existing `TeamPlayer` pattern — composite primary key (`team_id`, `user_id`), `TimestampMixin`, `VersionMixin`, and a unique constraint on the pair. Use `ForeignKey("teams.id")` and `ForeignKey("users.id")`.

**Rationale**: `TeamPlayer` is the closest existing many-to-many join model in the codebase. Following its structure ensures consistency. The `VersionMixin` on `TeamCoach` supports individual row-level versioning if needed, though the primary OCC mechanism for assignment updates is the coach user's `version_number` per the spec (FR-036). The unique constraint on `(team_id, user_id)` prevents duplicate assignments (FR-032).

**Alternatives considered**:
- Association table (no model class) — prevents adding timestamps and per-row metadata.
- Reusing `TeamPlayer` — semantically wrong (coaches are not players).

### 3. Coach Creation vs. User Creation

**Decision**: Create a dedicated `POST /coaches` endpoint rather than reusing `POST /users`. The coach creation endpoint automatically sets `role = "assistant coach"`, generates a temporary password server-side, optionally creates `team_coaches` rows atomically, and returns the temporary password in the response.

**Rationale**: `POST /users` requires a client-submitted password (`UserCreate.password` is a required field) and a freely-selectable `role`. The coach-creation flow differs: the password is server-generated, the role is fixed, and team assignments are optionally bundled. Extending `POST /users` with optional password and conditional role restrictions would complicate the existing schema and authorization logic. A dedicated endpoint provides clear separation of concerns.

**Alternatives considered**:
- Extend `POST /users` with optional fields — would require making `password` optional in `UserCreate`, checking caller role, and adding conditional validation; increases schema complexity.
- Two-step creation (user first, then assign teams) — violates the atomicity requirement (FR-029).

### 4. Reactivation Endpoint

**Decision**: Add `POST /users/{user_id}/reactivate` to the existing `users.py` routes module. The endpoint sets `is_active = true`, increments `version_number`, and explicitly does NOT restore previously revoked sessions.

**Rationale**: The existing `disable_user` endpoint already handles deactivation with session revocation. A paired reactivation endpoint follows REST conventions and keeps user-lifecycle operations in one route file. Sessions are not restored because they were intentionally revoked — a fresh login is required (FR-041).

**Alternatives considered**:
- `PATCH /users/{user_id}` — would require a more complex partial-update schema; overkill for a boolean toggle.
- Include in coach routes — separates user-lifecycle concerns from coach-specific domain logic.

### 5. Coach-List Query Strategy

**Decision**: Use a single SQLAlchemy query with `outerjoin` to `team_coaches` and `Team` to eagerly load team assignments, with server-side `WHERE` filtering on `is_active` and `role IN ('head coach', 'assistant coach')`, `ORDER BY` applying the spec's priority ordering, and `LIMIT`/`OFFSET` for pagination.

**Rationale**: The ordering requirement (Head Coach first, then last name, first name, user ID) is straightforward as a SQL `ORDER BY` expression. Eager-loading team assignments avoids N+1 queries for the card grid. Server-side filtering and pagination keep response sizes bounded — the academy's scale (tens of coaches) means no performance risk.

**Alternatives considered**:
- Two queries (users then teams) — simpler per-query logic but N+1 for team names.
- In-memory filtering/sorting — unacceptable for server-side pagination contract.

### 6. Frontend Feature Module Pattern

**Decision**: Create `frontend/src/features/coaches/` following the structure established by `features/players/` and `features/teams/` — with `api/`, `components/`, `hooks/`, `pages/`, `types/`, and `index.ts` barrel export.

**Rationale**: The existing player and team features use this pattern, and Constitution I (Clean Code) calls for consistency. Coach-specific components (`CoachCard`, `CoachDetailsModal`, `CoachStatusFilter`) adapt the existing card, modal, and form patterns rather than creating new abstractions. The `CoachesPage` in `pages/` delegates to the feature module page, matching how `PlayersPage` and `TeamsPage` delegate.

**Alternatives considered**:
- Colocate all coach components in a flat directory — less discoverable for a multi-component feature.
- Put everything in `pages/CoachesPage.tsx` — violates single-responsibility principle.

### 7. Role-Based Navigation Hiding

**Decision**: Use the existing `useAuth()` hook in `AppLayout` to conditionally filter the `navigationItems` array, removing the Coaches Portal entry when `user.role === 'player'`.

**Rationale**: The `useAuth` hook already provides the current user's role. Filtering the static `navigationItems` array is a minimal change to `AppLayout.tsx` — no new sidebar abstraction needed. Player-role users also cannot access the route because the backend returns 403, but hiding the nav item prevents confusion (FR-002).

**Alternatives considered**:
- Route-level guard only (no nav hiding) — would let players see a nav item they can't use.
- Per-item `roles` metadata — adds complexity without benefit for two roles.

### 8. ForbiddenPage Component

**Decision**: Create a shared `ForbiddenPage` component at `frontend/src/pages/ForbiddenPage.tsx` that displays a 403 message following the "Disciplined Clubhouse" design language. The CoachesPage route wrapper checks the user's role and renders `ForbiddenPage` for Player-role users.

**Rationale**: The spec requires a "dedicated 403 Forbidden page" that does not redirect silently (FR-003). A shared component avoids duplication if future features need 403 pages. The check can happen in the route component itself (since the page is already protected by `<ProtectedRoute>` which only checks authentication, not authorization).

**Alternatives considered**:
- Inline 403 in CoachesPage — not reusable.
- Route-level role guard component — adds a new abstraction for a single use case.
