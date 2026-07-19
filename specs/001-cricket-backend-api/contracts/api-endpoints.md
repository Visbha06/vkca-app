# API Endpoint Contracts: Cricket Team Management Backend API

**Date**: 2026-07-08

**Base URL**: `/api/v1`

**Content-Type**: `application/json`

**Common Headers**: All responses include `Content-Type: application/json`. Timestamps in UTC ISO 8601 format. UUIDs as strings. Version numbers as integers on every response entity.

**Error Format**:
```json
{
  "detail": "Human-readable error message"
}
```

---

## Core Entities

### Users

#### POST /api/v1/users

Create a new user account.

**Request**:
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "hashed_password": "$2b$12$...",
  "role": "head coach"
}
```

**Validation**:
- `first_name`: required, 1-100 chars
- `last_name`: required, 1-100 chars
- `email`: required, valid email format, unique
- `hashed_password`: required, non-empty
- `role`: required, one of `head coach`, `assistant coach`, `player`

**Response 201**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "role": "head coach",
  "is_active": true,
  "created_at": "2026-07-08T14:30:00Z",
  "updated_at": "2026-07-08T14:30:00Z",
  "version_number": 1
}
```
Note: `hashed_password` is never returned in responses.

**Error 409**: `{"detail": "A user with email 'john.doe@example.com' already exists."}`

---

#### GET /api/v1/users

List all users.

**Response 200**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "role": "head coach",
    "is_active": true,
    "created_at": "2026-07-08T14:30:00Z",
    "updated_at": "2026-07-08T14:30:00Z",
    "version_number": 1
  }
]
```

---

### Teams

#### POST /api/v1/teams

Create a new team/squad.

**Request**:
```json
{
  "name": "U14 Lions",
  "age_group": "U14"
}
```

**Response 201**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "U14 Lions",
  "age_group": "U14",
  "created_at": "2026-07-08T14:30:00Z",
  "updated_at": "2026-07-08T14:30:00Z",
  "version_number": 1
}
```

---

#### GET /api/v1/teams

List all teams.

**Response 200**:
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "U14 Lions",
    "age_group": "U14",
    "created_at": "2026-07-08T14:30:00Z",
    "updated_at": "2026-07-08T14:30:00Z",
    "version_number": 1
  }
]
```

---

#### POST /api/v1/teams/{team_id}/players/{player_id}

Add a player to a team squad.

**Response 201**:
```json
{
  "team_id": "660e8400-e29b-41d4-a716-446655440001",
  "player_id": "770e8400-e29b-41d4-a716-446655440002",
  "joined_at": "2026-07-08T14:30:00Z"
}
```

**Error 404**: `{"detail": "Team not found."}` or `{"detail": "Player not found."}`

**Error 409**: `{"detail": "Player is already a member of this team."}`

---

### Players

#### POST /api/v1/players

Create a player profile.

**Request**:
```json
{
  "first_name": "Sachin",
  "last_name": "Tendulkar",
  "date_of_birth": "1973-04-24",
  "bio": "Right-handed batsman",
  "batting_style": "right",
  "bowling_style": "right-arm leg-break",
  "player_type": "batter",
  "player_metadata": {}
}
```

**Validation**:
- `first_name`: required, 1-100 chars
- `last_name`: required, 1-100 chars
- `date_of_birth`: required, ISO 8601 date (YYYY-MM-DD)
- `batting_style`: required, one of `right`, `left`
- `bowling_style`: required, one of 8 enumerated variants
- `player_type`: required, one of `batter`, `bowler`, `all-rounder`, `wicket-keeper`
- `player_metadata`: optional, valid JSON object

**Response 201**:
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "first_name": "Sachin",
  "last_name": "Tendulkar",
  "date_of_birth": "1973-04-24",
  "bio": "Right-handed batsman",
  "batting_style": "right",
  "bowling_style": "right-arm leg-break",
  "player_type": "batter",
  "player_metadata": {},
  "is_active": true,
  "created_at": "2026-07-08T14:30:00Z",
  "updated_at": "2026-07-08T14:30:00Z",
  "version_number": 1
}
```

**Error 409**: `{"detail": "A player with this name and date of birth already exists."}`

---

#### GET /api/v1/players

List active players.

**Response 200**: Array of player objects (same shape as POST response). Inactive players are excluded.

---

## Match Ledger

### Matches

#### POST /api/v1/matches

Create a match record.

**Request**:
```json
{
  "match_date": "2026-07-01",
  "format": "T20",
  "opponent_name": "Rivals CC",
  "venue": "City Oval",
  "result": "Won by 5 wickets"
}
```

**Response 201**:
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "match_date": "2026-07-01",
  "format": "T20",
  "opponent_name": "Rivals CC",
  "venue": "City Oval",
  "result": "Won by 5 wickets",
  "created_at": "2026-07-08T14:30:00Z",
  "updated_at": "2026-07-08T14:30:00Z",
  "version_number": 1
}
```

---

#### GET /api/v1/matches

List all matches.

**Response 200**: Array of match objects.

---

### Match Performances (Batch Submit)

#### POST /api/v1/matches/{match_id}/performances

Submit a batch of player performances for a completed match. All writes are atomic — any validation failure rolls back the entire submission.

**Request**:
```json
{
  "performances": [
    {
      "player_id": "770e8400-e29b-41d4-a716-446655440002",
      "batting": {
        "runs_scored": 75,
        "balls_faced": 52,
        "dismissal": "caught",
        "fours": 8,
        "sixes": 2,
        "notes": "Player of the match"
      },
      "bowling": {
        "overs_bowled": 4.0,
        "maidens": 1,
        "runs_conceded": 22,
        "wickets_taken": 3,
        "wides": 1,
        "notes": "Excellent death bowling"
      },
      "fielding": {
        "catches": 1,
        "stumpings": 0,
        "run_outs": 0,
        "dropped_catches": 0,
        "notes": null
      }
    },
    {
      "player_id": "990e8400-e29b-41d4-a716-446655440004",
      "batting": {
        "runs_scored": 12,
        "balls_faced": 8,
        "dismissal": "bowled",
        "fours": 2,
        "sixes": 0,
        "notes": null
      }
    }
  ]
}
```

**Validation rules**:
- `performances`: required, non-empty array
- Each element: must have `player_id` (valid UUID, player must exist)
- At least one of `batting`, `bowling`, or `fielding` sub-objects must be present per player
- Each sub-object is independently optional
- `match_id` in URL must reference an existing match
- All `player_id` values must be valid; any invalid reference aborts the entire transaction

**Response 201**:
```json
{
  "match_id": "880e8400-e29b-41d4-a716-446655440003",
  "performances_created": 2,
  "batting_records": 2,
  "bowling_records": 1,
  "fielding_records": 1,
  "players_stats_updated": 2
}
```

**Error 400**: `{"detail": "Performances array must not be empty."}`

**Error 404**: `{"detail": "Match not found."}`

**Error 404**: `{"detail": "Player not found: 990e8400-e29b-41d4-a716-446655440099."}`

---

## Read-Only Aggregate Statistics

### GET /api/v1/players/{player_id}/stats/batting

Fetch lifetime batting totals, split by format.

**Query parameters**:
- `format` (optional): Filter to a single format. Values: `T20`, `one-day`, `test`, `other`.

**Response 200** (all formats):
```json
[
  {
    "format": "T20",
    "matches": 15,
    "innings": 14,
    "not_outs": 3,
    "runs": 450,
    "balls_faced": 320,
    "high_score": 89,
    "hundreds": 0,
    "fifties": 4,
    "ducks": 1,
    "fours": 48,
    "sixes": 12
  },
  {
    "format": "one-day",
    "matches": 22,
    "innings": 20,
    "not_outs": 4,
    "runs": 780,
    "balls_faced": 610,
    "high_score": 112,
    "hundreds": 1,
    "fifties": 6,
    "ducks": 0,
    "fours": 85,
    "sixes": 18
  }
]
```

**Edge case**: Player with no batting data returns an empty array `[]`.

---

### GET /api/v1/players/{player_id}/stats/bowling

Fetch lifetime bowling totals, split by format.

**Query parameters**:
- `format` (optional): Filter to a single format.

**Response 200** (single format):
```json
[
  {
    "format": "T20",
    "matches": 15,
    "innings": 14,
    "overs_bowled": 52.3,
    "runs_conceded": 310,
    "wickets": 22,
    "best_bowled": "4/18",
    "maidens": 3,
    "four_wicket_hauls": 2,
    "five_wicket_hauls": 1,
    "wides": 8,
    "catches": 1
  }
]
```

**Edge case**: Player with no bowling data returns an empty array `[]`.

---

## Error Reference

| Status | Meaning | Example |
|--------|---------|---------|
| 201 | Created successfully | |
| 400 | Invalid request body / validation error | Empty performances array |
| 404 | Referenced entity not found | Unknown player_id or match_id |
| 409 | Conflict — duplicate or version mismatch | Duplicate player, stale version_number, player already in team |
| 422 | Unprocessable entity (enum validation failure) | Invalid bowling_style value |

All 409 responses for version mismatches are also logged to DataSyncLogs.
