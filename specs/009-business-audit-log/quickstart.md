# Quickstart Validation: Business Audit Log and Recent Academy Activity

**Feature**: 009-business-audit-log

This guide validates the feature after implementation. It references the [data model](data-model.md) and [API contract](contracts/business-audit-api.md) rather than duplicating implementation code.

## Prerequisites

From the repository root:

```bash
docker compose up -d db
cd backend
uv run alembic upgrade head
```

Use the project’s normal local backend and frontend startup commands in separate terminals:

```bash
cd backend
uv run uvicorn src.main:app --reload
```

```bash
cd frontend
npm run dev
```

The test database must contain a Head Coach, an Assistant Coach, a Player, and enough valid players/teams/calendar fixtures for the existing mutation workflows.

## Automated validation

Run the required backend quickstart flow:

```bash
cd backend
uv run pytest tests/integration/quickstart/test_009_quickstart_flow.py
```

Run feature-specific backend unit and integration coverage:

```bash
cd backend
uv run pytest \
  tests/unit/test_business_audit_service.py \
  tests/unit/test_business_audit_routes.py \
  tests/integration/test_business_audit_logging.py
```

Run frontend unit/component coverage:

```bash
cd frontend
npm test -- \
  src/features/business-audit \
  src/layouts/AppLayout.test.tsx \
  src/app/router.test.tsx \
  src/pages/home/HomePage.test.tsx
```

Run the required Playwright journey:

```bash
cd frontend
npm run test:e2e -- audit-log-flow.spec.ts
```

## Required quickstart scenarios

### 1. Capture one event for one external mutation

1. Authenticate as a Head Coach.
2. Create a player through the existing player workflow.
3. Query `GET /api/v1/audit-log?page=1&page_size=20`.
4. Verify exactly one `player.created` event identifies the actor and player snapshots.
5. Verify the event contains only allowlisted metadata.

Expected result: the player and event are both committed.

### 2. Capture one event for a composite mutation

1. Authenticate as a Head Coach or Assistant Coach where the existing workflow permits it.
2. Replace a team’s details and complete ordered roster in one existing team update.
3. Query the business audit log.
4. Verify exactly one event represents the external mutation and metadata describes the affected team/roster areas.
5. Verify no per-row roster replacement events exist.

Repeat the equivalent assertion for coach-team assignment replacement and recurring-series editing.

### 3. Roll back domain data and audit data together

1. Arrange an audit persistence failure in the isolated service/integration fixture.
2. Execute a supported mutation.
3. Verify the request fails with the project’s safe error behavior.
4. Verify the domain rows and audit row are both absent after rollback.

Repeat with a domain validation, stale-version, not-found, and authorization failure. None may create a successful business event.

### 4. Verify historical IDs and snapshots

1. Create an audited actor/target event.
2. Rename or deactivate the actor/target, or remove the target in an isolated fixture.
3. Query the event again.
4. Verify historical UUID values and actor/target snapshots remain readable.
5. Verify deleting linked records does not delete the audit event and no live linked-record lookup is needed to render it.

### 5. Verify Head Coach-only retrieval

1. Request both business-audit endpoints as Head Coach and verify `200` responses.
2. Request both endpoints as Assistant Coach and Player and verify `403` responses with no event data.
3. Request the existing `/api/v1/auth/audit-log` endpoint separately and verify its security behavior is unchanged.

### 6. Verify filtering, ordering, and bounds

1. Seed events with equal timestamps, multiple categories, actors, action types, entity types, and dates.
2. Verify `created_at DESC, id DESC` ordering across repeated requests and page boundaries.
3. Verify each filter combines with the others and resets page to 1 in the UI.
4. Verify invalid UUIDs, unknown enum values, reversed dates, and spans over 366 dates fail safely.
5. Verify the recent route never returns more than four events even when a larger limit is requested.

### 7. Verify dashboard activity and recovery

1. As Head Coach, perform several supported administrative actions.
2. Open the dashboard and verify the latest four appear in the existing Recent academy activity position.
3. Verify category text/icon, concise summaries, and relative academy-local times.
4. Follow View all activity and verify the full Audit Log opens.
5. Simulate no events and a recent-query failure; verify distinct empty and retryable compact states while the rest of the dashboard remains usable.

### 8. Verify responsive accessibility

1. Open Audit Log at 320px width and desktop width.
2. Navigate filters, disclosures, retry, clear-filters, pagination, and View all activity using only the keyboard.
3. Verify visible focus, no horizontal overflow, accessible labels, status/error announcements, and disclosure state announcements.
4. Verify timestamps remain correct for both standard-time and daylight-saving-time fixtures in `America/Los_Angeles`.

## Expected completion signals

- Backend quickstart and feature tests pass.
- Frontend unit tests pass.
- The Playwright journey proves activity capture, dashboard-to-log navigation, filtering, disclosure safety, newest-first ordering, and unauthorized access behavior.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `npm run lint`, and `npm run build` pass before implementation handoff.
