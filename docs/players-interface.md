# Players Interface

## Purpose

The Players interface gives every authenticated VK Cricket Academy user a
responsive directory of active player profiles. Coaches can create and update
profiles, while players have read-only access. The interface keeps team
membership, playing attributes, biography data, and versioned edits in one
accessible workflow.

## Key flows

- Browse players in stable last-name order, 20 at a time, with team names or an
  Unassigned label.
- Filter the server-side list by one team or by unassigned players. Changing
  the filter returns to page 1.
- Open a card to view identity and playing details, team membership, biography,
  metadata, and the placeholder for future statistics.
- As a Head Coach or Assistant Coach, add a player from the directory, its true
  empty state, or the dashboard quick action at `/players?action=add`.
- Edit a player from the details dialog. Updates include the current
  `version_number`; a stale update shows a conflict and lets the coach reload
  the latest profile before trying again.

Create and edit forms share field definitions, enum labels, date conversion,
metadata controls, validation, and unsaved-change protection. Successful
mutations refresh the visible directory without a full page reload. Backend
authorization remains authoritative, and HTTP 403 responses produce a clear
permissions message.

## Interface states and accessibility

The page distinguishes initial loading, a truly empty directory, filtered
no-results, request errors, and successful mutations. Loading uses an
assistive-technology label and reduced-motion-safe skeletons. Coaches receive
an Add your first player action only in the true-empty state; filtered results
instead prompt users to change the filter.

Cards, filters, pagination, dialogs, and forms are keyboard accessible.
Dialogs trap focus, close with Escape or their close control, lock background
scroll, and restore focus. Controls meet the 44px touch-target minimum. The
card grid reflows from one column at 320px to three columns on desktop without
horizontal overflow.

## API surface

All paths are below `/api/v1` and require authentication.

| Method | Path | Purpose |
|---|---|---|
| GET | `/players?page=&page_size=&team_id=&unassigned=` | List active players with pagination and optional team filtering |
| GET | `/players/{player_id}` | Retrieve one player, including team summaries |
| POST | `/players` | Create a player as a Head or Assistant Coach |
| PUT | `/players/{player_id}` | Update a player with optimistic concurrency control |
| GET | `/teams` | Populate the directory team filter |

`team_id` and `unassigned=true` are mutually exclusive. List responses include
`players`, `page`, `page_size`, `total_players`, `total_pages`,
`has_previous`, and `has_next`. Player responses include lightweight
`teams: [{ id, name }]` entries.

## Configuration and validation

The feature adds no dependencies, environment variables, database tables, or
migrations. It uses the existing PostgreSQL connection, FastAPI authorization,
React application shell, and academy design tokens.

Run the focused validation:

```bash
cd backend
uv run python -m pytest tests/integration/quickstart/test_005_quickstart_flow.py -v

cd ../frontend
npm run test -- --run
npm run test:e2e -- e2e/players-flow.spec.ts --project=chromium
```

The complete request scenarios are documented in
`specs/005-players-interface/quickstart.md`.
