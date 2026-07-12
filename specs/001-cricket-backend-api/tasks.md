# Tasks: Cricket Team Management Backend API

**Input**: Design documents from `/specs/001-cricket-backend-api/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit tests are MANDATORY per the constitution. E2E test waived (backend-only, no frontend). Integration tests for OCC conflict and atomic transaction flows per spec requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/` for source, `backend/tests/` for tests
- Project structure from plan.md: `backend/src/models/`, `backend/src/schemas/`, `backend/src/routes/`, `backend/src/services/`, `backend/src/middleware/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency management, and basic structure

- [X] T001 Create backend source directory structure: `backend/src/models/`, `backend/src/schemas/`, `backend/src/routes/`, `backend/src/services/`, `backend/src/middleware/`, `backend/tests/unit/`, `backend/tests/integration/`
- [X] T002 [P] Add FastAPI, Pydantic v2, SQLAlchemy 2.0, asyncpg, Alembic dependencies to `backend/pyproject.toml` via `uv add`
- [X] T003 [P] Add pytest, pytest-asyncio, httpx, pytest-mock dev dependencies to `backend/pyproject.toml` via `uv add --dev`
- [X] T004 [P] Configure environment management: create `backend/.env.example` with DATABASE_URL, ensure `backend/src/config.py` loads settings via Pydantic `BaseSettings`
- [X] T005 [P] Configure Ruff linting settings in `backend/pyproject.toml` (extend existing config)
- [X] T006 Scaffold FastAPI app entry point in `backend/src/main.py` with `/api/v1` prefix router, health check endpoint, and CORS middleware

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database & Migrations

- [X] T007 Setup async SQLAlchemy engine and session factory in `backend/src/database.py` using DATABASE_URL from config
- [X] T008 Initialize Alembic in `backend/src/migrations/` with async template (`alembic init -t async`)
- [X] T009 Configure Alembic `env.py` to use async SQLAlchemy engine and auto-detect models from `backend/src/models/`

### Enums

- [X] T010 [P] Create `backend/src/enums.py` with all Python `StrEnum` classes: `UserRole`, `BattingStyle`, `BowlingStyle`, `PlayerType`, `MatchFormat`, `DismissalType`

### Base Model & Mixins

- [X] T011 Create SQLAlchemy declarative base and mixin classes in `backend/src/models/base.py` with `TimestampMixin` (created_at, updated_at with server_default), `VersionMixin` (version_number), and `UUIDMixin` (id with gen_random_uuid)

### Middleware & Cross-Cutting

- [X] T012 [P] Create OCC version check helper in `backend/src/services/occ.py` — function `check_and_increment_version(session, model, entity_id, incoming_version)` that runs UPDATE with WHERE version=:incoming, returns new version or raises `StaleVersionError`
- [X] T013 [P] Create DataSyncLogs model in `backend/src/models/data_sync_log.py` (standalone, no FKs)
- [X] T014 [P] Create DataSyncLogs Pydantic create schema in `backend/src/schemas/data_sync_log.py`
- [X] T015 [P] Create global error handlers in `backend/src/middleware/error_handlers.py` — map `StaleVersionError` to HTTP 409, SQLAlchemy `IntegrityError` to HTTP 409, generic exceptions to HTTP 500
- [X] T016 [P] Create Pydantic `BaseRequestSchema` mixin in `backend/src/schemas/base.py` that excludes `created_at`, `updated_at`, and `version_number` from request models — ensures client-supplied timestamps and version numbers are silently dropped by FastAPI. All entity request schemas MUST inherit from this mixin.
- [X] T017 Create Alembic initial migration for DataSyncLogs table in `backend/src/migrations/versions/` and apply it (`alembic upgrade head`)

**Checkpoint**: Foundation ready — database connected, migrations running, enums defined, base model with timestamps and versioning ready, OCC helper and error handlers in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Manage Player Profiles (Priority: P1) 🎯 MVP

**Goal**: Coaches can create and retrieve player profiles with playing style, bio, and metadata. Duplicate detection on (first_name, last_name, date_of_birth). OCC enforced on updates.

**Independent Test**: POST a player → GET player list → verify fields returned. PUT with stale version_number → verify HTTP 409. POST duplicate → verify HTTP 409.

### Tests for User Story 1 (MANDATORY unit tests) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T018 [P] [US1] Unit tests for Player Pydantic schemas (create/update/response) in `backend/tests/unit/test_player_schemas.py`
- [ ] T019 [P] [US1] Unit tests for Player routes (create, list, update with OCC) in `backend/tests/unit/test_player_routes.py`

### Implementation for User Story 1

- [ ] T020 [P] [US1] Create Player SQLAlchemy model in `backend/src/models/player.py` with all columns: id, first_name, last_name, date_of_birth, bio, batting_style, bowling_style, player_type, player_metadata (JSONB), is_active, plus TimestampMixin and VersionMixin
- [ ] T021 [P] [US1] Create Player Pydantic schemas in `backend/src/schemas/player.py`: `PlayerCreate`, `PlayerUpdate`, `PlayerResponse`
- [ ] T022 [US1] Create PlayerService in `backend/src/services/player_service.py`: `create_player()`, `list_players()` (active only), `get_player_by_id()`, `update_player()` — with OCC check and duplicate detection (SELECT before INSERT for composite unique)
- [ ] T023 [US1] Create Players router in `backend/src/routes/players.py`: `POST /api/v1/players`, `GET /api/v1/players`
- [ ] T024 [US1] Register Players router in `backend/src/main.py` under `/api/v1`
- [ ] T025 Create Alembic migration for Players table in `backend/src/migrations/versions/` with UNIQUE constraint on (first_name, last_name, date_of_birth) and apply it

**Checkpoint**: Players CRUD working — create, list, update with OCC, duplicate detection. Ready for MVP demonstration.

---

## Phase 4: User Story 6 - Manage User Accounts (Priority: P3)

**Goal**: Administrators can create and list user accounts with roles. Email uniqueness enforced.

**Independent Test**: POST a user → GET user list → verify hashed_password excluded from response. POST duplicate email → verify HTTP 409.

### Tests for User Story 6 (MANDATORY unit tests) ⚠️

- [ ] T026 [P] [US6] Unit tests for User Pydantic schemas (create/response, password exclusion) in `backend/tests/unit/test_user_schemas.py`
- [ ] T027 [P] [US6] Unit tests for User routes (create, list, duplicate detection) in `backend/tests/unit/test_user_routes.py`

### Implementation for User Story 6

- [ ] T028 [P] [US6] Create User SQLAlchemy model in `backend/src/models/user.py` with all columns: id, first_name, last_name, email (UNIQUE), hashed_password, role, is_active, plus TimestampMixin and VersionMixin
- [ ] T029 [P] [US6] Create User Pydantic schemas in `backend/src/schemas/user.py`: `UserCreate`, `UserResponse` (excludes hashed_password)
- [ ] T030 [US6] Create UserService in `backend/src/services/user_service.py`: `create_user()`, `list_users()` — with email duplicate detection (SELECT before INSERT; DB UNIQUE constraint as final guard)
- [ ] T031 [US6] Create Users router in `backend/src/routes/users.py`: `POST /api/v1/users`, `GET /api/v1/users`
- [ ] T032 [US6] Register Users router in `backend/src/main.py` under `/api/v1`
- [ ] T033 Create Alembic migration for Users table in `backend/src/migrations/versions/` with UNIQUE constraint on email and apply it

**Checkpoint**: User account CRUD working — create, list, password excluded from responses, email duplicate detection.

---

## Phase 5: User Story 2 - Create and Manage Teams (Priority: P2)

**Goal**: Coaches can create teams (name, age_group) and assign players to team squads. Duplicate membership prevented.

**Independent Test**: POST a team → add player via roster endpoint → verify membership created. Add same player again → verify HTTP 409.

### Tests for User Story 2 (MANDATORY unit tests) ⚠️

- [ ] T034 [P] [US2] Unit tests for Team and TeamPlayer Pydantic schemas in `backend/tests/unit/test_team_schemas.py`
- [ ] T035 [P] [US2] Unit tests for Team routes (create, list, add player) in `backend/tests/unit/test_team_routes.py`

### Implementation for User Story 2

- [ ] T036 [P] [US2] Create Team SQLAlchemy model in `backend/src/models/team.py` with columns: id, name, age_group, plus TimestampMixin and VersionMixin
- [ ] T037 [P] [US2] Create TeamPlayer SQLAlchemy model in `backend/src/models/team_player.py` with composite PK (team_id, player_id), joined_at, plus TimestampMixin and VersionMixin
- [ ] T038 [P] [US2] Create Team Pydantic schemas in `backend/src/schemas/team.py`: `TeamCreate`, `TeamResponse`, `TeamPlayerResponse`
- [ ] T039 [US2] Create TeamService in `backend/src/services/team_service.py`: `create_team()`, `list_teams()`, `add_player_to_team()` — with duplicate membership check
- [ ] T040 [US2] Create Teams router in `backend/src/routes/teams.py`: `POST /api/v1/teams`, `GET /api/v1/teams`, `POST /api/v1/teams/{team_id}/players/{player_id}`
- [ ] T041 [US2] Register Teams router in `backend/src/main.py` under `/api/v1`
- [ ] T042 Create Alembic migration for Teams and TeamPlayers tables in `backend/src/migrations/versions/` with FK constraints and apply it

**Checkpoint**: Teams working — create squads, list teams, add players to squads with duplicate prevention.

---

## Phase 6: User Story 3 - Record Match Events (Priority: P2)

**Goal**: Coaches can create match records with date, format, opponent, venue, and result. List all matches.

**Independent Test**: POST a match → GET match list → verify fields returned.

### Tests for User Story 3 (MANDATORY unit tests) ⚠️

- [ ] T043 [P] [US3] Unit tests for Match Pydantic schemas in `backend/tests/unit/test_match_schemas.py`
- [ ] T044 [P] [US3] Unit tests for Match routes (create, list) in `backend/tests/unit/test_match_routes.py`

### Implementation for User Story 3

- [ ] T045 [P] [US3] Create Match SQLAlchemy model in `backend/src/models/match.py` with columns: id, match_date, format, opponent_name, venue, result, plus TimestampMixin and VersionMixin
- [ ] T046 [P] [US3] Create Match Pydantic schemas in `backend/src/schemas/match.py`: `MatchCreate`, `MatchResponse`
- [ ] T047 [US3] Create MatchService in `backend/src/services/match_service.py`: `create_match()`, `list_matches()`
- [ ] T048 [US3] Create Matches router in `backend/src/routes/matches.py`: `POST /api/v1/matches`, `GET /api/v1/matches`
- [ ] T049 [US3] Register Matches router in `backend/src/main.py` under `/api/v1`
- [ ] T050 Create Alembic migration for Matches table in `backend/src/migrations/versions/` and apply it

**Checkpoint**: Matches working — create match events, list all matches.

---

## Phase 7: User Story 4 & 5 - Match Performances & Career Statistics (Priority: P1/P3)

**Goal**: Coaches can submit a batch of player performances (batting/bowling/fielding, each independently optional) for a completed match in one atomic transaction. The system automatically recalculates aggregate career stats. Coaches can then query lifetime batting and bowling stats split by format.

**Independent Test**: Create player + match → POST batch performance with batting only → verify MatchBattingPerformance written AND PlayerBattingStats updated in same transaction. Submit batch with invalid player_id → verify full rollback (no orphaned records). GET stats → verify aggregates match sum of performances.

### Tests for User Story 4 & 5 (MANDATORY unit tests) ⚠️

- [ ] T051 [P] [US4] Unit tests for performance Pydantic schemas (batch payload, optional sub-objects) in `backend/tests/unit/test_performance_schemas.py`
- [ ] T052 [P] [US5] Unit tests for stats Pydantic schemas in `backend/tests/unit/test_stats_schemas.py`
- [ ] T053 [US4] Integration test for atomic transaction: submit valid batch → verify all 3 performance tables + aggregate stats updated; submit invalid batch → verify full rollback in `backend/tests/integration/test_atomic_performance.py`

### Implementation for User Story 4 (Match Performances)

- [ ] T054 [P] [US4] Create MatchBattingPerformance SQLAlchemy model in `backend/src/models/match_batting_performance.py` with UNIQUE(player_id, match_id), FK to players and matches, plus TimestampMixin and VersionMixin
- [ ] T055 [P] [US4] Create MatchBowlingPerformance SQLAlchemy model in `backend/src/models/match_bowling_performance.py` with UNIQUE(player_id, match_id), FK to players and matches, plus TimestampMixin and VersionMixin
- [ ] T056 [P] [US4] Create MatchFieldingPerformance SQLAlchemy model in `backend/src/models/match_fielding_performance.py` with UNIQUE(player_id, match_id), FK to players and matches, plus TimestampMixin and VersionMixin
- [ ] T057 [P] [US4] Create PlayerBattingStats SQLAlchemy model in `backend/src/models/player_batting_stats.py` with UNIQUE(player_id, format), FK to players, all aggregate columns, plus TimestampMixin and VersionMixin
- [ ] T058 [P] [US4] Create PlayerBowlingStats SQLAlchemy model in `backend/src/models/player_bowling_stats.py` with UNIQUE(player_id, format), FK to players, all aggregate columns, plus TimestampMixin and VersionMixin
- [ ] T059 [P] [US4] Create performance Pydantic schemas in `backend/src/schemas/performance.py`: `BattingPerformance`, `BowlingPerformance`, `FieldingPerformance` (all with defaults), `PlayerPerformance` (with optional sub-objects), `BatchPerformanceRequest`, `BatchPerformanceResponse`
- [ ] T060 [US4] Create PerformanceService in `backend/src/services/performance_service.py` with `submit_batch_performance(match_id, performances)` using `async with session.begin()` for atomic transaction:
  - Validate all player_ids and match_id exist (abort if any missing)
  - Insert MatchBattingPerformance rows where batting sub-object present
  - Insert MatchBowlingPerformance rows where bowling sub-object present
  - Insert MatchFieldingPerformance rows where fielding sub-object present
  - SELECT existing aggregate stats (batting + bowling) for each player per format
  - Recalculate and UPSERT PlayerBattingStats and PlayerBowlingStats rows with OCC version check
  - Commit transaction

### Implementation for User Story 5 (Career Statistics — Read-Only)

- [ ] T061 [P] [US5] Create stats Pydantic schemas in `backend/src/schemas/stats.py`: `BattingStatsResponse`, `BowlingStatsResponse`
- [ ] T062 [US5] Create StatsService in `backend/src/services/stats_service.py`: `get_batting_stats(player_id, format)`, `get_bowling_stats(player_id, format)` — query aggregate tables, return empty array if no data
- [ ] T063 [US5] Create Stats router in `backend/src/routes/stats.py`: `GET /api/v1/players/{player_id}/stats/batting`, `GET /api/v1/players/{player_id}/stats/bowling` — with optional `format` query parameter

### Integration for US4 & US5

- [ ] T064 [US4] Create Performances router in `backend/src/routes/performances.py`: `POST /api/v1/matches/{match_id}/performances`
- [ ] T065 Register Performances and Stats routers in `backend/src/main.py` under `/api/v1`
- [ ] T066 Create Alembic migration for all 5 new tables (MatchBattingPerformance, MatchBowlingPerformance, MatchFieldingPerformance, PlayerBattingStats, PlayerBowlingStats) with FK constraints, UNIQUE constraints, and indexes in `backend/src/migrations/versions/` and apply it

**Checkpoint**: Full match data pipeline working — submit performances atomically, aggregate stats auto-calculated, career stats queryable by format.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation

- [ ] T067 [P] Integration test for OCC end-to-end flow (update player → stale version → 409 + DataSyncLogs entry) in `backend/tests/integration/test_occ_conflict.py`
- [ ] T067a [P] Automated performance assertions: verify SC-002 (batch submission for 11 players <3s) and SC-003 (OCC 409 response <1s) using `time.monotonic()` bounds in `backend/tests/integration/test_performance_timing.py`
- [ ] T068 Run full quickstart.md validation flow from `specs/001-cricket-backend-api/quickstart.md` — execute all 12 steps and verify all 8 success criteria pass
- [ ] T069 [P] Write feature documentation in `docs/cricket-backend-api.md` (MANDATORY per constitution Principle XII — concise version of spec reflecting what was built)
- [ ] T070 [P] Code cleanup: remove dead code, ensure consistent naming, verify all Ruff linting passes
- [ ] T071 Run all unit and integration tests, verify 100% pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1: Players (Phase 3)**: Depends on Foundational — no story dependencies. 🎯 MVP
- **US6: Users (Phase 4)**: Depends on Foundational — independent of other stories
- **US2: Teams (Phase 5)**: Depends on Foundational + US1 (Players must exist for TeamPlayer FKs)
- **US3: Matches (Phase 6)**: Depends on Foundational — independent of other stories (no FK to Players at creation time)
- **US4+US5: Performances & Stats (Phase 7)**: Depends on Foundational + US1 (Players) + US3 (Matches) — FKs to both
- **Polish (Phase 8)**: Depends on all desired user stories being complete

> **Note on US7 (Data Sync Conflict Logging)**: User Story 7 from spec.md does not have a dedicated phase in tasks.md. Its work is intentionally dispersed: OCC version check + DataSyncLogs model/schema are in Foundational (T012–T014), error handlers in T015, and end-to-end OCC conflict integration test in Polish (T067). This dispersal keeps the DataSyncLogs infrastructure where it's consumed rather than isolating it in a late phase.

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational
    ↓
    ├── Phase 3: US1 - Players (P1) 🎯 MVP
    │       ↓
    │       ├── Phase 5: US2 - Teams (P2)
    │       ↓
    │       Phase 7: US4+US5 - Performances & Stats (P1/P3)
    │           ↑
    ├── Phase 6: US3 - Matches (P2) ────┘
    │
    ├── Phase 4: US6 - Users (P3) [parallel with US1+US2+US3]
    │
    Phase 8: Polish
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before schemas before services before routes
- Apply migration after all models for that phase are defined
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T001–T006: directory creation, dependency adds, config, linting can all run in parallel
- **Phase 2**: T010 (enums) parallel with T011 (base model). T012–T016 (middleware, OCC, error handlers, DataSyncLogs model) all in parallel
- **Phase 3 (US1)**: T018+T019 tests in parallel. T020 (model) + T021 (schemas) in parallel
- **Phase 4 (US6)**: Fully parallel with Phase 5 (US2) and Phase 6 (US3) since they don't share FKs
- **Phase 5 (US2)**: T036+T037 models in parallel. T034+T035 tests in parallel
- **Phase 7 (US4+US5)**: T054–T059 (6 models + schemas) all parallel. T061 parallel with implementation
- **Phase 8**: T067, T069, T070 all parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests and models for US1 together:
Task: "Unit tests for Player Pydantic schemas in backend/tests/unit/test_player_schemas.py"
Task: "Unit tests for Player routes in backend/tests/unit/test_player_routes.py"
Task: "Create Player SQLAlchemy model in backend/src/models/player.py"
Task: "Create Player Pydantic schemas in backend/src/schemas/player.py"
# Then: PlayerService → PlayerRoutes → register router → migration
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup → Phase 2: Foundational
2. Complete Phase 3: US1 - Player Profiles
3. **STOP and VALIDATE**: Player CRUD works, OCC enforced, duplicates detected
4. Deploy/demo if ready

### Incremental Delivery

| Stage | Phases | What's New | Cumulative Value |
|-------|--------|------------|------------------|
| MVP | 1, 2, 3 | Player registry with OCC | Foundation for all features |
| +Users | 4 | User account CRUD | Staff can be provisioned |
| +Teams | 5 | Squad management | Organize players into teams |
| +Matches | 6 | Match events | Record game metadata |
| +Performances | 7 | Batch stats entry + career stats | Full cricket data pipeline |
| +Polish | 8 | Documentation, cleanup, validation | Production-ready |

### Recommended Approach

1. Phases 1-2 sequentially (blocking foundation)
2. Phase 3 (US1) for MVP
3. Phases 4, 5, 6 in any order after US1 (they're largely independent)
4. Phase 7 last (has the most dependencies)
5. Phase 8 to close
