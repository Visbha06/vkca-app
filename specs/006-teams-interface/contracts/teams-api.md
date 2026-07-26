# API Contracts: Teams Interface

**Feature**: 006-teams-interface | **Date**: 2026-07-25

Base path: `/api/v1/teams`

---

## 1. List Teams (Paginated)

```
GET /api/v1/teams?page=1&page_size=12
```

**Auth**: Authenticated (any role)

**Query Parameters**:

| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `page` | integer | 1 | ≥1 |
| `page_size` | integer | 12 | 1–100 |

**Response** `200 OK`:

```json
{
  "teams": [
    {
      "id": "uuid",
      "name": "Falcons",
      "age_group": "U13",
      "player_count": 12,
      "created_at": "2026-07-25T10:00:00Z",
      "updated_at": "2026-07-25T10:00:00Z",
      "version_number": 1
    }
  ],
  "page": 1,
  "page_size": 12,
  "total_teams": 25,
  "total_pages": 3
}
```

**Ordering**: `name ASC, age_group ASC, id ASC`

**Errors**:
- `401` — Not authenticated
- `422` — Invalid query parameters

---

## 2. Create Team (Atomic + Roster)

```
POST /api/v1/teams
```

**Auth**: Head Coach, Assistant Coach

**Request Body**:

```json
{
  "name": "Falcons",
  "age_group": "U13",
  "player_ids": [
    "uuid-1",
    "uuid-2",
    "...",
    "uuid-12"
  ]
}
```

**Constraints**:
- `name`: 1–200 chars, required
- `age_group`: Must be `J`, `U11`, `U13`, or `U15`
- `player_ids`: 7–15 UUIDs, no duplicates, all must be existing active players
- Name must be unique within age group (case-insensitive, whitespace-normalized)

**Response** `201 Created`:

```json
{
  "id": "uuid",
  "name": "Falcons",
  "age_group": "U13",
  "player_count": 12,
  "created_at": "2026-07-25T10:00:00Z",
  "updated_at": "2026-07-25T10:00:00Z",
  "version_number": 1
}
```

**Errors**:
- `400` — Validation error (fewer than 7 players, more than 15, duplicate players)
- `401` — Not authenticated
- `403` — Not authorized (Player role)
- `404` — Player not found
- `409` — Team name already exists in this age group
- `422` — Invalid request body

**Atomicity**: Entire operation (team + roster) succeeds or rolls back.

---

## 3. Update Team (Atomic + Roster)

```
PUT /api/v1/teams/{team_id}
```

**Auth**: Head Coach, Assistant Coach

**Request Body**:

```json
{
  "name": "Eagles",
  "age_group": "U15",
  "player_ids": [
    "uuid-3",
    "uuid-5",
    "...",
    "uuid-9"
  ],
  "version_number": 1
}
```

**Constraints**: Same as Create, plus:
- `version_number` must match current server value

**Response** `200 OK`:

```json
{
  "id": "uuid",
  "name": "Eagles",
  "age_group": "U15",
  "player_count": 10,
  "created_at": "2026-07-25T10:00:00Z",
  "updated_at": "2026-07-25T12:00:00Z",
  "version_number": 2
}
```

**Errors**:
- `400` — Validation error
- `401` — Not authenticated
- `403` — Not authorized
- `404` — Team not found
- `409` — Stale version (version_number mismatch) or name conflict
- `422` — Invalid request body

**Atomicity**: Roster is fully replaced in the same transaction. Delete-all + insert-new within transaction boundary.

---

## 4. Get Team Roster

```
GET /api/v1/teams/{team_id}/players
```

**Auth**: Authenticated (any role)

**Response** `200 OK`:

```json
{
  "team_id": "uuid",
  "players": [
    {
      "player_id": "uuid-1",
      "first_name": "Virat",
      "last_name": "Kohli",
      "is_active": true,
      "roster_order": 1
    },
    {
      "player_id": "uuid-3",
      "first_name": "Rohit",
      "last_name": "Sharma",
      "is_active": false,
      "roster_order": 2
    }
  ]
}
```

**Ordering**: `roster_order ASC`

**Includes**: All existing roster members (including inactive).
Inactive players have `is_active: false` and should be visually differentiated in the UI.

**Errors**:
- `401` — Not authenticated
- `404` — Team not found

---

## 5. Player Search for Dropdowns

```
GET /api/v1/players?search=koh&page=1&page_size=50
```

**Auth**: Authenticated (any role)  
**Existing endpoint** — no changes needed.

**Query Parameters**:

| Param | Type | Default | Constraints |
|-------|------|---------|-------------|
| `search` | string | — | Matches first_name, last_name, or full name (ilike) |
| `page` | integer | 1 | ≥1 |
| `page_size` | integer | 20 | 1–100 |

**Response**: Standard `PaginatedPlayerResponse` (existing shape, unchanged).

**Notes**:
- Returns only active players
- Frontend should request `page_size=50` for dropdown with client-side deduplication

---

## Error Response Shape (all endpoints)

All errors follow the existing project convention:

```json
{
  "detail": "Human-readable error message"
}
```

**Status codes used**:
- `400` — Bad request (validation)
- `401` — Not authenticated
- `403` — Not authorized
- `404` — Resource not found
- `409` — Conflict (duplicate name, stale version)
- `422` — Unprocessable content (invalid request body)
