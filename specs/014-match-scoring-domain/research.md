# Research: Match Scoring Domain and Innings Foundation

## Research status

Phase 0 is complete. All decisions needed by the Phase 1 design are resolved in this document and the linked contracts. The feature extends existing repository boundaries; it does not introduce a parallel Match or performance subsystem.

### Match-format identifier decision

The repository's existing `MatchFormat` enum and database checks already use
`T20`, `one-day`, `test`, and `other`. These are therefore the canonical API,
domain, policy, capability-profile, and persisted identifiers for this feature.
Human labels (`T20`, `One-day`, `Test`, and `Other/manual`) are display-only;
no `t20`, `one_day`, or `other_manual` aliases are introduced and no format
value migration is required.

## Existing repository seams

| Concern | Existing evidence | Design decision |
|---|---|---|
| Match boundary | backend/src/models/match.py and backend/src/services/match_service.py already own match metadata, participant type, team relationships, validation, versioning, and Match RAG impact | Extend Match with scoring lifecycle and compatibility fields. MatchService remains the configuration seam; ScoringService owns innings and delivery commands. |
| OCC | backend/src/services/occ.py performs conditional version increments and raises StaleVersionError | Require the expected Match or innings version for every scoring mutation, use a unique attempted sequence as a database backstop, and map all stale/sequence conflicts to HTTP 409. |
| Authentication | backend/src/middleware/auth.py reloads the current active User from the database instead of trusting JWT role claims | Use current database role and active status for every protected scoring request. |
| Team scope | backend/src/services/role_scope.py resolves Head Coach, Assistant Coach assignments, and Player TeamPlayer scope | Reuse the resolver. Head Coach has full access; Assistant Coach requires a current assignment covering the academy side; Player has read-only access when the current TeamPlayer scope covers the side. |
| Audit | backend/src/services/business_audit_service.py owns append-only events in the caller transaction | Add scoring actions to the existing registry and create events only for meaningful successful commands. Delivery-by-delivery ordinary scoring is intentionally not an audit stream. |
| Background work | backend/src/services/background_jobs/outbox.py stages typed work transactionally; the registry currently supports RAG reconciliation | Keep ordinary delivery mutations synchronous. Reuse the outbox for coalesced completion/correction refresh only. |
| RAG | backend/src/services/rag/registry.py and the Match builder already support current-state Match refreshes | Do not create a Delivery RAG source. Completion and correction may stage bounded Match-level refreshes using identifiers and committed-state reload. |
| Model discovery | backend/src/models/__init__.py is the model registry used by metadata and migrations | Import all scoring ORM models there. |
| API | backend/src/main.py centrally registers routers under the existing API prefix | Add one scoring router under /api/v1 and retain existing Match endpoints for legacy metadata reads. |
| Tests | Integration fixtures use a safe test database, ASGI transport, authenticated requests, and rollback isolation | Follow those fixtures. Add the exact quickstart file required by the specification and a request-level Playwright journey. |

## Why deliveries become authoritative

The current MatchBattingPerformance, MatchBowlingPerformance, and MatchFieldingPerformance tables are manually authored aggregate records keyed primarily by academy Player and Match. They cannot represent innings-specific participation, external match-scoped identities, immutable attempt history, or revision provenance. A delivery history therefore becomes authoritative for any Match configured for scoring.

Existing performance rows remain readable for legacy unscored Matches. For a scored Match, derived participant summaries are the write source for scoring reads; direct mutation of legacy aggregate rows is rejected. An adapter can synchronize academy-player projections into the existing performance tables where their existing shape is sufficient, while the new match-scoped performance projection remains canonical for external participants and multi-innings data.

## Cricket rule baseline

The requested scope follows the ordinary MCC innings, over, scoring-runs, no-ball, wide-ball, bye/leg-bye, run-out, stumped, and result concepts. References used during research:

- [MCC Law 17: The Over](https://www.lords.org/mcc/the-laws/the-over)
- [MCC Law 18: Scoring Runs](https://www.lords.org/MCC/The-Laws-of-Cricket/Scoring-runs)
- [MCC Law 21: No Ball](https://www.lords.org/mcc/the-laws/no-ball)
- [MCC Law 22: Wide Ball](https://www.lords.org/mcc/the-laws/wide-ball)
- [MCC Law 23: Bye and Leg Bye](https://www.lords.org/MCC/The-Laws-of-Cricket/Bye-and-Leg-bye)
- [MCC Law 38: Run Out](https://www.lords.org/mcc/the-laws/run-out)
- [MCC Law 39: Stumped](https://www.lords.org/mcc/the-laws/stumped)
- [MCC Law 16: The Result](https://www.lords.org/mcc/the-laws/innings)

Product scope deliberately excludes DLS, Super Over, automated umpiring, external score ingestion, and public live-feed delivery. Any competition-specific exception must be an explicit future policy extension, not an implicit fallback.

## Resolved scoring decisions

### Policy

- The T20 capability fixes one innings per side, six-ball overs, 120 legal balls, 24 legal balls per bowler, no consecutive overs by the same bowler, and ten wickets.
- The one-day capability fixes one innings per side, six-ball overs, no consecutive overs by the same bowler, and ten wickets. Configuration must supply a positive legal-ball limit divisible by 30; the service derives the quota as one fifth of that locked limit (for example, 240 legal balls yields a 48-ball quota) and rejects missing, non-whole-over, or client-supplied quota values.
- The test capability fixes `[A, B, A, B]`, six-ball overs, ten wickets per innings, no innings limit, no target, no quota, and no consecutive overs by the same bowler; declaration, draw, and manual Match completion are distinct policy paths.
- The other capability has no defaults and requires its innings sequence, over length, limits, quota, completion, dismissal, and transition sets before scoring.
- Policy is locked before the first innings or delivery and is versioned for historical explanation.

### Delivery input

The client submits only observed facts:

- striker, non-striker, bowler, attempted sequence, and captured version;
- runs off the bat;
- wide runs, no-ball penalty, bye runs, leg-bye runs, and penalty runs;
- zero or one wicket event with dismissal type, dismissed participant, and an
  ordered canonical fielder association collection;
- optional additional run detail needed to preserve the raw attempt.

The server derives total runs, legal/illegal classification, over number, ball-in-over, balls faced, bowler-conceded runs, strike rotation, over transitions, and all summaries. Strict request schemas reject derived fields and unknown fields.

### Run components

- A wide component includes the mandatory one-run wide penalty plus any additional completed wide runs.
- A no-ball has exactly one no-ball penalty run plus any bat, bye, or leg-bye runs recorded with that attempt.
- Byes and leg-byes are mutually exclusive and are not bowler-conceded.
- Batting-side penalty runs are explicit five-run events. Fielding-side penalties are represented as a separate future policy/event type rather than overloaded into ordinary delivery input.

All persisted scoring run components use the inclusive
`SCORING_RUN_COMPONENT_MAX = 2,147,483,647` bound, except
`no_ball_penalty_runs`, which is `0..1`. Recomputed delivery totals and
Innings/Match aggregate run totals use the inclusive
`SCORING_RUN_TOTAL_MAX = 2,147,483,647` bound. These constants follow the
existing PostgreSQL `INTEGER` persistence convention and are shared by schema,
domain validation, and tests; checked addition rejects aggregate overflow.

### Lifecycle and correction decisions

- Match lifecycle is the only authority for administrative abandonment. The
  Match completion endpoint sets `abandoned`/`no_result`; the current Innings
  remains `pending` or `in_progress` and incomplete, with no independent
  Innings abandonment state or completion event.
- Innings lifecycle is the only authority for reconciliation. Its
  `reconciliation_required` state is cleared only by a later compatible
  correction replay; Match-level reconciliation is derived from affected
  innings and is not stored as a second boolean.
- A completed Match can be reopened only inside the transaction-local
  `completed → correction_reprocessing → completed|in_progress` correction
  path. The intermediate phase is not externally visible; ordinary scoring
  cannot reopen a completed Match, and an abandoned Match is not reopened by
  this feature.
- The serialized `blocking_state` is a derived `{kind, is_blocked,
  reason_code}` object with explicit precedence, not a client-supplied or
  independently mutable scoring field.
- The database stores integer run values and never stores a decimal total; all
  component and aggregate bounds are the exact constants above.

### Legal balls and strike

- Wides and no-balls are illegal deliveries and do not consume an over ball.
- A legal delivery includes an ordinary legal ball, including a legal ball with byes, leg-byes, or an explicit penalty event.
- Balls faced are true for a legal delivered ball and false for a wide or no-ball.
- Completed runs used for strike rotation exclude the wide/no-ball penalty and penalty runs. A single wide therefore does not rotate strike; completed running on an illegal delivery may.
- End-of-over strike swap is applied after the legal sixth ball (or configured over limit), and a new over requires an explicit next bowler not equal to the previous bowler.
- Run-out handling records the dismissed end and does not infer it from a simplified strike toggle.

### Wickets

The initial T20, one-day, and test dismissal vocabulary covers bowled, caught,
caught and bowled, LBW, run out, stumped, hit wicket, and retired out. Retired
hurt is represented as a participation transition rather than a dismissal
event. `other` must supply its own dismissal and transition sets, but the
reserved future identifiers `obstructing_the_field`, `hit_the_ball_twice`, and
`timed_out` are rejected by every current capability. At most one wicket is
accepted per delivery in this increment. The API `fielders[]` collection and
ordered `DeliveryFielder` associations are canonical; a primary-fielder
pointer is derived from the first association. Bowled/LBW/hit-wicket/retired-out
use zero fielders, caught/caught-and-bowled/stumped use one catcher/bowler/
keeper respectively, and run-out uses one or more ordered fielders. Fielders
are match-scoped participants, never newly created User or Player accounts.

### Completion and result

An innings ends when the fixed-over chase target is reached, the configured
wicket or legal-ball limit is reached, a test innings is declared, or an
authorized user uses a capability-listed innings completion path. Match
completion derives from the stored innings sequence and produces a structured
result code plus compatibility text. The target is the prior completed innings
score plus one only for T20 and one-day innings 2. Test `draw`, `declared`, and
`manual` completion is accepted immediately after a completed innings and
before an automatic result; `other` uses its locked explicit completion
boundary. Match-level `abandonment` is accepted from any non-terminal Match
without unresolved reconciliation and produces `no_result`; it does not end or
complete the current Innings. In a fixed-over replay step, target reach takes
precedence over a same-delivery wicket or legal-ball limit when more than one
terminal condition becomes true.
The first result projection supports win by runs, win by wickets, tie, draw, no
result, declared, and manual, with the locked capability result precedence.

## Persistence and correction decisions

The authoritative write path is:

1. Lock or conditionally update the versioned Match/innings root.
2. Validate the current lifecycle, participant selection, policy, and submitted observed facts.
3. Insert the immutable attempted delivery parent and its first revision, or append a replacement revision for correction.
4. Rebuild the affected innings state with a pure replay function over active revisions and transition events.
5. Persist totals, over state, participant summaries, performance projections,
   the authoritative Innings reconciliation lifecycle/reason, and the derived
   `blocking_state` read model.
6. Append any meaningful Business Audit event and stage only allowed background/RAG work.
7. Commit all changes together; any failure rolls back the entire command.

An attempted delivery has a stable parent identity based on innings and attempted sequence. Revisions are append-only: a correction appends one replacement revision and marks the prior active revision `superseded`; exactly one active revision is allowed. There is no void revision state, direct revision replacement, or hard deletion. Corrections preserve author, time, reason, previous revision, and replacement provenance. Replay starts from the earliest affected attempt and recomputes all later state. A completed Match correction uses the transaction-local `completed → correction_reprocessing → completed|in_progress` path and is never exposed in the intermediate state. If a later active transition or delivery becomes incompatible, the Innings lifecycle is `reconciliation_required` with a bounded explanation rather than silently rewriting user choices; Match-level reconciliation is derived from that Innings state.

Live reads use the persisted projection and do not replay the full innings. A diagnostic or correction path can replay and compare projections to verify reconcilability.

## Authorization decisions

Every scoring read and mutation resolves the current authenticated database user and current team scope at request time. External participants are historical match-scoped identities only. Their display names and batting positions are stored on the Match participant row, never in User, Player, TeamPlayer, or TeamCoach tables.

The academy side is the authorization anchor. For internal matches both sides are academy teams and a user must have scope on the requested side. For external matches the academy team is the only side that grants access; the external opponent name grants no access. A Player may read scorecards and delivery history in scope but cannot configure, score, correct, or complete a Match. Operational scoring Data Quality findings are Head-Coach-only; Assistant Coaches and Players cannot view or re-run them. The existing Data Quality remediation route remains Head-Coach-only and non-scoring. Scoring corrections use the normal correction command, where Head Coaches and appropriately scoped Assistant Coaches may correct and Players may not.

## Audit, background, RAG, and Data Quality decisions

Meaningful successful events include scoring configuration, innings start, explicit batter/bowler transition, innings completion, Match completion, and correction. Ordinary delivery append, technical failures, validation failures, and stale conflicts create no Business Audit event. Audit metadata is allowlisted and contains identifiers, command type, and bounded reason—not raw delivery payloads.

Normal delivery append updates the live projection synchronously and stages no queue/provider/RAG work. Completion and correction stage at most one coalesced Match-level current-state refresh through the existing transactional outbox. Background handlers reload committed state and are idempotent. No per-delivery RAG source or ordinary-ball job is introduced.

Data Quality scoring rules are read-only. They flag projection mismatch,
impossible sequence/lifecycle transitions, duplicate active revisions, invalid
legal-ball/over state, invalid participant references, malformed historical
state, and reconciliation-required state. A scoring quality finding never
repairs or mutates scoring state and never creates Business Audit events. Any
existing non-scoring remediation route remains separate, Head-Coach-only, and
cannot accept a scoring finding. There is no public Data Quality trigger or
re-run endpoint; the bounded findings read is the only exposed check boundary.

## API and testing decisions

The API is a protected command/query surface under /api/v1. Mutations carry the expected version and return the updated version. Suggested resources are configuration, innings, bounded deliveries, next batter/bowler transitions, delivery correction, completion, and scorecard. Detailed request/response contracts are in contracts/match-scoring-api.md.

Tests must cover pure rules and replay, every new public scoring service/function
and API handler at unit level, external identity isolation, current team scope,
all component combinations, wickets and fielders, strike/over transitions,
completion/results, correction equivalence, Data Quality detection/reporting,
stale concurrency, atomic rollback, audit cardinality, outbox coalescing,
legacy compatibility, migration constraints, and the exact 25-step quickstart.
The Playwright test may use authenticated fetch requests; it does not require a
scorer UI.

## Migration decision

The migration chain currently ends at revision 015, so this feature uses revision 016. The migration creates parent tables before child tables, indexes current scorecard and scoped Match reads, adds constraints for fixed participants/sequence/revisions, and downgrades children before parents. New models must be imported before migration metadata checks.

## Research conclusion

The repository supports this feature without a new framework or dependency. The safe design is a versioned Match/innings aggregate with immutable delivery revisions and synchronous derived projections, integrated with—not parallel to—the existing Match, auth, audit, background, RAG, and performance foundations.
