# API Contract: Players Interface

**Date**: 2026-07-22
**Feature**: 005-players-interface

## Base URL

`/api/v1/players`

All endpoints require authentication. Authorization rules are enforced server-side. The frontend hides controls based on role but does not rely on frontend-only enforcement (FR-053).

---

## GET /api/v1/players

List active players with pagination and optional team filtering.

### Query Parameters

| Parameter | Type | Default | Constraints |
|-----------|------|---------|-------------|
| `page` | integer | 1 | ≥ 1 |
| `page_size` | integer | 20 | 1–100 |
| `team_id` | UUID | — | Mutually exclusive with `unassigned` |
| `unassigned` | boolean | — | `true` to filter unassigned players. Mutually exclusive with `team_id` |

**Validation**:
- `team_id` and `unassigned=true` together → 422 Unprocessable Entity
- `page` < 1 → 422
- `page_size` < 1 or > 100 → 422
- `page` > `total_pages` with results → returns empty `players` array, correct pagination metadata

### Authorization

Any authenticated user (Head Coach, Assistant Coach, Player).

### Response: 200 OK

```json
{
  "players": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "first_name": "Sachin",
      "last_name": "Tendulkar",
      "date_of_birth": "1973-04-24",
      "bio": "Right-handed opening batter",
      "batting_style": "right",
      "bowling_style": "right-arm leg-break",
      "player_type": "batter",
      "player_metadata": { "preferred_position": "opener" },
      "is_active": true,
      "created_at": "2026-07-01T10:00:00Z",
      "updated_at": "2026-07-15T14:30:00Z",
      "version_number": 3,
      "teams": [
        { "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7", "name": "Senior XI" }
      ]
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_players": 45,
  "total_pages": 3,
  "has_previous": false,
  "has_next": true
}
```

### Response: 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

### Response: 422 Unprocessable Entity

```json
{
  "detail": [
    {
      "loc": ["query", "team_id"],
      "msg": "team_id and unassigned are mutually exclusive",
      "type": "value_error"
    }
  ]
}
```

---

## GET /api/v1/players/{player_id}

Retrieve a single player by ID, including inactive profiles.

### Path Parameters

| Parameter | Type |
|-----------|------|
| `player_id` | UUID |

### Authorization

Any authenticated user.

### Response: 200 OK

Same shape as individual `PlayerResponse` in the list (with `teams` array).

### Response: 404 Not Found

```json
{
  "detail": "Player not found."
}
```

---

## POST /api/v1/players

Create a new player profile.

### Authorization

Head Coach, Assistant Coach only.

### Request Body

```json
{
  "first_name": "Virat",
  "last_name": "Kohli",
  "date_of_birth": "1988-11-05",
  "bio": "Aggressive top-order batter",
  "batting_style": "right",
  "bowling_style": "right-arm medium",
  "player_type": "batter",
  "player_metadata": {}
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `first_name` | string | Yes | 1–100 chars |
| `last_name` | string | Yes | 1–100 chars |
| `date_of_birth` | date | Yes | YYYY-MM-DD |
| `bio` | string \| null | No | Maximum 2,000 characters |
| `batting_style` | BattingStyle | Yes | `right` or `left` |
| `bowling_style` | BowlingStyle | Yes | One of 8 values |
| `player_type` | PlayerType | Yes | `batter`, `bowler`, `all-rounder`, `wicket-keeper` |
| `player_metadata` | object | No | Defaults to `{}`; bounded JSON (8 KiB, 4 container levels, 50 keys/object, 100 characters/key, 50 items/array, 2,000 characters/string) |

These write bounds also apply to the update endpoint. Directory and detail
responses preserve compliant values unchanged. For legacy rows that bypassed
write validation, biographies are projected to their first 2,000 characters
and non-compliant metadata is returned as `{}`. This response projection does
not alter the stored row.

### Response: 201 Created

Returns the created `PlayerResponse` (including server-generated `id`, `created_at`, `version_number: 1`, `teams: []`).

### Response: 409 Conflict

```json
{
  "detail": "A player with this name and date of birth already exists."
}
```

### Response: 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action"
}
```

---

## PUT /api/v1/players/{player_id}

Update an existing player profile with optimistic concurrency control.

### Path Parameters

| Parameter | Type |
|-----------|------|
| `player_id` | UUID |

### Authorization

Head Coach, Assistant Coach only.

### Request Body

All fields are optional except `version_number`.

```json
{
  "first_name": "Virat",
  "last_name": "Kohli",
  "bio": "Updated bio text",
  "version_number": 3
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `version_number` | integer | **Yes** | Must match current server version |

### Response: 200 OK

Returns the updated `PlayerResponse`. `version_number` incremented by 1.

### Response: 404 Not Found

```json
{
  "detail": "Player not found."
}
```

### Response: 409 Conflict (Stale Version)

```json
{
  "detail": "Stale version 3 for player 3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

**Frontend behavior**: Display conflict message, offer "Reload" action.

### Response: 403 Forbidden

```json
{
  "detail": "You do not have permission to perform this action"
}
```

**Frontend behavior**: Display clear permissions error (FR-054).

---

## Team Filter Values

The list of teams available for filtering is obtained from the existing `GET /api/v1/teams` endpoint (used to populate the team filter dropdown). The frontend maps this into filter options:

- `null` → "All Players"
- `team.id` → team name from the teams list
- `"__unassigned__"` → "Unassigned Players" (sent as `unassigned=true` to backend)
