# Implementation Plan: Live Ball-by-Ball Match Entry

**Branch**: 015-live-ball-scoring | **Date**: 2026-10-13 | **Spec**: specs/015-live-ball-scoring/spec.md

## Summary

Add an authenticated Matches destination and an operational Match workspace to the existing VKCA web application. Coaches create an internal or external Match through the existing Match endpoint, then continue into Feature 015's pre-match configuration screen, which submits participants, capability, and batting order through Feature 014. The workspace uses Feature 014's protected commands and persisted projections for live scoring, correction, and completion. Authorized read-only viewers receive a ten-second scorecard refresh while an in-progress Match view is visible. Feature 014 remains the sole cricket scoring authority.

The only required backend contract work is at the existing Match authorization boundary: apply current Team scope to Match discovery and ensure an Assistant Coach cannot create a Match that is outside their configuration scope. No scoring rules, endpoints, tables, or Match storage system are added.

## Technical Context

**Language/Version**: Python 3.12+ backend; TypeScript 6 and React 19 frontend, as pinned/configured by the repository.

**Primary Dependencies**: FastAPI, Pydantic, SQLAlchemy, React, React Router, Tailwind CSS, the existing authenticated apiClient, Vitest, pytest, and Playwright. No additional dependency is planned.

**Storage**: Existing PostgreSQL Match, scoring, Team, and Player records. No schema change or migration.

**Testing**: Backend pytest unit/integration tests including the mandated quickstart test; frontend Vitest unit/component tests; Playwright primary workflow; existing ESLint and TypeScript checks.

**Target Platform**: Authenticated browser experience, responsive from 320px to 2560px, with tablet/mobile scoring prioritized.

**Project Type**: Existing frontend/backend web application monorepo.

**Performance Goals**: Routine 0–6 batter-run entry takes one scoring choice. In a visible read-only view, committed score and innings changes appear within the specified ten-second polling interval. Poll requests do not overlap.

**Constraints**: Feature 014 owns cricket validation, scoring, progression, lifecycle, results, corrections, authorization, and optimistic concurrency. Render committed server projections. Do not blindly retry uncertain non-idempotent writes. Poll only visible, authorized read-only views while lifecycle is in progress. No WebSockets, public streaming, offline synchronization, new database schema, or new scoring cache.

**Scale/Scope**: One Match discovery page, Match create and pre-match configuration flow, innings initialization, live scorer workspace, read-only Match/scorecard view, and the journeys and role states in the feature specification. No advanced analytics or standalone spectator scorecard.

## Constitution Check

**Pre-design gate: PASS.** The feature follows existing product and design conventions and does not add a parallel scoring authority or an external dependency.

- Principles II, III, VIII: every route and workflow has a primary action, complete interaction states, responsive touch behavior, and accessibility requirements captured in the spec.
- Principles V, IX, X, XI: plan unit and integration coverage for new logic, OCC handling, schema-aligned TypeScript types, and modular UI boundaries; include the Playwright scorer journey and backend quickstart test.
- Principles VI, XIII: repository code and Feature 014 contracts provide the needed integration facts; no version-specific external library behavior or new technology choice requires Context7 research.
- Principle VII: no persistence change is planned, so no migration is required.
- Principle XII: implementation must add the feature documentation after verified behavior exists; planning does not claim it is already verified.

**Post-design gate: PASS.** The design uses existing Match/scoring/Team APIs and shared auth/request infrastructure. The only backend work tightens authorization on existing Match operations; it does not change cricket policy, scoring payloads, persistence, or external interfaces. Complexity tracking has no constitution exception.

## Design Decisions

1. Use the existing Match domain for create, discovery, configuration, and review. The creation form submits the existing discriminated internal/external participant payload, with the existing required initial result value Scheduled. It then routes to the Feature 015 pre-match configuration screen, which uses the existing Feature 014 configuration contract.
2. Place the feature in a new frontend matches feature area and register it through the existing React Router deferred-route and AppLayout navigation patterns. Use local feature hooks/state and shared UI/API utilities; do not introduce a state-management or polling package.
3. Use Feature 014 Match and scoring responses as the only source for lifecycle actions, blocking states, score, participant figures, overs, target, and result. Every scoring write carries the current version fields required by its existing contract. On conflict or uncertain response, reload authoritative state before enabling the next write.
4. Use the existing scorecard read as the read-only refresh source. It includes Match lifecycle and ordered innings projections. Refresh once per ten-second interval only when the view is visible and the Match is in progress; preserve the last response on transient failure, prevent overlapping requests, and stop on terminal state, navigation, or authorization loss. The active scoring-entry view does not poll.
5. Close two existing Match authorization gaps at their existing route/service boundaries. Scope GET /matches with the current authenticated read scope. Apply the existing configuration-scope policy to POST /matches so an Assistant Coach's selected academy side is within current assignment scope; Head Coach access remains full. External opponents do not grant scope.
6. Keep the current API payloads and database schema. Keep frontend API models synchronized with backend OpenAPI/Pydantic contracts and document the synchronization point in the integration contract.

## Project Structure

### Documentation

~~~text
specs/015-live-ball-scoring/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/feature-015-integration.md
~~~

### Source and tests

~~~text
backend/src/routes/matches.py                    # existing create/list scope boundary
backend/src/services/match_service.py            # existing Match reads and writes
backend/src/services/scoring/                    # Feature 014 authoritative operations
backend/tests/unit/                               # authorization/list/create coverage
backend/tests/integration/                        # existing API/OCC coverage
backend/tests/integration/quickstart/
  test_015_quickstart_flow.py                     # required isolated backend quickstart

frontend/src/app/router.tsx                       # authenticated /matches routes
frontend/src/app/DeferredRoutes.tsx               # deferred Matches route
frontend/src/layouts/AppLayout.tsx                # navigation entry
frontend/src/features/matches/
  api/ types/ hooks/ components/ pages/           # Matches feature, typed API, UI flows
frontend/src/shared/api/client.ts                 # existing auth, CSRF, refresh, errors
frontend/src/features/teams/api/teamApi.ts         # existing Team selectors and rosters
frontend/src/shared/components/                   # existing dialogs, feedback, controls
frontend/e2e/live-ball-scoring-flow.spec.ts        # primary browser scoring journey
~~~

**Structure Decision**: Keep the current monorepo and add a cohesive matches feature module. Reuse existing application routing, authenticated layout, Match endpoints, Team APIs, and shared UI primitives. Modify only the existing Match route/service authorization behavior needed for secure discovery and coherent Assistant Coach creation. Feature 014 scoring services and projections remain unchanged.

The implementation must add docs/live-ball-scoring.md after the behavior is
implemented and verified, as required by Constitution Principle XII.

## Constitution Recheck

All gates remain satisfied after the design decisions above. The polling design has a bounded cadence and no extra service/dependency. The scope changes are authorization checks on existing API operations, with no schema or scoring-rule expansion. Implementation must still pass the quality gates and add the verified feature documentation required by the constitution.

## Complexity Tracking

No constitution violations or additional project layers are introduced.
