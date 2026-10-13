# Feature 015 Validation Quickstart

This guide validates Match creation and live scoring through the frontend,
plus the backend scope checks needed by Matches. It follows the existing
Feature 014 PostgreSQL/test isolation conventions. The required backend
quickstart test is
backend/tests/integration/quickstart/test_015_quickstart_flow.py; the required
browser journey is frontend/e2e/live-ball-scoring-flow.spec.ts.

## Prerequisites

- Docker-hosted PostgreSQL is available for isolated backend tests.
- Backend dependencies are installed with uv and frontend dependencies with
  npm.
- Apply the repository's current migrations; Feature 015 introduces none.
- The browser journey uses the existing Playwright Chromium project and
  isolated Match/Team/Player fixtures or API routes. It does not require an
  external service or network connection.

From the repository root, prepare the test database and verify migrations:

~~~bash
cd backend
VKCA_ENV=test uv run alembic upgrade head
VKCA_ENV=test uv run alembic check
~~~

## Backend validation

Run the isolated required Match quickstart. It must cover a Head Coach and
scoped Assistant/Player: create/read scope, internal/external Match boundaries,
and preservation of existing Feature 014 scoring/API behavior.

~~~bash
VKCA_ENV=test uv run pytest tests/integration/quickstart/test_015_quickstart_flow.py -q
~~~

Run focused Match scope and existing scoring API/OCC coverage:

~~~bash
VKCA_ENV=test uv run pytest tests/unit/test_scoring_authorization.py tests/integration/test_match_scoring_api.py tests/integration/test_match_scoring_occ.py -q
~~~

Expected: a Head Coach sees all Matches; an Assistant Coach and Player see
only Matches anchored by a currently assigned academy Team; an external
opponent grants no access; an out-of-scope Assistant creation is rejected;
the same in-scope Match can still be configured and scored through the
existing Feature 014 commands. No schema migration is added.

## Frontend and browser validation

From the repository root:

~~~bash
cd frontend
npm run lint
npx tsc -p tsconfig.app.json --noEmit --pretty false
npx tsc -p tsconfig.node.json --noEmit --strict --pretty false
npm run test -- src/features/matches
npm run test:e2e -- e2e/live-ball-scoring-flow.spec.ts --project=chromium
~~~

The primary browser journey starts on Matches, creates and configures an
internal Match, sets batting order, starts an innings, records ordinary and
uncommon runs, a multi-run extra and a fielder-assisted wicket, selects the
next batter and bowler, corrects a delivery, completes the first innings,
chases the returned target, completes the Match, and checks the final
scorecard. It also covers opening/configuring an existing Match, creating and
configuring an external Match without academy opponent identities, and
Player read-only access.

For Player polling, verify a committed scorecard update appears within ten
seconds while the in-progress read-only view is visible; no second refresh
starts while the first is pending; transient failure leaves the last committed
view visible with stale status; hiding/leaving the view, terminal lifecycle,
or loss of authorization stops refresh; and no poll occurs in the scorer-entry
view. Verify that role-denied mutations remain unavailable and are rejected
by the backend.

## End-to-end acceptance signals

- A coach completes supported internal and external setup from the Matches
  interface without direct API or database operations.
- Displayed scores, innings states, and results match committed Feature 014
  responses after each accepted operation.
- Stale versions show a conflict and reload authoritative state without a
  duplicate active delivery.
- Read-only updates stay within the stated ten-second bound and stop on all
  specified conditions.
- Existing Feature 014 rules, API fields, persistence, and OCC behavior remain
  unchanged; no new scoring cache or database migration is present.
