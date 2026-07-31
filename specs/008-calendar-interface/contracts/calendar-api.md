# Calendar API Contract

Base path: `/api/v1/calendar`

All requests require an authenticated session. Read operations allow Head Coach, Assistant Coach, and Player. Create, update, and delete operations allow only Head Coach and Assistant Coach and retain the existing CSRF protection. Date/time fields are academy-local; server timestamps remain in the project’s established representation.

## Common types

```json
{
  "scope_kind": "age_group",
  "age_groups": ["U13", "U15"]
}
```

`scope_kind` is `age_group` or `all_academy`. An age-group scope has one or more unique values from `J`, `U11`, `U13`, `U15`. An All Academy scope has an empty `age_groups` list in the response and is persisted as one explicit academy-wide scope.

```json
{
  "event_type": "practice",
  "name": "Batting fundamentals",
  "event_date": "2026-08-05",
  "is_all_day": false,
  "start_time": "17:00:00",
  "end_time": "18:30:00",
  "scope": {
    "scope_kind": "age_group",
    "age_groups": ["U15"]
  }
}
```

Timed events require both times, with `start_time < end_time` on the same `event_date`. All-day is allowed only for Miscellaneous and has null times.

## Range retrieval

### `GET /events?start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}`

Returns all effective instances intersecting the inclusive academy-local range. The range must be no more than 45 dates. The frontend uses it for one complete month grid plus a modest buffer; arbitrary multi-year ranges are rejected.

Response `200`:

```json
{
  "academy_today": "2026-08-01",
  "start_date": "2026-07-26",
  "end_date": "2026-09-05",
  "events": [
    {
      "occurrence_id": "series-uuid:2026-08-05",
      "event_id": "event-uuid",
      "series_id": "series-uuid",
      "original_date": "2026-08-05",
      "event_date": "2026-08-05",
      "event_type": "practice",
      "name": "Batting fundamentals",
      "is_all_day": false,
      "start_time": "17:00:00",
      "end_time": "18:30:00",
      "scope_kind": "age_group",
      "age_groups": ["U15"],
      "is_recurring": true,
      "recurrence_summary": "Every week on Wednesday",
      "event_version_number": 2,
      "exception_id": null,
      "exception_version_number": null
    }
  ]
}
```

The list is sorted per date by all-day first, timed start time ascending, and `occurrence_id` ascending. A `400` response is returned for malformed dates or ranges, and a `422` response with code `calendar_range_too_large` is returned for ranges over 45 dates. Both contain a safe user-facing `detail`; neither performs recurrence expansion.

## Today retrieval

### `GET /today`

Returns the current academy date and all event instances whose effective academy date is today.

Response `200`:

```json
{
  "academy_today": "2026-08-01",
  "events": []
}
```

The event object is the same shape as the range contract. The frontend displays the specified empty message when the list is empty.

## Event-instance details

### `GET /instances/{occurrence_id}`

Returns the same effective event object as a range item, including the owning event and exception versions needed for authorized mutation. The `occurrence_id` is URL-encoded because recurring identities contain `:`. A recurring `series_id` always refers to `RecurrenceSeries.id`.

Responses: `200`, `403` for unauthenticated/unauthorized access according to existing authentication behavior, `404` when the instance no longer exists, and a safe retryable `503`/network failure as appropriate to the application’s existing error handling.

## Create

### `POST /events`

Request:

```json
{
  "event_type": "practice",
  "name": "Batting fundamentals",
  "event_date": "2026-08-05",
  "is_all_day": false,
  "start_time": "17:00:00",
  "end_time": "18:30:00",
  "scope": {
    "scope_kind": "age_group",
    "age_groups": ["U15"]
  },
  "recurrence": {
    "frequency": "weekly",
    "termination": "end_date",
    "end_date": "2026-10-28",
    "occurrence_count": null
  }
}
```

`recurrence` is null for a non-recurring event. A yearly rule derives its month/day from `event_date`; February 29 is rendered as February 28 in non-leap years. Exactly one termination mode is required for a recurring request.

Response `201`: the created definition, scope, optional series rule, and all currently relevant calculated instances in the request’s initial visible range where the caller supplies one. The frontend refreshes its range and Today data after success.

Responses: `400`/`422` validation failure, `403` Player mutation attempt, and `409` only for an explicitly detected uniqueness/concurrency conflict. Creation is transactional across all related rows.

## Standalone event update/delete

### `PATCH /events/{event_id}`

Request includes the complete effective event fields and `version_number`. It is valid only for a non-recurring event. Response `200` returns the updated event with its incremented version. A stale version returns `409` and does not modify data.

### `DELETE /events/{event_id}`

Request body:

```json
{ "version_number": 1 }
```

Response `204` after atomic hard deletion of the event and scope rows. Stale version returns `409`; Player access returns `403`.

## Occurrence-only update/delete

### `PATCH /instances/{occurrence_id}`

Request includes the effective replacement fields, the owning event `version_number`, and `exception_version_number` when an exception already exists. The request identifies the original occurrence through the path identity. A first edit creates exception version `1`; later edits require the current exception version. A moved occurrence must pass the same-day/past validation.

Response `200`: updated effective instance and current versions. The original generated instance is suppressed when moved.

### `DELETE /instances/{occurrence_id}`

Request body:

```json
{
  "version_number": 2,
  "exception_version_number": 1
}
```

For an untouched occurrence, `exception_version_number` is null. Response `204` after creating/updating a deletion exception. The series and other occurrences remain. Stale versions return `409`.

## Entire-series update

### `PATCH /series/{series_id}`

`series_id` is the UUID of the persisted `RecurrenceSeries.id`. The owning `CalendarEvent.version_number` is the canonical series OCC version. The request includes the complete series event fields, recurrence rule, `version_number`, and:

```json
{ "confirm_exception_removals": false }
```

When the proposed rule invalidates existing exception original dates and confirmation is false, the service returns `422` without saving:

```json
{
  "detail": "This change will remove saved changes for 2 occurrences.",
  "code": "exception_removal_confirmation_required",
  "removed_exception_original_dates": ["2026-08-05", "2026-08-12"]
}
```

The frontend presents the dates and asks the coach to continue or cancel. A resubmission with `confirm_exception_removals=true` preserves exceptions whose original dates still occur under the new rule, hard-deletes the invalid exceptions, updates the rule, increments the owning event version, and commits atomically.

Response `200`: updated series summary and current owning event version. A stale event version returns `409` without applying the rule or exception cleanup.

## Entire-series deletion

### `DELETE /series/{series_id}`

Request body:

```json
{ "version_number": 2 }
```

Response `204` after atomically hard-deleting the series event definition, `RecurrenceSeries` row, scope rows, and all exceptions. The request version is the owning event’s canonical `version_number`; a stale version returns `409`; partial deletion is not observable.

## Error contract

Mutation and read errors use safe, user-oriented messages. The frontend maps statuses and stable `code` values to feature copy and never renders an arbitrary backend exception. Important codes include:

- `calendar_range_too_large`
- `calendar_event_in_past`
- `calendar_event_times_invalid`
- `calendar_scope_invalid`
- `calendar_recurrence_invalid`
- `exception_removal_confirmation_required`
- `calendar_stale_version`

All mutation routes retain the existing CSRF and role dependencies.
