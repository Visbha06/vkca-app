# Dashboard API Contract

Base path: `/api/v1`. The dashboard route requires an authenticated active
session and accepts no user, Player, coach, or team scope parameters.

## `GET /api/v1/dashboard`

The server loads the authenticated `User` through the existing bearer/session
dependency and derives all scope from current database relationships. Dashboard
reads do not create Business Audit or security-audit events.

### Response envelope

```json
{
  "user": {
    "id": "user-uuid",
    "display_name": "Asha Coach",
    "role": "head coach"
  },
  "dashboard_state": "ready",
  "summary": {
    "training": {
      "status": "ready",
      "data": {
        "occurrence_id": "series-uuid:2026-08-12",
        "event_date": "2026-08-12",
        "start_time": "17:00:00",
        "end_time": "18:30:00",
        "name": "Batting fundamentals",
        "event_type": "practice",
        "age_groups": ["U15"]
      }
    },
    "next_match": {
      "status": "ready",
      "data": {
        "id": "match-uuid",
        "match_date": "2026-08-15",
        "format": "T20",
        "participants": {
          "kind": "external",
          "academy_team": {"id": "team-uuid", "name": "U15 Falcons"},
          "opponent_name": "Northside CC",
          "academy_side": "home"
        }
      }
    },
    "player_slot": {
      "status": "ready",
      "data": {
        "kind": "active_player_count",
        "count": 42,
        "team_count": 4
      }
    }
  },
  "upcoming_events": {
    "status": "ready",
    "data": [
      {
        "occurrence_id": "event-uuid",
        "event_date": "2026-08-12",
        "start_time": "17:00:00",
        "end_time": "18:30:00",
        "name": "Batting fundamentals",
        "event_type": "practice",
        "age_groups": ["U15"]
      }
    ]
  },
  "context": {
    "status": "ready",
    "data": {
      "kind": "recent_activity",
      "events": [],
      "view_all_path": "/audit-log"
    }
  }
}
```

The concrete Pydantic models use discriminated unions. Every section status is
one of:

- `ready`: `data` is present;
- `empty`: the section has no eligible records and includes a specific message;
- `unlinked`: only for an unlinked Player dashboard, with contact guidance;
- `unavailable`: the section failed independently and includes retryable state.

The response never includes both `data: null` and an implicit meaning. A
`dashboard_state` of `unlinked` prevents academy-wide data from appearing in
any section.

## Scope rules

| Authenticated role | Match/team scope | Calendar scope | Context panel |
|---|---|---|---|
| Head Coach | All valid academy Matches and Teams | All applicable academy scopes | Up to four Recent Academy Activity events |
| Assistant Coach | Matches with either side in active `TeamCoach` assignments | All Academy plus assigned-team age groups | Up to twelve assigned Teams |
| Linked Player | Matches with either side in current `TeamPlayer` memberships | All Academy plus membership age groups | Up to twelve current Teams |
| Unlinked Player | No academy records | No academy records | Typed contact-the-Head-Coach state |

An internal Match whose home and away Teams are both in scope appears once.
Calendar occurrences are deduplicated by stable `occurrence_id` and use the
existing effective recurrence/exception semantics. The response limits are
five Upcoming Events, twelve My Teams entries, and four Recent Activity events.
Matches are ordered by `match_date, id`; Calendar rows use effective date,
all-day/timed ordering, start time, and occurrence ID.

## Errors

- `401`: existing authentication/session-expiry response; no fallback data.
- `403`: only if the existing route authorization layer denies the request;
  no client scope value can override it.
- `5xx` or network failure: frontend displays the established initial or
  retryable error state and never renders the static example values.

