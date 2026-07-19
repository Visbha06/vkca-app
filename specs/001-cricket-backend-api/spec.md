# Feature Specification: Cricket Team Management Backend API

**Feature Branch**: `001-cricket-backend-api`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "Backend-only FastAPI service with PostgreSQL for managing cricket players, teams, matches, performance statistics, and data sync integrity with optimistic concurrency control."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Player Profiles (Priority: P1)

A coach or player member needs to create and maintain cricket player profiles that capture personal details, playing style, and career statistics. This is the foundation of the entire system — without player records, no other feature has meaning.

**Why this priority**: Players are the atomic unit of the system. Teams, match performances, and statistics all reference players. This must exist first.

**Independent Test**: Can be fully tested by creating a player profile via the API, retrieving it, and verifying all fields are stored and returned correctly. Delivers a working player registry.

**Acceptance Scenarios**:

1. **Given** no existing player, **When** an authorized user submits a new player profile with first name, last name, date of birth, batting style, bowling style, and player type, **Then** the system creates the player record with a unique ID and returns the full profile.
2. **Given** an existing player, **When** an authorized user updates the player's bio or playing style with the correct version_number, **Then** the system updates the record and increments the version_number.
3. **Given** an existing player with version_number 5 in the database, **When** an authorized user submits an update with version_number 4, **Then** the system returns HTTP 409 Conflict and logs the conflict in DataSyncLogs.
4. **Given** multiple players exist (some active, some inactive), **When** an authorized user requests the player list, **Then** the system returns only active player profiles.
5. **Given** an existing player with first_name "John", last_name "Smith", and date_of_birth "2005-03-15", **When** an authorized user attempts to create another player with the same first_name, last_name, and date_of_birth, **Then** the system returns HTTP 409 Conflict and does not create a duplicate.

---

### User Story 2 - Create and Manage Teams (Priority: P2)

A coach needs to organize players into teams (squads) by age group and assign players to those squads. This enables roster management and team-based filtering of statistics.

**Why this priority**: Teams are the organizing structure above individual players. Required before match data has context.

**Independent Test**: Can be fully tested by creating a team, adding players to it, and retrieving the team roster. Delivers squad management capability.

**Acceptance Scenarios**:

1. **Given** no existing team, **When** an authorized user creates a team with a name and age group, **Then** the system creates the team record and returns its details.
2. **Given** an existing team, **When** an authorized user lists all teams, **Then** the system returns all team records with their age groups.
3. **Given** an existing team and an existing player not yet in that team, **When** an authorized user adds the player to the team via the roster endpoint, **Then** the system creates a TeamPlayers link record with the joined_at timestamp.
4. **Given** a team with assigned players, **When** an authorized user requests the team details, **Then** the system returns the team along with its current player roster.

---

### User Story 3 - Record Match Events (Priority: P2)

A coach or player member needs to record match events — the date, format, opponent, venue, and result — as the parent container for all performance data collected during that game.

**Why this priority**: Matches are the events that produce all performance statistics. Must exist before match performances can be submitted.

**Independent Test**: Can be fully tested by creating a match record and retrieving it. Delivers a match ledger.

**Acceptance Scenarios**:

1. **Given** a scheduled game, **When** an authorized user creates a match record with date, format, opponent, venue, and result, **Then** the system stores the match and returns its details.
2. **Given** existing matches, **When** an authorized user requests the match list, **Then** the system returns all match records.

---

### User Story 4 - Submit Match Performances with Atomic Stats Update (Priority: P1)

After a match concludes, a coach or player member submits a batch of player performances — batting, bowling, and fielding metrics for each player who participated. The system must accept this batch in a single atomic transaction, write to the three performance tables, and automatically recalculate the player's career aggregate statistics before committing.

**Why this priority**: This is the core operational workflow. Match data entry is the primary daily activity for coaches, and the atomic accumulator rule is a critical data-integrity requirement.

**Independent Test**: Can be fully tested by creating a match, submitting a batch performance payload for one player, and verifying that the performance records are written AND the player's career stats are updated in the same atomic operation. Delivers the core data-entry loop.

**Acceptance Scenarios**:

1. **Given** an existing match and a player with existing career stats, **When** an authorized user submits a batch performance payload containing batting (runs, balls, dismissal), bowling (overs, maidens, runs, wickets, wides), and fielding (catches, stumpings, run outs, dropped catches) metrics for that player, **Then** the system writes to all three performance tables and recalculates the player's batting and bowling aggregate stats in a single transaction.
2. **Given** a player whose career batting stats show 500 runs from 10 innings before the match, **When** a performance is submitted for that player with 75 runs scored in 1 innings, **Then** after the transaction commits, the player's batting stats show 575 runs from 11 innings.
3. **Given** a batch payload that fails validation (e.g., missing required fields), **Then** the entire transaction rolls back — no performance records are written and no aggregate stats are updated.
4. **Given** a batch payload containing performances for multiple players, **When** the submission processes successfully, **Then** each player's performance records are written and each player's aggregate stats are recalculated atomically.
5. **Given** a player who only batted in a match (did not bowl and had no fielding contributions), **When** a performance is submitted with only the batting sub-object (bowling and fielding absent), **Then** only the MatchBattingPerformance record is created and only the player's batting aggregate stats are recalculated — no bowling or fielding records are written.

---

### User Story 5 - View Player Career Statistics (Priority: P3)

A coach wants to review a player's lifetime batting or bowling statistics, broken down by match format (T20, one-day, test, other), to inform selection decisions.

**Why this priority**: Read-only reporting on data that is already being collected. Provides immediate coaching value once match data is entered.

**Independent Test**: Can be fully tested by querying the batting and bowling stats endpoints for a player who has performance data, and verifying the returned aggregates match the sum of individual match performances across formats.

**Acceptance Scenarios**:

1. **Given** a player with batting performances in multiple T20 matches, **When** an authorized user requests the player's batting stats for the T20 format, **Then** the system returns aggregated totals (matches, innings, runs, balls faced, high score, hundreds, fifties, ducks, fours, sixes) for T20 only.
2. **Given** a player with no batting performances, **When** an authorized user requests the player's batting stats, **Then** the system returns stats with zero values for all numeric fields.
3. **Given** a player with bowling performances across multiple formats, **When** an authorized user requests the player's bowling stats for the one-day format, **Then** the system returns aggregated totals for one-day matches only.

---

### User Story 6 - Manage User Accounts (Priority: P3)

An administrator needs to create accounts for coaches and player members who will operate the system. Each user has a role that determines their access level.

**Why this priority**: User management gates access to all other features, but authentication is deferred to a future spec. Basic CRUD for user records enables the system to be used once auth is added.

**Independent Test**: Can be fully tested by creating a user account and listing all users. Delivers an identity registry.

**Acceptance Scenarios**:

1. **Given** no existing user account for a new coach, **When** an administrator creates a user with first name, last name, email, hashed password, and role, **Then** the system stores the user record and returns it (excluding the hashed password from responses).
2. **Given** existing users, **When** an administrator requests the user list, **Then** the system returns all user accounts with their roles and active status.
3. **Given** an existing user with email "coach@example.com", **When** an administrator attempts to create another user with the same email, **Then** the system returns HTTP 409 Conflict and does not create a duplicate.

---

### User Story 7 - Data Sync Conflict Logging (Priority: P3)

When a concurrent modification conflict occurs (OCC version mismatch), the system must log the incident so operators can audit and resolve data synchronization issues.

**Why this priority**: Supporting infrastructure for the OCC rule. Valuable for operational visibility but not a primary user workflow.

**Independent Test**: Can be fully tested by triggering a version conflict on a player update and verifying a DataSyncLogs entry is created with the correct source, status, and target table.

**Acceptance Scenarios**:

1. **Given** a version conflict during a player update, **When** the system returns HTTP 409, **Then** a DataSyncLogs entry is created recording the source, status "conflict", the target table, and the error message.
2. **Given** a successful data import or update, **When** the operation completes, **Then** a DataSyncLogs entry may be created with status "success" for audit purposes.

---

### Edge Cases

- What happens when a match performance is submitted but the match_id does not exist? The system must reject the request with a clear error (HTTP 404 or 422) and not create orphaned performance records.
- What happens when a batch performance payload includes a player_id that does not exist? The entire transaction must roll back — no partial writes.
- What happens when adding a player to a team they are already a member of? The system must reject the duplicate with an appropriate error (HTTP 409) rather than creating a duplicate TeamPlayers row.
- What happens when a user attempts to update a player profile with a version_number that does not match (stale data)? The system must reject with HTTP 409 and log the conflict.
- What happens when the batch performance payload is empty (zero performances)? The system must reject with a validation error.
- How does the system handle a player who only batted (no bowling or fielding stats) in a match? Bowling and fielding performance objects should be optional within the batch payload — only the provided metrics are written.
- What happens when recalculating aggregate stats results in an overflow (extremely large numbers)? The database schema must use appropriate integer types to accommodate realistic career totals.
- What happens when a user is deactivated (is_active = false)? Deactivated users must not be able to authenticate (future), but existing records they created remain intact.
- What happens when created_at or updated_at timestamps are manually supplied in the request payload? The system must ignore any client-supplied timestamps and always use the server-generated UTC timestamp.
- What happens when a user attempts to create a player with the same first_name, last_name, and date_of_birth as an existing player? The system must reject with HTTP 409 Conflict and a clear error message identifying the duplicate.
- What happens when an administrator attempts to create a user with an email address already in use? The system must reject with HTTP 409 Conflict.
- What happens when a player is deactivated (is_active = false)? The player no longer appears in the default player list, but their profile, match performance history, and career statistics remain accessible via direct ID lookup. The player cannot be added to new teams.

## Clarifications

### Session 2026-07-08

- Q: Are batting, bowling, and fielding performances all required in a match performance submission? → A: No — each performance type (batting, bowling, fielding) is independently optional. A player may not have batted, bowled, or contributed in the field during a given match.
- Q: What uniqueness rules should the system enforce across Users, Players, and Teams? → A: Email must be unique for Users. Players are unique by the composite of first_name + last_name + date_of_birth. Team names have no uniqueness constraint.
- Q: Should the Players entity support deactivation like Users? → A: Yes — add an `is_active` flag to Players. Inactive players are hidden from the default player list but their statistics and historical match performances remain fully queryable.
- Q: Should this spec include a bulk data import endpoint? → A: No — DataSyncLogs is for OCC conflict and manual-entry audit logging only. Bulk import is out of scope for this spec and would be a separate feature.

## Requirements *(mandatory)*

### Functional Requirements

**Core Entity Management**

- **FR-001**: System MUST allow authorized users to create new player profiles with first_name, last_name, date_of_birth, bio, batting_style, bowling_style, player_type, and player_metadata (JSON).
- **FR-002**: System MUST allow authorized users to retrieve a list of all player profiles.
- **FR-003**: System MUST allow authorized users to create new team records with name and age_group.
- **FR-004**: System MUST allow authorized users to retrieve a list of all teams.
- **FR-005**: System MUST allow authorized users to add a player to a team squad, creating a TeamPlayers association with the joined_at timestamp.
- **FR-006**: System MUST allow administrators to create user accounts with first_name, last_name, email, hashed_password, and role.
- **FR-007**: System MUST allow administrators to retrieve a list of all user accounts (excluding hashed_password from responses).

**Match Ledger**

- **FR-008**: System MUST allow authorized users to create match records with match_date, format, opponent_name, venue, and result.
- **FR-009**: System MUST allow authorized users to retrieve a list of all matches.
- **FR-010**: System MUST accept a batch performance payload for a match containing an array of player performances. Each player performance object MUST include a player_id and MAY independently include a batting metrics sub-object, a bowling metrics sub-object, a fielding metrics sub-object, or any combination thereof — each sub-object is independently optional because a player may not have batted, bowled, or contributed in the field during a given match.
- **FR-011**: System MUST write each player's batting performance to MatchBattingPerformance, bowling performance to MatchBowlingPerformance, and fielding performance to MatchFieldingPerformance within a single atomic database transaction.
- **FR-012**: System MUST reject the entire batch performance submission if any player_id or match_id reference is invalid, rolling back all writes.

**Read-Only Aggregate Statistics**

- **FR-013**: System MUST return a player's lifetime batting statistics (matches, innings, not_outs, runs, balls_faced, high_score, hundreds, fifties, ducks, fours, sixes) split by format.
- **FR-014**: System MUST return a player's lifetime bowling statistics (matches, innings, overs, runs_conceded, wickets, best_bowled, maidens, four_wicket_hauls, five_wicket_hauls, wides, catches) split by format.

**Backend Rules**

- **FR-015**: System MUST enforce optimistic concurrency control (OCC) on all PUT and POST operations that update player career stats or profiles: if the incoming version_number is lower than the database version_number, the system MUST return HTTP 409 Conflict and log the incident to DataSyncLogs.
- **FR-016**: System MUST automatically recalculate and update the corresponding PlayerBattingStats and/or PlayerBowlingStats rows when a match performance is submitted, within the same atomic transaction.
- **FR-017**: System MUST automatically set the created_at and updated_at fields to the current UTC timestamp on every row insert and update, ignoring any client-supplied timestamp values.

**Data Integrity**

- **FR-018**: All tables MUST include created_at and updated_at timestamp columns.
- **FR-019**: All tables that support concurrent modification MUST include a version_number column for optimistic concurrency control.
- **FR-020**: System MUST log data synchronization events and conflicts to DataSyncLogs with source, status, target_table, and error_message fields.
- **FR-021**: System MUST enforce the following uniqueness constraints: user email must be unique across all Users; player records must be unique by the composite of first_name + last_name + date_of_birth (attempting to create a duplicate must return HTTP 409 Conflict). Team names are not unique.
- **FR-022**: Players table MUST include an `is_active` flag (default true). The default player list endpoint MUST return only active players. Individual player queries by ID MUST return the player regardless of active status, so historical statistics remain accessible.

### Key Entities

- **User**: Represents a coach, administrator, or player member who operates the system. Key attributes: name, email (unique across all users), role (head coach / assistant coach / player), active status.
- **Player**: A cricket player whose profile and statistics are tracked. Key attributes: name, date of birth, bio, batting style (right/left), bowling style (8 variants), player type (batter / bowler / all-rounder / wicket-keeper), extensible metadata (JSON), active status. Uniqueness enforced on the composite of first_name + last_name + date_of_birth. Inactive players are excluded from the default list but remain queryable by ID.
- **Team**: A squad organized by age group. Key attributes: name, age group. Links to Players via TeamPlayers.
- **TeamPlayer**: A cross-reference linking a Player to a Team with the date they joined the squad.
- **Match**: A recorded game event. Key attributes: date, format (T20 / one-day / test / other), opponent, venue, result.
- **MatchBattingPerformance**: A player's batting output for a specific match. Key attributes: runs scored, balls faced, dismissal type, boundaries, notes.
- **MatchBowlingPerformance**: A player's bowling output for a specific match. Key attributes: overs bowled, maidens, runs conceded, wickets taken, wides, notes.
- **MatchFieldingPerformance**: A player's fielding output for a specific match. Key attributes: catches, stumpings, run outs, dropped catches, notes.
- **PlayerBattingStats**: Lifetime aggregate batting statistics for a player, split by format. Includes matches, innings, not outs, runs, balls faced, high score, centuries, half-centuries, ducks, fours, sixes.
- **PlayerBowlingStats**: Lifetime aggregate bowling statistics for a player, split by format. Includes matches, innings, overs bowled, runs conceded, wickets, best bowling figures, maidens, four/five-wicket hauls, wides, catches.
- **DataSyncLog**: An audit record tracking OCC conflict events and data synchronization outcomes. Key attributes: source, status, target table, error message. Used for operational visibility into concurrent modification conflicts and manual-entry audit trails; bulk data import is out of scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A coach can create a player profile and retrieve it via the API in under 2 seconds.
- **SC-002**: A batch match performance submission for 11 players (33 performance records across three tables) completes within a single atomic transaction in under 3 seconds.
- **SC-003**: When a version conflict occurs on a player update, the system returns HTTP 409 with a logged DataSyncLog entry within 1 second.
- **SC-004**: A coach can retrieve a player's complete career batting or bowling statistics (all formats) in under 1 second.
- **SC-005**: 100% of match performance submissions that fail validation result in zero partial writes — no orphaned performance records or stale aggregate stats.
- **SC-006**: 100% of batch performance submissions correctly recalculate the target player's aggregate statistics to within a 1-run and 1-wicket tolerance of manual calculation.
- **SC-007**: All API responses include server-generated timestamps with no leakage of client-supplied timestamp values.
- **SC-008**: Adding a player to a team they already belong to returns a clear conflict error (HTTP 409) with no duplicate association created.

## Assumptions

- Authentication and authorization enforcement is deferred to a future specification. The user endpoints in this spec create and list user records but do not enforce login or role-based access control. A placeholder mechanism (e.g., an admin bypass header or hardcoded test user) is acceptable for development and testing.
- The database runs as PostgreSQL in Docker, as stated in the project's technology stack.
- The `player_metadata` JSON field on the Player entity is a free-form extensible blob; its schema is not validated by the API beyond being valid JSON.
- The `hashed_password` field accepts a pre-hashed value from the client. The hashing algorithm and password policy are out of scope for this spec and will be addressed in the future authentication spec.
- Match "result" is stored as a free-text field (e.g., "Won by 5 wickets", "Lost by 32 runs", "Draw"). No structured result parsing is required at this stage.
- The best_bowled field on PlayerBowlingStats stores the best bowling figures as a string (e.g., "5/32") rather than a structured object.
- Performance statistics for a player who only bats (and does not bowl or field) in a match will have null/absent bowling and fielding sub-objects in the batch payload — the API handles partial performance submissions gracefully.
- The `format` enum value "other" serves as a catch-all for non-standard match formats not covered by T20, one-day, or test.
- Database migrations will follow the Constitution requirement (Principle VII) for versioned, reversible migration scripts tested against the Docker PostgreSQL instance.
- Frontend work is explicitly out of scope for this specification. No UI components, pages, or frontend state management are included.
- Bulk data import (CSV/JSON upload) is out of scope for this specification. DataSyncLogs serves OCC conflict and manual-entry audit logging only. All data entry occurs through the individual CRUD and batch performance endpoints defined in this spec.
