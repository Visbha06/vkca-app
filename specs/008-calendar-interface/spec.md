# Feature Specification: Calendar Interface

**Feature Branch**: `008-calendar-interface`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Part 8: Calendar Interface for the VK Cricket Academy web application, including a custom monthly calendar, event and recurring-series management, occurrence exceptions, Today events, Pacific-time behavior, role authorization, accessibility, responsive behavior, error states, concurrency, and tests."

## Clarifications

### Session 2026-07-31

- Q: How should yearly recurrence handle February 29 in non-leap years? → A: Use February 28 in non-leap years.
- Q: How should existing occurrence exceptions behave after an entire-series edit? → A: Preserve exceptions whose original occurrence identity still exists under the new rule; remove exceptions whose original occurrence no longer exists, and warn before saving when removals are required.
- Q: How should entire-series deletion persist? → A: Hard-delete the series and its exceptions.
- Q: May an event cross midnight? → A: No; its end time must be later on the same academy date as its start time.
- Q: What event-range retrieval scope is allowed? → A: A complete month grid with a modest required adjacent-date buffer; arbitrary multi-year retrieval is rejected.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review the academy calendar (Priority: P1)

As a Head Coach, Assistant Coach, or Player, I want to open a monthly calendar and see academy events in the correct local time so that I can understand what is scheduled for my academy day.

**Why this priority**: Reliable visibility is the core value of the calendar and is needed by every authenticated role.

**Independent Test**: Authenticate as each supported role, open Calendar, and verify the current academy month, complete month grid, event summaries, Today section, and event details are usable without mutation access.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they open Calendar, **Then** the page opens to the current month in `America/Los_Angeles`, shows a complete month grid, highlights the current academy date, and loads the matching Today section.
2. **Given** events in the visible range, **When** the user views a day, **Then** events are ordered all-day first, followed by timed events by start time and stable identifier, with no event content breaking the grid.
3. **Given** a Player user, **When** they open an event, **Then** they can read its details but cannot see create, edit, or delete controls.
4. **Given** a user navigating with a keyboard, **When** they move between dates, months, or years, **Then** focus is visible, movement is predictable, and the selected/current date and event summaries are announced accessibly.

### User Story 2 - Navigate the calendar and Today briefing (Priority: P1)

As an academy user, I want to move across months and years and see today’s schedule so that I can plan both upcoming and historical activities.

**Why this priority**: Coaches and players need a quick daily briefing and access to historical and future context.

**Independent Test**: Navigate one month in both directions across a year boundary, choose a permitted year, navigate to a pre-2026 month with arrows, and verify adjacent dates, loading, focus restoration, and Today behavior.

**Acceptance Scenarios**:

1. **Given** any visible month, **When** the user selects previous or next month, **Then** exactly one month is selected, including across December/January, and the newly visible grid range is loaded.
2. **Given** the current academy year is 2026, **When** the user opens the year selector, **Then** it offers 2026 through 2031; the latest option advances to the current academy year plus five as time passes.
3. **Given** the user is viewing a pre-2026 month reached with arrows, **When** they inspect the year selector, **Then** the historical month remains viewable even though years before 2026 are not offered as selector options.
4. **Given** no event occurs on the current academy date, **When** Today finishes loading, **Then** it displays `No events scheduled for today.`
5. **Given** events occur today, **When** the user selects one from Today, **Then** the same event-details experience opens as from the calendar grid.

### User Story 3 - Create and manage events (Priority: P1)

As a Head Coach or Assistant Coach, I want to create, edit, and delete events for selected age groups or the whole academy so that the calendar remains operationally accurate.

**Why this priority**: Calendar data must be maintained by coaches and must support the academy’s recurring training schedule.

**Independent Test**: As a coach, create a timed recurring event, inspect an occurrence, edit only that occurrence, verify other occurrences remain unchanged, delete that occurrence, and finally delete the series.

**Acceptance Scenarios**:

1. **Given** a coach on Calendar, **When** they select Create Event, **Then** a form opens with type, name, academy date, permitted all-day option, times, age-group scope, All Academy, and recurrence controls.
2. **Given** a valid non-recurring event, **When** the coach saves it, **Then** it appears without a full page reload, Today refreshes if affected, the form closes or shows success, and a success confirmation is announced.
3. **Given** a Practice or Game event, **When** the coach omits start/end time or makes end time not later than start time, **Then** submission is prevented with associated validation feedback.
4. **Given** a Miscellaneous event, **When** the coach selects all-day, **Then** time inputs are hidden or disabled and the event occupies the selected academy date.
5. **Given** a recurring event, **When** the coach selects weekly or yearly recurrence and exactly one termination mode, **Then** occurrences in the visible range appear and the count, date, and recurrence inputs are validated.
6. **Given** a recurring occurrence, **When** an authorized coach chooses This occurrence only and saves a change, **Then** an exception suppresses or moves only that occurrence and other series occurrences retain their prior values.
7. **Given** a recurring occurrence, **When** an authorized coach chooses Entire series, **Then** the series definition is updated, exceptions whose original occurrence identities still exist are retained, exceptions whose identities no longer exist are identified, and the coach must explicitly confirm their removal before saving.
8. **Given** a deletion request, **When** a coach confirms deletion of a non-recurring event, one occurrence, or an entire series, **Then** the selected data is removed from Calendar and Today without a full page reload and unrelated recurring occurrences remain when only one occurrence was deleted.

### User Story 4 - Recover safely from errors and concurrent changes (Priority: P2)

As a calendar user or coach, I want clear feedback when loading, validation, authorization, network, or concurrency problems occur so that I can recover without losing work or overwriting another user’s changes.

**Why this priority**: Calendar mutations affect shared operational data and must be trustworthy under ordinary failures and concurrent coaching work.

**Independent Test**: Simulate range, Today, details, validation, permission, network, and stale-version failures; verify retry/reload actions, preserved form data, user-safe messages, and no automatic conflicting mutation retry.

**Acceptance Scenarios**:

1. **Given** a calendar or Today load failure, **When** the user selects Retry, **Then** only the affected data is requested again and the page does not present a failed or empty load as an empty schedule.
2. **Given** a coach has unsaved form changes, **When** they attempt to close the form or navigate away, **Then** they can continue editing or intentionally discard changes.
3. **Given** a Player attempts a mutation directly, **When** the request reaches the service, **Then** it is rejected with HTTP 403 and no data changes.
4. **Given** a coach submits an outdated event, series, or exception version, **When** the service detects the stale version, **Then** it returns HTTP 409, preserves newer data, shows a conflict message, offers Reload, and does not retry the mutation automatically.
5. **Given** a superseded month request is still in flight, **When** a newer navigation request completes, **Then** stale results cannot replace the newest visible range.

### Edge Cases

- Academy dates and times use `America/Los_Angeles` for current date, validation, recurrence, range intersection, and display; daylight-saving transitions must not shift an event to the wrong academy date.
- Timed events cannot be created or moved to a past academy date/time; all-day Miscellaneous events cannot be created or moved to a past academy date. Authorized users may edit historical events only when the resulting date/time is not newly in the past.
- All Academy is an unambiguous scope; selecting it clears, disables, or treats individual age groups as redundant. The persisted scope contains no duplicate age groups.
- At least one of Juniors (`J`), U11, U13, U15, or All Academy must be selected.
- Day cells show at most three events; `+N more` opens an accessible full-day view. If concurrent changes leave that view empty, it displays a safe empty message.
- A recurring series with no end must calculate only the requested bounded range; it must not create unlimited future occurrences.
- A yearly recurrence created on February 29 occurs on February 28 in non-leap years and on February 29 in leap years; this rule appears consistently in generated occurrences and recurrence summaries.
- Timed events cannot cross midnight: the end time must be later than the start time on the same academy date. Events that would end on the next academy date are invalid.
- A recurrence end date must be on or after the first date; an occurrence count must be a positive integer and includes the initial occurrence.
- A moved occurrence never appears at both its original and moved identity; a deleted occurrence is excluded while its series continues.
- Normal calendar range requests are limited to one complete visible month grid plus a modest adjacent-date buffer required by the view. Arbitrary multi-year range retrieval is rejected with a generic retryable message and does not trigger unbounded expansion.
- Event details may open in a loading state, fail with a retry action, or become unavailable after a concurrent deletion; each state preserves modal accessibility behavior.
- Repeated submissions, double navigation, deletion during refresh, and closing during an unsafe mutation are prevented or handled safely.

## Requirements *(mandatory)*

### Functional Requirements

#### Access and calendar presentation

- **FR-001**: The system MUST expose Calendar to all authenticated Head Coach, Assistant Coach, and Player users through the existing authenticated application shell.
- **FR-002**: The system MUST allow all three roles to view event instances, Today, event details, historical months, and future months within the calendar navigation behavior.
- **FR-003**: The system MUST render a custom responsive monthly grid with complete weeks, muted but distinguishable adjacent-month dates, a visible current academy-date treatment, semantic weekday/date labels, visible focus, and touch-friendly controls.
- **FR-004**: The system MUST provide previous/next month controls that move exactly one month, handle year boundaries, support navigation before 2026, preserve or restore focus appropriately, and load the newly visible grid range.
- **FR-005**: The system MUST provide a year selector whose options begin at 2026 and end at the current academy year plus five, while preserving the selected month where possible and allowing arrow navigation to historical years.
- **FR-006**: The system MUST request only one complete visible month grid plus a modest adjacent-date buffer where required by the view, and MUST reject arbitrary multi-year or otherwise excessive ranges.
- **FR-007**: The system MUST display a calendar-shaped loading state for initial and navigation loads, prevent stale entries from being mistaken for the selected range, and ignore superseded responses.
- **FR-008**: The system MUST display a Today section beneath the calendar, calculated in the academy time zone, with the exact empty message `No events scheduled for today.` when applicable.

#### Events and scope

- **FR-009**: The system MUST support Practice, Game, and Miscellaneous event types, each with a distinct accessible icon and a text alternative; type color MUST NOT be the sole differentiator.
- **FR-010**: The system MUST display each day number and up to three event entries, show `+N more` for overflow, prevent layout overflow, and order entries all-day first, then ascending timed start, then stable identifier.
- **FR-011**: The system MUST provide an accessible full-day view for `+N more` and the same event-details modal for entries in the grid and Today.
- **FR-012**: The system MUST support one or more unique age-group values from Juniors (`J`), U11, U13, and U15, plus an unambiguous All Academy scope applying to all supported age groups.
- **FR-013**: Event details and Today items MUST display name, type/icon, academy date, time range or All day, age-group scope, All Academy indication, and recurring status/summary where applicable.

#### Coach mutations and validation

- **FR-014**: Head Coach and Assistant Coach users MUST see Create Event and edit/delete actions; Player users MUST not see those controls.
- **FR-015**: The system MUST allow authorized coaches to create events with name, type, date, scope, optional permitted all-day state, and required times when timed.
- **FR-016**: Practice and Game events MUST require start and end times, and the end MUST be later than the start on the same academy date; events MUST NOT cross midnight. Only Miscellaneous events may be all-day.
- **FR-017**: The system MUST validate new and moved event dates/times against the current academy date/time, while independently enforcing the same rule in the backend.
- **FR-018**: The system MUST support weekly-on-weekday and yearly-on-month/day recurrence with fixed interval one and exactly one termination mode: Never ends, Ends on date, or Ends after positive occurrence count.
- **FR-019**: The system MUST calculate recurring occurrences for requested ranges without pre-generating unlimited future rows, and MUST include the initial occurrence in occurrence-count termination.
- **FR-020**: Successful creation MUST be atomic across the event, scope, and recurrence data; visible occurrences and Today MUST refresh without a browser reload.
- **FR-021**: The system MUST allow authorized coaches to edit non-recurring events and, for recurring events, require an explicit choice between This occurrence only and Entire series. This and following events MUST remain unavailable.
- **FR-022**: Occurrence-only edits MUST persist an exception keyed to the stable original occurrence identity, suppress the original occurrence when moved, and leave the recurrence rule and other occurrences unchanged.
- **FR-023**: Series edits MUST update the series definition and recurrence rule, preserve exceptions whose original occurrence identity still exists under the new rule, and remove exceptions whose original occurrence no longer exists. Before saving, the interface MUST warn the coach when any exceptions will be removed and require an explicit decision to continue or cancel.
- **FR-024**: Deletion MUST require confirmation, be atomic, avoid duplicate submissions, remove the selected result without reload, and support non-recurring event deletion, one-occurrence deletion, and entire-series deletion.
- **FR-025**: One-occurrence deletion MUST persist a deletion exception and preserve all other occurrences; entire-series deletion MUST hard-delete the series and all associated occurrence exceptions atomically, preventing all calculated occurrences from appearing.

#### Service behavior and concurrency

- **FR-026**: The backend MUST provide authenticated event-range retrieval for one complete visible month grid plus a modest adjacent-date buffer, returning non-recurring events, calculated recurring occurrences, edited/moved exceptions, and excluding deleted occurrences that intersect the requested academy-date range. Arbitrary multi-year range requests MUST be rejected.
- **FR-027**: The backend MUST enforce role authorization as the authoritative layer: Players may retrieve calendar data but all event creation, update, and deletion attempts by Players MUST return HTTP 403.
- **FR-028**: The backend MUST use the academy time zone for date/time interpretation, past validation, recurrence calculations, range intersection, and Today calculations, while preserving the project’s established timestamp storage convention.
- **FR-029**: Each non-recurring event, recurring series, and occurrence exception MUST have a separately identifiable version used for optimistic concurrency. Stale mutation versions MUST return HTTP 409 and MUST NOT overwrite newer data.
- **FR-030**: Each calculated occurrence MUST have a stable identity derived from its series and original scheduled date/time, including when an occurrence is edited, moved, or deleted.
- **FR-031**: Backend validation MUST reject duplicate scope values, empty scope, invalid recurrence termination, invalid times, past creation/movement, invalid dates, and excessive ranges with user-safe errors; raw backend errors MUST not be exposed.
- **FR-032**: Schema changes required by the feature MUST use a versioned, reversible migration where possible and be covered by migration verification.

#### States, accessibility, and responsive behavior

- **FR-033**: The interface MUST provide accessible initial, navigation, Today, details, form-submit, recurrence, delete, permission, network, range, empty, and conflict states, including retry or reload actions where applicable.
- **FR-034**: Create and Edit forms MUST preserve entered values after failure, disable repeated submission, expose progress accessibly, associate errors with controls, and detect unsaved changes before close or navigation.
- **FR-035**: Event details and confirmation dialogs MUST have accessible names/descriptions, focus trapping, Escape closing where safe, visible close controls, background scroll locking, responsive internal scrolling, and focus restoration.
- **FR-036**: The calendar MUST support keyboard date navigation, semantic current/selected-date announcements, clear full-name accessible labels for shortened mobile event text, and reduced-motion-compatible focus/loading behavior.
- **FR-037**: The layout MUST remain usable from 320px through 2560px without horizontal page overflow; controls may wrap/stack, fields may stack, and the monthly view MUST remain a monthly grid on mobile.
- **FR-038**: Visual styling MUST follow `PRODUCT.md` and `DESIGN.md`: disciplined clubhouse composition, system typography, cool canvas and white surfaces, academy teal for focus/wayfinding, fine boundary lines, restrained elevation, and minimum 44px interactive targets.
- **FR-039**: Unit and integration coverage MUST cover the role, calendar, validation, recurrence, exception, error, concurrency, accessibility, responsive, and authorization behaviors described in this specification. At least one Playwright journey MUST cover coach login, timed recurring creation, occurrence-only edit, occurrence deletion, and series deletion.

### Key Entities

- **Event**: A named Practice, Game, or Miscellaneous activity with an academy-local date/time or all-day date, scope, lifecycle state, and version.
- **Recurring Event Series**: The reusable weekly or yearly rule, first scheduled date, termination mode, and series version that produces bounded calculated occurrences.
- **Occurrence**: A stable, calculated instance of a series identified by series and original scheduled date/time, with effective display values after exceptions.
- **Occurrence Exception**: A persisted occurrence-level edit, move, or deletion, with its original occurrence identity, optional replacement values, deletion state, and version.
- **Age-Group Scope**: A unique set of supported age groups or the academy-wide scope associated with an event.
- **Calendar Range**: A bounded inclusive academy-date interval requested for the visible grid or Today view.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In usability testing, at least 95% of authenticated users can open Calendar and identify the current academy date and current month on their first attempt.
- **SC-002**: At least 95% of valid calendar-range requests display the requested month and Today state within 2 seconds under normal test conditions, with a visible loading state during slower requests.
- **SC-003**: In automated and manual accessibility testing, all primary calendar, event, form, confirmation, loading, error, and conflict flows are operable by keyboard and expose no critical WCAG 2.1 AA violations.
- **SC-004**: Coaches can create a valid timed recurring event, edit one occurrence, delete that occurrence, and delete the series without a browser reload; the complete workflow succeeds in the required Playwright journey.
- **SC-005**: 100% of tested event creation, movement, recurrence, Today, and range-boundary cases produce the same academy-local date and time across Pacific Standard Time and Pacific Daylight Time scenarios.
- **SC-006**: 100% of tested Player mutation attempts are rejected with HTTP 403, and 100% of stale-version mutation attempts are rejected with HTTP 409 without overwriting newer data.
- **SC-007**: 100% of tested one-occurrence edits, moves, and deletions preserve all unaffected series occurrences and never display both original and replacement occurrences.
- **SC-008**: At least 95% of users can understand event type, scope, time/all-day status, and recurrence status without relying on color alone, including at mobile widths.
- **SC-009**: Range calculation remains bounded for never-ending series and rejects configured excessive ranges without creating unbounded stored occurrence data.

## Assumptions

- Existing authentication, authenticated application shell, CSRF protection, API error model, toast pattern, modal/focus behavior, unsaved-change confirmation, and optimistic-concurrency conventions are reused.
- The existing `AgeGroup` values and display labels remain the source of truth: `J` displays as Juniors, with U11, U13, and U15.
- The current academy date is determined by a trusted academy-time-zone clock rather than the browser’s local time zone.
- Backend timestamps continue using the project’s established storage convention; API-facing date/time values include enough information for consistent academy-local interpretation.
- The normal event range is one complete visible month grid plus a modest adjacent-date buffer; arbitrary multi-year retrieval is not a supported calendar operation.
- Yearly recurrence created on February 29 uses February 28 in non-leap years and February 29 in leap years; this is not a new user-configurable recurrence option.
- Entire-series edits preserve exceptions whose original occurrence identity remains valid under the new rule, remove exceptions whose original occurrence no longer exists, and warn the coach before saving when removals are required.
- Entire-series deletion hard-deletes the series and its occurrence exceptions atomically.
- No event reminders, invitations, attendance, external calendar synchronization, search, personal calendars, drag/drop scheduling, week/day/agenda views, or custom recurrence intervals are included.
- Frontend and backend tests may use isolated fixtures and mocked network/service boundaries consistent with project testing discipline; the required Playwright test exercises the primary integrated user journey.
