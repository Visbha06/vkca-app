# Calendar Interface Research

## Decision 1: Keep academy event scheduling in Pacific local date/time

**Decision**: Store the scheduled event date and wall-clock start/end values as academy-local calendar fields. Use `America/Los_Angeles` (`zoneinfo.ZoneInfo`) for the trusted current date/time, validation, recurrence expansion, and range intersection. Continue using the existing timezone-aware timestamp convention for `created_at` and `updated_at`.

**Rationale**: The product rule is based on the academy’s local calendar, not the browser’s zone. Keeping the event’s local date and time explicit avoids converting a 5:00 PM academy event through a viewer’s local timezone and makes DST transitions testable. The existing backend already uses Python 3.12 and timezone-aware timestamps, while the frontend’s current calendar utilities use date-only values that can be extended without making browser `Date` the source of truth.

**Alternatives considered**:

- Store only UTC instants: rejected because recurrence and all-day events are defined by academy-local dates and would be vulnerable to DST/date-boundary conversion errors.
- Let the browser determine “today”: rejected by the specification and unsafe for users outside Pacific time.
- Add a new timezone dependency: rejected because Python’s standard `zoneinfo` provides the required IANA timezone support.

## Decision 2: Use one calendar event definition with an optional recurrence series

**Decision**: Represent a standalone event and a recurring series with one versioned event definition. A one-to-one recurrence row exists only for recurring definitions. Store age-group scope rows separately, with one explicit All Academy scope row or one row per selected age group.

**Rationale**: Shared event fields (name, type, first date, time/all-day state, and scope) can be validated and returned consistently. The optional recurrence row cleanly distinguishes non-recurring events from series without duplicating event fields. An explicit scope row makes All Academy unambiguous and gives the database a unique constraint for duplicate age groups.

**Alternatives considered**:

- Separate standalone-event and series tables: rejected because it duplicates common fields and complicates shared event responses.
- A JSON array for age groups: rejected because it weakens database uniqueness and typed validation.
- Treat All Academy as four age-group rows: rejected because the persisted scope would be ambiguous and could drift if supported groups change.

## Decision 3: Persist exceptions by series and original academy date

**Decision**: Persist one occurrence exception per `(series_id, original_date)`, where `series_id` refers exclusively to `RecurrenceSeries.id`. The stable occurrence identity is the deterministic pair of the series identifier and the original scheduled academy date. An exception stores a complete effective-value snapshot, replacement date when moved, scope, deletion state, and its own OCC version.

**Rationale**: Each supported rule produces at most one occurrence per academy date, so the original date is sufficient and remains stable when a series time changes. A complete snapshot makes partial edits deterministic and avoids nullable “did the user clear this field?” ambiguity. The original date lets the recurrence engine suppress the generated occurrence before applying a move or deletion.

**Alternatives considered**:

- Use the effective/moved date as identity: rejected because moving an occurrence would lose the link to the generated occurrence and could show duplicates.
- Include the original time in the identity: rejected because changing the series time would incorrectly invalidate otherwise valid date-based exceptions.
- Pre-generate occurrence rows: rejected because never-ending series would grow without bound and the specification requires calculated occurrences.

## Decision 4: Expand only bounded calendar ranges

**Decision**: The frontend requests the complete visible month grid. The backend accepts a bounded inclusive range of no more than 45 academy dates, which covers the largest ordinary grid plus a small adjacent-date buffer. Arbitrary multi-year ranges are rejected before recurrence expansion.

**Rationale**: The calendar needs adjacent-month cells but never needs a general reporting range. A single modest limit provides a simple abuse and performance guard while allowing 35- or 42-cell month grids and a small buffer. Recurrence expansion then operates only over the requested interval.

**Alternatives considered**:

- No maximum: rejected because an unbounded never-ending series could be expanded abusively.
- A seven-day or 31-day limit: rejected because some complete month grids contain 42 dates.
- Permit multi-year queries with pagination: rejected because multi-year retrieval is explicitly out of scope for normal calendar requests.

## Decision 5: Use deterministic recurrence arithmetic without a new dependency

**Decision**: Implement weekly and yearly expansion with standard-library date arithmetic. Weekly rules advance by seven days from the first occurrence. Yearly rules use the selected month/day; February 29 maps to February 28 in non-leap years and remains February 29 in leap years. End-date and occurrence-count termination are checked during expansion.

**Rationale**: The supported recurrence vocabulary is intentionally small, fixed-interval, and local to the academy calendar. A focused service is easier to test against the explicit business rules than a general recurrence library and avoids adding a production dependency under the project’s minimal-dependency principle.

**Alternatives considered**:

- General-purpose recurrence package: rejected for the limited rule set and additional dependency/serialization surface.
- Database-generated series: rejected because recurrence semantics, exceptions, and timezone rules belong in the application domain and must remain bounded.
- Materialize all future occurrences: rejected by the feature scope.

## Decision 6: Keep mutation authorization and OCC at the service boundary

**Decision**: All authenticated roles may call read contracts. Mutation routes require Head Coach or Assistant Coach through the existing role dependency. The owning `CalendarEvent.version_number` is the canonical OCC version for both standalone events and recurring-series updates; occurrence exceptions carry their own version number. Occurrence mutations verify the owning event version and existing exception version where applicable. Stale writes return HTTP 409 without retrying the mutation.

**Rationale**: Existing routes already use database-loaded roles, CSRF-aware mutation requests, `version_number`, and `StaleVersionError`. Reusing those patterns keeps backend authorization authoritative and makes frontend conflict handling consistent with teams, coaches, and players.

**Alternatives considered**:

- Frontend-only role hiding: rejected because Players must still be denied if they call mutation endpoints directly.
- One global calendar version: rejected because independent event, series, and exception edits should not conflict unnecessarily.
- Automatic overwrite or retry: rejected because it could destroy another coach’s changes.

## Decision 7: Use a confirmation-aware entire-series update

**Decision**: A series update first evaluates which existing exceptions no longer correspond to an occurrence under the proposed rule. If removals exist and the request has not explicitly confirmed them, the service returns a structured validation response identifying the original dates. The UI shows a warning and resubmits only after the coach confirms. The confirmed update preserves valid exceptions and deletes invalid ones atomically.

**Rationale**: The requirement is a warning before saving, not a silent cleanup after saving. Keeping the impact check in the backend prevents a stale or malicious client from bypassing the warning and keeps the final update atomic.

**Alternatives considered**:

- Delete invalid exceptions immediately and notify afterward: rejected because it can silently discard coach corrections.
- Let the frontend calculate removals: rejected because the frontend cannot be authoritative about recurrence identity or concurrent changes.
- Block all series changes that affect exceptions: rejected because the clarified behavior permits safe changes and explicit removal confirmation.

## Decision 8: Hard-delete series and cascading exception records

**Decision**: Entire-series deletion physically deletes the event definition, recurrence row, scope rows, and all occurrence exceptions in one transaction using database cascades plus explicit service-level transactional protection. Non-recurring event deletion also removes its event and scope rows.

**Rationale**: The clarification explicitly selects hard deletion for a series and its exceptions. The existing project has no calendar soft-delete convention, and cascade relationships prevent orphaned exception data while preserving atomicity.

**Alternatives considered**:

- Soft-delete the series: rejected by the clarification.
- Leave exceptions for audit history: rejected because it conflicts with the requested hard deletion and would require an undeclared retention model.
- Delete parent and children in separate requests: rejected because partial deletion is forbidden.

## Decision 9: Expose typed range, detail, and mutation contracts

**Decision**: Add a `/api/v1/calendar` route group with typed schemas for range retrieval, Today retrieval, event details, create, standalone update/delete, occurrence update/delete, and series update/delete. Frontend types mirror these schemas and use the existing `apiClient`, CSRF handling, and `ApiClientError` status behavior.

**Rationale**: The project’s constitution requires strongly typed API boundaries. Explicit contracts allow frontend tests and Playwright mocks to stay aligned with backend behavior and keep raw backend errors out of the UI.

**Alternatives considered**:

- Reuse match endpoints: rejected because calendar event types and recurrence semantics differ from recorded matches.
- Return untyped dictionaries: rejected by the project’s typed-boundary rule.
- Add a third-party calendar API: rejected by scope and the custom-calendar requirement.

## Decision 10: Use existing modal, form, date-grid, and OCC UX patterns

**Decision**: Build the calendar page as small feature components, reuse `calendarDate.ts` for date/grid arithmetic, follow `DateOfBirthPicker.tsx` for focusable date cells and month/year controls, use `ModalDialog` for event/details/confirmation dialogs, and follow team/player forms for dirty-state, progress, error, and conflict reload behavior.

**Rationale**: These patterns already match the application shell, design system, focus rules, and accessibility expectations. Reuse reduces interaction drift and keeps components within the constitution’s maintainability limits.

**Alternatives considered**:

- Introduce a complete third-party calendar: rejected by the feature scope and visual-control requirement.
- Build a separate modal/focus system: rejected because it would duplicate tested infrastructure.
- Put all calendar state in one page component: rejected by the frontend component-discipline principle.
