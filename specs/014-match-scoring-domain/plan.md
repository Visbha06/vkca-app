# Implementation Plan: Match Scoring Domain and Innings Foundation

**Branch**: 014-match-scoring-domain | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from specs/014-match-scoring-domain/spec.md

## Summary

Extend the existing Match aggregate into the authoritative match-scoring boundary. Add fixed match-scoped sides and participants, explicit scoring policy, innings, immutable delivery attempts with revision/correction history, wicket and fielder events, and transactionally maintained read models. Delivery history is authoritative for scored Matches; legacy Match performance rows remain readable through an explicit compatibility boundary and become non-editable once scoring begins.

The implementation will reuse the repository's UUID/versioned SQLAlchemy models, MatchService, atomic OCC helper, current database-backed authentication and team-scope resolver, Business Audit service, RAG mutation stager, and transactional background outbox. Normal delivery writes update live summaries synchronously and perform no queue or RAG work. Completion and corrections may stage one coalesced current-state refresh. The backend API and request-level Playwright coverage are the required client surface; no scorer UI is in scope.

## Technical Context

**Language/Version**: Python 3.12; TypeScript for request-level Playwright coverage

**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy 2 async ORM, Alembic, PostgreSQL with pgvector, existing arq/background outbox, pytest, pytest-mock, HTTPX, Playwright

**Storage**: PostgreSQL; one feature migration at revision 016

**Testing**: pytest unit and integration suites, isolated migration tests, the required backend quickstart test, and at least one request-level Playwright E2E test

**Target Platform**: Existing Linux FastAPI service and repository frontend test harness

**Project Type**: Web application with a FastAPI backend and React TypeScript frontend

**Performance Goals**: Bounded current-state and scorecard reads remain under 1 second for a 1000-attempt innings; one concurrent write succeeds and all competing stale writes return 409; correction of 100 attempts replays to an equivalent state

**Constraints**: No new runtime dependency; strict Pydantic request validation; database transaction is the atomic boundary for delivery, derived state, audit, and outbox intent; current DB user/role/team scope is authoritative; no external account rows for external participants; no ordinary-delivery queue, provider, or RAG work; no scorer UI, live public feed, DLS, Super Over, or automated umpiring

**Scale/Scope**: One Match may contain multiple innings and a bounded delivery history. The first implementation supports T20 defaults, explicit one-day policies, and manually completed test/other formats while retaining readable legacy matches and performance data.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Status | Evidence |
|---|---|---|
| I. Clean code | PASS | Domain rules are isolated in typed scoring services and pure replay/projection functions; existing Match and service boundaries are extended. |
| II. Simple UX | PASS | The required client surface is a small, predictable API with explicit state and errors; no new UI is required. |
| III. Responsive design | PASS | No frontend surface is added beyond request-level E2E coverage. |
| IV. Minimal dependencies | PASS | Reuses the current FastAPI/PostgreSQL/Alembic/Pydantic/background stack; no package is added. |
| V. Testing | PASS | Unit, integration, migration, quickstart, and request-level Playwright coverage are planned, including pytest-mock and isolated tests. |
| VI. MCP/context | PASS | Repository architecture and code patterns were inspected through the available codebase and ripgrep MCP tools before finalizing the plan. |
| VII. Database migrations | PASS | A linear Alembic revision 016, constraints, downgrade ordering, and migration integration coverage are specified. |
| VIII. UX completeness | PASS | The feature explicitly excludes a polished scorer UI; the API journey and error contract are complete for this increment. |
| IX. Concurrency | PASS | Match/innings OCC, attempted-sequence uniqueness, atomic rollback, and HTTP 409 stale conflict behavior are specified. |
| X. Strict typing | PASS | Strict Pydantic schemas, bounded component types, typed enums, and no untyped escape hatch are required. |
| XI. Frontend standards | PASS | No new visual frontend is planned; the existing Playwright harness is used for the required boundary test. |
| XII. Documentation | PASS | Research, data model, API contracts, scoring rules, compatibility/background behavior, and the exact quickstart are included; implementation must update product docs if it creates a user-facing workflow. |

No constitution violations require an exception. This check was re-evaluated after the Phase 1 artifacts were designed.

## Project Structure

### Documentation (this feature)

```
specs/014-match-scoring-domain/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── match-scoring-api.md
│   ├── scoring-rules.md
│   └── background-and-compatibility.md
└── tasks.md                 # Created later by speckit-tasks; not created here
```

### Source Code (repository root)

```
backend/
├── src/
│   ├── models/
│   │   ├── match.py                         # Extend lifecycle/result compatibility fields
│   │   └── scoring/
│   │       ├── match_side.py
│   │       ├── scoring_policy.py
│   │       ├── participant.py
│   │       ├── innings.py
│   │       ├── batting_entry.py
│   │       ├── transition_event.py
│   │       ├── delivery.py
│   │       ├── delivery_revision.py
│   │       ├── wicket_event.py
│   │       ├── delivery_fielder.py
│   │       ├── over.py
│   │       ├── participant_summary.py
│   │       └── match_participant_performance.py
│   ├── schemas/
│   │   └── scoring.py
│   ├── services/
│   │   ├── scoring/
│   │   │   ├── policy.py
│   │   │   ├── rules.py
│   │   │   ├── replay.py
│   │   │   ├── projections.py
│   │   │   ├── authorization.py
│   │   │   ├── audit.py
│   │   │   └── service.py
│   │   └── match_service.py                  # Reuse for configuration/lifecycle seam
│   ├── routes/
│   │   └── match_scoring.py
│   ├── services/data_quality_rules.py        # Add read-only scoring findings
│   └── models/__init__.py                    # Register every new ORM model
├── migrations/versions/
│   └── 016_match_scoring_domain.py
└── tests/
    ├── unit/
    │   ├── test_scoring_rules.py
    │   ├── test_scoring_replay.py
    │   ├── test_scoring_authorization.py
    │   └── test_scoring_projections.py
    └── integration/
        ├── test_match_scoring_migration.py
        ├── test_match_scoring_api.py
        ├── test_match_scoring_occ.py
        ├── test_match_scoring_audit.py
        ├── test_match_scoring_background.py
        ├── test_match_scoring_compatibility.py
        └── quickstart/test_014_quickstart_flow.py

frontend/
└── e2e/
    └── match-scoring-domain-flow.spec.ts

docs/
└── MATCH_SCORING.md                       # Add/update only if implementation creates a user-facing workflow

```

**Structure Decision**: Use the existing backend/frontend web-application layout. Scoring ORM models are grouped under a backend scoring package, domain decisions live in typed scoring services, and the router is registered through the existing API application. Existing Match, performance, auth, audit, RAG, background, and Data Quality modules are extended rather than duplicated.

## Phase 0: Research

Research and decisions are recorded in [research.md](./research.md). The repository review confirmed the reuse seams for MatchService, OCC, current role/team scope, Business Audit, RAG reconciliation, background outbox, model registration, API registration, and integration fixtures. Official MCC law references were used only to pin down the requested cricket semantics; product scope explicitly excludes advanced competition rules.

## Phase 1: Design

The Phase 1 artifacts are:

- [data-model.md](./data-model.md): normalized authoritative entities, read models, constraints, indexes, and state transitions.
- [contracts/match-scoring-api.md](./contracts/match-scoring-api.md): protected endpoints, strict request/response shapes, and conflict/error behavior.
- [contracts/scoring-rules.md](./contracts/scoring-rules.md): delivery components and all derived scoring invariants.
- [contracts/background-and-compatibility.md](./contracts/background-and-compatibility.md): transaction, audit, RAG/background, legacy performance, and Data Quality boundaries.
- [quickstart.md](./quickstart.md): the required 25-step backend journey plus focused tests and Playwright invocation.

No agent-context update script exists under .specify, .agents, or .codex in this repository, so no generated agent context file is part of this plan.

## Implementation Sequencing

1. Add typed enums, schemas, model registry imports, and migration 016 for the complete scoring schema.
2. Implement policy validation, fixed sides/participants, lifecycle guards, and current role/team authorization.
3. Implement pure delivery validation, derived metrics, strike/over/bowler transitions, wicket validation, and innings completion rules.
4. Implement immutable delivery revisions and replay; persist active read models transactionally and surface reconciliation-required state on incompatible correction.
5. Add Match-scoped scoring service commands and protected API routes with Match/innings OCC and uniform 409 handling.
6. Add derived participant performance projections and the compatibility adapter for existing Match batting/bowling/fielding performance reads; reject direct aggregate mutation for scored Matches.
7. Extend Business Audit, Data Quality, RAG source/refresh behavior, and background outbox only at the bounded completion/correction boundary.
8. Add unit, integration, migration, audit, authorization, compatibility, and quickstart tests; add the request-level Playwright E2E.
9. Run offline lint/type/test gates, migration upgrade/downgrade checks, and the exact quickstart commands. Update product documentation if the implemented API becomes user-facing.

## Complexity Tracking

No constitution violations are present, so no exception table is required. The separate normalized event/revision tables and pure replay module are justified by the specification's immutable correction provenance, reconciliation behavior, and requirement that derived scorecards remain replayable and reconcilable.
