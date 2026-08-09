# Implementation Plan: Academy Data Quality Checks and Remediation

**Branch**: `010-academy-data-quality`
**Date**: 2026-08-08
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-academy-data-quality/spec.md`

## Summary

Add a Head Coach-only `/data-quality` capability that evaluates current Player,
Team/Roster, Coach, and Calendar state through a deterministic registry of 17
rules. The backend will use narrow SQLAlchemy projections and grouped/batched
queries to produce typed, non-persisted findings, summaries, and bounded pages.
Direct remediation will be a strict allowlist routed through extended
TeamService and CoachService business transactions so existing validation,
optimistic concurrency, and Business Audit behavior remain authoritative.

The frontend will extend the existing Head Coach route/navigation pattern with a
responsive Data Quality page, typed API client, filters, bounded pagination,
accessible states, and confirmation-gated actions. Navigate-to-Fix continues to
use existing domain workflows; no generic editor or Head Coach-removal action is
introduced.

## Technical Context

**Language/Version**: Python 3.12+ backend; TypeScript with React 19 frontend.

**Primary Dependencies**: Existing FastAPI, Pydantic 2, async SQLAlchemy 2,
asyncpg, PostgreSQL/pgvector runtime, React Router, Vitest, Testing Library,
pytest/pytest-asyncio/pytest-mock, and Playwright. No new dependency is needed.

**Storage**: Existing PostgreSQL academy schema. No new tables, columns,
indexes, or migrations in the initial release; findings and commands are
request-scoped objects.

**Testing**: pytest unit/route/integration tests, the required
`backend/tests/integration/quickstart/test_010_quickstart_flow.py`, frontend
Vitest/Testing Library tests, and one or more Playwright journeys using the
existing fixtures/mocks.

**Target Platform**: Existing Linux-hosted FastAPI service and browser-based
React application, with supported responsive widths from 320px through desktop.

**Project Type**: Existing full-stack web application with `backend/` and
`frontend/` projects.

**Performance Goals**: Keep API responses bounded with default page size 20 and
maximum 100; use set-based joins/aggregates/grouping or batched projections
where appropriate; avoid N+1 access; use realistic seeded scans and elapsed
time as regression signals without a fixed production latency SLA.

**Constraints**: Head Coach authorization on every read/write capability;
Assistant Coaches and Players receive existing 403 behavior; current-state
on-demand evaluation only; no persisted finding state, background work,
notifications, bulk actions, arbitrary SQL, or generic mutation; preserve
existing calendar timezone/recurrence semantics, OCC, domain validation,
Business Audit Log separation, and Product/Design accessibility conventions.

**Scale/Scope**: Five initial domains and 17 rules across current academy data.
The response is one deterministic filtered page plus a current unfiltered
summary. Evaluation reads narrow projections for existing players, teams,
rosters, coaches, assignments, events, recurrence series, and exceptions; it
does not load full ORM graphs or issue per-entity queries.

## Constitution Check

*GATE: Must pass before Phase 0 research and after Phase 1 design.*

| Principle/gate | Status | Plan alignment |
| --- | --- | --- |
| I. Clean Code | PASS | Separate typed schemas, evaluator/rules, domain-service adapters, route, and small frontend components; no parallel generic editor. |
| II. Simple UX | PASS | One Head Coach page, summary-first review, focused filters, direct action only for unambiguous corrections, and existing workflows for judgment. |
| III. Responsive Design | PASS | Reuse existing layout/tokens, stack filters and findings at 320px, and automate mobile/desktop coverage. |
| IV. Minimal Dependencies | PASS | Uses current dependencies; no `pyproject.toml` or package changes planned. |
| V. Testing Discipline | PASS | Unit tests for new logic/components, required integration tests from the spec, quickstart test `test_010_quickstart_flow.py`, and Playwright primary journey. |
| VI. MCP Server Priority | PASS | The repository review used codebase-memory and mcp-ripgrep patterns before design; implementation should continue using them for structure/literal searches. |
| VII. Database Schema Migrations | PASS | No persistence/schema change is planned. If implementation discovers a required schema change, stop and add a versioned migration before proceeding. |
| VIII. UX Completeness | PASS | UI contract references `PRODUCT.md` and `DESIGN.md` and defines layout, states, responsive behavior, focus, modal, and non-color severity behavior. |
| IX. Optimistic Concurrency | PASS | Direct actions carry current team/user versions, re-check conditions in the domain transaction, and map conflicts to HTTP 409/recovery UI. |
| X. Strongly-Typed API Boundaries | PASS | Pydantic schemas and mirrored TypeScript types use strict allowlists; no `any` or generic field maps. |
| XI. Frontend Component Discipline | PASS | Page logic is split into hook/API/container/presentational components and follows existing Tailwind spacing/size conventions. |
| XII. Documentation | PASS | Plan artifacts are created now; implementation will add verified `docs/academy-data-quality.md` after the feature is complete. |

**Gate result**: PASS. No constitution violation or unresolved technical
clarification remains at the planning stage.

## Repository-grounded design

### Backend evaluation

1. Add typed API schemas and enums for `QualitySeverity`, `QualityDomain`,
   finding/related-entity serialization, page/summary metadata, and the
   discriminated remediation command.
2. Add a pure normalization/rule module for player identity normalization,
   team-name grouping, finding IDs, rule metadata, severity, and rule-specific
   projection evaluation.
3. Add `DataQualityService` to load shared narrow projections, evaluate the
   registry once, apply rule precedence and deterministic ordering, aggregate
   unfiltered summary counts, validate filters, and paginate the filtered set.
4. Add a Head Coach-only route module and register it in
   `backend/src/main.py` under `/api/v1/data-quality`.
5. Extend `TeamService` with typed normalize/remove operations that retain its
   roster validation, team OCC, transaction ownership, and existing audit
   classification. A removal operation must remove only the selected inactive
   membership and preserve other legacy inactive memberships when the domain
   precondition allows it; it must not turn one action into a bulk replacement.
6. Extend `CoachService` with a removal-only inactive Assistant Coach
   assignment operation. It must reject Head Coach targets, validate exact
   assignment and user version, preserve all other assignments, and reuse
   `coach.team_assignments_updated`.
7. Keep Calendar checks read-only and route all schedule corrections to the
   existing Calendar workflow; reuse `calendar_recurrence.py` for recurrence
   semantics and never expand an unbounded series.

### Rule/query strategy

- Use one batched projection per logical domain, with SQL joins/aggregates and
  stable tie-breakers. Do not call `PlayerService`, `TeamService`,
  `CoachService`, or `CalendarService` list methods once per rule.
- Use outer joins/grouping for active-unassigned, inactive-rostered,
  roster-bound, no-coach, and Assistant assignment checks.
- Use one ordered team-player projection for all roster order checks and apply
  the specified non-positive/duplicate/gap/general rule precedence.
- Use normalized SQL grouping for team names and a narrow Python Unicode
  normalization pass for player duplicate candidates.
- Evaluate the sole Head Coach invariant separately from inactive Assistant
  assignment findings. A healthy exactly-one active Head Coach assigned to all
  current teams produces no finding; a broken invariant produces one Critical
  manual-review finding and no direct action.
- Join recurrence series to events and exceptions in one bounded read and call
  existing recurrence helpers per returned exception; do not add scope errors
  for empty scope collections.
- Sort findings by severity rank, domain rank/name, case-insensitive entity
  label, rule ID, and stable finding ID before filtering/pagination. Summary
  counts are computed before filters.

### Remediation transaction strategy

The route accepts only the three typed actions documented in
[`contracts/data-quality-api.md`](contracts/data-quality-api.md). The service
re-checks the referenced finding and target inside the same domain-service
transaction that performs the mutation. Stale version, role/status changes,
missing relationship, resolved finding, and invalid roster outcome all abort
without an audit event. Successful actions stage exactly one existing Business
Audit event and commit atomically.

No Data Quality service writes `TeamPlayer`, `TeamCoach`, or other domain rows
directly. No action is available for `coach.sole_head_coach_integrity`.

### Frontend strategy

- Create a `data-quality` feature with API functions, strict types, a fetch hook,
  page, summary, filter controls, finding list/card, state components, and a
  confirmation dialog.
- Add a Data Quality icon/navigation item directly after Audit Log and add a
  `HeadCoachRoute`-wrapped route.
- Reuse `Pagination`, `EmptyState`, `ModalDialog`, API-client errors/CSRF,
  `AbortController`, status/toast conventions, and focus restoration.
- Keep prior results during refresh/error; distinguish healthy no-issues from
  filtered no-results; refresh after successful remediation; show safe conflict
  recovery after HTTP 409.
- Navigate to existing `/players`, `/teams`, `/coaches`, and `/calendar`
  workflows for subjective fixes. Use textual severity and no color-only state.

## Project Structure

### Documentation (this feature)

```text
specs/010-academy-data-quality/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── data-quality-api.md
│   └── data-quality-ui.md
└── tasks.md                         # /speckit-tasks output; not created here
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── main.py                       # register data-quality router
│   ├── enums.py                      # quality severity/domain/action enums if needed
│   ├── schemas/
│   │   └── data_quality.py            # strict read/remediation contracts
│   ├── services/
│   │   ├── data_quality_service.py   # projections, registry orchestration, pagination, dispatch
│   │   ├── data_quality_rules.py     # pure normalization/rule evaluation and metadata
│   │   ├── team_service.py            # existing service extended for safe roster actions
│   │   └── coach_service.py           # existing service extended for Assistant removal
│   └── routes/
│       └── data_quality.py            # Head Coach-only GET/POST endpoints
└── tests/
    ├── unit/
    │   ├── test_data_quality_schemas.py
    │   ├── test_data_quality_rules.py
    │   ├── test_data_quality_service.py
    │   ├── test_data_quality_routes.py
    │   ├── test_team_service.py       # extend existing OCC/audit cases
    │   └── test_coach_service.py      # extend Assistant-only removal cases
    ├── integration/
    │   ├── test_data_quality_flow.py
    │   ├── test_data_quality_remediation.py
    │   └── quickstart/
    │       └── test_010_quickstart_flow.py
    └── ... existing fixtures and database safety helpers

frontend/
├── src/
│   ├── app/
│   │   └── router.tsx                  # HeadCoachRoute-wrapped route
│   ├── layouts/
│   │   └── AppLayout.tsx               # nav item directly below Audit Log
│   ├── features/
│   │   └── data-quality/
│   │       ├── api/dataQualityApi.ts
│   │       ├── api/dataQualityApi.test.ts
│   │       ├── components/
│   │       │   ├── DataQualitySummary.tsx
│   │       │   ├── DataQualityFilters.tsx
│   │       │   ├── DataQualityFindingList.tsx
│   │       │   ├── DataQualityFindingCard.tsx
│   │       │   ├── DataQualityStates.tsx
│   │       │   └── DataQualityRemediationDialog.tsx
│   │       ├── hooks/useDataQuality.ts
│   │       ├── hooks/useDataQuality.test.ts
│   │       ├── pages/DataQualityPage.tsx
│   │       ├── pages/DataQualityPage.test.tsx
│   │       ├── types/dataQuality.ts
│   │       └── index.ts
│   └── shared/components/icons/NavIcons.tsx # reuse/add navigation glyph
├── e2e/
│   └── data-quality-flow.spec.ts
└── ... existing auth, layout, API, state, and accessibility tests

docs/
└── academy-data-quality.md             # post-implementation verified docs
```

## Implementation sequence

1. Add typed quality enums, schemas, transient dataclasses, normalization
   helper, and stable registry definitions.
2. Implement batched projection loading and every rule with healthy/unhealthy
   fixtures, including sole Head Coach and calendar exclusions.
3. Implement deterministic sorting, summary/filter/pagination assembly, and
   the Head Coach-only read route.
4. Add/reuse safe TeamService and CoachService remediation operations with OCC,
   rollback, and existing audit actions; add the remediation route and conflict
   mapping.
5. Add frontend types/API/hook, route/nav, summary/filter/result/state
   components, navigation controls, and confirmation-gated direct actions.
6. Add backend route/remediation/quickstart tests, frontend tests, and the
   Playwright journey; add query-count/regression evidence using realistic
   seeded data where practical.
7. Run repository quality gates, verify responsive/accessibility behavior, and
   write `docs/academy-data-quality.md` only after implementation is verified.

## Verification and handoff

Phase 0 research and Phase 1 artifacts are complete in this feature directory.
The generic agent-context updater referenced by the planning workflow is not
present in this repository (`.specify/scripts` contains no such script), so no
agent context file was modified.
The next workflow should generate dependency-ordered `tasks.md` from this plan
and the clarified spec. Implementation must not begin until the generated tasks
retain the Head Coach manual-review boundary, Assistant-only inactive coach
remediation, existing audit actions, default/max page bounds, and the automated
performance/accessibility expectations.

## Complexity Tracking

No constitution violations require justification. The feature adds a registry,
projection evaluator, and typed UI because the requested domains must share one
deterministic bounded result and one Head Coach-only workflow; it does not add a
new persistence or generic mutation abstraction.
