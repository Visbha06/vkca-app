# Role-Aware Dashboard

## Purpose

The authenticated Home route is a live operational briefing derived from the
current signed-in User and academy records. It replaces the former sample
greeting, metrics, events, and activity with a bounded server projection. The
dashboard is calculated at read time; it does not persist summaries, create
background jobs, or write Business Audit events when loaded or retried.

The page preserves the existing composition: current-user greeting, one shared
three-part summary band, Upcoming Events, and a role-specific contextual panel.
Loading, empty, unlinked, unavailable, refresh, and retry states never fall
back to placeholder academy data.

## Role-specific behavior

| Role | Scope and summary | Context panel |
|---|---|---|
| Head Coach | Academy-wide upcoming Practice, Match, Calendar, Team, and active-Player data | Up to four newest eligible Business Audit events with Audit Log navigation |
| Assistant Coach | Active TeamCoach assignments plus all-academy Calendar events; distinct Players across assigned Teams | Up to twelve assigned Teams with roster count and next relevant event |
| Linked Player | Explicit `User -> Player -> TeamPlayer -> Team` membership scope only | Up to twelve current Teams with permitted coach and next-event context |
| Unlinked Player | Typed contact-the-Head-Coach state with no academy-wide fallback | The panel remains present with the same limited guidance |

Upcoming Events contains at most five effective Calendar occurrences and
reuses the Calendar service's 45-day, academy-local recurrence and exception
behavior. Event rows omit location. Matches come from Match records rather
than Calendar Game events, and an internal Match relevant through both sides
appears only once.

Every role receives exactly one primary action. Head and Assistant Coaches use
the existing Schedule event workflow. Players use View Upcoming Events; when
events are empty, View Teams replaces it only for a Player who already has a
scoped Team. No dashboard action grants a new permission or opens a Match
management interface.

## Dashboard API

`GET /api/v1/dashboard` requires an active authenticated session and accepts no
scope query parameters. The backend loads the current database User and derives
all Player, coach, Team, age-group, Calendar, Match, and audit scope itself.
Supplying any User ID, Player ID, coach ID, Team ID, or other query parameter
returns `422`.

The response includes:

- current display name and database-authoritative role;
- upcoming training, next Match, and active-Player or My Teams summary slots;
- up to five Upcoming Events; and
- either Recent Academy Activity or My Teams context.

Each independent section is a discriminated `ready`, `empty`, `unlinked`, or
`unavailable` state. Collections and ordering are deterministic, set-based,
and query-count tested. The frontend contract is generated from the backend
OpenAPI schema at
`frontend/src/features/dashboard/api/generated.ts`.

## Player account association

Revision `013` adds nullable unique `players.user_id` with `ON DELETE SET NULL`.
Existing account-less Player profiles remain valid. Identity is never inferred
from name, email, date of birth, or similar attributes.

Inside the existing Player Directory edit flow, a Head Coach can inspect a
safe account snapshot and explicitly link, unlink, or reassign a Player-role
account. Assistant Coaches and Players cannot discover eligible accounts or
render the controls. Responses expose only account ID, display name, email,
role, and active state—never credentials, hashes, tokens, or session details.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/players/account-linking/users` | Search bounded, eligible, unlinked Player-role accounts |
| `GET` | `/api/v1/players/{player_id}/account` | Read the protected safe association snapshot |
| `PUT` | `/api/v1/players/{player_id}/account` | Link one exact account |
| `DELETE` | `/api/v1/players/{player_id}/account` | Unlink after explicit confirmation |
| `POST` | `/api/v1/players/{player_id}/account/reassign` | Replace the expected account with one exact new account |

Every mutation carries the Player `version_number`. Stale versions, duplicate
links, expected-account mismatches, invalid roles, concurrent unique-index
races, and rolled-back operations leave the relationship unchanged. A
successful link, unlink, or reassignment stages exactly one corresponding
`player.account_linked`, `player.account_unlinked`, or
`player.account_reassigned` Business Audit event in the same transaction.

When a linked Player profile changes from active to inactive, all active
sessions for its Player-role User are revoked in the same transaction. Bearer,
login, and refresh authentication remain blocked while the profile is inactive.
Reactivation permits a new login but never restores revoked sessions or
reactivates an independently disabled User account.

## Match participant contract

Revision `013` replaces the ambiguous opponent-only Match representation with
one validated participant discriminator:

- `external`: exactly one academy Team, a nonblank external opponent, and the
  academy Team's `home` or `away` side;
- `internal`: two different academy Teams with explicit home and away sides
  and no external opponent.

The final columns are `participant_type`, `home_team_id`, `away_team_id`, and
`external_opponent_name`. Pydantic unions and PostgreSQL check/FK constraints
enforce the same invariant. `POST /api/v1/matches` and the OCC-aware
`PUT /api/v1/matches/{match_id}` accept the discriminated request; Match reads
return expanded safe Team references. Mixed, missing, blank, same-Team,
unknown-Team, and stale mutations are rejected without a successful audit
event. This release deliberately adds no Match page, modal, or dashboard
creation shortcut.

## Configuration and verification

No new runtime dependency, environment variable, dashboard table, worker, or
queue is required. Deploy Alembic revision `013` before the application code.
The migration refuses to guess participants for legacy Match rows and prevents
a downgrade that would silently discard an internal Match side.

Run the complete feature checks from the repository root:

```bash
cd backend
uv run alembic upgrade head
uv run ruff check src tests
uv run mypy src
uv run pytest tests/unit tests/integration -q
uv run pytest tests/integration/quickstart/test_011_quickstart_flow.py -q

cd ../frontend
npm run check:role-aware-dashboard-types
npm run test -- --run
npm run lint
npm run build
npm run test:e2e -- role-aware-dashboard-flow.spec.ts --project=chromium
npm run test:e2e -- role-aware-dashboard-performance.spec.ts --project=chromium --workers=1
```

The performance test uses a deterministic mocked local Head Coach fixture. It
warms up with ten opens, measures 100 sequential navigations, and requires the
nearest-rank p95 to be at most 2,000 ms. It is a local regression guard, not a
production-network service-level objective.
