# Academy Data Quality Quickstart

This guide validates the feature after implementation. It follows the
repository’s existing backend integration, frontend Vitest, and Playwright
conventions. API shapes are documented in
[`contracts/data-quality-api.md`](contracts/data-quality-api.md), and transient
objects/rule behavior are documented in
[`data-model.md`](data-model.md).

## Prerequisites

- Python 3.12+ and `uv`.
- Node/npm installed for the frontend.
- A test-only `.env.test` configured from `.env.test.example`.
- PostgreSQL test database available through the repository Docker setup.

Start the test database from the repository root when needed:

```bash
docker compose up -d db
```

Do not point backend tests at development or production data. The existing
database-safety fixtures reject unsafe test URLs.

## Backend unit and route checks

From `backend/`:

```bash
uv run pytest \
  tests/unit/test_data_quality_rules.py \
  tests/unit/test_data_quality_service.py \
  tests/unit/test_data_quality_routes.py \
  tests/unit/test_data_quality_remediation.py
```

These tests should demonstrate:

- all 17 rules, healthy fixtures, severities, normalized comparisons, stable
  serialization/order, and intentionally permitted states;
- exactly one active Head Coach assigned to all teams produces no integrity
  finding, while an inactive or incompletely assigned sole Head Coach produces
  Critical manual-review output and no removal action;
- Assistant Coach inactivity is the only inactive coach assignment eligible for
  direct removal;
- filters, summaries, default page size 20, maximum page size 100, and no
  unbounded response;
- query-count or equivalent regression assertions for set-based/batched access
  and no N+1 entity lookups.

## Backend integration and quickstart flow

Run the feature integration tests from `backend/`:

```bash
uv run pytest \
  tests/integration/test_data_quality_read.py \
  tests/integration/test_data_quality_remediation.py \
  tests/integration/test_data_quality_authorization.py \
  tests/integration/test_data_quality_performance.py \
  tests/integration/quickstart/test_010_quickstart_flow.py
```

The required quickstart test creates isolated known records, evaluates the
read endpoint as a Head Coach, and verifies at least:

1. A mixed result has deterministic ordering and correct severity/domain
   summary counts.
2. Assistant Coach and Player requests receive HTTP 403.
3. Filters return bounded matching pages while the summary remains global.
4. A supported inactive Assistant Coach assignment removal requires
   confirmation, uses OCC, produces exactly one
   `coach.team_assignments_updated` Business Audit event, and disappears on
   re-evaluation.
5. A stale or changed target is rejected without a partial mutation or audit
   event.
6. The resulting Business Audit Log contains the existing domain action and no
   data-quality scan event.

The integration fixture should also cover the healthy and broken sole Head
Coach cases, roster normalization/removal preconditions, and rollback when the
audit write or domain mutation fails.

## Frontend checks

From `frontend/`:

```bash
npm test -- --run src/features/data-quality
npm run lint
npm run build
```

The frontend suite should cover sidebar order/visibility, the protected route,
summary and filters, every loading/error/empty/remediation state, navigation,
confirmation, stale recovery, keyboard operation, and 320px-safe layout.

## Playwright journey

From `frontend/`:

```bash
npm run test:e2e -- data-quality-flow.spec.ts
```

The journey seeds or mocks multiple known findings, signs in as a Head Coach,
opens Data Quality from the sidebar, verifies summary and filters, reviews an
entity, removes one inactive Assistant Coach assignment, confirms that the
finding disappears, verifies the domain state and corresponding Business Audit
Log action, and verifies Assistant Coach/Player denial. If the fixture includes
a broken sole Head Coach invariant, it also verifies Critical manual-review
presentation and no Head Coach removal control.

## Repository quality gates

After the focused checks pass, run the existing full gates:

```bash
cd backend && uv run ruff check src tests && uv run pytest
cd ../frontend && npm run lint && npm test && npm run build
```

Scan duration on a realistic seeded dataset may be recorded for regression
comparison. It is not a fixed production latency SLA and does not require
dedicated load-testing infrastructure.
