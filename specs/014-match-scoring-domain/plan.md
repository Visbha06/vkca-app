# Implementation Plan: Match Scoring Domain and Innings Foundation

**Branch**: 014-match-scoring-domain | **Date**: 2026-08-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from specs/014-match-scoring-domain/spec.md

## Summary

Extend the existing Match aggregate into the authoritative match-scoring boundary. Add fixed match-scoped sides and participants, an immutable versioned format-capability policy, innings, immutable delivery attempts with revision/correction history, one wicket event per active delivery revision, retirement transitions, and transactionally maintained read models. Delivery history is authoritative for scored Matches; legacy Match performance rows remain readable through an explicit compatibility boundary and become non-editable when `delivery_history` is locked, before the first scoring write. Match lifecycle is the sole authority for abandonment, Innings lifecycle is the sole authority for reconciliation, and the canonical `blocking_state` is derived serialization rather than a second mutable state.

The implementation will reuse the repository's UUID/versioned SQLAlchemy models, MatchService, atomic OCC helper, current database-backed authentication and team-scope resolver, Business Audit service, RAG mutation stager, and transactional background outbox. Normal delivery writes update live summaries synchronously and perform no queue or RAG work. Successful Match completion and material correction stage the same canonical coalesced current-state refresh intent, at most once per logical refresh. The backend API and request-level Playwright coverage are the required client surface; no scorer UI is in scope.

## Technical Context

**Language/Version**: Python 3.12; TypeScript for request-level Playwright coverage

**Primary Dependencies**: FastAPI, Pydantic 2, SQLAlchemy 2 async ORM, Alembic, PostgreSQL with pgvector, existing arq/background outbox, pytest, pytest-mock, HTTPX, Playwright

**Storage**: PostgreSQL; one feature migration at revision 016

**Migration Path**: `backend/src/migrations/versions/016_match_scoring_domain.py`

**Testing**: pytest unit tests for every new public scoring function and API handler, complementary integration suites, isolated migration tests, the required parameterized backend quickstart test, and a request-level Playwright E2E test covering both Match variants; the final gate runs ESLint, strict application TypeScript, explicit `--strict` Node/Vite/Vitest/Playwright configuration TypeScript, and the Playwright journey

**Target Platform**: Existing Linux FastAPI service and repository frontend test harness

**Project Type**: Web application with a FastAPI backend and React TypeScript frontend

**Performance Goals**: For the defined 1000-attempt `test` fixture, at least 29 of 30 warm authenticated current-state reads remain at or below 1 second after five warm-ups; one concurrent write succeeds and all competing stale writes return 409; correction of 100 attempts replays to an equivalent state

**Constraints**: No new runtime dependency; strict Pydantic request validation derived from the locked FormatCapability and fixed scoring numeric bounds; database transaction is the atomic boundary for delivery, derived state, audit, and outbox intent; current DB user/role/team scope is authoritative; no external account rows for external participants; no ordinary-delivery queue, provider, or RAG work; no scorer UI, live public feed, DLS, Super Over, follow-on, or automated umpiring; arbitrary undo is deferred and uses the future correction seam

**Scale/Scope**: One Match may contain the immutable capability-defined innings sequence and a bounded delivery history. T20 and one-day use two fixed-over innings, test uses four ordered innings without follow-on or automatic target, and other requires an explicit sequence with manual completion. Legacy matches and performance data remain readable.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Status | Evidence |
|---|---|---|
| I. Clean code | PASS | Domain rules are isolated in typed scoring services and pure replay/projection functions; existing Match and service boundaries are extended. |
| II. Simple UX | PASS | The required client surface is a small, predictable API with explicit state and errors; no new UI is required. |
| III. Responsive design | PASS | No frontend surface is added beyond request-level E2E coverage. |
| IV. Minimal dependencies | PASS | Reuses the current FastAPI/PostgreSQL/Alembic/Pydantic/background stack; no package is added. |
| V. Testing | PASS | Unit tasks cover each new public scoring function and API handler; integration, migration, quickstart, and request-level Playwright coverage remain complementary, with pytest-mock and isolated tests. |
| VI. MCP/context | PASS | Repository architecture and code patterns were inspected through the available codebase and ripgrep MCP tools before finalizing the plan. |
| VII. Database migrations | PASS | A linear Alembic revision 016, constraints, downgrade ordering, and migration integration coverage are specified. |
| VIII. UX completeness | PASS | The feature explicitly excludes a polished scorer UI; the API journey and error contract are complete for this increment. |
| IX. Concurrency | PASS | Match/innings OCC, attempted-sequence uniqueness, atomic rollback, and HTTP 409 stale conflict behavior are specified. |
| X. Strict typing | PASS | Strict Pydantic schemas, bounded component types, typed enums, and no untyped escape hatch are required; T075 invokes the Node configuration compiler with explicit `--strict` because the existing `tsconfig.node.json` does not set the flag itself. |
| XI. Frontend standards | PASS | No new visual frontend is planned; the existing Playwright harness is used for the required boundary test. |
| XII. Documentation | PASS | The single required feature document is `docs/match-scoring-domain.md`; its task is sequenced after implementation and verification and must describe actual behavior, not an aspirational design. |

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
└── tasks.md                 # Actionable implementation and verification tasks
```

### Source Code (repository root)

```
backend/
├── src/
│   ├── main.py                              # Register the scoring router with the API application
│   ├── models/
│   │   ├── __init__.py                       # Register every new ORM model
│   │   ├── match.py                          # Extend lifecycle/result compatibility fields
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
│   │   ├── data_quality_rules.py             # Add read-only scoring findings
│   │   ├── data_quality_service.py           # Keep scoring findings separate from remediation
│   │   └── match_service.py                  # Reuse for configuration/lifecycle seam
│   ├── routes/
│   │   ├── match_scoring.py
│   │   └── data_quality.py                   # Extend read-only scoring findings
│   └── migrations/
│       └── versions/
│           └── 016_match_scoring_domain.py
└── tests/
    ├── unit/
    │   ├── test_scoring_rules.py
    │   ├── test_scoring_replay.py
    │   ├── test_scoring_authorization.py
    │   ├── test_scoring_commands.py
    │   ├── test_scoring_bowler_commands.py
    │   ├── test_scoring_correction_commands.py
    │   ├── test_scoring_completion_commands.py
    │   ├── test_scoring_public_handlers.py
    │   ├── test_scoring_data_quality.py
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
└── match-scoring-domain.md                 # Written after implementation and verification

```

**Structure Decision**: Use the existing backend/frontend web-application layout. Scoring ORM models are grouped under a backend scoring package, domain decisions live in typed scoring services, and the router is registered through the existing API application. Existing Match, performance, auth, audit, RAG, background, and Data Quality modules are extended rather than duplicated.

## Normative Scoring Design

`FormatCapability` is the single policy source for format behavior. The locked
policy stores its capability version, ordered `innings_sequence`, legal-ball
limit, over length, wicket limit, quota, consecutive-over rule, dismissal and
transition sets, completion modes, target mode, explicit Match-completion
boundary, and allowed result codes. It also uses the fixed
`SCORING_RUN_COMPONENT_MAX` and `SCORING_RUN_TOTAL_MAX` constants from
`spec.md`. The registry uses the existing canonical profiles: `T20` (`[A, B]`,
120 legal balls in six-ball overs, 24 per bowler, ten wickets, automatic
target), `one-day` (`[A, B]`, exactly 300 legal balls in six-ball overs, 60 per
bowler, ten wickets, automatic target), `test` (`[A, B, A, B]`, six-ball overs,
ten wickets, no innings limit/quota/target, declaration/draw/manual paths), and
`other` (all sequence and rule values supplied by policy and manual completion;
Match-level abandonment supplies `no_result`). API schemas, policy validation, scoring rules, replay, and completion
commands all consume this registry; no handler may infer format behavior from a
raw format string or an unrelated boolean.

Replay processes active delivery revisions and anchored transition events in
attempted-sequence order for each innings, then applies the locked sequence to
derive sides, targets, aggregate state, and result precedence. Fixed-over
Matches derive innings-2 target as innings-1 total plus one; test and other do
not derive a target. Within one fixed-over replay step, target reach takes
precedence over a same-delivery wicket or legal-ball limit. Reconciliation is
authoritative only on the Innings
`lifecycle_state`; it blocks all completion and produces a derived Match
`blocking_state` when present. Incomplete required innings blocks automatic
completion. Test `draw`, `declared`, and `manual` completion is accepted only
immediately after a completed innings and before an automatic result; `other`
uses its locked `explicit_match_completion_boundary`. Abandonment is a
Match-level administrative path only: it sets Match `abandoned`/`no_result`,
leaves the current Innings pending or in progress without completing it, and
serializes `blocking_state.kind = match_abandoned`.

A completed Match can be corrected only through the delivery-correction
command. The command uses a transaction-local
`completed → correction_reprocessing → completed|in_progress` lifecycle path;
the intermediate phase is never committed or externally visible. A compatible
non-terminal correction returns `in_progress`/`pending`; an incompatible later
transition leaves the Match `in_progress` and the affected Innings
`reconciliation_required`; an unsafe replay rolls back with 409. No ordinary
scoring command reopens a completed Match, and abandoned Matches remain closed.

Data Quality scoring findings are a Head-Coach-only read/report boundary. They
identify replay, identity, lifecycle, legacy, and malformed-state divergence
without repairing scoring rows or creating audit/outbox work; this feature has
no public trigger/re-run endpoint. Scoring amendments use the correction
command, and any existing Head-Coach-only non-scoring remediation remains
separate.

Business Audit uses a closed scoring-domain allowlist: successful scoring
initialization, innings start, innings completion, Match completion, and
delivery correction. Routine delivery entry, batter/retirement/bowler
selection, recalculation, background processing, and rejected or stale
commands use existing technical logging only. The existing audit infrastructure
records one bounded event for each committed allowlisted command.

Successful Match completion and material correction stage the same canonical
coalesced current-state refresh intent through the existing transactional
outbox. The stager deduplicates a logical refresh, so a completion or
correction cannot create a second refresh mechanism or more than one intent.

The event model intentionally permits zero or one `WicketEvent` per active
delivery revision. The delivery API accepts one optional wicket object; its
ordered `fielders[]` collection is canonical and persists to ordered
`DeliveryFielder` rows. A derived primary-fielder pointer is never an
independent input. Dismissal-specific zero/one/multiple fielder cardinality is
validated before persistence, and a second or conflicting wicket payload fails
closed with 422. Correction appends a replacement revision and supersedes the
old active revision; no void state is used. Retired hurt is an explicit
transition event and never a team-wicket event. Arbitrary undo is deferred;
future undo must delegate to the correction service boundary. The canonical
serialized progression indicator is `blocking_state` with explicit kind,
blocked flag, and reason code; it is derived from Match/Innings lifecycle and
active participant state and is never client-supplied.

## Phase 0: Research

Research and decisions are recorded in [research.md](./research.md). The repository review confirmed the reuse seams for MatchService, OCC, current role/team scope, Business Audit, RAG reconciliation, background outbox, model registration, API registration, and integration fixtures. Official MCC law references were used only to pin down the requested cricket semantics; product scope explicitly excludes advanced competition rules.

## Phase 1: Design

The Phase 1 artifacts are:

- [data-model.md](./data-model.md): normalized authoritative entities, capability policy, innings sequence, read models, constraints, indexes, and state transitions.
- [contracts/match-scoring-api.md](./contracts/match-scoring-api.md): protected endpoints, strict request/response shapes, capability-derived validation, and conflict/error behavior.
- [contracts/scoring-rules.md](./contracts/scoring-rules.md): capability profiles, delivery components, one-wicket cardinality, and derived scoring invariants.
- [contracts/background-and-compatibility.md](./contracts/background-and-compatibility.md): transaction, audit, RAG/background, legacy performance, and Data Quality boundaries.
- [quickstart.md](./quickstart.md): the parameterized 25-step internal/external backend journey, focused tests, benchmark, and Playwright invocation.

No agent-context update script exists under .specify, .agents, or .codex in this repository, so no generated agent context file is part of this plan.

## Implementation Sequencing

1. Add typed enums, the versioned FormatCapability registry, strict schemas, model registry imports, and migration 016 for the complete scoring schema.
2. Implement policy locking, explicit innings sequences, fixed sides/participants, lifecycle guards, and current role/team authorization.
3. Implement pure delivery validation, derived metrics, strike/over/bowler transitions, one-wicket validation, retirement transitions, and capability-defined completion rules.
4. Implement immutable delivery revisions and deterministic multi-innings replay; persist active read models transactionally, keep reconciliation authoritative on Innings lifecycle, derive `blocking_state`, and apply the correction-only completed-Match reprocessing path on incompatible correction.
5. Add Match-scoped scoring service commands and protected API routes with Match/innings OCC and uniform 409 handling; register the scoring router through the existing API application before API verification.
6. Add derived participant performance projections and the compatibility adapter for existing Match batting/bowling/fielding performance reads; reject direct aggregate mutation for scored Matches.
7. Extend Business Audit, Data Quality, RAG source/refresh behavior, and background outbox only at the bounded completion/correction boundary.
8. Add unit tests for every new public scoring function and API handler, complementary integration/migration/audit/compatibility/quickstart tests, the focused benchmark, and the parameterized request-level Playwright E2E; include exact run/aggregate boundary cases and lifecycle/blocking serialization.
9. Run the exact backend Ruff/format/type/unit/integration/Alembic/quickstart gates plus frontend ESLint, strict application TypeScript, explicit `--strict` TypeScript for `tsconfig.node.json`, and the Playwright journey.
10. After all implementation and verification gates pass, write the actual feature documentation at `docs/match-scoring-domain.md`.

## Complexity Tracking

No constitution violations are present, so no exception table is required. The separate normalized event/revision tables and pure replay module are justified by the specification's immutable correction provenance, reconciliation behavior, and requirement that derived scorecards remain replayable and reconcilable.
