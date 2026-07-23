# Quickstart Validation Guide: Players Interface

**Date**: 2026-07-22
**Feature**: 005-players-interface

**Purpose**: Runnable end-to-end validation scenarios to prove the Players Interface feature works. Use `curl` or an HTTP client against a running backend instance for the API layer, and the Playwright E2E suite for the frontend.

---

## Prerequisites

- PostgreSQL running via Docker (`docker compose up -d db` from repo root)
- Backend server running (`cd backend && uv run uvicorn src.main:app --reload`)
- Base URL: `http://localhost:8000/api/v1`
- Head Coach user credentials already seeded (`cd backend && uv run python scripts/seed_head_coach.py`)

---

## Validation Flow: Player CRUD with Pagination and Filtering

This flow creates multiple players across teams, then exercises pagination, team filtering, unassigned-player filtering, and OCC conflict handling — proving the extended player-list endpoint works end-to-end.

### 1. Authenticate as Head Coach

```bash
LOGIN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "head.coach@vkca.local", "password": "VKCA-Head-Coach-2025!"}')
TOKEN=$(echo "$LOGIN" | jq -r '.access_token')
AUTH="Authorization: Bearer $TOKEN"
```

**Expected**: HTTP 200. `access_token` is populated. Note the token for subsequent requests.

---

### 2. Create Players

Create at least 22 players (to have enough for a second page with default page_size=20).

```bash
for i in $(seq 1 22); do
  curl -s -X POST http://localhost:8000/api/v1/players \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d "{
      \"first_name\": \"Player$i\",
      \"last_name\": \"Test$i\",
      \"date_of_birth\": \"2000-01-01\",
      \"batting_style\": \"right\",
      \"bowling_style\": \"right-arm medium\",
      \"player_type\": \"batter\"
    }"
  echo ""
done
```

**Expected**: Each returns HTTP 201 with `teams: []`, `version_number: 1`.

---

### 3. View Paginated Player List (Page 1)

```bash
curl -s "http://localhost:8000/api/v1/players?page=1&page_size=20" \
  -H "$AUTH" | jq '.'
```

**Expected**: HTTP 200.
- `players` array has ≤20 items.
- `page: 1`, `page_size: 20`.
- `total_players: 22`, `total_pages: 2`.
- `has_previous: false`, `has_next: true`.
- Players ordered by `last_name ASC, first_name ASC` (e.g., "Test1" through "Test20").

---

### 4. View Page 2

```bash
curl -s "http://localhost:8000/api/v1/players?page=2&page_size=20" \
  -H "$AUTH" | jq '.'
```

**Expected**: HTTP 200.
- `players` array has 2 items (remaining players).
- `page: 2`, `has_next: false`.

---

### 5. Verify Default Page Size

```bash
curl -s "http://localhost:8000/api/v1/players" \
  -H "$AUTH" | jq '.page_size'
```

**Expected**: `20` (the default).

---

### 6. Verify Default Ordering (FR-059)

```bash
curl -s "http://localhost:8000/api/v1/players?page=1&page_size=5" \
  -H "$AUTH" | jq '[.players[].last_name]'
```

**Expected**: First 5 last names are alphabetically ascending.

---

### 7. Verify Invalid Pagination Parameters

```bash
# Negative page
curl -s "http://localhost:8000/api/v1/players?page=-1" \
  -H "$AUTH" | jq '.detail'
```

**Expected**: HTTP 422. Validation error for `page`.

```bash
# Excessive page_size
curl -s "http://localhost:8000/api/v1/players?page_size=200" \
  -H "$AUTH" | jq '.detail'
```

**Expected**: HTTP 422. `page_size` must be ≤100.

---

### 8. Create Teams and Assign Players

```bash
TEAM1=$(curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"name": "Junior XI", "age_group": "U15"}' | jq -r '.id')

TEAM2=$(curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"name": "Senior XI", "age_group": "Senior"}' | jq -r '.id')
```

Assign the first 3 players from the list to Team 1:

```bash
PLAYERS=$(curl -s "http://localhost:8000/api/v1/players?page=1&page_size=3" \
  -H "$AUTH" | jq -r '.players[].id')

for pid in $PLAYERS; do
  curl -s -X POST "http://localhost:8000/api/v1/teams/$TEAM1/players/$pid" \
    -H "$AUTH"
  echo ""
done
```

---

### 9. Verify Team Membership in Player List

```bash
curl -s "http://localhost:8000/api/v1/players?page=1&page_size=3" \
  -H "$AUTH" | jq '.players[0].teams'
```

**Expected**: `teams` array is populated (e.g., `[{"id": "...", "name": "Junior XI"}]`). Previously unassigned players now show their team.

---

### 10. Filter by Team

```bash
curl -s "http://localhost:8000/api/v1/players?team_id=$TEAM1" \
  -H "$AUTH" | jq '.'
```

**Expected**: HTTP 200.
- Only the players assigned to Team 1 appear.
- `teams` array on each player includes "Junior XI".
- `total_players` reflects the count for this filter.

---

### 11. Filter Unassigned Players

```bash
curl -s "http://localhost:8000/api/v1/players?unassigned=true" \
  -H "$AUTH" | jq '.'
```

**Expected**: HTTP 200.
- Only players with `teams: []` appear.
- `total_players` reflects unassigned count.

---

### 12. Verify Mutual Exclusivity of Filters

```bash
curl -s "http://localhost:8000/api/v1/players?team_id=$TEAM1&unassigned=true" \
  -H "$AUTH" | jq '.detail'
```

**Expected**: HTTP 422. `team_id` and `unassigned` are mutually exclusive.

---

### 13. Verify Inactive Players Excluded

Get the ID of the first player:

```bash
PID=$(curl -s "http://localhost:8000/api/v1/players?page=1&page_size=1" \
  -H "$AUTH" | jq -r '.players[0].id')
```

Deactivate via update (mark `is_active: false`):

```bash
VERSION=$(curl -s "http://localhost:8000/api/v1/players/$PID" \
  -H "$AUTH" | jq -r '.version_number')

curl -s -X PUT "http://localhost:8000/api/v1/players/$PID" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"is_active\": false, \"version_number\": $VERSION}" | jq '.is_active'
```

**Expected**: `is_active: false`.

Now list players again:

```bash
curl -s "http://localhost:8000/api/v1/players?page=1&page_size=50" \
  -H "$AUTH" | jq --arg pid "$PID" '[.players[].id] | index($pid)'
```

**Expected**: `null` — the deactivated player is not in the active list.

---

### 14. OCC Conflict (Stale Update)

Get a player's current version:

```bash
ANOTHER_PID=$(curl -s "http://localhost:8000/api/v1/players?page=1&page_size=1" \
  -H "$AUTH" | jq -r '.players[0].id')
VERSION=$(curl -s "http://localhost:8000/api/v1/players/$ANOTHER_PID" \
  -H "$AUTH" | jq -r '.version_number')
```

Update successfully:

```bash
curl -s -X PUT "http://localhost:8000/api/v1/players/$ANOTHER_PID" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"bio\": \"First update\", \"version_number\": $VERSION}" | jq '.version_number'
```

**Expected**: `version_number` incremented.

Now retry with the stale version:

```bash
curl -s -X PUT "http://localhost:8000/api/v1/players/$ANOTHER_PID" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"bio\": \"Stale update\", \"version_number\": $VERSION}" | jq '.detail'
```

**Expected**: HTTP 409. Detail contains "Stale version".

---

### 15. Player-Role Cannot Create/Update

Authenticate as a player-role user (first seed a player account, or test via the unit test suite for this case — see [contracts/players-api.md](./contracts/players-api.md) for expected 403 responses).

**Quick validation via unit test**: `cd backend && uv run pytest tests/unit/test_player_routes.py -v -k "create"`

---

## Quickstart Automated Test

The automated quickstart test lives at `backend/tests/integration/quickstart/test_005_quickstart_flow.py`. Run it with:

```bash
cd backend && uv run python -m pytest tests/integration/quickstart/test_005_quickstart_flow.py -v
```

This test programmatically executes the key scenarios above: pagination, default ordering, team filtering, unassigned filtering, inactive exclusion, and OCC conflict detection — against a real PostgreSQL test database.

---

## Frontend E2E Validation

The Playwright E2E test for the full frontend flow lives at `frontend/e2e/players-flow.spec.ts`. Run it with:

```bash
cd frontend && npm run test:e2e -- e2e/players-flow.spec.ts --project=chromium
```

This test covers (per FR-073):
- Login and navigation to Players page
- Team filtering
- Opening a Player Details modal
- Creating or editing a player as an authorized user
