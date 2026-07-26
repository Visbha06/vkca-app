# Research: Teams Interface

**Feature**: 006-teams-interface | **Date**: 2026-07-25

## 1. Player Search Endpoint

**Decision**: No backend changes needed. The existing `GET /api/v1/players?search=` already matches first name, last name, and full name via `ilike` patterns.

**Rationale**: `PlayerService.list_players()` already applies `or_(Player.first_name.ilike(...), Player.last_name.ilike(...), func.concat(Player.first_name, " ", Player.last_name).ilike(...))`. The spec requirement (FR-017) is already satisfied.

**Alternatives considered**: Adding a separate search endpoint — unnecessary given existing pattern.

## 2. AgeGroup Enum

**Decision**: Add `class AgeGroup(StrEnum)` to `src/enums.py` with values `J = "J"`, `U11 = "U11"`, `U13 = "U13"`, `U15 = "U15"`. Constrain `Team.age_group` to `String(50)` with a server-side check constraint.

**Rationale**: Follows existing pattern (`UserRole`, `PlayerType`, etc. are all `StrEnum` in `enums.py`). SQLAlchemy `String` column with application-level validation via Pydantic schema is the established approach. A database check constraint (`age_group IN ('J','U11','U13','U15')`) adds defense in depth.

**Human-readable labels**: Map in frontend only — `J → "Juniors"`, `U11 → "U11"`, `U13 → "U13"`, `U15 → "U15"`. Backend stores and returns raw enum values.

**Alternatives considered**: PostgreSQL native ENUM type — rejected because the project uses check constraints and String columns consistently; native ENUMs complicate migrations and testing.

## 3. Roster Order Column

**Decision**: Add `roster_order: Mapped[int]` column to `TeamPlayer` model, non-nullable, default 0. Order by `roster_order ASC` in all roster queries. Index on `(team_id, roster_order)` for performance.

**Rationale**: The spec requires stable, explicit ordering. An integer column is the simplest approach. Default 0 ensures existing rows get a value; application code always provides explicit orders. The composite index supports the common query pattern (roster for one team, ordered).

**Alternatives considered**:
- Array column on Team (ordered player IDs) — violates normalization, makes per-player queries complex.
- `position` as a float to support "insert between" without renumbering — overengineered; full roster replacement makes renumbering trivial.

## 4. Atomic Team + Roster Creation

**Decision**: Single `POST /api/v1/teams` endpoint. Body: `{name, age_group, player_ids: [UUID, ...]}`. Transaction flow:
1. Validate all `player_ids` exist and are active (single query)
2. Validate 7 ≤ len(player_ids) ≤ 15, no duplicates
3. Validate name uniqueness (case-insensitive, whitespace-normalized) within age group
4. Create `Team` row, flush to get ID
5. Bulk insert `TeamPlayer` rows with `roster_order = index + 1`
6. Commit

Rollback on any failure.

**Rationale**: Single HTTP round-trip keeps the frontend simple. Full server-side validation before any writes ensures atomicity. `session.flush()` after team insert gives us the team ID for roster rows without committing.

**Alternatives considered**: Two-phase creation (create team, then add players) — rejected because it complicates the frontend and breaks atomicity guarantees.

## 5. Atomic Team + Roster Update

**Decision**: Single `PUT /api/v1/teams/{team_id}` endpoint. Body: `{name, age_group, player_ids: [UUID, ...], version_number}`. Transaction flow:
1. Fetch team, check `version_number` via `check_and_increment_version()`
2. Validate all `player_ids` exist and are active
3. Validate 7 ≤ len(player_ids) ≤ 15, no duplicates
4. Validate name uniqueness (excluding current team) within age group
5. Update team `name` and `age_group`
6. Delete all existing `TeamPlayer` rows for this team
7. Bulk insert new `TeamPlayer` rows with `roster_order = index + 1`
8. Commit

Rollback on any failure (including stale version → HTTP 409).

**Rationale**: Full roster replacement is cleaner than diffing (add/remove individual rows). The delete-all + re-insert pattern is atomic within the transaction and avoids complex ordering logic for partial updates.

**Alternatives considered**: Separate endpoints for details and roster — rejected per spec clarification (single atomic transaction required).

## 6. Team Name Uniqueness

**Decision**: Application-level validation in `TeamService`. Before create/update, query: `SELECT id FROM teams WHERE LOWER(TRIM(name)) = LOWER(TRIM(:name)) AND age_group = :age_group`. For updates, exclude the current team ID.

**Rationale**: PostgreSQL functional unique indexes on `(LOWER(TRIM(name)), age_group)` are possible but complex via Alembic and ORM. Application-level checks with a simple select query are sufficient at academy scale and easier to test.

**Alternatives considered**: Database unique constraint — viable but adds migration complexity; can be added later if needed.

## 7. Server-Side Pagination

**Decision**: Follow the exact pattern from `PlayerService.list_players()`:
- Query params: `page` (default 1, ≥1), `page_size` (default 12, 1–100)
- Response: `{teams: [...], page, page_size, total_teams, total_pages}`
- Default ordering: `Team.name ASC, Team.age_group ASC, Team.id ASC`
- Count query + offset/limit query pattern

**Rationale**: Proven pattern from the Players feature. Reusing the same response shape (`PaginatedTeamResponse`) keeps the API consistent.

**Alternatives considered**: Cursor-based pagination — overengineered for academy scale (tens of teams).

## 8. Roster Retrieval Endpoint

**Decision**: `GET /api/v1/teams/{team_id}/players` returns team members with `player_id`, `first_name`, `last_name`, `is_active`, `roster_order`. Joined query: `TeamPlayer JOIN Player ON player_id ORDER BY roster_order ASC`. Include inactive players (returned with `is_active: false`).

**Rationale**: Separate endpoint keeps the team list response lightweight (no nested roster). Joining with Player avoids N+1 queries. Including inactive players ensures the roster display is historically accurate.

**Alternatives considered**: Embedding roster in the team detail response — rejected because roster can be large (15 players) and is not always needed (team list page doesn't need it).

## 9. Optimistic Concurrency

**Decision**: Use existing `occ.check_and_increment_version()` helper. Team model already inherits `VersionMixin`. `PUT /api/v1/teams/{team_id}` requires `version_number` in body. Stale version → `StaleVersionError` → HTTP 409.

**Rationale**: Consistent with existing player update pattern (`PUT /api/v1/players/{player_id}`). Reuses proven infrastructure.

## 10. Frontend Team Cards

**Decision**: Follow the Player Card pattern from `PlayerCard.tsx` and `PlayerDirectoryResults.tsx`:
- Card as `<button>` for keyboard accessibility
- Clubhouse White background, 1px Boundary Line border, `rounded.lg` (12px)
- Academy teal focus ring and hover border
- `role="button"` with ARIA label
- Loading skeleton matching card anatomy

**Rationale**: Spec requires team cards to "follow the same general visual structure" as Player cards. Reusing the established pattern speeds development and ensures consistency.

## 11. Searchable Player Dropdown

**Decision**: Custom `Combobox` implementation using a controlled `<input>` with filtered dropdown list. Debounced search (300ms) calls `GET /api/v1/players?search=...&page_size=50`. Results filtered client-side to exclude already-selected players. States: loading spinner, "No players found" when empty, error with retry on API failure.

**Rationale**: No third-party combobox libraries needed. The existing `ApiClient` and player search endpoint provide everything. Debouncing prevents excessive API calls. Client-side deduplication is simpler than server-side exclusion lists.

**Alternatives considered**: Headless UI Combobox, Downshift — add dependencies without proportional benefit for a single dropdown use case.

## 12. Drag-and-Drop Roster Reordering

**Decision**: HTML5 Drag and Drop API (native browser). No library. Grip icon (`⋮⋮` or six-dot SVG) with `draggable="true"`. Drag events: `dragstart`, `dragover`, `drop` to reorder array in state. Visual feedback via `opacity-50` on dragged item and `border-2 border-dashed border-academy` on drop target.

**Rationale**: Keeps dependencies minimal (Constitution IV). HTML5 DnD is well-supported in all target browsers. Keyboard-accessible alternatives (Move Up/Move Down buttons) ensure accessibility compliance.

**Alternatives considered**: `@dnd-kit/core` — well-regarded library but adds a dependency for a single use case; native DnD is sufficient for a simple vertical reorder list.

## 13. Modal Patterns

**Decision**: Reuse existing `ModalDialog` component for Team Details and Team Form modals. Team Details → Player Details transition: close Team Details modal first, then open Player Details modal on next tick (avoids stacking). Unsaved changes confirmation via a separate `ConfirmationDialog` modal.

**Rationale**: `ModalDialog` already handles focus trapping, Escape-key, backdrop click, scroll locking, and focus restoration. Stacking prevention is straightforward: call `onClose()` before opening the next modal.

## 14. Unsaved Changes Detection

**Decision**: Custom `useUnsavedChanges` hook that tracks a `isDirty` flag. Form fields set dirty on change. Modal close (`onClose` callback) checks `isDirty` — if true, shows `ConfirmationDialog`. Browser navigation protection via `window.addEventListener('beforeunload', ...)` when dirty.

**Rationale**: Simple state tracking without form-library overhead. Matches the lightweight pattern of the existing codebase.

## 15. Age Group Badge

**Decision**: Reuse the `player-type-badge` design token pattern from `DESIGN.md`:
- Background: Academy Teal Wash (`#eef5f7`)
- Text: Slate Ink (`#1e293b`)
- Font: Label typography (`0.875rem`, 600, 1.25)
- Border radius: `rounded.sm` (6px)
- Padding: `2px 8px`

Human-readable label mapping in a constant: `{J: "Juniors", U11: "U11", U13: "U13", U15: "U15"}`.

**Rationale**: DESIGN.md already defines a badge component token. Consistent with existing `PlayerTypeBadge`.
