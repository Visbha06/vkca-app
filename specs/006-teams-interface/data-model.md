# Data Model: Teams Interface

**Feature**: 006-teams-interface | **Date**: 2026-07-25

## Entity Changes

### New Enum: AgeGroup

```python
class AgeGroup(StrEnum):
    J = "J"        # Juniors
    U11 = "U11"
    U13 = "U13"
    U15 = "U15"
```

Added to `backend/src/enums.py`.

---

### Modified Entity: Team

**Table**: `teams`

| Column | Type | Change | Notes |
|--------|------|--------|-------|
| `id` | `UUID` (PK) | Existing | |
| `name` | `String(200)` | Existing | |
| `age_group` | `String(50)` | **Constrained** | Add DB check constraint: `IN ('J','U11','U13','U15')` |
| `version_number` | `Integer` | Existing | Used for OCC on PUT |
| `created_at` | `DateTime(tz)` | Existing | |
| `updated_at` | `DateTime(tz)` | Existing | |

**New constraints**:
- `CHECK (age_group IN ('J', 'U11', 'U13', 'U15'))`

**Validation rules** (application-level):
- Name: 1–200 characters, required
- Age group: Must be a valid `AgeGroup` enum value
- Name uniqueness: Case-insensitive, whitespace-normalized, scoped to same age group

---

### Modified Entity: TeamPlayer (Team Roster Membership)

**Table**: `team_players`

| Column | Type | Change | Notes |
|--------|------|--------|-------|
| `team_id` | `UUID` (PK, FK → teams.id) | Existing | |
| `player_id` | `UUID` (PK, FK → players.id) | Existing | |
| `roster_order` | `Integer` | **New** | NOT NULL, DEFAULT 0, 1-based ordering |
| `joined_at` | `DateTime(tz)` | Existing | |
| `version_number` | `Integer` | Existing | |
| `created_at` | `DateTime(tz)` | Existing | |
| `updated_at` | `DateTime(tz)` | Existing | |

**New index**:
- `CREATE INDEX ix_team_players_team_order ON team_players (team_id, roster_order)`

**Primary key**: Composite `(team_id, player_id)` — unchanged.

---

### Unchanged Entities (Referenced)

**Player** — no changes. Key attributes used:
- `id` (UUID PK)
- `first_name` (String(100))
- `last_name` (String(100))
- `is_active` (Boolean)

**User** — no changes. Key attributes used:
- `id` (UUID PK)
- `role` (UserRole enum: HEAD_COACH, ASSISTANT_COACH, PLAYER)

---

## Schema Changes (Pydantic)

### TeamCreate (new shape)

```python
class TeamCreate(BaseRequestSchema):
    name: str = Field(min_length=1, max_length=200)
    age_group: AgeGroup
    player_ids: list[UUID] = Field(min_length=7, max_length=15)
```

### TeamUpdate (new)

```python
class TeamUpdate(BaseRequestSchema):
    name: str = Field(min_length=1, max_length=200)
    age_group: AgeGroup
    player_ids: list[UUID] = Field(min_length=7, max_length=15)
    version_number: int = Field(ge=1)
```

### TeamResponse (extended)

Add `player_count: int` field for roster count display on cards.

```python
class TeamResponse(BaseModel):
    id: UUID
    name: str
    age_group: AgeGroup
    player_count: int
    created_at: datetime
    updated_at: datetime
    version_number: int
```

### PaginatedTeamResponse (new)

```python
class PaginatedTeamResponse(BaseModel):
    teams: list[TeamResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_teams: int
    total_pages: int
```

### TeamRosterPlayerResponse (new)

```python
class TeamRosterPlayerResponse(BaseModel):
    player_id: UUID
    first_name: str
    last_name: str
    is_active: bool
    roster_order: int
```

---

## State Transitions

### Team Lifecycle

```
Created (via POST) → Active (default) → [Deletion out of scope]
```

Teams have no soft-delete or deactivation. All created teams are visible.

### Roster Lifecycle

```
Empty (0 players) → Populated (7–15 players) via POST
Populated → Updated (7–15 players) via PUT (full replacement)
```

Roster can never drop below 7 via edit. No individual add/remove endpoint.

### Roster Member is_active

```
Player created → is_active = true
Player deactivated → is_active = false
  → Remains in existing rosters (visible with muted styling)
  → Cannot be selected in roster form dropdowns
  → Can be removed when roster is edited (replaced with active player)
```

---

## Relationship Diagram

```
Team 1──* TeamPlayer *──1 Player
│                            │
│ (team_id, player_id       │ (id, first_name,
│  roster_order)            │  last_name, is_active)
│                            │
▼                            ▼
team.name                   player.first_name
team.age_group              player.last_name
team.version_number         player.is_active
```

---

## Migration Plan

**Alembic migration** (`versions/<hash>_add_age_group_and_roster_order.py`):

1. Add check constraint on `teams.age_group` (if not already present):
   ```sql
   ALTER TABLE teams ADD CONSTRAINT ck_teams_age_group
   CHECK (age_group IN ('J', 'U11', 'U13', 'U15'));
   ```

2. Add `roster_order` column to `team_players`:
   ```sql
   ALTER TABLE team_players ADD COLUMN roster_order INTEGER NOT NULL DEFAULT 0;
   ```

3. Add index:
   ```sql
   CREATE INDEX ix_team_players_team_order ON team_players (team_id, roster_order);
   ```

**No data migration needed**: Existing teams and team_players get default values.

**Rollback** (for development convenience):
- Drop index, drop column, drop constraint. Not required for production.
