# Academy Data Quality

## Purpose

Academy Data Quality gives Head Coaches one current view of operational data
issues across Players, Teams, Rosters, Coaches, and Calendar. Findings are
evaluated on demand from existing academy records; they are not persisted and
do not create scan history or background work.

The evaluator has 17 allowlisted rules. Every finding has a stable rule and
finding ID, severity, domain, affected entity label, explanation, and a safe
next step. Results use deterministic ordering and bounded pagination with a
default page size of 20 and maximum of 100.

## Head Coach workflow

1. Sign in as a Head Coach and select **Data Quality**, immediately below
   **Audit Log** in the application navigation.
2. Review the unfiltered academy summary for total, Critical, Warning, and Info
   counts.
3. Filter the current findings by severity, domain, or rule. Filtering changes
   the bounded result page but not the global summary.
4. Use **Navigate to Fix** for issues that require judgment. The action opens
   the existing Players, Teams, Coaches, or Calendar workflow.
5. When the API identifies a currently safe direct correction, open its
   confirmation dialog and explicitly confirm the one-record or one-relationship
   change. Current findings refresh after success.

Assistant Coaches and Players do not see the navigation item. Direct browser
access renders the existing 403 experience without requesting findings, and
every backend capability independently enforces the Head Coach role.

## API surface

### `GET /api/v1/data-quality`

Returns one bounded current-state findings page and an unfiltered summary.
Supported query parameters are:

- `page` (minimum 1, default 1)
- `page_size` (1–100, default 20)
- `severity`: `critical`, `warning`, or `info`
- `domain`: `players`, `teams`, `rosters`, `coaches`, or `calendar`
- `rule_id`: one of the registered Data Quality rule IDs

Invalid values use the normal FastAPI validation response. Reads, filters, and
refreshes do not create Business Audit events.

### `POST /api/v1/data-quality/remediations`

Accepts a strict discriminated request for exactly one of these actions:

- `normalize_roster_order`
- `remove_inactive_player`
- `remove_inactive_assistant_assignment`

Each request carries the finding identity, exact target IDs, expected team or
coach version, and `confirmed: true`. Unsupported actions and arbitrary field
maps are rejected.

## Remediation safety and audit behavior

Direct remediation re-evaluates the referenced finding and exact target before
changing data. It delegates to the existing TeamService or CoachService so
normal validation, optimistic concurrency, transaction rollback, and audit
behavior remain authoritative.

- A stale version, resolved finding, changed role/status, or missing target is
  rejected without a partial mutation.
- Inactive-player removal must leave a valid 7–15 active-player roster.
- Inactive coach removal is limited to one selected Assistant Coach/team
  assignment. Head Coach assignments are never directly removable.
- A broken sole Head Coach invariant is Critical and manual-review-only.
- One successful remediation produces exactly one existing Business Audit
  action: `roster.reordered`, `roster.removed`, or
  `coach.team_assignments_updated`.
- No generic Data Quality audit event is added. Authorization-denial security
  audit remains separate from the Business Audit Log.

## Configuration and operation

The feature adds no database tables, migrations, runtime dependencies,
environment variables, schedules, or workers. It uses the existing PostgreSQL,
FastAPI, authentication, audit, React, and Playwright configuration.

Frontend Data Quality API types are generated from the registered FastAPI
OpenAPI schema:

```bash
cd frontend
npm run generate:data-quality-types
npm run check:data-quality-types
```

Focused verification:

```bash
cd backend
uv run pytest \
  tests/unit/test_data_quality_service.py \
  tests/unit/test_data_quality_schemas.py \
  tests/unit/test_data_quality_routes.py \
  tests/integration/test_data_quality_read.py \
  tests/integration/test_data_quality_remediation.py \
  tests/integration/test_data_quality_authorization.py \
  tests/integration/test_data_quality_performance.py \
  tests/integration/quickstart/test_010_quickstart_flow.py

cd ../frontend
npm test -- --run src/features/data-quality
npm run test:e2e -- data-quality-flow.spec.ts
```

The seeded performance regression records scan timing as a comparison signal
and verifies that projection query count stays fixed as data grows; it does not
define a production latency SLA.
