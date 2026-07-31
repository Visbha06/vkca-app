# Calendar Interface Data Model

This model describes the persisted calendar definitions and the calculated event-instance projection returned to the frontend. All event dates and times below are academy-local (`America/Los_Angeles`). Server-managed `created_at`, `updated_at`, and version fields follow the existing project convention.

## Enumerations

| Name | Values | Meaning |
|---|---|---|
| `EventType` | `practice`, `game`, `miscellaneous` | Visual/event classification. |
| `ScopeKind` | `age_group`, `all_academy` | Whether scope rows identify selected groups or the whole academy. |
| `RecurrenceFrequency` | `weekly`, `yearly` | Supported recurrence patterns. |
| `RecurrenceTermination` | `never`, `end_date`, `occurrence_count` | Exactly one series termination mode. |
| `AgeGroup` | `J`, `U11`, `U13`, `U15` | Existing project enum; `J` displays as Juniors. |

## CalendarEvent

Represents either a standalone event or the shared event definition for a recurring series.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Primary identity. |
| `event_type` | `EventType` | Required. |
| `name` | string | Required after trimming; bounded by the project’s normal user-text limit. |
| `first_date` | date | First/initial academy date; cannot be in the past for creation. |
| `is_all_day` | boolean | True only for Miscellaneous events. |
| `start_time` | time or null | Required for timed events; null for all-day. |
| `end_time` | time or null | Required for timed events; later than `start_time` on the same date. |
| `version_number` | positive integer | Canonical OCC version for this event definition. It controls standalone edits/deletes or recurring-series updates when this event owns a `RecurrenceSeries`. |
| `created_at` | timezone-aware timestamp | Server-managed. |
| `updated_at` | timezone-aware timestamp | Server-managed. |

The event has no stored deleted state. Deleting a standalone event physically removes it. Deleting a recurring series physically removes this row and cascades its recurrence, scope, and exception rows.

## CalendarEventScope

Represents the event’s unambiguous audience. It is associated with one `CalendarEvent`.

| Field | Type | Rules |
|---|---|---|
| `event_id` | UUID | Foreign key to `CalendarEvent`; cascades on parent deletion. |
| `scope_kind` | `ScopeKind` | Required. |
| `age_group` | `AgeGroup` or null | Required only when `scope_kind=age_group`; null for All Academy. |

Invariants:

- Every event has at least one scope row.
- All Academy is exactly one `all_academy` row and has no age-group rows.
- Age-group scope has one row per unique age group and no All Academy row.
- A database uniqueness constraint prevents duplicate `(event_id, scope_kind, age_group)` values; service validation prevents mixed scope kinds.

## RecurrenceSeries

An optional one-to-one rule attached to a `CalendarEvent`. Its presence makes the event a recurring series; every recurring event has exactly one `RecurrenceSeries` row and every non-recurring event has none.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Primary identity of exactly one persisted recurrence series. |
| `event_id` | UUID | Unique foreign key to the owning `CalendarEvent`; one-to-one and cascades on deletion. |
| `frequency` | `RecurrenceFrequency` | Weekly or yearly only. Interval is always one and is not user-configurable. |
| `weekday` | integer or null | Required for weekly; academy weekday corresponding to `first_date`. |
| `month` | integer or null | Required for yearly; month corresponding to `first_date`. |
| `month_day` | integer or null | Required for yearly; day corresponding to `first_date`. |
| `termination` | `RecurrenceTermination` | Exactly one mode. |
| `end_date` | date or null | Required only for `end_date`; on/after `first_date`. |
| `occurrence_count` | positive integer or null | Required only for `occurrence_count`; includes the initial occurrence. |
| `created_at` | timezone-aware timestamp | Server-managed. |
| `updated_at` | timezone-aware timestamp | Server-managed. |

Validation invariants:

- `id` is the only series identity exposed as `series_id`; `event_id` is unique and identifies the owning event.
- Weekly rules have `weekday` and no yearly-only values; yearly rules have `month` and `month_day` and no weekly-only value.
- Never-ending rules have neither `end_date` nor `occurrence_count`.
- End-date rules have only `end_date`.
- Occurrence-count rules have only a positive `occurrence_count`.
- A yearly February 29 rule yields February 28 in non-leap years and February 29 in leap years.
- Expansion produces no occurrence outside the requested bounded range, before `first_date`, after `end_date`, or beyond the occurrence count.

## OccurrenceException

Represents one occurrence-level edit, move, or deletion. It is never generated for an untouched occurrence.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Primary identity. |
| `series_id` | UUID | Foreign key exclusively to `RecurrenceSeries.id`; cascades on series deletion. |
| `original_date` | date | The generated academy date being overridden; unique per series. |
| `replacement_date` | date or null | Effective date when moved; null means the original date. Must not be newly in the past. |
| `event_type` | `EventType` or null | Complete effective snapshot when not deleted. |
| `name` | string or null | Complete effective snapshot when not deleted. |
| `is_all_day` | boolean or null | Complete effective snapshot when not deleted. |
| `start_time` | time or null | Null for all-day; required for timed snapshot. |
| `end_time` | time or null | Null for all-day; later than start on the same effective date for timed snapshot. |
| `is_deleted` | boolean | True suppresses the generated occurrence. |
| `version_number` | positive integer | OCC version for repeated edits/deletes of this exception. |
| `created_at` | timezone-aware timestamp | Server-managed. |
| `updated_at` | timezone-aware timestamp | Server-managed. |

An exception has child scope rows with the same scope invariants as `CalendarEventScope`. For a deleted exception, effective-value and scope rows may be absent because the exception’s purpose is suppression.

Stable occurrence identity:

```text
occurrence_id = "{series_id}:{original_date in YYYY-MM-DD}"
```

The identity does not change when the occurrence is moved, edited, or deleted. The effective display date is `replacement_date` when present; otherwise it is `original_date`.

## CalendarEventInstance (calculated response entity)

The read model returned by range and Today retrieval. It is not persisted for recurring events.

| Field | Type | Meaning |
|---|---|---|
| `occurrence_id` | string | Event UUID for standalone events or stable series/date identity for series occurrences. |
| `event_id` | UUID | Parent event definition. |
| `series_id` | UUID or null | Present for recurring instances. |
| `original_date` | date | Initial generated date; equals effective date for standalone events unless an exception moves it. |
| `event_date` | date | Effective academy date shown to users. |
| `event_type` | `EventType` | Effective type. |
| `name` | string | Effective name. |
| `is_all_day` | boolean | Effective all-day state. |
| `start_time` | time or null | Effective academy-local start time. |
| `end_time` | time or null | Effective academy-local end time. |
| `scope_kind` | `ScopeKind` | Effective scope. |
| `age_groups` | unique list of `AgeGroup` | Empty only when `scope_kind=all_academy`. |
| `is_recurring` | boolean | Whether the instance came from a series. |
| `recurrence_summary` | string or null | User-facing summary for recurring instances. |
| `event_version_number` | positive integer | Canonical OCC version of the owning `CalendarEvent`; used for standalone updates or recurring-series mutations. |
| `exception_id` | UUID or null | Present when the instance has an exception. |
| `exception_version_number` | positive integer or null | Current exception version when present. |

Range results are sorted per day by all-day first, timed start time ascending, and `occurrence_id` as the final stable tie-breaker.

## Lifecycle and transaction rules

1. **Create standalone**: validate request → create event → create scope rows → commit together.
2. **Create series**: validate request and recurrence → create event → create scope rows → create recurrence row → commit together.
3. **Calculate range**: load active definitions whose first date/rule can intersect the bounded range → expand series in memory → load matching exceptions → suppress deleted originals → apply effective snapshots → sort results.
4. **Edit standalone**: verify event version → validate resulting values → update event and replace scope rows → increment version → commit.
5. **Edit one occurrence**: verify the owning `CalendarEvent.version_number` and exception version if present → validate effective values → insert/update exception keyed by original date → increment exception version → commit.
6. **Edit series**: verify the owning `CalendarEvent.version_number` → calculate exception impacts under the proposed rule → require explicit confirmation if invalid exceptions would be removed → update definition/rule, preserve valid exceptions, remove invalid exceptions, increment the owning event version → commit.
7. **Delete one occurrence**: verify the owning event version and exception version → insert/update a deleted exception → commit; the series remains.
8. **Delete standalone or entire series**: verify the relevant `CalendarEvent.version_number` → delete the parent inside one transaction; database cascades remove scopes, recurrence, and exceptions → commit or roll back completely.

## Date and range rules

- The backend is authoritative for the current academy date/time and all recurrence decisions.
- Normal range requests are inclusive and limited to 45 academy dates.
- The frontend requests the complete visible month grid (35 or 42 dates) and may add only the small buffer supported by the 45-date guard.
- `Today` is a one-date range calculated independently from the visible month.
- Timed events require `start_time < end_time` on the same academy date; midnight crossing is invalid.
- New and moved timed events cannot precede the current academy date/time; new and moved all-day Miscellaneous events cannot precede the current academy date.
