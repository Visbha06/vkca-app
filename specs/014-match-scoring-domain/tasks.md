---

description: "Implementation tasks for the Match Scoring Domain and Innings Foundation"
---

# Tasks: Match Scoring Domain and Innings Foundation

**Input**: Design documents from `specs/014-match-scoring-domain/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Unit tests are mandatory for all new backend logic, including every new public scoring service/function and API handler. Integration tests remain complementary for cross-module, database, migration, authorization, and concurrency behavior. The specification also requires migration, integration, quickstart, benchmark, and request-level Playwright coverage. Use `pytest-mock` for isolated external-service and database-boundary tests; all tests must run without Internet access.

**Implementation boundary**: Extend the existing `Match`, `MatchService`, authentication/team-scope, Business Audit, performance, RAG, and background-outbox seams. Delivery history and immutable revisions are the authoritative scoring source; persisted projections are reconcilable read models. Format behavior comes from the immutable `FormatCapability` registry and locked innings sequence. The initial event model permits one `WicketEvent` per active delivery revision; retired hurt is a transition event, not a team-wicket event. Arbitrary undo is deferred; delivery correction is the current amendment path. No undo implementation, endpoint, or dedicated undo test suite is required.

**Documentation boundary**: The only feature documentation task is T076. It creates or updates `docs/match-scoring-domain.md` after implementation and all verification gates pass, and must describe actual behavior rather than an aspirational design.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the package and test seams needed by the scoring implementation without adding runtime dependencies.

- [X] T001 [P] Create the scoring package scaffolding in `backend/src/models/scoring/__init__.py` and `backend/src/services/scoring/__init__.py`, keeping exports explicit and limited to the new domain boundary.
- [X] T002 [P] Create reusable scoring test builders for users, teams, fixed participants, capability policies, innings sequences, deliveries, wicket events, and revisions in `backend/tests/fixtures/match_scoring.py` for unit and integration isolation.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared typed domain, complete persistence schema, strict request boundary, and common authorization/error seams. No user-story implementation can begin until this phase is complete.

- [X] T003 Define canonical `T20`/`one-day`/`test`/`other` scoring identifiers, FormatCapability profiles, the one-day positive-multiple-of-30 legal-limit and one-fifth derived-quota policy, Test consecutive-over prohibition, dismissal/transition/lifecycle values (including transaction-local `correction_reprocessing` and no independent Innings abandonment), `SCORING_RUN_COMPONENT_MAX = 2,147,483,647`, `SCORING_RUN_TOTAL_MAX = 2,147,483,647`, canonical blocking-state values, explicit Match-completion boundary values, completion modes, and result/authority codes in `backend/src/enums.py`.
- [X] T004 [P] Extend the existing Match model and response compatibility fields for lifecycle state, scoring authority, result code/details, and configuration timestamp in `backend/src/models/match.py` and `backend/src/schemas/match.py`.
- [X] T005 [P] Implement stable MatchSide and locked ScoringPolicy ORM entities with canonical format/profile identifier and version, ordered innings sequence, side-kind, team/opponent, legal-ball limit, over length, wicket limit, consecutive-over rule, dismissal/transition sets, target mode, explicit Match-completion boundary, innings/Match completion modes, result-code set, quota, declaration, draw, and manual-completion constraints; represent the one-day quota as server-derived from its locked legal-ball limit in `backend/src/models/scoring/match_side.py` and `backend/src/models/scoring/scoring_policy.py`.
- [X] T006 [P] Implement fixed MatchParticipant and BattingOrderEntry ORM entities with internal-player versus external-display identity boundaries, positive unique batting positions, and participation states in `backend/src/models/scoring/participant.py` and `backend/src/models/scoring/batting_entry.py`.
- [X] T007 [P] Implement extensible Innings and append-only transition-event ORM entities with ordered batting/fielding sides, active pair/bowler, target, completion, canonical reconciliation lifecycle/reason, derived `blocking_state` snapshot, projection, and OCC fields, without an independent Innings abandonment state, in `backend/src/models/scoring/innings.py` and `backend/src/models/scoring/transition_event.py`.
- [X] T008 [P] Implement stable attempted-delivery parents and immutable revision rows with attempted sequence uniqueness, active-revision state, observed run components, derived scoring fields, provenance, and revision metadata in `backend/src/models/scoring/delivery.py` and `backend/src/models/scoring/delivery_revision.py`.
- [X] T009 [P] Implement explicit WicketEvent and DeliveryFielder ORM entities with one-to-zero-or-one wicket cardinality per active delivery revision, current public dismissal vocabulary excluding reserved future identifiers, dismissed end, team-wicket/bowler-credit inputs, ordered fielder roles/cardinality, and Match-scoped fielder references in `backend/src/models/scoring/wicket_event.py` and `backend/src/models/scoring/delivery_fielder.py`.
- [X] T010 [P] Implement rebuildable innings over, innings participant summary, and Match participant performance projection entities in `backend/src/models/scoring/over.py`, `backend/src/models/scoring/participant_summary.py`, and `backend/src/models/scoring/match_participant_performance.py`.
- [X] T011 Register every scoring ORM model and relationship with the metadata import boundary in `backend/src/models/__init__.py`, and verify that model discovery includes all parent and child tables before migration generation/checks.
- [X] T012 Create reversible Alembic revision 016 with parent-before-child table creation, canonical capability/sequence and explicit-completion-boundary fields, one-day positive-multiple-of-30 legal-limit validation and derived-quota persistence, exact scoring component/total checks, no independent Innings abandonment or reconciliation boolean, correction lifecycle/OCC columns, foreign keys, partial active-revision uniqueness, one-wicket-per-revision uniqueness, ordered `delivery_fielders` uniqueness, sequence/order indexes, downgrade ordering, and re-upgrade safety in `backend/src/migrations/versions/016_match_scoring_domain.py`.
- [X] T013 Define strict Pydantic request and response schemas for canonical capability-derived configuration, sides, participants, innings commands, delivery facts, exact component/aggregate bounds, extras, one optional wicket object with ordered `fielders[]`, corrections with Match/Innings versions, Match-only abandonment, canonical `blocking_state`, completion boundaries, bounded history, projections, scorecards, and structured errors in `backend/src/schemas/scoring.py`; require a one-day positive legal-ball limit divisible by 30, derive rather than accept its quota, and reject unknown fields, capability contradictions, reserved future dismissals, duplicate wicket shapes, separately supplied primary-fielder data, client-derived fields, and innings-level abandonment.
- [X] T014 Implement the shared scoring command context and authorization adapter that reloads the active database User and delegates current role/team scope decisions to `backend/src/services/role_scope.py` in `backend/src/services/scoring/authorization.py`.
- [X] T015 Extend the standard exception translation seam for scoring validation, visibility, lifecycle, revision, reconciliation, and OCC failures in `backend/src/middleware/error_handlers.py`, preserving the repository error envelope and HTTP 401/403/404/409/422 mapping.

## Phase 3: User Story 1 - Freeze Match Participants and Batting Order (Priority: P1) 🎯 MVP

**Goal**: Configure an internal or external Match once, snapshot its two sides and fixed participants, preserve batting order and the capability-defined innings sequence, and prevent later roster changes from changing scoring identity.

**Independent Test**: Configure both an internal Match and an external Match, mutate the source academy roster afterward, then read the Match and verify fixed side identity, participant identity, external privacy, batting order, capability policy, and innings sequence; invalid duplicate/cross-side configuration must roll back atomically.

### Tests for User Story 1

- [X] T016 [P] [US1] Add unit coverage for internal/external participant validation, current team scope, capability-policy authorization, duplicate participant/order rejection, and rejection of account fields on external identities in `backend/tests/unit/test_scoring_authorization.py` using `pytest-mock` for resolver boundaries.
- [X] T017 [P] [US1] Add unit coverage for the public capability-profile resolver, `configure_match`/`configure_scoring` service commands, and the `PUT /matches/{match_id}/configuration` handler, including canonical `T20`/`one-day`/`test`/`other` identifiers, one-day configured legal limits and one-fifth derived quotas (including missing/non-divisible limits and client-supplied quota rejection), rejection of lowercase/underscore/profile-name aliases, capability-derived fields, version serialization, strict errors, and atomic failure behavior in `backend/tests/unit/test_scoring_commands.py`.
- [X] T018 [P] [US1] Add authenticated API integration coverage for internal and external configuration using canonical format values, roster mutation stability, capability/innings-sequence validation, Match-version conflicts, atomic invalid configuration rollback, and application-level reachability of a mounted scoring route in `backend/tests/integration/test_match_scoring_api.py`.

### Implementation for User Story 1

- [X] T019 [US1] Implement the deterministic canonical `T20`, `one-day`, `test`, and `other` FormatCapability profiles, six-ball over lengths, fixed T20 limits/quotas/wicket rules, one-day explicit positive-multiple-of-30 legal limits with server-derived one-fifth quotas, Test consecutive-over prohibition with no quota, fixed/test innings sequences, dismissal/transition sets, target modes, explicit Match-completion boundaries, completion modes, result-code sets, reserved future-dismissal rejection, and pre-scoring policy locking in `backend/src/services/scoring/policy.py`.
- [X] T020 [US1] Implement the Match configuration command through the existing MatchService seam, including fixed side snapshots, capability policy persistence, ordered innings sequence, participant creation, Match-version OCC, and one-transaction rollback behavior in `backend/src/services/match_service.py` and `backend/src/services/scoring/service.py`.
- [X] T021 [US1] Implement side eligibility, internal academy-player ownership, external match-scoped identity restrictions, duplicate/cross-side checks, stable batting-order validation, and capability/sequence consistency in `backend/src/services/scoring/authorization.py` and `backend/src/services/scoring/service.py`.
- [X] T022 [US1] Add `PUT /matches/{match_id}/configuration` with strict request parsing, capability-derived validation, scoped authorization, versioned response serialization, and configuration conflict/validation handling in `backend/src/routes/match_scoring.py`; after the router exists, import its `match_scoring_router` and register it in `backend/src/main.py` using the existing API-router convention so the route is reachable before API verification.
- [X] T023 [US1] Extend existing Match retrieval/serialization to expose lifecycle, scoring authority, locked capability, and innings sequence while preserving legacy Match metadata and result behavior in `backend/src/schemas/match.py` and `backend/src/routes/matches.py`.
- [X] T024 [US1] Register successful scoring configuration as the allowlisted scoring-initialization Business Audit action with actor, Match target, capability/sequence identifiers, bounded metadata, and caller-transaction rollback semantics in `backend/src/services/business_audit_registry.py`, `backend/src/services/scoring/audit.py`, and `backend/src/services/business_audit_service.py`.

**Checkpoint**: US1 is independently demonstrable when fixed internal/external participant configuration, capability policy, innings sequence, and batting order survive roster changes and all invalid configurations leave the prior Match unchanged.

## Phase 4: User Story 2 - Start an Innings and Record Authoritative Deliveries (Priority: P1)

**Goal**: Start a valid innings and atomically append authoritative delivery attempts for ordinary runs, boundaries, five bat runs, wides, no-balls, byes, leg-byes, penalties, wickets, and fielders while maintaining a capability-driven, replayable current projection.

**Independent Test**: Use a configured fixture Match, start an innings with a valid pair and bowler, submit the specified extras-heavy and wicket sequence, and compare persisted totals, legal balls, balls faced, bowler charges, one-wicket behavior, wicket state, and active selections with a pure replay.

### Tests for User Story 2

- [ ] T025 [P] [US2] Add unit tests for canonical delivery classification and component validation covering ordinary runs, boundaries, five bat runs, single/multiple wides, no-ball plus additional runs, byes, leg-byes, penalties, exact minimum/maximum/below-minimum/above-maximum component boundaries, delivery-total and innings/match aggregate overflow, totals, balls faced, bowler-conceded runs, one optional wicket object, dismissal-specific zero/one/multiple fielder cardinality and ordered roles, duplicate/conflicting wicket rejection, reserved future-dismissal rejection, and all capability-listed dismissal effects in `backend/tests/unit/test_scoring_rules.py`.
- [ ] T026 [P] [US2] Add pure replay and projection unit tests for innings initialization, active delivery folding, over/participant summary derivation, wicket state, retired-hurt transitions, unresolved replacement-batter blocking, canonical `blocking_state` derivation for pending/completed/in-progress/terminal states with batter-before-bowler precedence, Match-level abandonment with an incomplete current Innings, and no independent Innings abandonment state in `backend/tests/unit/test_scoring_replay.py` and `backend/tests/unit/test_scoring_projections.py`.
- [ ] T027 [P] [US2] Add authenticated API integration coverage for innings start, legal/illegal delivery append, exact component/aggregate bounds, extras combinations, dismissal-specific zero/one/multiple fielder cardinality, ordered `fielders[]` persistence/serialization and derived primary-fielder behavior, one-wicket persistence, duplicate/conflicting wicket rejection, rejection before/after lifecycle boundaries, canonical blocking-state serialization, explicit rejection of innings-level abandonment, Match-level abandonment serialization, and next-batter gating in `backend/tests/integration/test_match_scoring_api.py`.
- [ ] T028 [P] [US2] Add unit coverage for public `start_innings`, `append_delivery`, `select_next_batter`, `retire_hurt`, and `retired_hurt_return` commands plus their protected route handlers, including server-derived response fields, canonical `blocking_state`, exact run-boundary errors, rollback/error mapping, and the allowlisted innings-start audit event (actor, target, action, bounded metadata, and no event on failed or invalid starts) in `backend/tests/unit/test_scoring_commands.py`.

### Implementation for User Story 2

- [ ] T029 [US2] Implement one canonical scoring-rule classifier for the fixed component/total bounds, checked aggregate addition, extras coexistence, total runs, legal-ball status, completed runs, balls faced, bowler-conceded runs, boundary counts, one-wicket cardinality/effects, ordered fielder associations and derived primary-fielder mapping, capability limits, reserved future-dismissal rejection, and fail-closed unsupported combinations in `backend/src/services/scoring/rules.py`.
- [ ] T030 [US2] Implement a pure replay state machine over active delivery revisions and explicit transition events, including capability/innings-sequence validation, active batter validation, wicket resolution, retirement transitions, participation state, strike inputs, and deterministic state snapshots in `backend/src/services/scoring/replay.py`.
- [ ] T031 [US2] Implement projection builders and persistence for innings totals, extras, wickets, overs, active state, participant summaries, fall-of-wicket inputs, target/chase fields, and projection revision in `backend/src/services/scoring/projections.py`.
- [ ] T032 [P] [US2] Extend scoring authorization decisions for fixed Match-participant membership, batting-side/fielding-side ownership, active striker/non-striker validity, eligible current bowler, dismissed states, unresolved vacancies, and capability-defined innings order in `backend/src/services/scoring/authorization.py`.
- [ ] T033 [US2] Implement transactional `start_innings` and `append_delivery` commands with expected innings/Match versions, monotonic attempted sequence, strict observed-fact validation, immutable first revisions, one-wicket-per-revision enforcement, projection rebuild, and full rollback on failure; on a committed innings start only, emit the allowlisted bounded Business Audit event through the existing audit seam in `backend/src/services/scoring/service.py` and `backend/src/services/scoring/audit.py`.
- [ ] T034 [US2] Implement wicket/fielder persistence using ordered `DeliveryFielder` associations as the canonical source, derive any primary-fielder compatibility pointer, enforce dismissal-specific zero/one/multiple fielder cardinality and roles, apply team-wicket and bowler-credit semantics, reject one-event duplicates/conflicts, support replacement-batter selection, enforce retired-hurt transition/return and retired-out restrictions, and record explicit transition events in `backend/src/services/scoring/service.py` and `backend/src/models/scoring/wicket_event.py`.
- [ ] T035 [US2] Add protected start, innings read, bounded delivery-history, next-batter, retired-hurt, and retired-hurt-return endpoints with capability-derived and server-derived response fields in `backend/src/routes/match_scoring.py`.
- [ ] T036 [US2] Enforce the ordinary-delivery transaction boundary so synchronous append updates projections without Business Audit, queue, provider, embedding, or RAG work; keep next-batter and retirement/return selection outside the Business Audit allowlist while retaining request/version/outcome logging without raw payloads in `backend/src/services/scoring/service.py` and `backend/src/services/scoring/audit.py`.

**Checkpoint**: US2 is independently demonstrable when a replay of active revisions exactly matches the persisted innings projection after the required ordinary, extras-heavy, one-wicket, and retired-hurt flows.

## Phase 5: User Story 3 - Maintain Strike, Overs, and Bowler Eligibility (Priority: P1)

**Goal**: Keep strike, legal-ball/over progression, next-bowler selection, deterministic suggestions, consecutive-over rules, and legal-ball bowler quotas correct across normal and illegal attempts under the locked capability.

**Independent Test**: Score odd/even outcomes across an over with wides/no-balls interspersed, verify legal-ball and end-of-over transitions, query the default bowler, override it with an eligible choice, and verify quota/consecutive-over rejection.

### Tests for User Story 3

- [ ] T037 [P] [US3] Add unit coverage for completed-run parity, illegal-delivery strike behavior, end-of-over exchange, legal-ball indexes, deterministic bowler suggestion, configured one-day quota derivation and usage, Test consecutive-over exclusion despite no quota, and no-eligible-bowler errors in `backend/tests/unit/test_scoring_rules.py` and `backend/tests/unit/test_scoring_projections.py`.
- [ ] T038 [P] [US3] Add authenticated API integration coverage for six-legal-ball over completion, illegal attempts not consuming balls/quota, configurable one-day quota responses, Test next-bowler exclusion after a completed over, next-bowler GET/POST, explicit overrides, previous-over preference, and quota conflicts in `backend/tests/integration/test_match_scoring_api.py`.
- [ ] T039 [P] [US3] Add unit coverage for public next-bowler query/selection commands and `GET/POST /matches/{match_id}/innings/{innings_id}/next-bowler` handlers, including override reasons, transition anchoring, OCC, and proof that routine next-bowler operations create no Business Audit event in `backend/tests/unit/test_scoring_bowler_commands.py`.

### Implementation for User Story 3

- [ ] T040 [US3] Implement strike progression, completed-run parity, legal-ball indexing, over numbering, ball-in-over derivation, end-of-over exchange, and explicit next-state requirements in `backend/src/services/scoring/rules.py` and `backend/src/services/scoring/replay.py`.
- [ ] T041 [US3] Implement reusable bowler eligibility/quota decisions, one-day quota derivation from its locked legal-ball limit, capability-derived legal-ball accounting, consecutive-over exclusion for T20, one-day, and Test, normalized name/ID tie-breaks, and Test/other no-hidden-quota behavior in `backend/src/services/scoring/policy.py` and `backend/src/services/scoring/authorization.py`.
- [ ] T042 [US3] Implement next-bowler query/selection commands, explicit override reasons, transition anchoring, innings OCC, and capability checks without creating Business Audit events for routine selection in `backend/src/services/scoring/service.py` and `backend/src/routes/match_scoring.py`.
- [ ] T043 [US3] Persist and expose structured over progress, completed-bowler history, quota usage, capability, and next-bowler eligibility reasons without using decimal overs as arithmetic or source-of-truth state in `backend/src/services/scoring/projections.py` and `backend/src/routes/match_scoring.py`.

**Checkpoint**: US3 is independently demonstrable when legal-ball counts and strike/over/bowler state remain correct despite any number of illegal attempts between legal balls.

## Phase 6: User Story 4 - Correct Scoring Without Losing History (Priority: P1)

**Goal**: Correct an earlier delivery through immutable revisions, rebuild all affected state, preserve provenance, mark incompatible later transitions explicitly, and reject stale concurrent writers. Arbitrary undo remains future scope.

**Independent Test**: Score several deliveries, correct an earlier attempt, compare the persisted result with a clean replay of the final active stream, inspect superseded history, and submit two stale mutations to verify exactly one succeeds and no duplicate active sequence exists.

### Tests for User Story 4

- [ ] T044 [P] [US4] Add revision-chain, correction-boundary, canonical fielder-association replacement, replay-equivalence, incompatible-transition, Innings reconciliation lifecycle/clearing, canonical blocking-state, and completed-Match `correction_reprocessing → completed|in_progress` unit tests in `backend/tests/unit/test_scoring_replay.py`.
- [ ] T045 [P] [US4] Add integration tests for concurrent delivery writes, stale corrections/selections/completion, completed-Match correction reopening and non-terminal result, transient reprocessing invisibility, revision conflicts, atomic rollback, unique attempted sequence, no ordinary reopen path, and standard HTTP 409 behavior in `backend/tests/integration/test_match_scoring_occ.py`.
- [ ] T046 [P] [US4] Add unit coverage for public `correct_delivery`/reconciliation commands and the correction endpoint, including required Match and Innings versions, authorized completed-Match reopening only through correction, final `completed` versus `in_progress`/`pending` outcomes, reconciliation blocking/clearing, bounded reason, OCC/error translation, audit/supersession response, and active-history serialization in `backend/tests/unit/test_scoring_correction_commands.py`.

### Implementation for User Story 4

- [ ] T047 [US4] Implement append-only correction revisions, active-revision supersession, expected Match/Innings/revision checks, predecessor links, author/time/reason provenance, exactly-one-active-revision enforcement without a void state, and a reusable correction command boundary in `backend/src/services/scoring/service.py` and `backend/src/models/scoring/delivery_revision.py`.
- [ ] T048 [US4] Implement correction-boundary replay, full downstream projection rebuild, target/chase/result recalculation, deterministic multi-innings replay, canonical Innings reconciliation lifecycle/clearing, derived blocking state, and the safe completed-Match `correction_reprocessing → completed|in_progress` outcomes for incompatible later transitions in `backend/src/services/scoring/replay.py` and `backend/src/services/scoring/projections.py`.
- [ ] T049 [US4] Enforce Match, innings, attempted-sequence, delivery-revision, transition, capability, and correction-reprocessing OCC checks and map stale/lifecycle/reconciliation conflicts to the repository 409 response without partial mutations in `backend/src/services/scoring/service.py`, `backend/src/services/occ.py`, and `backend/src/middleware/error_handlers.py`.
- [ ] T050 [US4] Add the correction endpoint with expected Match and active revision versions, completed-Match reopening only through the transaction-local correction path, final lifecycle/blocking serialization, bounded reason, active-history response, and no direct revision replacement/deletion or undo path in `backend/src/routes/match_scoring.py`.
- [ ] T051 [US4] Record the allowlisted delivery-correction Business Audit event for append-only superseding revisions, including prior/final lifecycle and bounded metadata, and stage the canonical coalesced current-state refresh after a successful material correction in `backend/src/services/scoring/audit.py` and `backend/src/services/scoring/service.py`.

**Checkpoint**: US4 is independently demonstrable when old revisions remain immutable and a correction produces the same state as replaying the corrected active history from the beginning.

## Phase 7: User Story 5 - Complete Innings, Chase a Target, and Finish a Match (Priority: P1)

**Goal**: Derive innings completion, fixed-over targets, multi-innings aggregate state, Match lifecycle, and capability-listed results from completed delivery history, while requiring explicit policy/authorization for manual outcomes.

**Independent Test**: Complete a first T20 innings, start the second innings from its derived target, reach the target early, and verify automatic innings/Match completion plus win-by-wickets result details; also cover test declaration/draw, other manual completion, and Match-level abandonment/no-result paths.

### Tests for User Story 5

- [ ] T052 [P] [US5] Add unit tests for the ten-wicket and exact T20 120-ball limit, configured one-day legal-ball limits with one-fifth derived quotas, target-reached precedence when one delivery also reaches a wicket or legal-ball limit, test declaration advancing the sequence, test draw/declared/manual only immediately after a completed innings and before an automatic result, other manual at each configured explicit boundary, Match-only abandonment/no-result from any non-terminal state without unresolved reconciliation, preservation of the current Innings `pending`/`in_progress` lifecycle on abandonment, canonical blocking-state precedence, fixed-over runs/wickets remaining, test aggregate result, win-by-runs, win-by-wickets, tie, draw, declared, and manual result derivation in `backend/tests/unit/test_scoring_rules.py` and `backend/tests/unit/test_scoring_projections.py`.
- [ ] T053 [P] [US5] Add authenticated API integration coverage for internal and external first-innings completion, derived target, fixed-over chase completion and tie, test declaration/draw/declared boundary behavior, other manual boundary behavior, Match-level abandonment serialization with no independent Innings abandonment, rejection of innings-level `abandonment`, and rejection of unsupported or stale completion requests in `backend/tests/integration/test_match_scoring_api.py`.
- [ ] T054 [P] [US5] Add unit coverage for public `complete_innings`/`complete_match` commands in the scoring service and MatchService plus their completion handlers, including Match-only abandonment, result precedence, capability result-code validation, server-derived totals, bounded reasons, exact component/aggregate overflow behavior, canonical `blocking_state`, and lifecycle serialization in `backend/tests/unit/test_scoring_completion_commands.py`.

### Implementation for User Story 5

- [ ] T055 [US5] Implement automatic innings completion triggers and locked explicit Match-completion boundaries for test and other, plus capability-defined declaration/manual policy gates and the separate Match-only abandonment/no-result path. A successful Match completion MUST stage the same canonical coalesced current-state refresh intent used by material correction, in the committing transaction and at most once per logical refresh, without inferring DLS, Super Over, follow-on, interruption, or other unsupported rules in `backend/src/services/scoring/policy.py`, `backend/src/services/scoring/rules.py`, `backend/src/services/scoring/service.py`, and `backend/src/services/background_jobs/outbox.py`.
- [ ] T056 [US5] Implement ordered innings creation, fixed-over target/chase state, test aggregate state, wickets/balls remaining, Match lifecycle transition including Match-only abandonment with unchanged current-Innings lifecycle, deterministic result precedence, derived blocking state, structured result code/details, and compatibility result text in `backend/src/services/scoring/projections.py` and `backend/src/services/match_service.py`.
- [ ] T057 [US5] Add protected innings-completion and Match-completion commands with expected versions, explicit rejection of innings-level abandonment, Match-only abandonment behavior, capability-derived normal results, exact completion-boundary validation, explicit bounded reasons for allowed manual/declaration/draw outcomes, canonical `blocking_state` response, and completion audit events in `backend/src/routes/match_scoring.py` and `backend/src/services/scoring/audit.py`.
- [ ] T058 [US5] Ensure completion and correction reopening cannot bypass Innings-authoritative reconciliation, canonical blocking-state precedence, target/lifecycle invariants, ordered innings policy, result-code capability, or required completion mode; ensure innings-level abandonment is rejected, Match-level abandonment preserves the current Innings' underlying lifecycle, and client-supplied final totals/results are rejected in `backend/src/services/scoring/service.py` and `backend/src/schemas/scoring.py`.

**Checkpoint**: US5 is independently demonstrable when a T20 chase completes automatically at the derived target, a test sequence replays to a deterministic aggregate result, and all result fields are reproducible from completed innings.

## Phase 8: User Story 6 - Read Coherent Internal and External Scorecards (Priority: P2)

**Goal**: Provide protected, coherent live/complete innings and scorecard reads for internal and external Matches, preserve external identity privacy, expose derived summaries and Data Quality findings, and make legacy performance/RAG/background boundaries explicit.

**Independent Test**: Read completed internal and external scorecards as Head Coach, scoped Assistant Coach, and permitted Player; verify delivery-derived batting/bowling/fielding/extras/fall-of-wickets/overs/target/result data, read-only Player behavior, current Team scope, no academy identity for opposition, and verify that only Head Coaches can view scoring Data Quality findings while scoring corrections remain on the normal correction authorization path.

### Tests for User Story 6

- [ ] T059 [P] [US6] Add unit coverage for scorecard serialization, canonical `blocking_state` and Match-derived reconciliation serialization across pending/completed/in-progress/terminal precedence, ordered `fielders[]` and derived primary-fielder serialization, participant summaries, extras/fall-of-wickets/overs/target/result projections, capability/innings-order output, external identity redaction, and legacy authority labels in `backend/tests/unit/test_scoring_projections.py`.
- [ ] T060 [P] [US6] Add internal/external scorecard, Player read-only, Assistant Coach scope, Head-Coach-only scoring Data Quality visibility, legacy aggregate-only readability/writes, delivery-history aggregate-write conflict for every direct write, and opposition identity-isolation integration coverage in `backend/tests/integration/test_match_scoring_compatibility.py`.
- [ ] T061 [P] [US6] Add unit coverage for every new public scorecard/innings/history handler and cross-cutting boundary function in `backend/tests/unit/test_scoring_public_handlers.py`, covering `backend/src/routes/match_scoring.py`, `backend/src/routes/matches.py`, `backend/src/routes/performances.py`, `backend/src/routes/data_quality.py`, `backend/src/services/match_service.py`, `backend/src/services/performance_service.py`, `backend/src/services/business_audit_registry.py`, `backend/src/services/scoring/audit.py`, `backend/src/services/business_audit_service.py`, `backend/src/services/data_quality_service.py`, `backend/src/services/data_quality_rules.py`, `backend/src/services/occ.py`, `backend/src/middleware/error_handlers.py`, `backend/src/services/rag/builders/match.py`, `backend/src/services/rag/registry.py`, `backend/src/services/background_jobs/registry.py`, `backend/src/services/background_jobs/outbox.py`, and `backend/src/services/background_jobs/handlers/rag_reconciliation.py` with `pytest-mock` isolation, including 403 behavior for Assistant Coach/Player access to scoring Data Quality findings.
- [ ] T062 [P] [US6] Add dedicated Data Quality unit and integration coverage, including the Head-Coach-only read/reporting handler and no-public-rerun boundary, for replay/projection mismatch, duplicate or conflicting active revisions/sequences, invalid player/team/Match identities, lifecycle/state violations, Innings lifecycle `reconciliation_required` versus derived Match blocking state, legacy-data divergence or malformed historical state, and proof that scoring findings do not repair scoring data or create audit/outbox work; verify that scoring corrections use the normal Head Coach/scoped Assistant Coach correction path and keep any existing non-scoring remediation path separate in `backend/tests/unit/test_scoring_data_quality.py` and `backend/tests/integration/test_match_scoring_compatibility.py`.

### Implementation for User Story 6

- [ ] T063 [US6] Implement bounded scorecard, innings, participant-summary, delivery-history, extras, wickets with ordered `fielders[]` and derived primary-fielder mapping, fall-of-wickets, target/chase, result, canonical `blocking_state`, capability, authority, and projection-revision response mapping in `backend/src/schemas/scoring.py`, `backend/src/services/scoring/projections.py`, and `backend/src/routes/match_scoring.py`.
- [ ] T064 [P] [US6] Implement the legacy performance compatibility adapter: keep `legacy_aggregate` Match reads/writes supported without assuming delivery history, lock configured scored Matches to `delivery_history`, reject every direct aggregate write for delivery-history Matches, synchronize only compatible academy-derived rows with derived provenance, preserve innings identity, and keep external participants out of player-keyed tables in `backend/src/services/performance_service.py` and `backend/src/routes/performances.py`.
- [ ] T065 [P] [US6] Enforce protected read scope for Match/innings/scorecard/history endpoints, current Assistant Coach assignment checks, Player read-only behavior, Head-Coach-only scoring Data Quality findings, and external-side non-authorization in `backend/src/services/scoring/authorization.py`, `backend/src/routes/match_scoring.py`, and `backend/src/routes/data_quality.py`.
- [ ] T066 [P] [US6] Add read-only scoring consistency findings for projection/replay mismatch, duplicate active revisions/sequences, invalid participant/lifecycle/over/quota state, one-wicket violations, reconciliation-required state, and legacy-adapter divergence in `backend/src/services/data_quality_rules.py` and `backend/src/schemas/data_quality.py`.
- [ ] T067 [P] [US6] Extend Match-level RAG builder and source registry behavior to refresh bounded current scoring summaries only after completion/material correction, with no Delivery source or per-delivery provider/queue work, in `backend/src/services/rag/builders/match.py` and `backend/src/services/rag/registry.py`.
- [ ] T068 [US6] Register an idempotent coalesced scoring refresh handler that reloads committed current state, uses bounded identifiers/reasons, remains safe on duplicate delivery, and never creates scoring truth or Business Audit events in `backend/src/services/background_jobs/registry.py`, `backend/src/services/background_jobs/handlers/rag_reconciliation.py`, and `backend/src/services/background_jobs/outbox.py`.

**Checkpoint**: US6 is independently demonstrable when legacy and scored Match reads coexist, external participants remain Match-scoped, all scorecard figures reconcile with active delivery history, and Data Quality reports without repairing state.

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Verify persistence, cross-cutting integrations, the complete parameterized acceptance journey, the focused performance target, documentation, and all repository quality gates.

- [ ] T069 [P] Add isolated Docker PostgreSQL migration integration coverage for upgrade to revision 016, canonical policy identifiers and explicit-completion-boundary fields, exact component/aggregate checks, no independent Innings abandonment or reconciliation boolean, ordered fielder association constraints, required tables/constraints/indexes, downgrade where practical, and clean re-upgrade in `backend/tests/integration/test_match_scoring_migration.py`.
- [ ] T070 [P] Add Business Audit allowlist coverage for scoring initialization, innings start, innings completion, Match completion, and correction; verify actor/target/action/bounded metadata, rollback, and that ordinary delivery, next-batter/retirement operations, and next-bowler operations create no Business Audit event in `backend/tests/integration/test_match_scoring_audit.py`.
- [ ] T071 [P] Add transactional outbox/RAG fake coverage for no ordinary-delivery work; successful Match completion and material correction staging the same canonical refresh intent; per-logical-refresh coalescing and duplicate-staging prevention; current-state reload; idempotent duplicate delivery; scope/privacy; Data Quality isolation; and failure isolation in `backend/tests/integration/test_match_scoring_background.py`.
- [ ] T072 [P] Implement the parameterized 25-step backend acceptance journey once for a canonical `T20` internal Match and once for a canonical `T20` external Match, including migration, capability/sequence setup, extras, one wicket/fielder, both retired-hurt branches (next batter and approved return), canonical blocking-state responses, over/bowler, chase, correction/replay with a completed-Match terminal-preservation case, OCC, audit, Head-Coach-only Data Quality, external privacy, and bounded background assertions in `backend/tests/integration/quickstart/test_014_quickstart_flow.py`.
- [ ] T073 [P] Add the authenticated request-level Playwright journey for both internal and external T20 variants, covering initialize, configure, score, correct, complete, read, external identity privacy, and conflict outcomes without introducing scorer UI in `frontend/e2e/match-scoring-domain-flow.spec.ts`.
- [ ] T074 Add the SC-002 benchmark and SC-004 replay-equivalence acceptance cases: pre-seed exactly 1,000 active attempts (900 legal/100 illegal) in a test innings, record one cold diagnostic read, perform five warm-ups, measure 30 warm reads, assert at least 29 individual reads complete in one second or less, verify projection use without full-history replay, and correct/replay 100 attempts in `backend/tests/integration/test_match_scoring_api.py` and `backend/tests/unit/test_scoring_replay.py`.
- [ ] T075 Run the final quality gates from the repository root and resolve failures without weakening coverage or adding a runtime dependency: `cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src && VKCA_ENV=test uv run pytest tests/unit tests/integration -q && VKCA_ENV=test uv run alembic check && VKCA_ENV=test uv run pytest tests/integration/quickstart/test_014_quickstart_flow.py -q`; then `cd ../frontend && npm run lint && npx tsc -p tsconfig.app.json --noEmit --pretty false && npx tsc -p tsconfig.node.json --noEmit --strict --pretty false && npm run test:e2e -- e2e/match-scoring-domain-flow.spec.ts --project=chromium`. `tsconfig.app.json` has `strict: true` and includes `e2e`; the explicit `--strict` override makes the Node configuration check strict while validating `vite.config.ts`, `vitest.config.ts`, and `playwright.config.ts`.
- [ ] T076 After T075 passes, write or update the verified feature document at `docs/match-scoring-domain.md`, covering the actual capability matrix and canonical identifiers, innings ordering, Match-only abandonment and current-Innings serialization, Innings-authoritative reconciliation, canonical blocking state, correction-only completed-Match reprocessing and append-only supersession/OCC, one-wicket policy and ordered fielder mapping, participants, rules, wickets/fielders, strike/overs/quotas, completion boundaries/chase/results, projections, compatibility, Head-Coach-only scoring Data Quality findings versus separate non-scoring remediation, background/RAG boundaries, exact 29-of-30 benchmark protocol and numeric run bounds, deferred undo boundary, and future scorecard/pitch-map/wagon-wheel/player-stat extension points.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001-T002 have no implementation dependencies and can run in parallel.
- **Foundational (Phase 2)**: T003 precedes the typed models; T004-T010 can then be developed in parallel by disjoint model files. T011-T015 depend on the model/schema foundation and block all stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2; it establishes fixed Match sides, participants, the FormatCapability, innings sequence, policy, and batting order used by scoring. T022 creates and registers the scoring router through `backend/src/main.py`; that registration must complete before T018's reachability assertion is made green and before final API verification.
- **User Story 2 (Phase 4)**: Depends on US1's configuration boundary and the shared replay/projection foundation; its tests can seed a configured fixture independently.
- **User Story 3 (Phase 5)**: Depends on US2 delivery and replay state because legal-ball, strike, over, and quota usage fold delivery history.
- **User Story 4 (Phase 6)**: Depends on US2/US3 active history and transition state; correction rebuilds the complete downstream state.
- **User Story 5 (Phase 7)**: Depends on US2-US4 projections and replay because completion/result state must be correction-safe and multi-innings deterministic.
- **User Story 6 (Phase 8)**: Depends on the projection, lifecycle, capability, and result contracts from US1-US5, while its read/compatibility tests can use isolated scored and legacy fixtures.
- **Polish (Phase 9)**: Depends on the desired stories being implemented; T069-T073 can run in parallel, T074 follows replay/projection implementation, T075 is the final verification gate, and T076 runs only after T075 passes.

### User Story Dependency Graph

```text
Phase 1 Setup
    ↓
Phase 2 Foundation
    ↓
US1 fixed Match configuration and capability
    ↓
US2 authoritative deliveries and innings state
    ↓
US3 strike, overs, and bowler eligibility
    ↓
US4 immutable correction and replay
    ↓
US5 completion, chase, multi-innings result
    ↓
US6 scorecards, compatibility, Data Quality, RAG/background
    ↓
T069-T074 verification
    ↓
T075 final quality gates
    ↓
T076 verified feature documentation
```

### Within Each User Story

- Write the story's unit/API tests before its implementation tasks and make them fail against the unimplemented boundary. Unit tasks explicitly cover public commands and handlers; integration tasks remain for cross-module, database, authorization, and concurrency behavior.
- Implement pure rules and models before service commands, service commands before routes, and routes before end-to-end integration.
- Preserve independent story setup through the shared scoring fixtures in `backend/tests/fixtures/match_scoring.py`; do not make a story's test depend on another test's database side effects.
- Run the checkpoint test criteria after each story before advancing to the next dependent phase.

## Parallel Execution Examples

### Setup and Foundation

```text
T001 Create package scaffolding in backend/src/models/scoring/__init__.py and backend/src/services/scoring/__init__.py
T002 Create fixtures in backend/tests/fixtures/match_scoring.py

After T003:
T004 Match extension in backend/src/models/match.py and backend/src/schemas/match.py
T005 MatchSide/ScoringPolicy/capability models in backend/src/models/scoring/match_side.py and backend/src/models/scoring/scoring_policy.py
T006 MatchParticipant/BattingOrderEntry models in backend/src/models/scoring/participant.py and backend/src/models/scoring/batting_entry.py
T007 Innings/transition models in backend/src/models/scoring/innings.py and backend/src/models/scoring/transition_event.py
T008 Delivery/revision models in backend/src/models/scoring/delivery.py and backend/src/models/scoring/delivery_revision.py
T009 Wicket/fielder models in backend/src/models/scoring/wicket_event.py and backend/src/models/scoring/delivery_fielder.py
T010 Projection models in backend/src/models/scoring/over.py, backend/src/models/scoring/participant_summary.py, and backend/src/models/scoring/match_participant_performance.py
```

### User Story 1

```text
T016 Unit authorization/capability tests in backend/tests/unit/test_scoring_authorization.py
T017 Unit public configuration command/handler tests in backend/tests/unit/test_scoring_commands.py
T018 API configuration integration tests in backend/tests/integration/test_match_scoring_api.py
```

### User Story 2

```text
T025 Rule tests in backend/tests/unit/test_scoring_rules.py
T026 Replay/projection tests in backend/tests/unit/test_scoring_replay.py and backend/tests/unit/test_scoring_projections.py
T027 API delivery integration tests in backend/tests/integration/test_match_scoring_api.py
T028 Unit public innings/delivery command and handler tests in backend/tests/unit/test_scoring_commands.py
```

### User Story 3

```text
T037 Rule/projection tests in backend/tests/unit/test_scoring_rules.py and backend/tests/unit/test_scoring_projections.py
T038 API bowler integration tests in backend/tests/integration/test_match_scoring_api.py
T039 Unit next-bowler command/handler tests in backend/tests/unit/test_scoring_bowler_commands.py
```

### User Story 4

```text
T044 Replay correction tests in backend/tests/unit/test_scoring_replay.py
T045 OCC/revision integration tests in backend/tests/integration/test_match_scoring_occ.py
T046 Unit correction command/handler tests in backend/tests/unit/test_scoring_correction_commands.py
```

### User Story 5

```text
T052 Completion rule/projection tests in backend/tests/unit/test_scoring_rules.py and backend/tests/unit/test_scoring_projections.py
T053 Completion/result integration tests in backend/tests/integration/test_match_scoring_api.py
T054 Unit completion command/handler tests in backend/tests/unit/test_scoring_completion_commands.py
```

### User Story 6 and Polish

```text
T059 Projection/scorecard unit tests in backend/tests/unit/test_scoring_projections.py
T060 Compatibility integration tests in backend/tests/integration/test_match_scoring_compatibility.py
T061 Public read/cross-cutting unit tests in backend/tests/unit/test_scoring_public_handlers.py
T062 Data Quality unit/integration tests in backend/tests/unit/test_scoring_data_quality.py and backend/tests/integration/test_match_scoring_compatibility.py

After story implementation:
T069 Migration tests in backend/tests/integration/test_match_scoring_migration.py
T070 Audit tests in backend/tests/integration/test_match_scoring_audit.py
T071 Background tests in backend/tests/integration/test_match_scoring_background.py
T072 Parameterized quickstart in backend/tests/integration/quickstart/test_014_quickstart_flow.py
T073 Parameterized Playwright journey in frontend/e2e/match-scoring-domain-flow.spec.ts
T074 Focused benchmark and replay-equivalence cases in backend/tests/integration/test_match_scoring_api.py and backend/tests/unit/test_scoring_replay.py
T075 Final backend/frontend quality gates
T076 Verified documentation in docs/match-scoring-domain.md
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 setup and Phase 2 foundation, including migration 016, strict schemas, and the immutable capability registry.
2. Complete US1 to lock Match policy, side identities, fixed participants, batting order, and innings sequence.
3. Run US1's independent internal/external configuration tests and stop for MVP validation/demo.

### Incremental Delivery

1. Add US2 for authoritative innings and delivery recording; validate replay-equivalent projections and one-wicket behavior.
2. Add US3 for strike, overs, next-bowler selection, and quota enforcement.
3. Add US4 for immutable correction, reconciliation, deferred undo boundary, and OCC conflict safety.
4. Add US5 for capability-defined completion, fixed-over target/chase, multi-innings test ordering, and derived Match results.
5. Add US6 for scorecards, legacy compatibility, Data Quality, RAG, and background boundaries.
6. Complete Phase 9 for migrations, audit/background integration, both quickstart variants, Playwright, the focused benchmark, final quality gates, and verified documentation.

### Parallel Team Strategy

After Phase 2, keep write scopes disjoint: one developer can own the capability/rules/replay path, another the API/service path, and another the migration/projection/integration coverage. Coordinate before touching shared `backend/src/services/scoring/service.py`, `backend/src/routes/match_scoring.py`, or the consolidated API test file.

## Notes

- `[P]` marks only tasks that use disjoint files and have no incomplete prerequisite in the task list.
- `[US1]` through `[US6]` map directly to the prioritized user stories in `spec.md`.
- Every task has a checkbox, sequential ID, required story label where applicable, and at least one concrete repository file path.
- Unit and integration tasks are intentionally complementary; integration coverage is not a substitute for the constitution-required unit coverage of public commands and handlers.
- No task adds a new runtime dependency; ordinary delivery entry remains synchronous and downstream work remains bounded to completion/correction refreshes.
- T076 is the sole feature-documentation task and must run after T075; no aspirational documentation file is created during specification-only work.
