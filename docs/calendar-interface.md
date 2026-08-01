# Calendar Interface

The Calendar page gives authenticated VK Cricket Academy users a monthly view
of academy events and a Today briefing. Head Coaches and Assistant Coaches can
create and manage events; Players can review the same calendar and details in a
read-only experience.

## User flows

- Open `/calendar` to load the server-authoritative academy date, Today events,
  and the complete visible month grid.
- Move between months or select a supported year. Navigation keeps the grid
  structure visible, ignores superseded requests, and restores logical focus.
- Select an event for details. Days with more than three events expose an
  accessible `+N more` action for the full-day list.
- Coaches create timed Practice/Game events or all-day Miscellaneous events,
  optionally repeating weekly or yearly. A recurring event can be edited or
  deleted as one occurrence or as the entire series; `This and following` is
  intentionally unsupported.
- Failed loads can be retried. Failed form submissions preserve entered values,
  repeated submissions are blocked, and unsaved changes require confirmation
  before dismissal. A stale write shows a reloadable conflict instead of
  retrying automatically.

## API surface

The authenticated API is rooted at `/api/v1/calendar`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/events?start_date=&end_date=` | Bounded inclusive range projection |
| GET | `/today` | Effective events for the academy-local current date |
| GET | `/instances/{occurrence_id}` | Event or stable recurring-instance details |
| POST | `/events` | Create a standalone event or recurring series |
| PATCH/DELETE | `/events/{event_id}` | Update or hard-delete a standalone event |
| PATCH/DELETE | `/instances/{occurrence_id}` | Edit or delete one recurring occurrence |
| PATCH/DELETE | `/series/{series_id}` | Update or hard-delete an entire series |

All reads require authentication. Mutations require a Head Coach or Assistant
Coach, CSRF protection, and the relevant owning-event/exception version. Player
mutation attempts return `403`; stale versions return `409` with the stable
`calendar_stale_version` code. Series edits that would remove saved occurrence
exceptions return `422` with the affected original dates until the coach
explicitly confirms the removal.

## Timezone and recurrence behavior

Event dates and wall-clock times are academy-local. The backend uses
`America/Los_Angeles` for Today, validation, range intersection, and recurrence;
the browser timezone never determines the academy date. Timed events must end
later on the same academy date. Only Miscellaneous events may be all-day.

Range requests are inclusive and limited to 45 dates. Recurrences are expanded
only inside the requested range; never-ending series are not materialized into
future rows. Weekly rules use the weekday of the first event. Yearly rules use
the first event's month/day, with February 29 falling back to February 28 in
non-leap years. Termination is exactly one of never-ending, end date, or
positive occurrence count, including the initial occurrence.

Recurring instances use the persisted `RecurrenceSeries.id` and original
academy date for a stable identity. An occurrence exception stores its complete
effective snapshot, replacement date, deletion state, scope, and independent
version. Moving an occurrence suppresses its generated original and displays
the replacement once. Entire-series deletion hard-deletes the owning event,
recurrence, scopes, and exceptions atomically through cascading foreign keys.

## Configuration

No new environment variables or production dependencies are required. The
existing PostgreSQL/Alembic configuration supplies persistence, and the
academy timezone is the service constant `America/Los_Angeles`. Run the
feature's isolated backend quickstart, frontend tests, Playwright journey, and
bounded performance test using
`specs/008-calendar-interface/quickstart.md`.

The calendar-specific Ruff checks, full backend test suite, migration
round-trip, mypy check, frontend lint/tests/build, and Playwright journey pass.
The repository-wide `ruff format --check .` command still reports formatting
differences in thirteen pre-existing non-calendar files; those unrelated files
were left unchanged during this feature implementation.
