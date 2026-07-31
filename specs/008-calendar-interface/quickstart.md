# Calendar Interface Quickstart Validation

This guide validates the implemented Calendar Interface against the [API contract](contracts/calendar-api.md), [UI contract](contracts/calendar-ui.md), and [data model](data-model.md). It is intended for local verification after implementation.

## Prerequisites

From the repository root:

```bash
docker compose up -d db
cd backend
uv sync --all-groups
uv run alembic upgrade head
```

The backend test environment supplies an isolated JWT secret. For manual browser validation, start the backend and frontend in separate terminals:

```bash
# Terminal 1
cd backend
uv run uvicorn src.main:app --reload
```

```bash
# Terminal 2
cd frontend
npm install
npm run dev
```

Use a seeded Head Coach account or the project’s normal account setup flow. Create separate Assistant Coach and Player accounts when validating role behavior.

## Automated backend quickstart

Run the required feature quickstart test:

```bash
cd backend
uv run pytest tests/integration/quickstart/test_008_quickstart_flow.py
```

The test must independently create and clean up its own authenticated users and calendar data, then verify:

1. A coach creates a timed weekly series with a bounded end date and selected age-group scope.
2. A range request returns the initial occurrence and later weekly occurrences, ordered correctly.
3. A yearly Feb 29 rule returns Feb 28 in a non-leap year.
4. A range over 45 academy dates is rejected without recurrence expansion.
5. The `/calendar/today` route returns the academy-local current date and effective instances, including empty results, all-day/timed ordering, recurring occurrences, moved/deleted exceptions, authorization, and Pacific-time boundaries.
6. A Player can read the range and Today data but receives HTTP 403 for create, update, occurrence-delete, and series-delete attempts.
7. An occurrence edit creates a stable exception, suppresses the original when moved, and leaves other occurrences unchanged.
8. A series update preserves valid exceptions, returns the removal-warning contract without saving when confirmation is absent, and removes invalid exceptions after confirmation.
9. A stale owning-event/exception version returns HTTP 409 without overwriting newer data.
10. Entire-series deletion hard-deletes the series and exceptions atomically.

## Automated frontend validation

Run feature unit/component tests:

```bash
cd frontend
npm test -- --run
```

At minimum, the feature tests cover the route for all roles, current academy month, range navigation/loading/retry, year range, grid semantics, event ordering/overflow, Today states, type/scope display, form validation, recurrence controls, exception/series flows, 403/409 handling, dirty-state confirmation, modal focus behavior, and mobile layout.

Run the required Playwright journey:

```bash
cd frontend
npm run test:e2e -- calendar-flow.spec.ts
```

The journey must:

1. Log in as a coach.
2. Open `/calendar` and verify the current academy month.
3. Create a timed weekly recurring event through the UI.
4. Confirm the event appears in the visible calendar.
5. Open one occurrence and edit This occurrence only.
6. Confirm the edited occurrence changes while another occurrence remains unchanged.
7. Delete the edited occurrence and confirm the rest of the series remains.
8. Delete the entire series and confirm no remaining occurrences appear.

The Playwright API mock should model the contracts in `contracts/calendar-api.md`, including the series exception-removal warning and version fields. It must not bypass the Calendar page or rely on a full browser reload.

Run the bounded-range performance validation:

```bash
cd backend
uv run pytest tests/integration/test_calendar_performance.py -q
```

The validation repeatedly requests one complete six-week (42-date) calendar grid populated with representative standalone events, recurring series, and occurrence exceptions. It records elapsed request times, reports the p95 duration, and verifies that at least 95% of requests complete within two seconds under this documented local Docker/PostgreSQL and test-runner environment.

## Manual acceptance checks

- Set the browser timezone outside Pacific time and verify the page still highlights the academy date and displays event times in `America/Los_Angeles`.
- Exercise both standard-time and daylight-time dates, including a weekly event around a DST transition.
- Navigate backward through 2026 into a pre-2026 month, then return with the year selector where available.
- Test a 42-cell month grid, adjacent-month muted dates, a day with four or more events, and a day with no events.
- Test Practice/Game timed validation, Miscellaneous all-day validation, duplicate/empty scope, and same-day end-time validation.
- Test Player read-only details and direct mutation denial.
- Test 320px, tablet, and desktop widths for overflow, focus visibility, touch targets, Today readability, and modal internal scrolling.

## Quality gates

```bash
# Backend
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest tests/integration/test_calendar_performance.py -q

# Frontend
cd ../frontend
npm run lint
npm test -- --run
npm run build
npm run test:e2e -- calendar-flow.spec.ts
```

The migration must also be exercised against the local PostgreSQL service by applying it from a clean schema and by running the project’s migration downgrade/upgrade verification where supported.
