# Quickstart: Dynamic Role-Aware Dashboard

This is a validation guide, not an implementation recipe. It proves the
backend domain invariants, role isolation, session behavior, audit boundaries,
and frontend journey described in the feature spec.

## Prerequisites

- Docker-hosted PostgreSQL configured by the repository's `.env.test`.
- Python 3.12+, `uv`, Node/npm, and installed backend/frontend dependencies.
- Run commands from the indicated project directory.

## Prepare the database

```bash
cd backend
uv run alembic upgrade head
```

The upgrade must finish at revision `013`. The migration test must also run
the repository's downgrade path and restore the baseline schema.

## Execute the isolated backend quickstart

```bash
cd backend
uv run pytest tests/integration/quickstart/test_011_quickstart_flow.py -q
```

The test uses the existing rollback-only PostgreSQL integration fixture and
must seed unique data for its run. It should validate all of the following:

1. Create Head Coach, Assistant Coach, linked Player, and unlinked Player
   accounts; create assigned Teams, current TeamPlayer rows, Practice and
   other Calendar events, and one external plus one internal Match through the
   domain/API contract.
2. Authenticate each role and call `GET /api/v1/dashboard`.
   - Head Coach sees academy-wide summaries and at most four audit events.
   - Assistant Coach sees only assigned-team data plus all-academy Calendar
     events.
   - Linked Player sees only current membership data, including an internal
     Match once when both sides are relevant.
   - Unlinked Player receives contact guidance and no academy-wide fallback.
3. Assert external and internal participant responses, reject mixed/missing/
   same-Team participant payloads before persistence, and assert no successful
   Business Audit event for rejected Match validation.
4. As Head Coach, perform link, unlink, and explicit reassignment mutations.
   Assert one appropriate audit event per committed mutation and zero events
   for forbidden, duplicate, stale, rejected, or rolled-back requests.
5. Deactivate a linked Player profile and assert all associated active sessions
   are revoked, the current bearer request fails with `401`, a fresh login is
   rejected, and reactivation permits a new login without restoring the old
   session.
6. Repeat dashboard reads and assert no Business Audit events are created.
   Use the existing SQL statement counter to enforce bounded queries and no
   N+1 Team/Player/Calendar/Match/audit loading.

## Backend unit and integration checks

```bash
cd backend
uv run pytest tests/unit/test_match_schemas.py tests/unit/test_match_routes.py -q
uv run pytest tests/unit/test_auth_service.py tests/unit/test_auth_routes.py -q
uv run pytest tests/unit/test_player_service.py tests/unit/test_player_routes.py -q
uv run pytest tests/integration -q
uv run ruff check src tests
uv run mypy src
```

Add focused feature tests for dashboard schemas/service/routes, Player account
service/routes, audit registry actions, migration constraints, Calendar scope
projection, and SQL query bounds. Keep unit tests isolated with `pytest-mock`
where external/database collaborators are not under test.

## Frontend contract and unit checks

```bash
cd frontend
npm run check:role-aware-dashboard-types
npm run test -- --run
npm run lint
npm run build
```

Frontend tests must cover Head Coach, Assistant Coach, linked/unlinked Player,
dynamic summaries, no-data states, section-level retry, no placeholder data,
the removed/deferred Match quick action, account-linking confirmation and
conflict states, keyboard/focus behavior, and 320px/tablet/desktop layout.

## Playwright journey

```bash
cd frontend
npm run test:e2e -- role-aware-dashboard-flow.spec.ts
```

The journey must verify the primary dashboard route for all three roles,
including that unrelated Team/Player/Business Audit data is absent, and that
the existing Player Directory flow can link an exact eligible account without
exposing credentials. It must not navigate to or create a Match-management UI.

## Expected completion signals

- Migration upgrade/downgrade succeeds from current revision `012`.
- All role-scoped dashboard responses contain only current seeded records,
  explicit empty states, or explicit unavailable/unlinked states.
- Internal Matches are never duplicated for a viewer relevant to both sides.
- Successful account association mutations produce exactly one appropriate
  Business Audit event in their transaction; failures produce none.
- Inactive linked Player sessions are revoked and new login is rejected until
  profile reactivation; revoked sessions are not restored.
- No dashboard read or retry writes business audit data, and no N+1 query
  regression is observed.
