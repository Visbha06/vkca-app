# Business Audit API Contract

**Feature**: 009-business-audit-log  
**Base path**: `/api/v1`

These contracts are business-audit-only. The existing `/api/v1/auth/audit-log` security endpoint, model, schema, and service remain unchanged and are never included here.

## Authentication and authorization

- All routes use the existing bearer authentication behavior.
- Head Coach authorization is required for all business-audit routes.
- Assistant Coach and Player requests return `403` with the existing safe `{"detail":"Not authorized"}` response.
- Missing or invalid authentication retains the existing `401` behavior.
- Authorization denials do not create business-audit events.

## Event representation

```json
{
  "id": "uuid",
  "actor_user_id": "uuid",
  "actor_display_name": "Alex Morgan",
  "actor_role": "head coach",
  "action_type": "team.created",
  "action_category": "team",
  "target_entity_type": "team",
  "target_entity_id": "uuid",
  "target_label": "U15 Falcons",
  "summary": "Alex Morgan created the U15 Falcons team",
  "metadata": {
    "age_group": "U15",
    "roster_count": 12
  },
  "created_at": "2026-08-05T19:30:00Z",
  "request_id": null
}
```

`actor_user_id`, `actor_display_name`, and `actor_role` may be null only for future system-generated actions. `target_entity_id` and `target_label` may be null only for actions with no durable target. The response uses stored snapshots and does not require linked-record joins.

`metadata` contains only action-specific allowlisted fields. It never contains credentials, tokens, secrets, raw payloads, raw exception messages, stack traces, or unrestricted snapshots.

## Full audit log

### `GET /api/v1/audit-log`

Query parameters:

| Name | Type | Default | Constraints |
|---|---|---:|---|
| `page` | integer | `1` | `>= 1` |
| `page_size` | integer | `20` | `1–100` |
| `actor_user_id` | UUID | omitted | Historical actor UUID filter |
| `action_category` | string | omitted | `coach`, `player`, `team`, `roster`, or `calendar` |
| `action_type` | string | omitted | Registered initial action identifier |
| `entity_type` | string | omitted | Registered target entity type |
| `target_entity_id` | UUID | omitted | Optional drill-down filter |
| `start_date` | `YYYY-MM-DD` | omitted | Inclusive academy-local date |
| `end_date` | `YYYY-MM-DD` | omitted | Inclusive academy-local date |

All supplied filters combine with AND. Date bounds use `America/Los_Angeles`; the maximum inclusive span is 366 dates. `end_date < start_date` is invalid.

Response `200`:

```json
{
  "events": [],
  "page": 1,
  "page_size": 20,
  "total_events": 0,
  "total_pages": 0,
  "has_previous": false,
  "has_next": false
}
```

Events are ordered `created_at DESC, id DESC`.

Errors:

- `400` or the project’s established validation status for invalid date combinations/filter combinations;
- `401` for missing/invalid authentication;
- `403` for Assistant Coach or Player;
- safe error response for unexpected retrieval failure without database details.

## Bounded dashboard activity

### `GET /api/v1/audit-log/recent?limit=4`

The route returns the same event representation in an envelope:

```json
{
  "events": [
    {
      "id": "uuid",
      "actor_user_id": "uuid",
      "actor_display_name": "Priya Shah",
      "actor_role": "assistant coach",
      "action_type": "player.created",
      "action_category": "player",
      "target_entity_type": "player",
      "target_entity_id": "uuid",
      "target_label": "Aryan Patel",
      "summary": "Priya Shah added Aryan Patel",
      "metadata": {},
      "created_at": "2026-08-05T18:00:00Z",
      "request_id": null
    }
  ]
}
```

`limit` is required to be between 1 and 4, defaults to 4, and is enforced server-side. The route uses the same retrieval service and ordering as the full log and never returns pagination beyond the bounded event list.

## Actor filter options

### `GET /api/v1/audit-log/actors`

This Head Coach-only route returns bounded actor choices derived from distinct actor snapshots present in business audit history:

```json
{
  "actors": [
    {
      "actor_user_id": "uuid",
      "actor_display_name": "Alex Morgan",
      "actor_role": "head coach"
    }
  ]
}
```

Only events with a non-null `actor_user_id` contribute options. Options are ordered by display name, deduplicated by actor UUID, and limited to at most 100 actors represented in current history. Events with null actor IDs remain valid feed events but are excluded from actor options in the initial release. Assistant Coaches and Players receive HTTP 403.

## Action identifiers

Initial action identifiers are:

```text
coach.created
coach.activated
coach.deactivated
coach.team_assignments_updated
player.created
player.updated
team.created
team.updated
roster.added
roster.removed
roster.reordered
calendar.standalone_created
calendar.standalone_updated
calendar.standalone_deleted
calendar.series_created
calendar.series_updated
calendar.series_deleted
calendar.occurrence_updated
calendar.occurrence_moved
calendar.occurrence_deleted
```

The action registry is extensible without changing the response or database shape. Match, performance, and player-statistics actions are not valid in this release.

## Mutation transaction contract

Every audited mutation must:

1. apply and flush the complete domain mutation;
2. create exactly one event at the outer externally initiated mutation boundary;
3. sanitize allowlisted metadata and snapshot actor/target labels;
4. flush the event;
5. commit domain and event together; and
6. roll back both when any persistence step fails.

No lower-level row helper or security audit writer creates a business event.
