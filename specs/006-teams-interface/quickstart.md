# Quickstart: Teams Interface

**Feature**: 006-teams-interface | **Date**: 2026-07-25

Validation guide for the Teams Interface feature. Covers backend API operations end-to-end against a running PostgreSQL instance.

## Prerequisites

- Docker running with PostgreSQL (see `docker-compose.yml`)
- Python 3.12+ with `uv` installed
- Project dependencies installed: `cd backend && uv sync`
- Database migrated: `cd backend && uv run alembic upgrade head`
- Head Coach user seeded: `cd backend && uv run python scripts/seed_head_coach.py`
- Application running: `cd backend && uv run uvicorn src.main:app --reload`
- At least 8 active players exist in the database

## Setup: Seed Test Data

```bash
# Ensure at least 15 active players exist for roster testing.
# If seeding is needed, use the seed script or create players via the API.
# Verify players exist:
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/players?page_size=5" | python3 -m json.tool
```

## 1. Create a Team (Atomic POST)

```bash
TOKEN="<head-coach-access-token>"

# Create team with 8 players
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Falcons",
    "age_group": "U13",
    "player_ids": [
      "<player-uuid-1>",
      "<player-uuid-2>",
      "<player-uuid-3>",
      "<player-uuid-4>",
      "<player-uuid-5>",
      "<player-uuid-6>",
      "<player-uuid-7>",
      "<player-uuid-8>"
    ]
  }' | python3 -m json.tool
```

**Expected**: `201 Created` with team object containing `id`, `name: "Falcons"`, `age_group: "U13"`, `player_count: 8`, `version_number: 1`.

## 2. Verify Paginated Team List

```bash
curl -s "http://localhost:8000/api/v1/teams?page=1&page_size=12" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Expected**: `200 OK`. Response contains `teams` array (includes "Falcons"), `page: 1`, `page_size: 12`, `total_teams`, `total_pages`. Teams ordered by `name ASC, age_group ASC, id ASC`.

## 3. Verify Team Roster Retrieval

```bash
TEAM_ID="<team-uuid-from-create>"

curl -s "http://localhost:8000/api/v1/teams/$TEAM_ID/players" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Expected**: `200 OK`. Response contains `team_id` and `players` array in roster order (order matches `player_ids` array from creation). Each player has `player_id`, `first_name`, `last_name`, `is_active: true`, `roster_order` (1–8).

## 4. Update Team (Atomic PUT)

```bash
# Change name, age group, and reorder/replace roster
curl -s -X PUT "http://localhost:8000/api/v1/teams/$TEAM_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Eagles",
    "age_group": "U15",
    "player_ids": [
      "<player-uuid-8>",
      "<player-uuid-1>",
      "<player-uuid-3>",
      "<player-uuid-5>",
      "<player-uuid-2>",
      "<player-uuid-4>",
      "<player-uuid-6>",
      "<player-uuid-7>"
    ],
    "version_number": 1
  }' | python3 -m json.tool
```

**Expected**: `200 OK`. Team name is "Eagles", age group is "U15", `version_number: 2`, `player_count: 8`. Roster re-retrieval shows new order.

## 5. Verify Roster Order Persists After Update

```bash
curl -s "http://localhost:8000/api/v1/teams/$TEAM_ID/players" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Expected**: Players in the order specified in step 4. Roster order stable across repeated requests.

## 6. Reject Stale Version (OCC)

```bash
# Submit with old version_number (still 1, but server is at 2)
curl -s -X PUT "http://localhost:8000/api/v1/teams/$TEAM_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ShouldFail",
    "age_group": "U13",
    "player_ids": [
      "<player-uuid-1>","<player-uuid-2>","<player-uuid-3>",
      "<player-uuid-4>","<player-uuid-5>","<player-uuid-6>",
      "<player-uuid-7>"
    ],
    "version_number": 1
  }' | python3 -m json.tool
```

**Expected**: `409 Conflict`. `detail` contains "Stale version" message. Team data unchanged.

## 7. Reject Fewer Than 7 Players

```bash
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tiny",
    "age_group": "U11",
    "player_ids": ["<uuid-1>","<uuid-2>"]
  }' | python3 -m json.tool
```

**Expected**: `422 Unprocessable Content`. Validation error for `player_ids` minimum length.

## 8. Reject Duplicate Players

```bash
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dups",
    "age_group": "U11",
    "player_ids": [
      "<uuid-1>","<uuid-1>","<uuid-3>","<uuid-4>",
      "<uuid-5>","<uuid-6>","<uuid-7>"
    ]
  }' | python3 -m json.tool
```

**Expected**: `400 Bad Request` or `422`. Error indicates duplicate player detected.

## 9. Reject Duplicate Team Name in Same Age Group

```bash
# Try to create "Eagles" again in U15 (already exists from step 4)
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "  eagles  ",
    "age_group": "U15",
    "player_ids": [
      "<uuid-1>","<uuid-2>","<uuid-3>","<uuid-4>",
      "<uuid-5>","<uuid-6>","<uuid-7>"
    ]
  }' | python3 -m json.tool
```

**Expected**: `409 Conflict`. Whitespace-normalized, case-insensitive duplicate rejected.

## 10. Allow Same Name in Different Age Group

```bash
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Eagles",
    "age_group": "U13",
    "player_ids": [
      "<uuid-1>","<uuid-2>","<uuid-3>","<uuid-4>",
      "<uuid-5>","<uuid-6>","<uuid-7>"
    ]
  }' | python3 -m json.tool
```

**Expected**: `201 Created`. "Eagles" in U13 is allowed even though "Eagles" exists in U15.

## 11. Reject Unauthorized (Player Role)

```bash
PLAYER_TOKEN="<player-access-token>"

curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $PLAYER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "NoAuth",
    "age_group": "U11",
    "player_ids": [
      "<uuid-1>","<uuid-2>","<uuid-3>","<uuid-4>",
      "<uuid-5>","<uuid-6>","<uuid-7>"
    ]
  }' | python3 -m json.tool
```

**Expected**: `403 Forbidden`. `detail: "Not authorized"`.

## 12. Inactive Player in Roster Retrieval

```bash
# 1. Create team with a player
# 2. Deactivate that player (PUT /api/v1/players/{id} with is_active: false)
# 3. Retrieve roster — player still appears with is_active: false
curl -s "http://localhost:8000/api/v1/teams/$TEAM_ID/players" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Expected**: `200 OK`. If any roster member is inactive, their entry has `is_active: false`.

## Quickstart Test

Per Constitution V, create `backend/tests/integration/quickstart/test_006_quickstart_flow.py` that validates these steps programmatically (using pytest + httpx AsyncClient or TestClient).
