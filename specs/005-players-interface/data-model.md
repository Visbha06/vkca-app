# Data Model: Players Interface

**Date**: 2026-07-22
**Feature**: 005-players-interface

## Overview

No new database tables or schema migrations are required. The feature extends the query layer on the existing `players`, `teams`, and `team_players` tables. The only new data structures are response schemas for pagination and team-summary embedding.

---

## Existing Entities (Unchanged)

### Player
See `backend/src/models/player.py`. Key fields used by this feature:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | |
| `first_name` | String(100) | |
| `last_name` | String(100) | Default ordering column |
| `date_of_birth` | Date | |
| `bio` | Text? | Optional bio for details |
| `batting_style` | BattingStyle (enum) | right / left |
| `bowling_style` | BowlingStyle (enum) | 8 values |
| `player_type` | PlayerType (enum) | batter / bowler / all-rounder / wicket-keeper |
| `player_metadata` | JSONB | Key-value metadata dict |
| `is_active` | Boolean | Filtered to `true` in list queries |
| `version_number` | Integer | OCC version for updates |
| `created_at` | DateTime (UTC) | |
| `updated_at` | DateTime (UTC) | |

### Team
See `backend/src/models/team.py`. Fields used:

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID (PK) | |
| `name` | String(200) | Displayed on cards and in details |

### TeamPlayer (Join)
See `backend/src/models/team_player.py`.

| Field | Type | Notes |
|-------|------|-------|
| `team_id` | UUID (PK, FK → teams.id) | |
| `player_id` | UUID (PK, FK → players.id) | |
| `joined_at` | DateTime (UTC) | |

**Relationship**: Many-to-many. A player can belong to zero or more teams. The `team_players` table is the join table.

---

## New/Extended Pydantic Schemas

### TeamSummary

Lightweight team reference for embedding in player responses.

```python
class TeamSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
```

### Extended PlayerResponse

The existing `PlayerResponse` is extended with an optional `teams` field.

```python
class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    bio: str | None
    batting_style: BattingStyle
    bowling_style: BowlingStyle
    player_type: PlayerType
    player_metadata: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version_number: int
    teams: list[TeamSummary] = []   # NEW
```

**Validation rules**:
- `teams` is always present (defaults to `[]` for players with no team).
- `first_name`, `last_name` min 1 char, max 100 chars (existing validation).
- No new validation rules beyond the existing `PlayerResponse`.

### PaginatedPlayerResponse

```python
class PaginatedPlayerResponse(BaseModel):
    players: list[PlayerResponse]
    page: int
    page_size: int
    total_players: int
    total_pages: int
    has_previous: bool
    has_next: bool
```

**Validation rules**:
- `page` ≥ 1
- `page_size` between 1 and 100
- `total_players` ≥ 0
- `total_pages` = `ceil(total_players / page_size)`
- `has_previous` = `page > 1`
- `has_next` = `page < total_pages`

---

## New Frontend Types (TypeScript)

Mirroring backend schemas per Constitution X:

```typescript
// frontend/src/types/player.ts

export interface TeamSummary {
  id: string
  name: string
}

export interface PlayerResponse {
  id: string
  first_name: string
  last_name: string
  date_of_birth: string  // ISO date string
  bio: string | null
  batting_style: BattingStyle
  bowling_style: BowlingStyle
  player_type: PlayerType
  player_metadata: Record<string, unknown>
  is_active: boolean
  created_at: string       // ISO datetime
  updated_at: string       // ISO datetime
  version_number: number
  teams: TeamSummary[]
}

export interface PaginatedPlayerResponse {
  players: PlayerResponse[]
  page: number
  page_size: number
  total_players: number
  total_pages: number
  has_previous: boolean
  has_next: boolean
}

export interface PlayerCreatePayload {
  first_name: string
  last_name: string
  date_of_birth: string       // YYYY-MM-DD
  bio?: string | null
  batting_style: BattingStyle
  bowling_style: BowlingStyle
  player_type: PlayerType
  player_metadata?: Record<string, unknown>
}

export interface PlayerUpdatePayload {
  first_name?: string
  last_name?: string
  date_of_birth?: string      // YYYY-MM-DD
  bio?: string | null
  batting_style?: BattingStyle
  bowling_style?: BowlingStyle
  player_type?: PlayerType
  player_metadata?: Record<string, unknown>
  is_active?: boolean
  version_number: number       // required for OCC
}

export type BattingStyle = 'right' | 'left'

export type BowlingStyle =
  | 'right-arm fast'
  | 'right-arm medium'
  | 'right-arm off-break'
  | 'right-arm leg-break'
  | 'left-arm fast'
  | 'left-arm medium'
  | 'left-arm orthodox'
  | 'left-arm unorthodox'

export type PlayerType = 'batter' | 'bowler' | 'all-rounder' | 'wicket-keeper'
```

---

## State Transitions

### Player Card Selection
```
Player List (idle) → Click/Enter on card → Player Details Modal open
Player Details Modal open → Escape/Close click → Player List (idle, focus restored to card)
```

### Add Player Flow
```
Player List → "Add Player" button → Add Player Modal (empty form)
Add Player Modal → Submit success → Modal closes, list refreshes
Add Player Modal → Validation error → Form shows errors, modal stays
Add Player Modal → Close with unsaved changes → Confirm dialog
  → Confirm: modal closes
  → Cancel: return to form
```

### Edit Player Flow
```
Player Details Modal → "Edit" button → Edit Player Modal (pre-filled)
Edit Player Modal → Submit success → Modal closes, list refreshes
Edit Player Modal → HTTP 409 (OCC conflict) → Conflict message + Reload button
  → Reload: re-fetch player, replace form values
Edit Player Modal → HTTP 403 (forbidden) → Permissions error message
Edit Player Modal → Close with unsaved changes → Confirm dialog
```

### Team Filter
```
Player List (page N) → Select team filter → Page resets to 1, fetch new results
Player List → Select "Unassigned" → Page resets to 1, fetch unassigned players
Filtered list (no results) → Select "All Players" → Page 1, full list
```

---

## Relationships

```
Player ←→ TeamPlayer (one-to-many: player has one TeamPlayer row per team membership)
TeamPlayer → Team (many-to-one: each TeamPlayer row references one Team)
Player → Team (many-to-many: through TeamPlayer join table)
```

For the player-list query, teams are eagerly loaded via SQLAlchemy relationships or explicit JOINs to populate the `teams` field on each `PlayerResponse`.
