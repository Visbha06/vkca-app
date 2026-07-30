# Coaches Portal

The Coaches Portal gives academy coaches a single place to review coach
accounts and team coverage. Head Coaches can also create Assistant Coach
accounts, manage access, and replace team assignments. Assistant Coaches have
read-only access to the active coach directory.

## Access and navigation

- Head Coaches and Assistant Coaches can open `/coaches`.
- Players do not see the Coaches Portal navigation item and receive a
  dedicated 403 page if they open the route directly.
- The backend remains authoritative for every role check; hidden frontend
  controls are not treated as authorization.

## Main workflows

### Browse coaches

The directory defaults to active coaches, displays 12 results per page, and
supports Active, Inactive, and All status filters. Results are ordered with
Head Coaches first, followed by Assistant Coaches sorted by last name, first
name, and user ID. Cards show account status and up to two team names.

Selecting a card opens coach details with contact information, assigned teams,
and the current placeholder statistics. Assistant Coaches cannot open inactive
coach cards.

### Create an Assistant Coach

A Head Coach can:

1. Open **Add Coach**.
2. Enter the coach's name and email.
3. Optionally select initial team assignments.
4. Create the account and copy the one-time temporary password.

The role is always Assistant Coach and the account starts active. Account and
assignment creation is atomic. The plaintext temporary password is returned
only in the creation response and is never persisted or retrievable later.

### Manage account access

From coach details, a Head Coach can deactivate another coach after confirming
that login will be blocked and active sessions revoked. Assignments and
historical data remain intact. Reactivation restores login eligibility but
does not restore revoked sessions. Head Coaches cannot deactivate themselves.

### Manage team assignments

For an active coach, a Head Coach can open **Edit assignments**, select the
complete desired team set, and save it atomically. Inactive coaches keep their
assignments in read-only form until reactivated.

Status and assignment writes include `version_number`. A stale write receives
HTTP 409 and the interface offers a reload action instead of overwriting newer
data.

## API surface

All paths are under `/api/v1` and require authentication.

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/coaches` | Head Coach, Assistant Coach | List coaches with status filtering and pagination |
| `POST` | `/coaches` | Head Coach | Create an Assistant Coach and return a one-time password |
| `GET` | `/coaches/{coach_id}` | Head Coach, Assistant Coach | Get coach details; inactive details are restricted for Assistant Coaches |
| `PUT` | `/coaches/{coach_id}/teams` | Head Coach | Atomically replace team assignments with optimistic concurrency |
| `POST` | `/users/{user_id}/disable` | Head Coach | Deactivate an account and revoke its sessions |
| `POST` | `/users/{user_id}/reactivate` | Head Coach | Reactivate an account without restoring sessions |

Coach list responses include pagination metadata. Coach responses include the
current account version and compact team summaries.

## Data and configuration

The feature adds the `team_coaches` join table with a composite
`(team_id, user_id)` primary key, timestamps, and optimistic-lock version
metadata. Apply the normal Alembic migrations before deployment.

No new packages, environment variables, or runtime services are required.
Existing PostgreSQL, authentication, password hashing, and session-revocation
configuration is reused.

## Validation

- Frontend unit tests cover directory states, cards, forms, modals, status
  changes, assignments, and conflict recovery.
- Backend unit tests cover schemas, authorization, account creation, status
  changes, assignments, and optimistic concurrency.
- `frontend/e2e/coaches-flow.spec.ts` covers the full Head Coach journey.
- `backend/tests/integration/quickstart/test_007_quickstart_flow.py` exercises
  all backend quickstart scenarios against PostgreSQL.
