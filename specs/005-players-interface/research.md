# Research: Players Interface

**Date**: 2026-07-22
**Feature**: 005-players-interface

## 1. Backend Pagination + Filtering Pattern

### Decision
Extend the existing `PlayerService.list_players` method with optional `page`, `page_size`, `team_id`, and `unassigned` parameters. Add a `PaginatedPlayerResponse` schema wrapping the existing `PlayerResponse` list with pagination metadata. The route handler accepts query parameters and delegates to the service.

### Rationale
- The existing `list_players` already queries active players with stable ordering (last_name, first_name, id).
- SQLAlchemy's `slice()` and `count()` provide efficient offset-based pagination without raw SQL.
- Team filtering joins `team_players` and `teams`; unassigned filtering uses a `NOT EXISTS` subquery.
- This keeps the change purely at the query layer — no schema migrations needed.

### Alternatives Considered
- **Cursor-based pagination**: Overkill for academy-scale (<1K players). Offset pagination is simpler and sufficient.
- **Separate `/players/unassigned` endpoint**: Fractures the API surface. A query parameter keeps one consistent endpoint.
- **Full-text search or sorting**: Explicitly out of scope per spec assumptions.

### Key Details
- Default `page_size`: 20 (matching spec FR-041).
- Default ordering: `last_name ASC, first_name ASC, id ASC` (matching spec FR-044/FR-059 and existing behavior).
- Pagination metadata: `page`, `page_size`, `total_players`, `total_pages`, `has_previous`, `has_next`.
- `team_id` parameter filters to a specific team via JOIN.
- `unassigned=true` returns players with no `team_players` rows (exclusive with `team_id`).
- Error on invalid params: page < 1 → 422, page_size < 1 or > 100 → 422.

---

## 2. Team Membership in Player Responses

### Decision
Extend `PlayerResponse` with an optional `teams: list[TeamSummary]` field, where `TeamSummary` has `id` and `name`. The player-list query eagerly loads team memberships via SQLAlchemy `selectinload` on `team_players` → `team`.

### Rationale
- The existing `Player` model has no direct relationship to teams; the ORM relationship must be added (or a manual join used).
- Eager loading avoids N+1 queries across the paginated result set.
- The frontend needs team names for player cards (FR-006) and the details modal (FR-009).
- `TeamSummary` is a lightweight subset — no need to ship full `TeamResponse` objects.

### Alternatives Considered
- **Separate `/players/{id}/teams` endpoint**: Requires an extra request per card/modal, degrading UX.
- **Include full TeamResponse objects**: Unnecessary payload bloat — only `id` and `name` are needed.

---

## 3. Frontend Modal Pattern

### Decision
Reuse the existing `useModalDialog` hook (from `AccountSettingsModal`) for the Player Details, Add Player, and Edit Player modals. Each modal is a self-contained component following the same pattern: backdrop with `bg-slate-900/60`, `role="dialog"`, `aria-modal="true"`, focus trapping via `useModalDialog`, Escape-key close, and backdrop-click close.

### Rationale
- The spec assumption explicitly states the `AccountSettingsModal` pattern should be reused or adapted.
- `useModalDialog` already handles focus trapping, Escape, scroll lock, and focus restoration — all required by FR-010, FR-061, SC-004.
- Consistent modal UX across the application per Constitution II (Simple UX) and DESIGN.md.

### Alternatives Considered
- **Third-party modal library**: Violates Constitution IV (Minimal Dependencies). Unnecessary when the pattern already exists.
- **React Router modal routes**: Adds routing complexity; the feature uses local component state for modals, matching the SettingsPage pattern.

---

## 4. Frontend Pagination State

### Decision
Server-side pagination managed in the `PlayersPage` container component via `useState` for `page` and `teamFilter`. The API call fetches one page at a time with the current filter. Pagination controls are a presentational `Pagination` component receiving `page`, `totalPages`, and `onPageChange`.

### Rationale
- Server-side pagination is required (FR-041), so the frontend must not load all players at once.
- A `useEffect` keyed on `[page, teamFilter]` triggers the fetch. Rapid clicks are handled by an abort controller or ignoring stale responses (edge case from spec).
- The filter change resets `page` to 1 (FR-040).

### Alternatives Considered
- **Client-side pagination**: Violates FR-041 and would not scale if the academy grows.
- **React Query / SWR**: Adding a caching library for a single paginated list is overkill per Constitution IV.

---

## 5. Enum Formatting

### Decision
A shared `enumLabels.ts` utility exports constant mappings from backend enum values to user-facing labels (e.g., `"right-arm leg-break"` → `"Right-Arm Leg-Break"`). An `EnumLabel` component wraps this for consistent rendering. Unknown enum values fall back to a title-cased version of the raw value.

```typescript
// Example mapping
const BATTING_STYLE_LABELS: Record<string, string> = {
  right: "Right-Handed",
  left: "Left-Handed",
}

function formatEnum(raw: string, mapping: Record<string, string>): string {
  return mapping[raw] ?? raw.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}
```

### Rationale
- FR-045–049 require centralized, consistent formatting across cards, details, and forms.
- Fallback for unknown values (FR-049) handles backend additions without frontend breakage.
- Forms use the reverse mapping for select options (label → value).

### Alternatives Considered
- **Inline `switch` statements per component**: Duplication violates FR-047 and Constitution I.
- **Backend-provided labels**: Couples display to API, and backend enums use snake_case/url-friendly values intentionally.

---

## 6. Date Formatting

### Decision
A shared `formatDate.ts` utility provides `toDisplayDate(isoDate: string): string` (e.g., "24 Apr 1973") and `toApiDate(date: Date): string` (YYYY-MM-DD). Used by cards, details modals, and forms.

### Rationale
- FR-015 requires human-readable display (e.g., "24 Apr 1973").
- FR-016 requires YYYY-MM-DD submission format.
- Centralized utility prevents inconsistent formatting across components.

### Alternatives Considered
- **date-fns / luxon / dayjs**: Adding a date library for two functions violates Constitution IV.
- **Intl.DateTimeFormat with `toLocaleDateString`**: Browser-dependent output format; `Date.prototype` manipulation with manual month abbreviations gives consistent output.

---

## 7. Team Filter

### Decision
A `TeamFilter` component renders as a `<select>` (stylized with Tailwind) with options: "All Players", each team name, and "Unassigned Players". It calls `onChange(teamId: string | null)` — `null` for "All", `"__unassigned__"` for unassigned.

On the backend, `team_id` is a UUID query parameter; `unassigned=true` is a boolean parameter. They are mutually exclusive — the backend returns 422 if both are provided.

### Rationale
- FR-038–040 describe the filter behavior.
- A `<select>` is the simplest accessible control for single-choice filtering. Keyboard-accessible by default.
- Mutual exclusivity enforced server-side since the UI naturally presents these as mutually exclusive options.

### Alternatives Considered
- **Chip/tag-based multi-select**: Overengineered for single-team filtering.
- **Client-side filtering of all players**: Violates server-side pagination requirement and FR-039.

---

## 8. Add/Edit Form Reuse

### Decision
A single `PlayerForm` component handles both Add and Edit workflows. It accepts an optional `player` prop: when present, it pre-fills fields and switches to Edit mode (PATCH semantics with `version_number`); when absent, it uses POST semantics. The form uses shared validation, enum mappings, and date handling.

### Rationale
- FR-017 explicitly requires shared form fields, validation, enum mappings, and metadata controls.
- Single source of truth for field definitions eliminates drift between Add and Edit forms.
- Constitution I (Clean Code) and XI (Component Discipline) are satisfied.

### Alternatives Considered
- **Separate `AddPlayerForm` and `EditPlayerForm`**: Duplicates all field definitions, validation, and styling — violates FR-017.
- **Higher-order component wrapping a base form**: Equivalent pattern; the `player?: PlayerResponse` prop approach is simpler TypeScript.

---

## 9. OCC Conflict Handling (HTTP 409)

### Decision
When the backend returns HTTP 409 on update, the frontend catches the `ApiClientError` (status 409), displays a conflict message: "This player was updated by another user. Please reload the latest data and try again.", and provides a "Reload" button that re-fetches the player and replaces the form state with fresh data — including the new `version_number`.

### Rationale
- FR-036–037 specify the exact UX.
- The `ApiClientError` class already surfaces `status` and parsed `body` — no new infrastructure needed.
- The reload replaces all form values and version, preventing stale retry (FR-037).

---

## 10. Unsaved Changes Protection

### Decision
A `useUnsavedChanges` hook tracks a "dirty" boolean. When the user attempts to close the Add/Edit modal (Escape, close button, backdrop click) with `dirty === true`, a `window.confirm` dialog appears: "You have unsaved changes. Discard them?" The modal only closes on confirm.

### Rationale
- Spec requirement (clarification session + FR-028, SC-008).
- `window.confirm` is the simplest accessible confirmation mechanism; it blocks the JS thread and provides native keyboard/AT support.
- The hook is reusable for any future form that needs exit protection.

### Alternatives Considered
- **Custom confirmation dialog**: Overengineered for a simple yes/no gate. `window.confirm` is universally accessible.
- **`beforeunload` event**: Only fires on browser tab close/navigation, not modal close.

---

## 11. No New Dependencies

### Decision
No new npm or PyPI packages are added. All required functionality is achievable with the existing stack: React, Tailwind CSS, FastAPI, SQLAlchemy, pytest, Vitest, Playwright.

### Rationale
- Constitution IV (Minimal Dependencies) requires justification for every new dependency.
- Date formatting: pure JS `Date` + `Intl` is sufficient.
- Enum formatting: static TypeScript mappings.
- Modal/focus management: existing `useModalDialog`.
- Pagination: pure React state + SQLAlchemy slicing.
- No third-party form library needed — controlled React inputs with a shared `PlayerForm`.

---

## 12. Backend Test Strategy

### Decision
Unit tests extend `test_player_routes.py` and `test_player_schemas.py` to cover new pagination parameters, team-filtered responses, and pagination metadata validation. Integration quickstart test at `backend/tests/integration/quickstart/test_005_quickstart_flow.py` validates the extended endpoint end-to-end against a real test database.

### Rationale
- Constitution V requires unit tests for all new logic and a quickstart test for the feature.
- Existing test patterns (mocking `PlayerService`, `httpx.AsyncClient` with overridden dependencies) are proven and should be extended.
- The quickstart test follows the `test_00X_quickstart_flow.py` naming convention per Constitution V.

---

## Summary

All design decisions are resolved. No NEEDS CLARIFICATION items remain. The approach extends existing patterns without introducing new dependencies, architectural changes, or schema migrations.
