# Quickstart Validation Guide: Cricket Team Management Backend API

**Date**: 2026-07-08

**Purpose**: Runnable end-to-end validation scenarios to prove the feature works. Use `curl` or an HTTP client against a running backend instance.

---

## Prerequisites

- PostgreSQL running via Docker (`docker compose up -d db` from repo root)
- Backend server running (`cd backend && uv run uvicorn src.main:app --reload`)
- Base URL: `http://localhost:8000/api/v1`

---

## Validation Flow: Full Match Lifecycle

This flow walks through creating a player, a team, a match, submitting performances, and reading the resulting statistics — proving all three backend rules (OCC, Atomic Accumulator, Timestamp Injection) work end-to-end.

### 1. Create a Player

```bash
curl -s -X POST http://localhost:8000/api/v1/players \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Virat",
    "last_name": "Kohli",
    "date_of_birth": "1988-11-05",
    "batting_style": "right",
    "bowling_style": "right-arm medium",
    "player_type": "batter"
  }'
```

**Expected**: HTTP 201. Response contains `id`, `version_number: 1`, `created_at` is a UTC timestamp, `is_active: true`. Note the `id` as `$PLAYER_ID`.

### 2. Verify Timestamp Injection (FR-017)

```bash
curl -s -X POST http://localhost:8000/api/v1/players \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Rohit",
    "last_name": "Sharma",
    "date_of_birth": "1987-04-30",
    "batting_style": "right",
    "bowling_style": "right-arm off-break",
    "player_type": "batter",
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2020-01-01T00:00:00Z"
  }'
```

**Expected**: HTTP 201. Response `created_at` is the current server time, NOT "2020-01-01". Client-supplied timestamps are silently ignored.

### 3. Verify Duplicate Player Detection (FR-021)

```bash
curl -s -X POST http://localhost:8000/api/v1/players \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Virat",
    "last_name": "Kohli",
    "date_of_birth": "1988-11-05",
    "batting_style": "right",
    "bowling_style": "right-arm medium",
    "player_type": "batter"
  }'
```

**Expected**: HTTP 409 Conflict. `{"detail": "A player with this name and date of birth already exists."}`

### 4. Create a Team

```bash
curl -s -X POST http://localhost:8000/api/v1/teams \
  -H "Content-Type: application/json" \
  -d '{"name": "Senior XI", "age_group": "Senior"}'
```

**Expected**: HTTP 201. Note `$TEAM_ID`.

### 5. Add Player to Team

```bash
curl -s -X POST http://localhost:8000/api/v1/teams/$TEAM_ID/players/$PLAYER_ID
```

**Expected**: HTTP 201. Response contains `team_id`, `player_id`, and `joined_at` timestamp.

### 6. Verify Duplicate Team Membership

```bash
curl -s -X POST http://localhost:8000/api/v1/teams/$TEAM_ID/players/$PLAYER_ID
```

**Expected**: HTTP 409. `{"detail": "Player is already a member of this team."}`

### 7. Create a Match

```bash
curl -s -X POST http://localhost:8000/api/v1/matches \
  -H "Content-Type: application/json" \
  -d '{
    "match_date": "2026-07-01",
    "format": "T20",
    "opponent_name": "Challengers CC",
    "venue": "Main Ground",
    "result": "Won by 7 wickets"
  }'
```

**Expected**: HTTP 201. Note `$MATCH_ID`.

### 8. Submit Match Performances (Atomic Accumulator — FR-016)

```bash
curl -s -X POST http://localhost:8000/api/v1/matches/$MATCH_ID/performances \
  -H "Content-Type: application/json" \
  -d '{
    "performances": [
      {
        "player_id": "'$PLAYER_ID'",
        "batting": {
          "runs_scored": 82,
          "balls_faced": 55,
          "dismissal": "not out",
          "fours": 9,
          "sixes": 3
        },
        "fielding": {
          "catches": 2
        }
      }
    ]
  }'
```

**Expected**: HTTP 201. Response: `performances_created: 1`, `batting_records: 1`, `bowling_records: 0`, `fielding_records: 1`, `players_stats_updated: 1`.

### 9. Verify Aggregate Stats (FR-013)

```bash
curl -s http://localhost:8000/api/v1/players/$PLAYER_ID/stats/batting?format=T20
```

**Expected**: HTTP 200. Array with one element:
```json
[{
  "format": "T20",
  "matches": 1,
  "innings": 1,
  "not_outs": 1,
  "runs": 82,
  "balls_faced": 55,
  "high_score": 82,
  "hundreds": 0,
  "fifties": 1,
  "ducks": 0,
  "fours": 9,
  "sixes": 3
}]
```

### 10. Submit Another Performance and Verify Cumulative Stats

```bash
curl -s -X POST http://localhost:8000/api/v1/matches/$MATCH_ID/performances \
  -H "Content-Type: application/json" \
  -d '{
    "performances": [
      {
        "player_id": "'$PLAYER_ID'",
        "batting": {
          "runs_scored": 45,
          "balls_faced": 30,
          "dismissal": "caught",
          "fours": 5,
          "sixes": 1
        }
      }
    ]
  }'
```

**Expected**: HTTP 409 — a player can only have one performance row per match. The unique constraint `(player_id, match_id)` prevents duplicate entries.

### 11. Verify OCC (FR-015)

First, get the player's current version number:

```bash
curl -s http://localhost:8000/api/v1/players/$PLAYER_ID | jq '.version_number'
```

Suppose it returns `1`. Now submit an update with `version_number: 1`:

```bash
curl -s -X PUT http://localhost:8000/api/v1/players/$PLAYER_ID \
  -H "Content-Type: application/json" \
  -d '{"bio": "Updated bio", "version_number": 1}'
```

**Expected**: HTTP 200. `version_number: 2`.

Now submit a stale update with `version_number: 1`:

```bash
curl -s -X PUT http://localhost:8000/api/v1/players/$PLAYER_ID \
  -H "Content-Type: application/json" \
  -d '{"bio": "Stale update", "version_number": 1}'
```

**Expected**: HTTP 409 Conflict. DataSyncLogs contains a new entry with `status: "conflict"`.

### 12. Verify Inactive Player Filtering (FR-022)

Deactivate a player (update is_active to false):

```bash
curl -s -X PUT http://localhost:8000/api/v1/players/$PLAYER_ID \
  -H "Content-Type: application/json" \
  -d '{"is_active": false, "version_number": 2}'
```

Then list all players:

```bash
curl -s http://localhost:8000/api/v1/players
```

**Expected**: The deactivated player is NOT in the list.

Then fetch by ID:

```bash
curl -s http://localhost:8000/api/v1/players/$PLAYER_ID
```

**Expected**: The player IS returned, with `is_active: false`. Historical stats remain accessible.

---

## Success Criteria Validation

| Criterion | How to Verify | Expected |
|-----------|---------------|----------|
| SC-001: Player creation <2s | Time step 1 with `time` | Elapsed <2s |
| SC-003: OCC 409 <1s | Time step 11 (stale update) with `time` | Elapsed <1s |
| SC-004: Stats retrieval <1s | Time step 9 with `time` | Elapsed <1s |
| SC-005: Zero partial writes | Step 8 with invalid player_id | 404, no orphaned records in DB |
| SC-006: Aggregate stats accuracy | Manual sum of step 8 + step 10 | runs = 82 + 45 = 127 |
| SC-007: No client timestamp leakage | Step 2 | Server timestamp used, not "2020-01-01" |
| SC-008: Duplicate team membership | Step 6 | HTTP 409 |

---

## Cleanup

No cleanup needed — all test data remains in the database for further exploration or can be removed with a targeted DELETE.
