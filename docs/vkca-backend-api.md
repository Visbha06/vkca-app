# VKCA Backend API

The VKCA backend is the FastAPI service that powers the VK Cricket Academy application.

It provides authenticated, role-aware APIs for academy users, players, teams, coaches, calendar events, matches, player performances, statistics, authentication/session management, and academy business auditing.

PostgreSQL is the system of record, and all application endpoints are served below:

```text
/api/v1
```

The backend uses an asynchronous SQLAlchemy + asyncpg stack and is organized into routes, services, repositories, schemas, database models, and middleware.

---

## Backend Responsibilities

The API currently supports:

- Authentication and session management
- Role-based authorization
- User and profile management
- Player management
- Team and roster management
- Coach account and assignment management
- Academy calendar and recurring events
- Match and performance data
- Player statistics
- Authentication/security auditing
- Business activity auditing

---

## Authentication and Sessions

Authentication is handled under:

```text
/api/v1/auth
```

The application uses short-lived JWT access tokens together with rotating refresh sessions.

### Session Model

- Users authenticate with email and password.
- Successful login returns a short-lived access token.
- Refresh credentials are stored in an HTTP-only cookie.
- A separate CSRF cookie is used for double-submit CSRF protection.
- Refresh sessions rotate when refreshed.
- Invalid or expired sessions return HTTP 401.
- Login attempts are rate limited.
- Disabled users cannot continue using authenticated sessions.
- Current-user responses include metadata for the active session.

### Authentication Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Authenticate and establish a session |
| POST | `/auth/refresh` | Rotate the refresh session and issue a new access token |
| GET | `/auth/me` | Return the authenticated user and session |
| PATCH | `/auth/me` | Update editable profile information |
| GET | `/auth/audit-log` | Read authentication/security audit events; Head Coach only |
| POST | `/auth/logout` | End the current session |

Authentication mutations that rely on refresh cookies require a valid CSRF token.

---

## Roles and Authorization

The backend defines three application roles:

```text
head_coach
assistant_coach
player
```

Authorization is enforced in the backend even when corresponding frontend controls are hidden.

### Head Coach

Head Coaches have administrative access across the application, including:

- Player management
- Team management
- Coach management
- Calendar management
- Business audit review
- User and account administration

### Assistant Coach

Assistant Coaches have operational access, including:

- Player management
- Team management
- Calendar event management
- Coach-directory access

Head Coach-only administrative actions remain restricted.

### Player

Players primarily receive authenticated read access to relevant academy data.

They cannot perform coach-only mutations or access restricted administrative audit information.

---

## Players

Player APIs are served under:

```text
/api/v1/players
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/players` | Create a player |
| GET | `/players` | List active players with filtering and pagination |
| GET | `/players/{player_id}` | Retrieve one player |
| PUT | `/players/{player_id}` | Update a player |

Player creation and updates require Head Coach or Assistant Coach access.

Player listing supports:

- Server-side pagination
- Team filtering
- Unassigned-player filtering
- Search

`team_id` and `unassigned=true` are mutually exclusive.

Direct player lookup may return inactive players, while normal directory listing returns active players.

### Optimistic Concurrency

Mutable player records use a `version_number`.

Updates must use the current version. Stale updates are rejected instead of overwriting newer data.

Successful player mutations also generate business audit events.

---

## Teams and Rosters

Team APIs are served under:

```text
/api/v1/teams
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/teams` | Create a team and roster |
| GET | `/teams` | List teams with server-side pagination |
| PUT | `/teams/{team_id}` | Replace team details and roster |
| GET | `/teams/{team_id}/players` | Retrieve the ordered roster |
| POST | `/teams/{team_id}/players/{player_id}` | Add one player to a roster |

The single-player roster endpoint remains available as a legacy operation.

Current team creation and editing workflows can operate on the complete intended roster atomically.

### Team Mutation Behavior

Team mutations require Head Coach or Assistant Coach access.

Team create/update workflows validate the requested state before committing changes.

The API rejects conditions such as:

- Invalid players
- Duplicate memberships
- Conflicting team names
- Invalid team state
- Stale entity versions

Successful team and roster mutations generate business audit events.

---

## Coaches

Coach APIs are served under:

```text
/api/v1/coaches
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/coaches` | Create an Assistant Coach |
| GET | `/coaches` | List coaches |
| GET | `/coaches/{coach_id}` | Retrieve coach details |
| PUT | `/coaches/{coach_id}/teams` | Replace coach team assignments |

Coach listing supports:

```text
status=active|inactive|all
page=<number>
page_size=<number>
```

### Permissions

Head Coaches can:

- Create Assistant Coach accounts
- View coach details
- Manage coach team assignments
- Perform account-management operations available through the coach and user APIs

Assistant Coaches can browse permitted coach information but cannot perform Head Coach-only administrative actions.

### Temporary Passwords

Creating an Assistant Coach returns a generated temporary password exactly once in the creation response.

The plaintext password is not designed to remain retrievable afterward.

### Team Assignments

Coach team-assignment updates replace the full desired assignment set atomically.

Inactive coaches cannot have their assignments modified until reactivated.

Successful coach-management mutations generate business audit events.

---

## Academy Calendar

Calendar APIs are served under:

```text
/api/v1/calendar
```

Calendar reads are available to authenticated users.

Calendar mutations require Head Coach or Assistant Coach access.

Academy dates and times are interpreted using:

```text
America/Los_Angeles
```

### Read Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/calendar/events` | Retrieve effective event instances for a date range |
| GET | `/calendar/today` | Retrieve events for the current academy-local date |
| GET | `/calendar/instances/{occurrence_id}` | Retrieve one event occurrence |

Range requests use:

```text
start_date=YYYY-MM-DD
end_date=YYYY-MM-DD
```

Invalid or excessively large ranges are rejected.

### Mutation Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/calendar/events` | Create a standalone or recurring event |
| PATCH | `/calendar/events/{event_id}` | Update a standalone event |
| DELETE | `/calendar/events/{event_id}` | Delete a standalone event |
| PATCH | `/calendar/instances/{occurrence_id}` | Edit one recurring occurrence |
| DELETE | `/calendar/instances/{occurrence_id}` | Delete one recurring occurrence |
| PATCH | `/calendar/series/{series_id}` | Update an entire recurring series |
| DELETE | `/calendar/series/{series_id}` | Delete an entire recurring series |

### Supported Calendar Behavior

The calendar supports:

- Practice events
- Games
- Miscellaneous events
- Timed events
- Permitted all-day events
- Academy age-group scopes
- All Academy scope
- Weekly recurrence
- Yearly recurrence
- Recurrence end dates
- Recurrence occurrence counts
- Individual occurrence exceptions
- Moved occurrences
- Deleted occurrences
- Entire-series edits
- Optimistic concurrency

Recurring occurrences are calculated for bounded requested ranges rather than pre-generating unlimited future rows.

### Calendar Concurrency

The owning calendar event's `version_number` is the canonical optimistic-concurrency version for standalone events and recurring series.

Occurrence exceptions maintain separate versioning where applicable.

Stale mutations return HTTP 409 and do not overwrite newer state.

---

## Business Audit Log

Business activity APIs are served under:

```text
/api/v1/audit-log
```

These endpoints are restricted to Head Coaches.

The business audit system is separate from authentication/security auditing.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/audit-log` | Retrieve filtered and paginated business events |
| GET | `/audit-log/recent` | Retrieve recent academy activity |
| GET | `/audit-log/actors` | Retrieve historical actor options for filtering |

Business audit history records successful academy/domain changes such as:

- Player creation and updates
- Team creation and updates
- Roster changes
- Coach-management actions
- Coach team-assignment updates
- Calendar changes

### Audit Record Design

Business audit records contain historical snapshots of the actor and target.

This allows an event to remain understandable even if the underlying actor or target is later:

- Renamed
- Deactivated
- Removed

Audit records are append-only and are not exposed through ordinary update or delete operations.

### Transaction Integrity

Business audit events are written as part of the same transaction as the domain change they describe.

If the domain mutation fails, the corresponding audit event is rolled back as well.

One externally initiated mutation normally produces one business audit event, even if several database rows are changed internally.

Audit metadata is sanitized and must not expose:

- Credentials
- Tokens
- Secrets
- Raw request payloads
- Stack traces
- Unrestricted personal information

---

## Matches and Performances

Match and performance APIs are exposed through:

```text
/api/v1/matches
/api/v1/performances
```

The backend supports match records and player-performance submission.

Performance workflows can contain batting, bowling, and fielding data according to the request schema.

Multi-player performance batches are atomic.

All referenced entities are validated before persistence, and a failed batch does not leave partially written performance or aggregate data.

---

## Statistics

Statistics APIs are exposed through:

```text
/api/v1/stats
```

The backend provides accumulated cricket statistics, including batting and bowling aggregates.

Historical statistics remain available independently of whether a player currently appears in the active player directory.

---

## Users

User-management APIs are exposed through:

```text
/api/v1/users
```

These routes support account-oriented workflows separate from player profiles.

User operations participate in the application's authorization, session, and optimistic-concurrency rules where applicable.

---

## Health Check

The API exposes:

```http
GET /api/v1/health
```

Successful response:

```json
{
  "status": "ok"
}
```

---

## API Surface Overview

The current backend mounts the following major route groups:

```text
/api/v1/auth
/api/v1/audit-log
/api/v1/calendar
/api/v1/coaches
/api/v1/matches
/api/v1/performances
/api/v1/players
/api/v1/stats
/api/v1/teams
/api/v1/users
/api/v1/health
```

The generated OpenAPI schema is the authoritative source for the exact current request and response models.

---

## Transaction Model

The backend uses asynchronous SQLAlchemy transactions.

Multi-record workflows are designed to commit atomically.

Examples include:

- Team and roster changes
- Performance batch submission
- Coach creation and assignments
- Coach team-assignment replacement
- Calendar event and recurrence mutations
- Business audit creation alongside audited domain changes

If an operation fails before commit, its related database changes are rolled back together.

---

## Optimistic Concurrency Control

Mutable domain entities use optimistic concurrency through `version_number`.

When a client submits stale state, the backend returns an HTTP 409 conflict where OCC applies.

The stale request does not overwrite newer data.

This behavior is used across workflows such as:

- Player updates
- Team updates
- Coach-management changes
- Calendar mutations

---

## Request Correlation

Audited mutation routes may accept:

```text
X-Request-ID
```

The request identifier may be stored alongside the resulting business audit event to improve operational traceability.

It is not used for authentication or authorization.

---

## Error Model

The API uses explicit HTTP status codes for domain and authorization failures.

Common responses include:

```text
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
409 Conflict
422 Unprocessable Content
429 Too Many Requests
```

Client-facing errors are intended to avoid exposing internal database or implementation details.

---

## Backend Architecture

The backend follows a layered structure:

```text
backend/
└── src/
    ├── middleware/       # Authentication and error handling
    ├── migrations/       # Database schema migrations
    ├── models/           # SQLAlchemy models
    ├── repositories/     # Persistence and query logic
    ├── routes/           # FastAPI HTTP layer
    ├── schemas/          # Pydantic request/response models
    ├── services/         # Domain and application logic
    ├── config.py
    ├── database.py
    └── main.py
```

Route handlers act primarily as the HTTP boundary.

Business rules and domain workflows are implemented primarily in services, while repository modules encapsulate data-access logic where applicable.

---

## Feature Evolution

The backend has evolved across multiple specification-driven features.

Relevant backend-affecting specifications include:

```text
001-cricket-backend-api
002-auth-api-security
005-players-interface
006-teams-interface
007-coaches-portal
008-calendar-interface
009-business-audit-log
```

Older specifications describe the system at the time that individual feature was designed and should not be treated as a complete representation of the current API.

For current behavior, the backend route implementations and generated OpenAPI schema should be considered authoritative.