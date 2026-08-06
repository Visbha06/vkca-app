# Feature Specification: Business Audit Log and Recent Academy Activity

**Feature Branch**: `009-business-audit-log`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Part 9: Business Audit Log and Recent Academy Activity"

## Clarifications

### Session 2026-08-05

- Q: Should each externally initiated API mutation create exactly one business audit event, even when it changes multiple database rows or invokes several internal service operations? → A: Yes. One user action normally produces one audit event; allowlisted metadata describes the affected areas, avoiding duplicate entries for roster replacement, recurring-series edits, and coach assignment updates.
- Q: Should actor_user_id and target IDs remain stored as historical UUID values without cascading deletion, even when the referenced user or entity is removed? → A: Yes. Retain historical UUID values, never cascade-delete an audit event, store actor UUIDs without strict foreign-key enforcement to preserve permanent traceability, store polymorphic target IDs without direct foreign keys, and use snapshots as the display source of truth.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture Administrative and Academy Activity (Priority: P1)

As a Head Coach or Assistant Coach performing an administrative task, I want each successful player, team, roster, coach, and calendar change to leave a clear business record so that the academy can understand what changed and who made it happen.

**Why this priority**: A trustworthy activity history is the foundation for both the Audit Log and dashboard activity feed. It must be correct before either user-facing view is useful.

**Independent Test**: Perform one supported domain mutation, commit it, and verify that exactly one matching business audit event is present with readable actor and target snapshots. Force the mutation to fail and verify that neither the domain change nor its audit event remains.

**Acceptance Scenarios**:

1. **Given** an authorized coach creates a player, **When** the mutation succeeds, **Then** one business event records the actor, the player target, the creation action, and a safe human-readable summary in the same transaction.
2. **Given** a supported mutation fails validation, authorization, optimistic-concurrency checks, or persistence, **When** the request completes, **Then** no successful business audit event is created and no partial domain change is committed.
3. **Given** an audited actor or target is later renamed, deactivated, or removed, **When** a Head Coach views the historical event, **Then** the stored actor and target snapshots remain understandable without requiring the current records to exist.

---

### User Story 2 - Review and Investigate the Business Audit Log (Priority: P1)

As a Head Coach, I want a filterable, paginated record of academy business activity so that I can review recent changes, investigate a particular actor or entity, and understand historical actions without exposing security logs or sensitive data.

**Why this priority**: Head Coaches need a dependable operational history for academy oversight. Separating business activity from authentication history keeps the page relevant and prevents inappropriate disclosure.

**Independent Test**: Sign in as a Head Coach, open Audit Log, verify newest-first events, apply each supported filter, paginate through a multi-page fixture, expand a safe detail view, and confirm that Assistant Coach and Player requests receive HTTP 403 and cannot view the page.

**Acceptance Scenarios**:

1. **Given** business audit history exists, **When** a Head Coach opens Audit Log, **Then** events appear newest first with actor name, role snapshot, summary, target label, category identification, and academy-local timestamp.
2. **Given** a Head Coach selects an actor, action category, action type, entity type, or inclusive date range, **When** the filter is applied, **Then** the server returns only matching events, pagination resets to the first page, and the result status identifies the count or no-results state.
3. **Given** business audit history contains actor snapshots, **When** a Head Coach opens the actor filter, **Then** the application loads bounded actor options from the business-audit actor-options endpoint, ordered by display name and suitable for selecting a historical actor.
4. **Given** multiple events share the same creation timestamp, **When** the Head Coach refreshes or changes pages, **Then** their relative order remains deterministic.
5. **Given** an event has useful safe metadata, **When** the Head Coach expands its details, **Then** the page shows the action identifier and allowlisted context without showing raw payloads, credentials, tokens, secrets, stack traces, or unrestricted personal information.
6. **Given** no business events exist, **When** the Head Coach opens Audit Log, **Then** the page distinguishes an empty history from a filtered no-results response and offers no placeholder events.

---

### User Story 3 - See Recent Activity on the Head Coach Dashboard (Priority: P1)

As a Head Coach, I want the dashboard’s Recent academy activity section to reflect the latest real academy changes so that I can understand what has happened without opening the full log.

**Why this priority**: The dashboard is the academy’s operational starting point. Real, bounded activity gives immediate context while preserving the existing layout and visual capacity.

**Independent Test**: Seed more than four business events, open the Head Coach dashboard, verify that only the latest four appear with concise summaries and relative times, then follow View all activity to Audit Log. Verify that an empty history and a retrieval failure each have their own compact state.

**Acceptance Scenarios**:

1. **Given** at least four supported business events exist, **When** a Head Coach opens the dashboard, **Then** Recent academy activity shows the latest four events from the same business-audit history used by Audit Log.
2. **Given** recent activity exists, **When** the Head Coach selects View all activity, **Then** the application opens the full Audit Log page.
3. **Given** no business activity exists, **When** the dashboard loads, **Then** the Recent academy activity section shows a suitable empty message rather than static or placeholder events.
4. **Given** the recent-activity request fails, **When** the dashboard loads, **Then** a compact error and retry action appear in that section while the remainder of the dashboard remains usable.
5. **Given** the account is an Assistant Coach or Player, **When** the dashboard loads, **Then** the Recent academy activity section is not exposed.

---

### User Story 4 - Preserve Clear Permissions and Accessible Recovery (Priority: P2)

As an academy user, I want the Audit Log and dashboard activity to respect my role and communicate loading, empty, error, and recovery states clearly so that I am never misled about what I can see or whether a request succeeded.

**Why this priority**: The feature contains historical and potentially sensitive operational information. Clear authorization and accessible recovery are required for safe day-to-day use.

**Independent Test**: Exercise the navigation and direct route as all three roles, simulate slow, empty, filtered, failed, and retryable responses, and use keyboard-only navigation at 320px and desktop widths.

**Acceptance Scenarios**:

1. **Given** a Head Coach is authenticated, **When** the sidebar is rendered, **Then** Audit Log appears directly beneath Calendar and the Head Coach can open it.
2. **Given** an Assistant Coach or Player is authenticated, **When** the sidebar is rendered or `/audit-log` is requested directly, **Then** the navigation item is hidden, the page shows the existing permission-denied experience, and the backend returns HTTP 403 for the business-audit request.
3. **Given** a list request is loading, fails, changes filters, or changes pages, **When** the state is rendered, **Then** the user receives an accessible status announcement and a clear retry or recovery action where applicable.
4. **Given** the Audit Log is used from a 320px viewport, **When** filters, event details, and pagination are operated by keyboard or touch, **Then** controls wrap or stack without horizontal page overflow and retain visible focus.

### Edge Cases

- A request with an end date before its start date is rejected with a clear validation error and does not query an unbounded range.
- Audit Log date ranges may span at most 366 inclusive academy dates. Requests exceeding this limit return the project’s standard validation response and must not execute the audit-history query.
- A filter combination that is syntactically valid but matches no events returns the filtered no-results state, not the initial empty-history state.
- A malformed actor, action category, action type, entity type, entity ID, page, page size, or date filter is rejected without exposing database details.
- Equal timestamps use the event’s stable identifier as the secondary sort key, with newest creation timestamp first.
- A target entity or actor may be renamed, deactivated, or deleted after the event is created; historical UUID values and snapshots remain readable, deleting a linked record never deletes an audit event, and linked-record lookups are never required for the primary feed.
- An actor may be unavailable when a future system-generated action is recorded; the optional actor ID and snapshots remain nullable as defined by the event contract.
- An audit persistence failure causes the related domain mutation to fail and roll back rather than silently completing without a trail.
- A failed validation, authorization denial, stale-version response, not-found response, or other unsuccessful request does not create a successful business event.
- Each externally initiated API mutation produces one business audit event, even when it changes multiple database rows or invokes several internal service operations. Allowlisted metadata describes the affected business areas; this prevents duplicate entries for roster replacement, recurring-series edits, coach assignment updates, and other composite mutations.
- A retry after a transient feed failure must not duplicate audit events or duplicate visible activity items.
- Calendar recurrence edits, occurrence moves, and daylight-saving transitions must preserve the original event meaning while displaying the correct academy-local time.
- Business activity must never include match, performance, or player-statistics activity until those workflows are explicitly added to scope.
- Existing authentication, authorization, session, login, logout, token, and other security events remain outside the business feed even when they occur in the same application.

## Requirements *(mandatory)*

### Functional Requirements

#### Business Audit Record and Boundaries

- **FR-001**: The system MUST provide a separate append-only business audit record for administrative and domain actions. It MUST remain independent from the existing authentication and security audit model, service, routes, schemas, and display behavior.
- **FR-002**: Each business audit record MUST contain a UUID event identifier, an optional historical actor user UUID, actor display-name snapshot, actor role snapshot, action identifier, action category, target entity type, an optional historical target UUID where an action has no durable target, target display-label snapshot, safe human-readable summary, sanitized structured metadata, a timezone-aware creation timestamp, and a nullable request or correlation ID.
- **FR-003**: Historical actor and target UUID values MUST remain stored after the linked user or entity is renamed, deactivated, or deleted. Actor UUIDs MUST be stored without strict foreign-key enforcement in this feature to preserve permanent traceability, and polymorphic target IDs MUST have no direct foreign keys. No deletion of a linked user or entity may cascade-delete a business audit event; snapshots are the source of truth for display.
- **FR-004**: A business audit record MUST have a creation timestamp only. It MUST NOT expose or support `updated_at`, optimistic-concurrency fields, edit timestamps, or other fields that imply an audit record can be modified.
- **FR-005**: Business audit records MUST be append-only. The application MUST provide no update endpoint, delete endpoint, modification service method, user-facing edit control, user-facing deletion control, or ordinary workflow for clearing history.
- **FR-006**: The application MUST define the intended retention policy in feature documentation as a future governance decision for append-only history, while this feature MUST NOT implement automatic deletion, archival, or retention cleanup.

#### Audit Writing and Transaction Integrity

- **FR-007**: A reusable business-audit service MUST accept the caller’s existing database transaction context, stage and flush a new event, and never commit independently.
- **FR-008**: The service MUST centralize action identifiers, metadata sanitization, and summary construction so that future action types can be added without changing the audit record shape.
- **FR-009**: Every successful audited domain mutation and its business audit event MUST commit together in one transaction. If either cannot be persisted, both MUST roll back.
- **FR-010**: Existing player, team, coach, roster, and calendar mutation workflows MUST be adapted so that their transaction boundary includes the business audit event and no audited mutation can commit independently before its event is staged successfully.
- **FR-011**: A failed validation, authorization check, not-found check, stale-version check, or other unsuccessful mutation MUST NOT create a successful business audit event. An authorization denial MUST continue to follow the existing security behavior and MUST NOT be added to the business feed.
- **FR-012**: Each externally initiated API mutation MUST create exactly one business audit event when it succeeds, even when it changes multiple database rows or invokes several internal service operations. Allowlisted metadata MUST describe the affected business areas, and the service and integration tests MUST prevent duplicate events for roster replacement, recurring-series edits, coach assignment updates, and other composite mutations.

#### Safe Metadata and Summaries

- **FR-013**: Structured metadata MUST use an explicit action-specific allowlist. It MAY contain only the minimum safe context needed to explain the business action, such as changed field names, roster position, safe counts, related entity identifiers, event scope, or a concise academy-local schedule label.
- **FR-014**: Sensitive values MUST be removed before metadata reaches the business-audit service. Business audit records MUST never contain plaintext or temporary passwords, password hashes, access or refresh tokens, CSRF tokens, secrets, environment values, complete request or response bodies, raw exception messages, unrestricted before-and-after snapshots, or unnecessary personal information.
- **FR-015**: Human-readable summaries MUST be consistent, safe, and constructed from stored snapshots and approved action context. They MUST identify the actor and target where appropriate without exposing credentials or raw payload data.

#### Initial Audited Actions

- **FR-016**: The system MUST record one expected business event for successful Assistant Coach account creation, coach activation, coach deactivation, and coach-team assignment changes.
- **FR-017**: The system MUST record one expected business event for successful player creation and player profile updates.
- **FR-018**: The system MUST record one expected business event for successful team creation, team details updates, roster additions, roster removals, and roster ordering changes.
- **FR-019**: The system MUST record one expected business event for successful standalone calendar event creation, update, and deletion; recurring-series creation, editing, and deletion; occurrence-only edits; occurrence moves; and occurrence deletion.
- **FR-020**: Match, performance, and player-statistics events MUST remain deferred and MUST NOT appear in the business feed until their workflows are implemented and explicitly integrated.

#### Business Audit Retrieval

- **FR-021**: The backend MUST provide one reusable business-audit retrieval capability for the full Audit Log and the bounded dashboard recent-activity query. The dashboard MUST NOT use a separate activity store or tracking mechanism.
- **FR-022**: The full business-audit list MUST be server-paginated, bounded, and ordered by creation timestamp descending with the stable event identifier descending as the secondary key.
- **FR-023**: The list MUST support server-side filtering by actor, action category, action type, entity type, and inclusive date range. It MAY support target entity ID filtering for drill-down links.
- **FR-024**: Filter values, date ranges, page numbers, page sizes, and filter combinations MUST be validated using the project’s established API error conventions. Date ranges exceeding 366 inclusive academy dates MUST return the standard validation response before executing the audit-history query. Invalid or excessive requests MUST fail safely and MUST NOT retrieve the complete audit history.
- **FR-025**: The retrieval contract MUST support a bounded recent-activity request limited to the latest four business events, and the dashboard request MUST never retrieve the complete audit history.
- **FR-026**: Primary feed responses MUST use stored actor and target snapshots and MUST avoid N+1 linked-record lookups. Current linked records MAY be loaded only for an explicitly requested secondary view and MUST not be required for normal list rendering.
- **FR-027**: Retrieval MUST expose business audit events only. Authentication, authorization, session, login, logout, token, and other security events MUST never be included or mixed into the response.

#### Authorization and Audit Log Page

- **FR-028**: The Audit Log page MUST be accessible only to authenticated Head Coach users. The backend MUST enforce this independently of frontend visibility.
- **FR-029**: Direct business-audit requests from Assistant Coaches and Players MUST return HTTP 403 with the project’s non-sensitive permission error behavior. They MUST not receive audit records.
- **FR-030**: The sidebar MUST show an Audit Log navigation item directly beneath Calendar only for Head Coaches. It MUST be hidden from Assistant Coaches and Players.
- **FR-031**: Unauthorized direct navigation MUST use the project’s existing role-protected route and permission-denied experience without exposing business audit data.
- **FR-032**: The Audit Log page MUST show newest-first activity items containing actor name, actor role at the time of action, human-readable summary, target entity label, category or icon, and an academy-local timestamp.
- **FR-033**: Each item MUST offer an accessible expandable details control when additional safe information is useful. Details MAY include action identifier, role snapshot, entity type, target-label snapshot, safe changed-field summary, related safe identifiers, and request ID when available.
- **FR-034**: Expanded details MUST NOT display raw database payloads, credentials, secrets, tokens, stack traces, raw exception text, unrestricted personal information, or authentication/security events.
- **FR-035**: The Audit Log page MUST provide accessible labeled controls for actor, category, action type, entity type, and date range filters, plus accessible server-side pagination controls.
- **FR-036**: The page MUST distinguish initial empty history from filtered no-results, and MUST provide loading, error, retry, unauthorized, and result-change states.
- **FR-037**: Filter changes MUST reset pagination to the first page, preserve valid selected filters while paging, prevent requests beyond the available page range, and announce meaningful result-count or no-results changes to assistive technology.

#### Dashboard Recent Academy Activity

- **FR-038**: The Recent academy activity section MUST be available only to Head Coaches and MUST retain its current dashboard placement and general visual composition while replacing static entries with real business audit data. Assistant Coaches and Players MUST neither render the section nor initiate the recent-activity request.
- **FR-039**: The section MUST display the latest four business audit events using a category-appropriate icon, concise activity title or summary, a short supporting description where useful, and a relative timestamp such as “2h ago” or “Yesterday.”
- **FR-040**: Dashboard activity MUST exclude performance-related entries until match and performance workflows are implemented.
- **FR-041**: The section MUST provide a View all activity link or equivalent action to the full Audit Log page.
- **FR-042**: The dashboard MUST show a suitable empty message when no business activity exists and a compact, retryable error state when the bounded recent-activity request fails. A recent-activity failure MUST NOT fail the rest of the dashboard.

#### Time, Performance, and Accessibility

- **FR-043**: Business audit creation timestamps MUST use the project’s timezone-aware storage convention and MUST remain the source of truth rather than storing formatted academy-local strings.
- **FR-044**: Audit Log timestamps MUST display in `America/Los_Angeles`, including correct behavior across daylight-saving transitions. Relative dashboard labels MUST derive from the same academy-local interpretation.
- **FR-045**: The business audit record and retrieval patterns MUST include indexes appropriate for creation timestamp, actor user ID, action category, action type, and entity type plus entity ID. Combined indexes MUST be limited to justified filtering and ordering patterns.
- **FR-046**: All business-audit list requests MUST remain bounded and paginated, and the dashboard request MUST remain bounded to four records.
- **FR-047**: The Audit Log page MUST remain usable from 320px through desktop widths. Filters and pagination MAY wrap or stack, but no page-level horizontal overflow is permitted.
- **FR-048**: Feed items, disclosures, filters, pagination, retry controls, and navigation MUST be keyboard operable with visible focus and touch-friendly targets. Icons MUST not be the only indication of category.
- **FR-049**: Loading, errors, filter changes, expansion changes, and result counts MUST be announced accessibly where appropriate using the project’s established status and alert patterns.
- **FR-050**: The feature MUST follow `PRODUCT.md` and `DESIGN.md`, reusing existing application-shell navigation, typography, colors, buttons, loading states, empty states, error states, pagination, disclosure, toast, and responsive patterns where available.

#### Verification Requirements

- **FR-051**: Unit tests MUST cover the business-audit service, including caller-transaction use, flush without independent commit, allowlisted metadata, sensitive-field exclusion, safe summaries, snapshots, duplicate prevention, and absence of update/delete methods or endpoints.
- **FR-052**: Integration tests MUST cover successful and rolled-back audit capture for Assistant Coach account creation, coach activation and deactivation, coach-team assignment changes, player mutations, team and roster mutations, standalone calendar mutations, recurring-series mutations, and occurrence-only calendar mutations.
- **FR-053**: Backend route tests MUST cover Head Coach access, Assistant Coach and Player HTTP 403 responses, each supported filter, the actor-options route’s alphabetical ordering, actor-ID deduplication, 100-option bound, null-actor exclusion, and empty results, pagination, stable newest-first ordering, invalid filters and date ranges, bounded recent-activity retrieval, initial empty history, and filtered no-results responses.
- **FR-054**: Frontend tests MUST cover role-protected navigation and route behavior, hidden unauthorized navigation, feed rendering, filters, pagination, loading, initial empty, filtered no-results, error and retry states, safe expandable details, academy-local timestamp formatting, dashboard activity rendering and failure isolation, and navigation from dashboard to Audit Log.
- **FR-055**: One Playwright journey MUST sign in as Head Coach, perform several existing administrative actions, verify those actions in dashboard Recent academy activity, open full Audit Log, verify stable newest-first order, filter by category or entity type, expand an event’s details, and verify Assistant Coach or Player cannot access Audit Log.
- **FR-056**: The backend MUST provide a bounded Head Coach-only actor-options endpoint returning only actors represented by business audit events with a non-null `actor_user_id`. Each option MUST contain the actor user ID, actor display-name snapshot, and actor role snapshot. Options MUST be ordered by display name, deduplicated by actor ID, and limited to at most 100 actors represented in current business audit history. Business audit events with a null `actor_user_id` remain valid and may appear in the audit feed, but are excluded from actor filter options in the initial release.

### Key Entities

- **Business Audit Event**: An immutable historical record of one successful administrative or domain mutation. It contains an event ID, actor ID and snapshots, action identifier, category, target type and ID, target-label snapshot, safe summary, allowlisted metadata, creation timestamp, and optional request or correlation ID.
- **Audit Action**: A stable identifier and category describing one supported business mutation, such as `player.created`, `roster.reordered`, or `calendar.occurrence.moved`. Action identifiers are extensible without changing the event’s core shape.
- **Actor Snapshot**: The actor’s display name and role captured at event creation, with an optional historical actor UUID for future system-generated actions. The UUID is retained independently of the actor account lifecycle.
- **Target Snapshot**: The target entity type, optional polymorphic historical UUID, and display label captured at event creation so the feed remains readable after the linked entity changes or disappears. Target IDs do not use direct foreign keys.
- **Audit Query**: A bounded, server-side retrieval of business events with deterministic ordering, optional filters, and pagination metadata. The same query capability serves the full Audit Log and the four-item dashboard feed.
- **Recent Academy Activity**: The Head Coach dashboard presentation of the four newest business audit events, with concise summaries and relative academy-local times.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested successful mutations in the initial audited-action list produce exactly one corresponding business audit event, and 100% of tested failed or rolled-back mutations produce no committed successful business event.
- **SC-002**: 100% of sampled business audit events retain readable actor and target snapshots after the associated actor or target is renamed, deactivated, or deleted.
- **SC-003**: 100% of sampled business audit records pass the sensitive-data checks: no passwords, password hashes, tokens, CSRF values, secrets, environment values, raw request/response bodies, raw exception text, or unrestricted snapshots are present.
- **SC-004**: 100% of tested Assistant Coach and Player direct Audit Log requests return HTTP 403, and no unauthorized response contains a business audit event.
- **SC-005**: Head Coaches can open the Audit Log, apply each supported filter, and reach a requested page with a bounded result set; no tested request retrieves more than the configured page size or four dashboard records.
- **SC-006**: 100% of tested equal-timestamp result sets remain in the same newest-first order across repeated requests and page navigation.
- **SC-007**: In the required Playwright journey, the Recent academy activity section becomes available during the dashboard session without requiring a browser reload; Head Coaches can reach the full log in one navigation action and can filter and expand an event without a full browser reload.
- **SC-008**: Automated and manual verification confirms that the initial empty, filtered no-results, loading, error, and unauthorized states are visually and semantically distinguishable at supported viewport widths, including 320px.
- **SC-009**: All tested timestamps display the correct `America/Los_Angeles` date and time across both standard-time and daylight-saving-time scenarios, with no source-of-truth dependence on formatted local strings.
- **SC-010**: Accessibility testing finds no critical WCAG 2.1 AA issue in the Audit Log or dashboard activity section, including keyboard disclosure, focus visibility, labeled filters, status announcements, and responsive use.
- **SC-011**: The existing dashboard remains usable when the bounded recent-activity request fails; 100% of failure fixtures preserve the other dashboard sections and expose a working retry action.

## Assumptions

- Existing authentication, session handling, current-user data, role dependencies, HTTP 403 behavior, API error conventions, optimistic-concurrency behavior, database transaction conventions, and frontend route protection are reused. This feature does not redesign or integrate authentication or security logging.
- The existing domain services remain the owners of player, team, coach, roster, and calendar business rules; planning will adjust commit ownership or transaction boundaries as needed so the business audit event participates in the same transaction.
- Historical actor and target UUIDs are intentionally independent of linked-record lifecycle: no foreign-key cascade may remove an audit event, actor UUIDs use no strict foreign key in this feature, and polymorphic target IDs use no direct foreign keys. Stored snapshots are authoritative for historical display.
- A default full-log page size of 20 and maximum page size of 100 follow the project’s existing pagination conventions. The precise response envelope and URL naming will be settled during planning without changing the user-visible behavior specified here.
- Actor filtering uses the stable actor identifier while presenting a human-readable actor choice. The feed does not need live actor records to render historical snapshots.
- Date-range filters are inclusive and interpreted using the academy’s `America/Los_Angeles` calendar semantics before comparison with stored timezone-aware creation timestamps.
- Request or correlation IDs are optional in the first release. The audit record remains nullable when no compatible request context exists; full tracing and observability are deferred.
- The feature documentation will state that audit history is append-only and retained until a future approved retention policy is defined. No automatic cleanup or export is included.
- No audit events are generated by authentication, authorization denials, sessions, login, logout, token, infrastructure, or general application logging workflows.
- No Assistant Coach or Player activity feed is included; only Head Coaches receive the dashboard section and full Audit Log page.
- Existing static dashboard schedule content remains outside this feature except for replacing the static Recent academy activity entries.
- Existing match, performance, and player-statistics workflows are unchanged and remain outside the initial event catalogue.
