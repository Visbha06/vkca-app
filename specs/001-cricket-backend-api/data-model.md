# Data Model: Cricket Team Management Backend API

**Date**: 2026-07-08

**Reference**: [spec.md](./spec.md), [research.md](./research.md)

All tables use `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, and `version_number INTEGER NOT NULL DEFAULT 1`. Timestamps are server-generated; client-supplied values are ignored.

---

## Entity-Relationship Summary

```
Users ────────────────────────────────┐
                                      │ (no FK; auth deferred)
Players ──< TeamPlayers >── Teams     │
  │                    │              │
  │                    │              │
  ├──< MatchBattingPerformance >── Matches
  ├──< MatchBowlingPerformance >── Matches
  ├──< MatchFieldingPerformance >── Matches
  │
  ├── PlayerBattingStats (aggregate, split by format)
  └── PlayerBowlingStats (aggregate, split by format)

DataSyncLogs (standalone audit table; no FKs)
```

---

## Table Definitions

### 1. Users

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(100) | NOT NULL | |
| email | VARCHAR(255) | NOT NULL, UNIQUE | |
| hashed_password | VARCHAR(255) | NOT NULL | Pre-hashed; hashing algorithm deferred to auth spec |
| role | VARCHAR(20) | NOT NULL, CHECK (role IN ('head coach', 'assistant coach', 'player')) | |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Soft-deactivation support |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Server-generated |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Server-generated; updated on every write |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC; incremented on every update |

**Unique constraint**: `UNIQUE(email)`

### 2. Players

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(100) | NOT NULL | |
| date_of_birth | DATE | NOT NULL | |
| bio | TEXT | NULLABLE | |
| batting_style | VARCHAR(10) | NOT NULL, CHECK (batting_style IN ('right', 'left')) | |
| bowling_style | VARCHAR(30) | NOT NULL, CHECK (bowling_style IN ('right-arm fast', 'right-arm medium', 'right-arm off-break', 'right-arm leg-break', 'left-arm fast', 'left-arm medium', 'left-arm orthodox', 'left-arm unorthodox')) |
| player_type | VARCHAR(20) | NOT NULL, CHECK (player_type IN ('batter', 'bowler', 'all-rounder', 'wicket-keeper')) | |
| player_metadata | JSONB | NULLABLE, DEFAULT '{}' | Free-form extensible blob; no internal schema enforcement |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Inactive players hidden from default list; queryable by ID |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

**Unique constraint**: `UNIQUE(first_name, last_name, date_of_birth)`

### 3. Teams

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| name | VARCHAR(200) | NOT NULL | No uniqueness constraint |
| age_group | VARCHAR(50) | NOT NULL | e.g., "U12", "U14", "U16", "Senior" |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

### 4. TeamPlayers

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| team_id | UUID | NOT NULL, FK → teams(id) | Composite PK with player_id |
| player_id | UUID | NOT NULL, FK → players(id) | Composite PK with team_id |
| joined_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | When player joined the squad |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

**Primary key**: `(team_id, player_id)`
**Unique constraint**: `UNIQUE(team_id, player_id)` — enforced by PK

### 5. Matches

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| match_date | DATE | NOT NULL | |
| format | VARCHAR(10) | NOT NULL, CHECK (format IN ('T20', 'one-day', 'test', 'other')) | |
| opponent_name | VARCHAR(200) | NOT NULL | |
| venue | VARCHAR(200) | NULLABLE | |
| result | VARCHAR(200) | NULLABLE | Free-text; e.g., "Won by 5 wickets" |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

### 6. MatchBattingPerformance

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| player_id | UUID | NOT NULL, FK → players(id) | |
| match_id | UUID | NOT NULL, FK → matches(id) | |
| runs_scored | INTEGER | NOT NULL, DEFAULT 0 | |
| balls_faced | INTEGER | NOT NULL, DEFAULT 0 | |
| dismissal | VARCHAR(20) | NOT NULL, CHECK (dismissal IN ('not out', 'caught', 'bowled', 'lbw', 'run out', 'stumped', 'other')) | |
| fours | INTEGER | NOT NULL, DEFAULT 0 | |
| sixes | INTEGER | NOT NULL, DEFAULT 0 | |
| notes | TEXT | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

**Unique constraint**: `UNIQUE(player_id, match_id)` — one batting performance row per player per match

### 7. MatchBowlingPerformance

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| player_id | UUID | NOT NULL, FK → players(id) | |
| match_id | UUID | NOT NULL, FK → matches(id) | |
| overs_bowled | NUMERIC(5,1) | NOT NULL, DEFAULT 0 | e.g., 4.0, 4.3 (4 overs 3 balls) |
| maidens | INTEGER | NOT NULL, DEFAULT 0 | |
| runs_conceded | INTEGER | NOT NULL, DEFAULT 0 | |
| wickets_taken | INTEGER | NOT NULL, DEFAULT 0 | |
| wides | INTEGER | NOT NULL, DEFAULT 0 | |
| notes | TEXT | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

**Unique constraint**: `UNIQUE(player_id, match_id)` — one bowling performance row per player per match

### 8. MatchFieldingPerformance

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| player_id | UUID | NOT NULL, FK → players(id) | |
| match_id | UUID | NOT NULL, FK → matches(id) | |
| catches | INTEGER | NOT NULL, DEFAULT 0 | |
| stumpings | INTEGER | NOT NULL, DEFAULT 0 | |
| run_outs | INTEGER | NOT NULL, DEFAULT 0 | |
| dropped_catches | INTEGER | NOT NULL, DEFAULT 0 | |
| notes | TEXT | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

**Unique constraint**: `UNIQUE(player_id, match_id)` — one fielding performance row per player per match

### 9. PlayerBattingStats

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| player_id | UUID | NOT NULL, FK → players(id) | |
| format | VARCHAR(10) | NOT NULL, CHECK (format IN ('T20', 'one-day', 'test', 'other')) | |
| matches | INTEGER | NOT NULL, DEFAULT 0 | |
| innings | INTEGER | NOT NULL, DEFAULT 0 | |
| not_outs | INTEGER | NOT NULL, DEFAULT 0 | |
| runs | INTEGER | NOT NULL, DEFAULT 0 | |
| balls_faced | INTEGER | NOT NULL, DEFAULT 0 | |
| high_score | INTEGER | NOT NULL, DEFAULT 0 | |
| hundreds | INTEGER | NOT NULL, DEFAULT 0 | |
| fifties | INTEGER | NOT NULL, DEFAULT 0 | |
| ducks | INTEGER | NOT NULL, DEFAULT 0 | |
| fours | INTEGER | NOT NULL, DEFAULT 0 | |
| sixes | INTEGER | NOT NULL, DEFAULT 0 | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC on recalculation |

**Unique constraint**: `UNIQUE(player_id, format)` — one aggregate row per player per format
**Note**: Integer types use BIGINT to accommodate realistic career totals (no overflow risk for cricket statistics).

### 10. PlayerBowlingStats

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| player_id | UUID | NOT NULL, FK → players(id) | |
| format | VARCHAR(10) | NOT NULL, CHECK (format IN ('T20', 'one-day', 'test', 'other')) | |
| matches | INTEGER | NOT NULL, DEFAULT 0 | |
| innings | INTEGER | NOT NULL, DEFAULT 0 | |
| overs_bowled | NUMERIC(7,1) | NOT NULL, DEFAULT 0 | |
| runs_conceded | INTEGER | NOT NULL, DEFAULT 0 | |
| wickets | INTEGER | NOT NULL, DEFAULT 0 | |
| best_bowled | VARCHAR(20) | NULLABLE | Free-text; e.g., "5/32" |
| maidens | INTEGER | NOT NULL, DEFAULT 0 | |
| four_wicket_hauls | INTEGER | NOT NULL, DEFAULT 0 | |
| five_wicket_hauls | INTEGER | NOT NULL, DEFAULT 0 | |
| wides | INTEGER | NOT NULL, DEFAULT 0 | |
| catches | INTEGER | NOT NULL, DEFAULT 0 | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC on recalculation |

**Unique constraint**: `UNIQUE(player_id, format)` — one aggregate row per player per format

### 11. DataSyncLogs

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default `gen_random_uuid()` | |
| source | VARCHAR(100) | NOT NULL | e.g., "player-update", "stats-recalc" |
| status | VARCHAR(20) | NOT NULL | e.g., "success", "conflict", "error" |
| target_table | VARCHAR(100) | NOT NULL | Table name where event occurred |
| error_message | TEXT | NULLABLE | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| version_number | INTEGER | NOT NULL, DEFAULT 1 | OCC |

**No foreign keys** — DataSyncLogs is a standalone audit log.

---

## Relationships

| From | To | Type | FK Column |
|------|----|------|-----------|
| TeamPlayers | Teams | Many-to-1 | team_id |
| TeamPlayers | Players | Many-to-1 | player_id |
| MatchBattingPerformance | Players | Many-to-1 | player_id |
| MatchBattingPerformance | Matches | Many-to-1 | match_id |
| MatchBowlingPerformance | Players | Many-to-1 | player_id |
| MatchBowlingPerformance | Matches | Many-to-1 | match_id |
| MatchFieldingPerformance | Players | Many-to-1 | player_id |
| MatchFieldingPerformance | Matches | Many-to-1 | match_id |
| PlayerBattingStats | Players | Many-to-1 | player_id |
| PlayerBowlingStats | Players | Many-to-1 | player_id |

---

## Index Strategy

| Table | Index | Purpose |
|-------|-------|---------|
| Players | `(first_name, last_name, date_of_birth)` UNIQUE | Duplicate detection |
| Users | `(email)` UNIQUE | Duplicate detection |
| TeamPlayers | `(team_id, player_id)` PK | Roster queries |
| MatchBattingPerformance | `(match_id)` | Match-centric lookups |
| MatchBattingPerformance | `(player_id, match_id)` UNIQUE | Deduplication |
| MatchBowlingPerformance | `(match_id)` | Match-centric lookups |
| MatchBowlingPerformance | `(player_id, match_id)` UNIQUE | Deduplication |
| MatchFieldingPerformance | `(match_id)` | Match-centric lookups |
| MatchFieldingPerformance | `(player_id, match_id)` UNIQUE | Deduplication |
| PlayerBattingStats | `(player_id, format)` UNIQUE | Stat lookup |
| PlayerBowlingStats | `(player_id, format)` UNIQUE | Stat lookup |

---

## OCC Version Flow

```
Client submits entity with version_number=N
  → Server: SELECT version_number FROM table WHERE id = :id
  → If DB version_number > N:
      → INSERT INTO DataSyncLogs (source, status, target_table, error_message)
      → Return HTTP 409 Conflict
  → If DB version_number == N:
      → UPDATE ... SET ... version_number = N + 1, updated_at = NOW()
      → Return updated entity with version_number = N + 1
```
