# Data Model: Business Audit Log and Recent Academy Activity

**Feature**: 009-business-audit-log  
**Migration**: `012_create_business_audit_events.py` after migration `011`

## BusinessAuditEvent

Represents one successful externally initiated administrative or domain mutation. It is append-only and independent of `AuthAuditLog`.

| Field | Type | Nullability | Rules |
|---|---|---:|---|
| `id` | UUID | No | Server-generated primary identifier; stable secondary sort key. |
| `actor_user_id` | UUID | Yes | Historical actor UUID; no strict foreign key; nullable for future system-generated events. |
| `actor_display_name` | string, max 201 | Yes | Snapshot of actor display name at action time; required when `actor_user_id` is present. |
| `actor_role` | string, max 20 | Yes | Role snapshot at action time; nullable only for future system-generated events. |
| `action_type` | string, max 80 | No | Stable registry identifier such as `player.created` or `calendar.occurrence.moved`. |
| `action_category` | string, max 20 | No | One of `coach`, `player`, `team`, `roster`, or `calendar` for the initial scope. |
| `target_entity_type` | string, max 30 | No | One of `coach`, `player`, `team`, `roster`, `calendar_event`, or `recurrence_series`. |
| `target_entity_id` | UUID | Yes | Historical polymorphic target UUID; no direct foreign key. Nullable for actions with no durable target. |
| `target_label` | string, max 255 | Yes | Historical display label; authoritative for feed presentation. |
| `summary` | string/text, max 500 | No | Safe human-readable summary generated from snapshots and approved action context. |
| `metadata` | JSONB/object | No | Sanitized action-specific allowlist; default `{}`; never raw payloads. |
| `created_at` | timezone-aware timestamp | No | Server-managed creation timestamp; no `updated_at`. |
| `request_id` | string, max 128 | Yes | Optional request/correlation identifier from compatible request context. |

The model MUST NOT use the shared `TimestampMixin`, because that mixin adds `updated_at`. It MUST use the project’s UUID primary-key convention and `DateTime(timezone=True)` convention while retaining only creation time.

## Action registry

The action registry is application-level vocabulary, not a separate persisted table. It centralizes the action type, category, entity type, summary template, and metadata allowlist.

| Action type | Category | Target | Example allowlisted metadata |
|---|---|---|---|
| `coach.created` | coach | coach | assigned team IDs/count |
| `coach.activated` | coach | coach | changed fields |
| `coach.deactivated` | coach | coach | changed fields |
| `coach.team_assignments_updated` | coach | coach | added/removed team IDs/counts |
| `player.created` | player | player | changed fields if needed |
| `player.updated` | player | player | changed field names |
| `team.created` | team | team | age group, roster count |
| `team.updated` | team | team | changed fields, roster replaced flag/count |
| `roster.added` | roster | team | player ID, new roster position |
| `roster.removed` | roster | team | player ID, prior roster position |
| `roster.reordered` | roster | team | affected player IDs/count, changed positions |
| `calendar.standalone_created` | calendar | calendar_event | event type, scope, academy-local schedule label |
| `calendar.standalone_updated` | calendar | calendar_event | changed field names, scope, schedule label |
| `calendar.standalone_deleted` | calendar | calendar_event | event type, scope, schedule label |
| `calendar.series_created` | calendar | recurrence_series | event type, frequency, scope, schedule label |
| `calendar.series_updated` | calendar | recurrence_series | changed fields, frequency, exception count |
| `calendar.series_deleted` | calendar | recurrence_series | event type, frequency, scope, schedule label |
| `calendar.occurrence_updated` | calendar | recurrence_series | original date, changed field names |
| `calendar.occurrence_moved` | calendar | recurrence_series | original/replacement academy dates |
| `calendar.occurrence_deleted` | calendar | recurrence_series | original date |

These are examples of the initial registry and may be represented as typed constants/enums. No action creates an event for authentication, authorization denial, session, login, logout, token, match, performance, or player-statistics activity.

## Immutable actor context

`AuditActorContext` is an in-memory value passed from an authenticated route to an audited service operation:

- `user_id: UUID | None`
- `display_name: str | None`
- `role: UserRole | None`
- `request_id: str | None`

The context is captured before the mutation commits. It is not persisted separately and does not expose the ORM user object to the audit writer.

## Immutable target context

`AuditTargetContext` is an in-memory value assembled at the outer mutation boundary:

- `entity_type: AuditEntityType`
- `entity_id: UUID | None`
- `label: str | None`

Deletion operations capture the label and ID before deleting the domain row. Occurrence operations use the owning recurrence-series UUID as the target and put the original occurrence date in allowlisted metadata.

## Query/filter model

`BusinessAuditFilter` contains:

- `actor_user_id: UUID | None`
- `action_category: AuditActionCategory | None`
- `action_type: AuditActionType | None`
- `entity_type: AuditEntityType | None`
- `target_entity_id: UUID | None`
- `start_date: date | None`
- `end_date: date | None`

All supplied filters combine with AND. `start_date` and `end_date` are inclusive academy-local dates. The query converts them to timezone-aware bounds using `America/Los_Angeles`; the maximum span is 366 dates. An end date before the start date is invalid.

## Response models

### BusinessAuditEventResponse

The response mirrors the stored safe fields and never joins linked actor/target tables for primary rendering:

- `id`
- `actor_user_id`
- `actor_display_name`
- `actor_role`
- `action_type`
- `action_category`
- `target_entity_type`
- `target_entity_id`
- `target_label`
- `summary`
- `metadata`
- `created_at`
- `request_id`

### BusinessAuditPageResponse

- `events: list[BusinessAuditEventResponse]`
- `page`
- `page_size`
- `total_events`
- `total_pages`
- `has_previous`
- `has_next`

### RecentBusinessAuditResponse

- `events: list[BusinessAuditEventResponse]`

The recent query is bounded to at most four records and uses the same event serialization and retrieval service as the full page.

## Lifecycle and invariants

1. A successful external mutation flushes domain changes, records one event, flushes the event, and commits both together.
2. Any failure before commit rolls back both domain and audit changes.
3. No business-audit update/delete operation exists.
4. Deleting or changing a linked actor/target never deletes or rewrites an existing event.
5. Snapshots remain the source of truth for normal feed presentation.
6. A retry of a failed read does not write audit events.

## Indexes

Migration `012` adds indexes for:

- `created_at` for newest-first retrieval;
- `actor_user_id` for actor filtering;
- `action_category` for category filtering;
- `action_type` for action filtering;
- `(target_entity_type, target_entity_id)` for entity filtering;
- `(action_category, created_at)` only if query analysis confirms it benefits the combined category-plus-order pattern.

No foreign-key constraints are added to the historical actor or polymorphic target IDs.
