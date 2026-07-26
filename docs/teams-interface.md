# Teams Interface

## Purpose

The Teams interface gives authenticated VK Cricket Academy users a responsive
directory of academy squads and their ordered rosters. Head Coaches and
Assistant Coaches can create and edit teams, while player-role users have
read-only access. Team details, age group, roster membership, roster order,
and concurrent edits are handled in one accessible workflow.

## Key flows

- Browse teams in stable name, age-group, and ID order, 12 at a time. Each card
  shows the team name, age group, and roster count.
- Open a team card to review every roster member in saved order. Inactive
  members remain visible and are clearly identified.
- Create a team with a name, age group, and 7–15 distinct active players. The
  team and complete roster are committed atomically.
- Edit team details and replace the complete roster in one transaction.
  Updates include the current `version_number`; stale writes return HTTP 409
  and the form can reload the latest server state.
- Reorder selected players with drag and drop or the keyboard-accessible Move
  Up and Move Down controls. The saved order persists across API requests and
  page reloads.

The shared create/edit form provides 15 player slots, debounced player search,
duplicate and minimum-roster validation, submission feedback, and unsaved
changes protection. Successful mutations refresh the directory without a full
page reload. Backend role checks remain authoritative.

## Interface states and accessibility

The directory distinguishes initial loading, an empty academy, request errors,
retryable refresh errors, and successful mutations. Team details and forms use
the shared dialog behavior for focus trapping, Escape handling, scroll locking,
and focus restoration.

Cards and reorder controls are keyboard operable. Form controls and action
buttons meet the 44px touch-target minimum. The card grid reflows from one
column on mobile to three columns on wide screens without horizontal overflow.
Inactive roster members use muted styling and cannot be selected for a new or
updated roster.

## API surface

All paths are below `/api/v1` and require authentication.

| Method | Path | Purpose |
|---|---|---|
| GET | `/teams?page=&page_size=` | List teams with roster counts and pagination metadata |
| GET | `/teams/{team_id}/players` | Retrieve all roster members in persisted order |
| POST | `/teams` | Atomically create a team and ordered roster as a coach |
| PUT | `/teams/{team_id}` | Atomically update team details and replace its roster using OCC |
| GET | `/players?search=&page_size=50` | Search active players by first, last, or full name for roster selection |

Create requests contain `name`, `age_group`, and ordered `player_ids`. Update
requests add `version_number`. Valid age groups are `J`, `U11`, `U13`, and
`U15`. Team names are compared with surrounding whitespace removed and case
ignored, and must be unique within an age group.

Roster responses include `player_id`, name fields, `is_active`, and
one-based `roster_order`. Team list responses include `teams`, `page`,
`page_size`, `total_teams`, and `total_pages`.

## Data and configuration

The feature adds the `AgeGroup` enum, a database check constraint for valid
team age groups, and `team_players.roster_order` with a
`(team_id, roster_order)` index. The Alembic migration is reversible. No new
dependencies, environment variables, or external services are required.

## Validation

Run the focused checks:

```bash
cd backend
uv run pytest tests/unit/test_team_routes.py tests/unit/test_team_service.py tests/unit/test_team_schemas.py tests/unit/test_player_routes.py
uv run pytest tests/integration/quickstart/test_006_quickstart_flow.py

cd ../frontend
npm run test
npm run test:e2e -- e2e/teams-flow.spec.ts --project=chromium
```

The complete API scenarios are documented in
`specs/006-teams-interface/quickstart.md`.
