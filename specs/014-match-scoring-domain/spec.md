# Feature Specification: Match Scoring Domain and Innings Foundation

**Feature Branch**: `014-match-scoring-domain`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Match Scoring Domain and Innings Foundation"

## Scope and Boundaries

This feature establishes the authoritative domain for configuring a cricket
Match, selecting its participants, starting and completing innings, and storing
every attempted delivery needed for future live scoring, scorecards, analytics,
pitch maps, wagon wheels, and player statistics.

Delivery history is the authoritative scoring record. Innings totals, current
state, scorecards, match performance summaries, future career statistics, RAG
summaries, and analytics are derived or materialized views of that history.
They must be reproducible and reconcilable from active delivery history.

The implementation extends the existing `Match`, `MatchService`, participant,
performance, authorization, Business Audit, RAG, background-work, and
optimistic-concurrency boundaries. It must not create a parallel Match or
scoring subsystem. Existing Match date, format, venue, participant type,
academy home/away Team references, and external opponent semantics remain
available.

No polished live-scoring page, pitch map, wagon wheel, analytics dashboard,
WebSocket stream, public live-score feed, DLS calculation, automated umpiring,
external live-data ingestion, or full Test-match rule engine is included.
Career-statistics aggregation and a player career-statistics dashboard are also
deferred; this increment only preserves the delivery data needed to derive them
later.
There is no new frontend surface required for this foundation. The primary
interaction boundary is the protected scoring/read contract exercised by
authenticated request-level end-to-end tests. If a minimal control is added,
it must follow the existing Product and Design guidance: familiar flat white
surfaces, practice-night primary actions, restrained academy teal for focus and
wayfinding, 44px targets, keyboard operation, visible labels, explicit loading,
error, conflict, and success states, readable contrast, and responsive use
from 320px through 2560px without relying on color alone.

## Match-Format Capability Model

Every configured Match MUST resolve exactly one immutable, versioned
`FormatCapability` before scoring starts. The capability is selected from the
Match format and the locked scoring policy; request schemas, scoring rules,
replay, completion, and result derivation MUST read this capability rather than
reimplementing format checks independently. A policy that contradicts its
capability is rejected before the first innings starts.

### Canonical match-format identifiers

The existing `MatchFormat` values are the canonical machine identifiers for
this feature. The same identifier MUST be used in the API `format` field, the
scoring-policy `policy_code` and `capability_profile` fields, the domain enum,
and the persisted Match `format` value. No case, separator, or profile-name
variation is accepted at the scoring boundary. Human labels are display-only:

| Human/display label | API/wire value | Domain enum value | Persisted/storage value | Capability profile |
|---|---|---|---|---|
| T20 | `T20` | `MatchFormat.T20` | `T20` | `T20` |
| One-day | `one-day` | `MatchFormat.ONE_DAY` | `one-day` | `one-day` |
| Test | `test` | `MatchFormat.TEST` | `test` | `test` |
| Other/manual | `other` | `MatchFormat.OTHER` | `other` | `other` |

The enum member names are source-code symbols only: for example,
`MatchFormat.ONE_DAY.value` is exactly `one-day`. Every enum value is the
same machine string used on the wire and in storage; no serializer or
repository layer performs a format-name transformation.

`other` is the canonical identifier; its manual-completion behavior is a
capability property, not a separate `other_manual` profile. Existing legacy
Match rows retain their stored values because these are the repository's
existing format values; this feature introduces no format-value migration.

The following matrix is normative for this feature. `A` and `B` mean the two
configured Match sides in the stored innings sequence; they are positional
placeholders, not literal persisted values, and are not assumed to be home/away
or academy/external.

| Match format | Required innings sequence | Innings legal-ball limit / over length | Bowler quota | Wicket limit | Consecutive-over rule | Declaration | Draw | Manual completion | Target/chase | Explicit Match-completion boundary | Allowed innings completion modes | Allowed Match completion modes / result codes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `T20` | `[A, B]` | 120 per innings / 6 legal balls per over | 24 legal balls per bowler | 10 per innings | Prohibited | No | No | No | Automatic innings 1 total + 1 for innings 2 | None | `all_out`, `legal_ball_limit`, `target_reached` | Automatic `win_by_runs`, `win_by_wickets`, `tie`; Match `abandonment` → `no_result` |
| `one-day` | `[A, B]` | 300 per innings / 6 legal balls per over | 60 legal balls per bowler | 10 per innings | Prohibited | No | No | No | Automatic innings 1 total + 1 for innings 2 | None | `all_out`, `legal_ball_limit`, `target_reached` | Automatic `win_by_runs`, `win_by_wickets`, `tie`; Match `abandonment` → `no_result` |
| `test` | `[A, B, A, B]` | No innings limit / 6 legal balls per over | None | 10 per innings | Allowed; no consecutive-over restriction | Yes, to complete an innings | Yes, to complete the Match | Yes, to complete the Match | None | `after_completed_innings` before the automatic result | `all_out`, `declaration` | Automatic after innings 4: `win_by_runs`, `tie`; explicit `draw`, `declared`, `manual`; Match `abandonment` → `no_result` |
| `other` | Policy-supplied ordered side sequence | Policy-supplied over length; legal-ball limit may be null | Policy-supplied quota, or null | Policy-supplied limit | Policy-supplied boolean | No | No | Yes | None | The locked policy MUST select `after_completed_innings` or `any_nonterminal_state` | `manual` | Explicit `manual` → `manual`; Match `abandonment` → `no_result` |

The non-terminal Match result code `pending` is valid for every row until a
terminal completion is committed. The initial T20, one-day, and test profiles
all use the core dismissal set `bowled`, `caught`, `caught_and_bowled`, `lbw`,
`run_out`, `stumped`, `hit_wicket`, and `retired_out`; they also expose the
`retired_hurt`/`retired_hurt_return` transition pair. `retired_hurt` is never a
WicketEvent. An `other` capability MUST provide its dismissal and transition
sets, including the fielding-role/cardinality rules for each selected type;
it MAY select only from the current public dismissal/transition vocabularies
and MUST NOT introduce a new runtime enum value. The service MUST reject a
type not in that set. `obstructing_the_field`,
`hit_the_ball_twice`, and `timed_out` are reserved future dismissal identifiers.
They are rejected with a validation error by every current capability,
including `other`, and require a future capability version before they can be
submitted. They MUST NOT appear in the current public dismissal enum.

The `allowed_innings_completion_modes` set never contains `abandonment`.
Abandonment is a Match-level administrative command only and is not an
independent innings completion mode. The `explicit_match_completion_boundary` capability value is `none` for T20
and one-day, `after_completed_innings` for test, and policy-supplied for
`other`. `draw`, `declared`, and `manual` Match completion actions are accepted
only at that locked boundary while the Match is incomplete and before an
automatic result. `abandonment` is the separate administrative terminal path
and is accepted from any non-terminal Match state without unresolved
reconciliation. No explicit action can override an already-derived automatic
result.

`one-day` has no format-string fallback: configuration MUST carry exactly the
300-ball innings limit, six-ball over length, 60-ball bowler quota, and
ten-wicket limit in the selected capability version. A missing or different
value is rejected until a separate capability profile is introduced. `test`
uses the fixed four-innings sequence above, six-ball overs, and ten wickets per
innings; it intentionally does not implement follow-on, interruption, DLS,
Super Over, or other full Test-match rules. `other` has no defaults: all
sequence, over-length, wicket-limit, quota, consecutive-over, dismissal, and
transition fields used by scoring are policy data, and no automatic completion
or result is inferred.

`abandonment` is an explicit administrative Match completion mode available in
every row. It sets Match lifecycle to `abandoned` and result code to
`no_result`; `abandoned` is not a separate result code. The current Innings,
if any, remains in its underlying `pending` or `in_progress` state and does not
receive an `innings_completed` transition or an independent `abandoned` state.
The enclosing Match state blocks further scoring and is serialized as
`blocking_state.kind = match_abandoned`; completed prior innings remain
`completed`. Replay folds the persisted delivery and transition history first,
then applies the persisted Match-level abandonment state, so it never infers
abandonment from an innings event. `manual`, `draw`, and `declared` are
accepted only in the rows that list them. `Match.lifecycle_state = abandoned`
is the authoritative abandonment state; `result_code = no_result` is its
required derived serialization and is not an independent input. A manual,
draw, or declared outcome records a bounded reason and never accepts client-supplied
final totals as authoritative. Test `declaration` completes the current
innings and advances the stored sequence; test `declared` completes the Match
explicitly and is distinct from that innings command.

### Scoring numeric limits

The scoring boundary uses the existing PostgreSQL `INTEGER` range as its
authoritative numeric bound. `SCORING_RUN_COMPONENT_MAX` and
`SCORING_RUN_TOTAL_MAX` are both `2,147,483,647` and are inclusive constants,
not Match-policy values. `runs_off_bat`, `wide_runs`, `bye_runs`, `leg_bye_runs`,
and `penalty_runs` MUST each be integers from `0` through
`SCORING_RUN_COMPONENT_MAX`. `no_ball_penalty_runs` MUST be `0` or `1`.
Server-derived `total_runs`, every Innings run total, and every Match aggregate
run total MUST be integers from `0` through `SCORING_RUN_TOTAL_MAX`.

The server MUST reject a negative or non-finite component, a component above
its limit, or a component sum above `SCORING_RUN_TOTAL_MAX` with validation
error 422 before persistence. Checked addition MUST also reject an Innings or
Match aggregate overflow before changing projections. These constants are the
single source for API schema, domain validation, persistence checks, and tests.

### Canonical blocking-state derivation

`blocking_state` is one read-only serialization of whether the addressed
scoring boundary can progress and the first reason that it cannot. Its exact
shape and values are defined by FR-012. For an Innings response, after the
enclosing Match terminal state is applied, the derivation precedence is:

1. `reconciliation_required` when that Innings lifecycle requires
   reconciliation.
2. `innings_not_started` when the Innings lifecycle is `pending`.
3. `innings_completed` when the Innings lifecycle is `completed`.
4. `awaiting_next_batter` when an in-progress Innings has fewer than two valid
   active batters.
5. `awaiting_next_bowler` when an in-progress Innings requires a bowler and
   no valid current bowler is selected; `no_eligible_bowler` is the reason when
   quotas or side eligibility leave no valid choice.
6. `none` when the in-progress Innings can accept the next valid scoring
   operation.

For a Match response, `match_abandoned` and `match_completed` take precedence;
otherwise the lowest-numbered Innings in `reconciliation_required` wins, then
the current in-progress Innings uses the same batter-before-bowler precedence.
If no current Innings exists for the next required sequence position, or the
current Innings is completed and another required sequence position is waiting
to start, the Match emits `innings_not_started`; it does not emit
`innings_completed`, because a completed prior Innings does not block creation
of the next sequence position. `innings_completed` is therefore only emitted
for an addressed non-terminal Innings resource. If no blocker exists, the
Match emits `none`. This derivation is used for persisted snapshot refresh,
replay, API responses, and tests; clients never infer it from nullable IDs.

### Multi-innings ordering, target, and result semantics

The locked `innings_sequence` determines both innings ordering and sides:

- The side at position `n` bats in innings `n`; the other configured side is
  the fielding/bowling side. Current Team membership is used only for
  authorization and configuration-time eligibility, never to recalculate a
  historical side.
- An innings projection folds only the active delivery revisions and anchored
  transitions belonging to that innings. Match-level aggregate state folds all
  completed prior innings in the locked sequence: a test innings 3 therefore
  contributes to the Match aggregate alongside innings 1 and 2, while its own
  innings totals and active pair remain independent. No prior innings is mixed
  into the current innings' legal-ball, over, strike, or wicket counters.
- A fixed-over profile (`T20` or `one-day`) permits exactly innings 1 and 2.
  Innings 2 cannot start until innings 1 is completed. Its target becomes
  active at creation from innings 1's completed total plus one. Reaching that
  target completes innings 2 and the Match automatically. If one folded
  delivery also reaches the target and reaches the wicket or legal-ball limit,
  `target_reached` takes precedence as the innings completion reason; the
  persisted wicket and delivery facts are still retained and replayed.
- If a fixed-over chase completes without reaching its target, the higher
  completed score wins by runs and equal scores produce a tie. A target,
  wickets remaining, or balls remaining is never calculated from an incomplete
  prior innings.
- A `test` profile permits exactly four innings in the stored `[A, B, A, B]`
  order. Each innings must complete before the next begins; no target is set.
  After innings 4, the aggregate score for each side is compared: the higher
  aggregate produces `win_by_runs`, and equal aggregates produce `tie`. An
  explicit `draw`, `declared`, or `manual` completion may end the Match earlier
  only immediately after a completed innings and before an automatic result.
- An `other` Match cannot start an innings until its explicit side sequence is
  locked. It has no target or automatic result; an authorized scorer must use
  `manual` at the locked `explicit_match_completion_boundary`. Match-level
  `abandonment` remains available from any non-terminal state without
  unresolved reconciliation.
- Result precedence is deterministic: an unresolved reconciliation blocks all
  completion; an accepted `abandonment` ends the Match as `no_result`; a
  profile's automatic target or aggregate condition then completes the Match
  as soon as its precondition is true; for test, an allowed explicit draw,
  declared, or manual command is accepted only immediately after a completed
  innings and before an automatic result, while `other` uses its locked
  `explicit_match_completion_boundary`. No explicit command can override an
  automatic completion that already occurred. An incomplete required innings
  blocks automatic completion, and an explicit command outside its boundary is
  rejected.
- Replay folds active delivery revisions and anchored transition events in
  attempted-sequence order within each innings, then applies the locked
  innings sequence and capability to build the Match result. It does not use
  current rosters, wall-clock order, or client-supplied derived state, so the
  same persisted events produce the same result.

### Correction-only Match reopening

An authorized Head Coach or appropriately scoped Assistant Coach may correct a
delivery in a `completed` Match only through the delivery-correction command.
The command requires the current Match version, current Innings version, and
expected active delivery revision. It enters a transactional internal
`correction_reprocessing` phase, appends the replacement revision, supersedes
the prior active revision, and replays all affected innings and Match-level
derived state. The phase is never committed or exposed by a normal read; a
concurrent command cannot score, complete, abandon, or start another
correction against it.

Corrections to an eligible `in_progress` Match use the same append-only
revision and replay transaction without reopening its Match lifecycle; the
`correction_reprocessing` phase is required only for the completed-Match path.
An abandoned Match is not an eligible correction target.

If replay remains terminal and compatible, the transaction commits
`correction_reprocessing → completed` with the recalculated result. If the
correction removes the terminal precondition, it commits
`correction_reprocessing → in_progress` with result `pending`; the affected
Innings is likewise rebuilt to `in_progress` unless replay marks that Innings
`reconciliation_required`. Incompatible later transitions may commit with
the Match `in_progress` and the affected Innings in
`reconciliation_required`, which blocks scoring progression until another
authorized correction makes the active history compatible. If a safe projection
cannot be produced, the transaction rolls back and returns the normal 409
conflict without changing revisions or lifecycle state.

No ordinary scoring operation may reopen a completed Match. The successful
correction audit records
the prior and final lifecycle, while the revision chain preserves predecessor,
actor, timestamp, reason, and supersession history. There is no committed
public `correction_reprocessing` response state.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Freeze Match Participants and Batting Order (Priority: P1)

A Head Coach or appropriately scoped Assistant Coach needs to prepare a Match
for scoring by fixing both sides, their selected players, and the intended
batting order. The preparation must remain historically stable even when team
rosters change later.

**Why this priority**: Every delivery and scorecard identity depends on a
stable Match participant set. Without it, later scoring could change when an
academy roster changes.

**Independent Test**: Create an internal and an external Match, configure each
side's selected participants and batting order, change the source Team roster,
and verify that the Match selections and identities remain unchanged.

**Acceptance Scenarios**:

1. **Given** an internal Match with two distinct academy Teams, **When** an
   authorized scorer configures both sides with academy Players from the
   respective Team rosters, **Then** the Match stores those selected identities
   and their batting-order positions independently of future roster changes.
2. **Given** an external Match, **When** the scorer configures the academy side
   with academy Players and the opposition with named match participants,
   **Then** both sides can be used for scoring without creating an academy
   Player, User, or Team membership for an opposition participant.
3. **Given** a side containing a duplicate participant, duplicate batting
   positions, or a participant assigned to both sides, **When** configuration is
   submitted, **Then** the whole configuration is rejected without changing
   the Match.
4. **Given** a configured Match whose current Team roster later changes,
   **When** the scorer reads the Match, **Then** the fixed Match participant set
   and batting order are returned exactly as selected at configuration time.

### User Story 2 - Start an Innings and Record Authoritative Deliveries (Priority: P1)

A scorer needs to start an innings with a valid batting pair and bowler, then
record ordinary deliveries, boundaries, five-run bat outcomes, wides, no-balls,
byes, leg-byes, penalty runs, and wickets while the system maintains the
current score and over state.

**Why this priority**: Delivery entry is the primary operational workflow and
the source from which all later cricket data is derived.

**Independent Test**: Start a limited-overs innings, submit a sequence that
contains ordinary runs, a boundary, five bat runs, multiple wides, a no-ball
with additional runs, and a wicket, then compare the persisted current state
with a replay of the recorded delivery sequence.

**Acceptance Scenarios**:

1. **Given** a configured Match with two eligible batters and an eligible
   bowler, **When** the scorer starts an innings, **Then** the innings becomes
   active with distinct striker, non-striker, and current-bowler identities.
2. **Given** an innings that has not started or has completed, **When** a normal
   delivery is submitted, **Then** the operation is rejected and no delivery
   or derived state is written.
3. **Given** a valid delivery with five runs off the bat, **When** it is
   recorded, **Then** the batter receives five runs, the delivery total
   reconciles, and the scorer is not forced to represent it as a boundary.
4. **Given** a wide carrying multiple wide runs or a no-ball carrying its
   penalty plus additional permitted runs, **When** it is recorded, **Then**
   the extras breakdown, team total, bowler figures, legal-ball count, and
   display progression are all correct.
5. **Given** a wicket that requires a replacement batter, **When** the wicket
   is recorded, **Then** the wicket is resolved first, the innings requires an
   eligible next-batter selection, and another delivery is blocked until a
   valid batting pair is restored.

### User Story 3 - Maintain Strike, Overs, and Bowler Eligibility (Priority: P1)

A scorer needs predictable strike rotation, over completion, bowler selection,
and quota enforcement so that the next delivery starts from the state implied
by the previous legal deliveries.

**Why this priority**: Small state errors compound across an innings and make
the final scorecard unreliable even when individual delivery totals look right.

**Independent Test**: Score odd and even run outcomes, complete an over using
legal deliveries interspersed with illegal deliveries, and verify strike,
legal-ball counts, the completed bowler, and the next-bowler suggestion.

**Acceptance Scenarios**:

1. **Given** an active innings, **When** a delivery changes the number of
   completed runs or completes an over, **Then** striker and non-striker are
   updated according to the capability-defined scoring rules and over-end
   exchange.
2. **Given** six legal deliveries and any number of wides or no-balls in an
   over, **When** the sixth legal delivery is recorded, **Then** the over
   completes based on legal deliveries only and illegal attempts do not consume
   legal-ball capacity.
3. **Given** an over has completed, **When** the scorer requests the next
   bowler, **Then** the system excludes the bowler who just completed the over
   where consecutive overs are prohibited and suggests the preceding
   alternate-over bowler when eligible, otherwise the alphabetically first
   eligible bowler using a deterministic name/ID tie-break.
4. **Given** a scorer overrides the suggestion with another eligible bowler,
   **When** the selection is committed, **Then** the override is accepted and
   the suggestion does not override it later.
5. **Given** a bowler has reached the applicable legal-over quota, **When** the
   scorer tries to select that bowler, **Then** selection is rejected while
   other eligible bowlers remain selectable.

### User Story 4 - Correct Scoring Without Losing History (Priority: P1)

A scorer needs to correct an earlier delivery after it has affected later
state, while preserving what was entered, rebuilding the affected innings, and
protecting concurrent scorers from overwriting one another.

**Why this priority**: Correction is normal in live scoring. A manual counter
decrement or an untracked deletion would make historical scorecards and later
analytics untrustworthy.

**Independent Test**: Score multiple deliveries, correct an earlier delivery,
replay the active delivery history, and submit two stale mutations against the
same innings version. Verify rebuilt state, preserved superseded history, and
one successful writer with one conflict.

**Acceptance Scenarios**:

1. **Given** an active delivery with later deliveries already recorded, **When**
   an authorized scorer corrects that delivery with the current OCC versions,
   **Then** the original remains available as correction provenance, the active
   delivery version is unambiguous, and all affected totals and state are
   rebuilt from active history.
2. **Given** a correction changes whether an innings is complete or whether a
   target has been reached, **When** reconciliation finishes, **Then** innings,
   Match result, chase state, and derived performance summaries reflect the
   corrected history rather than stale counters.
3. **Given** two clients submit the next delivery using the same current
   innings version, **When** both requests commit, **Then** exactly one succeeds,
   the other receives the repository's normal conflict response, and no
   duplicate active delivery sequence exists.
4. **Given** a stale client attempts a correction, next-batter selection,
   next-bowler selection, or innings completion, **When** the write is received,
   **Then** it is rejected without changing scoring state or creating a
   misleading business mutation event.
5. **Given** a scorer needs to amend an earlier delivery, **When** the scorer
   uses the correction command, **Then** it uses the same validated revision,
   OCC, audit, and reconstruction path for every amendment. Arbitrary
   user-facing undo controls are deferred from this feature.

### User Story 5 - Complete Innings, Chase a Target, and Finish a Match (Priority: P1)

A scorer needs innings completion and Match completion to follow the completed
delivery history, including target chases and no-result outcomes, so that the
final result does not need to be entered a second time.

**Why this priority**: A complete, derived result is the handoff to scorecards,
reports, RAG summaries, and future player statistics.

**Independent Test**: Complete a first limited-overs innings, start a second
innings with a derived target, score until the target is reached, and verify
automatic innings and Match completion plus the derived result.

**Acceptance Scenarios**:

1. **Given** a T20 or one-day capability, **When** all ten available batting
   wickets are lost or the innings reaches exactly 120 legal balls for T20 or
   exactly 300 legal balls for one-day, **Then** the innings completes with the
   corresponding reason and cannot accept normal delivery entry.
2. **Given** a later innings with a target from a completed prior innings,
   **When** the batting side reaches the target, **Then** the chase completes
   automatically with runs required equal to zero and the Match completes when
   no required innings remain.
3. **Given** a completed chase that reaches the target before the legal-ball
   limit, **When** the result is read, **Then** it identifies a win by wickets
   with the correct wickets remaining and does not claim unused balls were
   bowled.
4. **Given** a fixed-over Match whose second innings completes below its target
   with a score equal to the first innings, **When** the scenario is run once
   with `legal_ball_limit` at the exact configured limit and once with
   `all_out` at the exact wicket limit, **Then** each run makes the Match
   `completed` with result code `tie`; target reach and win-by-wickets are not
   reported.
5. **Given** a test Match with an in-progress innings before the final required
   `[A, B, A, B]` sequence position, **When** an authorized scorer commits
   innings completion `declaration`, **Then** that innings becomes `completed`
   with reason `declaration`, the next sequence position may start, and the
   Match remains non-terminal with result `pending`.
6. **Given** an incomplete test Match immediately after a completed innings and
   before an automatic result, **When** an authorized scorer commits Match
   completion `declared`, **Then** the Match becomes `completed` with result code
   `declared` and no later innings may start.
7. **Given** an incomplete test Match immediately after a completed innings and
   before an automatic result, **When** an authorized scorer commits Match
   completion `draw`, **Then** the Match becomes `completed` with result code
   `draw` and no later innings may start.
8. **Given** any non-terminal Match without unresolved reconciliation, **When**
   an authorized scorer commits Match-level `abandonment`, **Then** the Match
   becomes `abandoned` with result code `no_result`, the current Innings keeps
   its underlying `pending` or `in_progress` lifecycle without an
   `innings_completed` transition, its serialized `blocking_state.kind` is
   `match_abandoned`, and no later scoring or completion command is accepted.
   The innings-completion endpoint rejects `abandonment` with 422; only the
   Match-completion endpoint accepts it.
9. **Given** an `other` Match with a locked explicit completion boundary,
   **When** an authorized scorer manually completes it at that boundary, **Then**
   the Match becomes `completed` with result code `manual`; a manual request
   outside the boundary is rejected and no unsupported result is inferred.

### User Story 6 - Read Coherent Internal and External Scorecards (Priority: P2)

A coach or player needs protected live state and completed scorecard data that
identifies academy Players directly, keeps opposition participants coherent,
and exposes derived batting, bowling, fielding, extras, fall-of-wickets, over,
target, and result information without exposing external identities as academy
accounts.

**Why this priority**: Read readiness lets later scorecard and player-development
features build on one trusted domain without re-entering aggregate data.

**Independent Test**: Read an internal and external Match as authorized Head
Coach, assigned Assistant Coach, and Player users; compare returned scorecard
figures to delivery-derived truth and verify role and participant boundaries.
Verify that only Head Coaches can view scoring Data Quality findings and that
scoring corrections remain on the normal correction authorization path.

**Acceptance Scenarios**:

1. **Given** a completed internal Match, **When** an authorized reader requests
   its scorecard, **Then** both academy Teams and their academy Player figures
   are available with totals derived from deliveries.
2. **Given** a completed external Match, **When** an authorized reader requests
   its scorecard, **Then** academy detail remains first-class and opposition
   batters, bowlers, fielders, and wicket events use their match-scoped
   identities.
3. **Given** an Assistant Coach assigned to one participating academy Team,
   **When** that coach reads or mutates the Match through an authenticated
   request, **Then** access follows the current TeamCoach relationship and does
   not trust client-supplied scope.
4. **Given** a Player user with current Team membership, **When** the Player
   reads a permitted Match, **Then** live and completed scorecard data is
   read-only and no scoring mutation is accepted.
5. **Given** a completed innings or Match, **When** downstream reconciliation
   runs, **Then** existing Match and match-performance RAG representations can
   refresh from derived summaries without registering every delivery as a
   standalone RAG source.

### Edge Cases

- A scorer attempts to select the same participant as striker and non-striker;
  the state is rejected before persistence.
- A participant not fixed to the Match, a participant from the wrong side, or a
  dismissed/ineligible participant is used in a delivery or active-state
  selection; the operation is rejected.
- A Player is removed from a Team, deactivated, or reassigned after Match
  configuration; the fixed Match participant identity remains unchanged, while
  a newly configured Match still follows current eligibility rules.
- A side has duplicate participants, duplicate batting positions, a missing
  required side, or the same academy Player on both sides; configuration is
  rejected atomically.
- An external participant is supplied with a User ID, academy Player ID,
  academy Team membership, email, date of birth, or arbitrary metadata; the
  field is rejected and no identity is created.
- An innings is started without a valid batting pair or current bowler; start
  is rejected.
- A delivery is submitted before innings start, after completion, after an
  unresolved wicket, or after target reach; no scoring record is added.
- A delivery uses decimal over notation as authoritative input, a duplicate
  attempted sequence, or a sequence that skips the required append position;
  validation rejects it.
- A wide and no-ball, or a bye and leg-bye, are supplied together; the invalid
  combination is rejected.
- A wide or no-ball contains multiple runs; the quantity is retained and the
  over advances only when legal-ball rules say it should.
- A no-ball includes additional bat, bye, leg-bye, or penalty runs; the
  canonical scoring-rule table accepts only its capability-listed combinations
  and reconciles the total exactly once.
- A delivery contains negative runs, a non-finite value, a component above
  `SCORING_RUN_COMPONENT_MAX`, a total or aggregate above
  `SCORING_RUN_TOTAL_MAX`, or an impossible total; the delivery is rejected.
- A legal delivery contains byes, leg-byes, or penalty runs; balls faced,
  bowler-conceded runs, and team runs follow their separate derivation rules.
- An innings reaches six legal balls with illegal attempts in between; the raw
  delivery count does not determine over completion.
- The only eligible bowler is the bowler who just completed the over while
  consecutive overs are prohibited; the system reports that another selection
  is required instead of silently violating the rule.
- No eligible bowler remains because quotas or side eligibility are exhausted;
  normal delivery entry is blocked with a recoverable domain error.
- A wicket names an unused batter, a participant on the wrong side, or a fielder
  from the batting side; the wicket is rejected.
- A caught, caught-and-bowled, stumped, or run-out event has the wrong fielder
  cardinality, role, ordering, or participant side; the event is rejected
  unless it uses the canonical capability-listed fielder shape.
- A wicket is bowler-credited when its dismissal type is not bowler-credited,
  or a retired-hurt event is counted as a team wicket; the event is rejected.
- A retired-hurt batter is returned without the capability-listed transition,
  or a retired-out batter is selected again; the state is rejected.
- A delivery supplies a second wicket object, a wicket array, or duplicate or
  conflicting wicket data; schema validation rejects the complete delivery
  with no persisted event rather than silently dropping one. A correction may
  replace the single active wicket event only by appending a new revision.
- A target is calculated from an incomplete prior innings, a chase continues
  after target reach, or wickets/balls remaining become negative; the state is
  rejected.
- A correction makes later active deliveries incompatible with the rebuilt
  state; the history remains preserved and the innings enters an explicit
  reconciliation-required state until the conflicting delivery history is
  corrected, rather than silently rewriting later actors.
- A correction or completion is submitted with a stale Match, innings, delivery
  revision, or sequence version; the repository's normal conflict response is
  returned and no partial state commits.
- A caller requests arbitrary undo; no undo endpoint exists in this feature and
  the caller must use the validated delivery-correction command instead.
- A failed atomic delivery operation writes a Delivery but not its extras,
  wicket, fielder, state, summary, version, or downstream intent; the whole
  transaction must roll back.
- A direct aggregate performance submission targets a scored Match with
  `scoring_authority = delivery_history`; it is rejected with the
  scoring-authority conflict, even if its values match delivery-derived
  figures. Aggregate writes remain available only for
  `scoring_authority = legacy_aggregate` Matches.
- A data-quality scan detects inconsistent totals or identities; it reports the
  finding and does not invent or modify a delivery.
- A normal ball is recorded while Redis, an embedding provider, or a worker is
  unavailable; synchronous scoring still commits and no expensive downstream
  work is required for that ordinary ball.
- A completion-triggered background job is delivered more than once or after a
  correction; existing idempotency, coalescing, and current-source reload rules
  prevent stale RAG or summary state from replacing newer truth.
- An unauthorized or deactivated user attempts any scoring mutation; backend
  authorization rejects it regardless of client-supplied role or team scope.

## Requirements *(mandatory)*

### Functional Requirements

#### Match integration and fixed participants

- **FR-001**: The system MUST extend the existing Match domain and service so
  that Match metadata, participant semantics, protected retrieval, existing
  performance compatibility, RAG integration, and current authorization
  behavior remain available; it MUST NOT create a parallel Match or scoring
  subsystem.
- **FR-002**: The system MUST represent Match lifecycle separately from
  unfinished legacy result text, with states equivalent to scheduled/not
  started, in progress, completed, and abandoned/no result. A final Match
  result MUST be derived from completed innings whenever the locked
  FormatCapability defines an automatic result; otherwise the capability's
  permitted explicit completion mode is required.
- **FR-003**: The system MUST represent each Match side with a stable side
  identity, side/team or opponent identity, and its fixed selected participants.
  Internal Matches MUST reference two distinct academy Teams; external Matches
  MUST reference one academy Team and one match-scoped opposition side.
- **FR-004**: Internal Match participants MUST reference existing academy
  Player records directly. The feature MUST NOT create match-only duplicate
  identities for academy Players.
- **FR-005**: External opposition participants MUST be match-scoped scoring
  identities containing only a stable participant ID, Match ID, side/opponent
  identity, display name, batting-order position for batting participants, and
  capability-listed scoring role data. They MUST NOT create or require User
  accounts, academy Player profiles, email, date of birth, Team membership,
  career statistics, authentication data, or arbitrary metadata.
- **FR-006**: Playing-side configuration MUST validate that every participant
  is eligible for that side at configuration time, that duplicate participants
  are impossible within a side, and that one participant cannot represent both
  sides of a Match.
- **FR-007**: Once configured, the Match playing XI/match squad MUST be fixed
  to the Match. Later Team roster additions, removals, reordering, or Player
  status changes MUST NOT retroactively change Match participants or historical
  delivery identities.
- **FR-008**: The system MUST persist a positive, unique batting-order position
  for each selected participant on a side and MUST preserve the intended order
  even when the scorer chooses a different eligible next batter after a wicket.
- **FR-009**: Match configuration MUST be atomic and MUST include the current
  Match/version precondition. A failed validation, authorization check, or
  optimistic-concurrency check MUST leave the previous participant set intact.

#### Innings lifecycle and scoring policy

- **FR-010**: The system MUST provide a first-class Innings entity that
  identifies its Match, unique innings number, batting side, bowling side,
  lifecycle status, active striker, active non-striker, current bowler, team
  totals, wicket count, legal-ball count, structured overs, target when the
  locked capability enables it, completion reason, optimistic-concurrency
  state, and the canonical derived `blocking_state` representation.
- **FR-011**: An Innings MUST support the capability-defined innings sequence
  per Match; the data model MUST NOT hard-code a Match to exactly two innings.
  T20 and one-day use two innings, test uses four ordered innings, and other
  requires an explicit ordered sequence before scoring.
- **FR-012**: An Innings MUST distinguish not started, in progress, and
  completed, and MUST expose one canonical read-only `blocking_state` object.
  It MUST have the shape `{kind, is_blocked, reason_code}` and use only
  `none`, `innings_not_started`, `awaiting_next_batter`,
  `awaiting_next_bowler`, `reconciliation_required`, `innings_completed`,
  `match_completed`, or `match_abandoned` for `kind`. `is_blocked` MUST be
  false only for `none`; `reason_code` MUST be null for `none` and MUST be a
  deterministic bounded code for every other kind. The current codes are
  `innings_not_started`, `next_batter_required`, `next_bowler_required`,
  `no_eligible_bowler`, `incompatible_replay`, `innings_completed`,
  `match_completed`, and `match_abandoned`. Match and Innings responses MUST
  serialize this same object rather than requiring clients to infer a blocker
  from nullable participant fields. The derivation precedence is defined in
  the canonical blocking-state section above; when batter and bowler blockers
  coexist, `awaiting_next_batter` takes precedence.
- **FR-013**: Starting an Innings MUST require distinct eligible striker and
  non-striker participants from the batting side and an eligible current bowler
  from the bowling side. Normal delivery entry MUST be unavailable before a
  successful start.
- **FR-014**: An Innings MUST support every innings-completion mode listed by
  the locked FormatCapability, including all out, the configured maximum legal
  deliveries, target reached, or declaration where that capability lists it.
  Match-level draw, declared, and manual completion MUST likewise be accepted
  only when listed by the capability. Match-level abandonment is not an
  innings mode and MUST be accepted only by the Match completion endpoint.
  Unsupported automatic format rules MUST NOT be inferred.
- **FR-015**: Before scoring starts, the system MUST resolve the immutable
  FormatCapability matrix defined above. The capability MUST determine innings
  sequence, legal-ball limit, over length, wicket limit, consecutive-over
  restriction, bowler quota, dismissal/retirement set, declaration and draw
  support, manual completion, target/chase mode, explicit Match-completion
  boundary, completion modes, and valid result codes. T20 MUST resolve to 120
  legal balls in six-ball overs, 24
  legal balls per bowler, and ten wickets; one-day MUST receive exactly 300
  legal balls in six-ball overs, 60 legal balls per bowler, and ten wickets;
  test MUST use the fixed four-innings sequence, six-ball overs, ten wickets,
  no target, no quota, and no consecutive-over restriction; and other MUST
  require all policy values needed by its selected sequence and rule sets before
  scoring. All profiles MUST also use the fixed scoring numeric limits defined
  above; those limits are not policy-supplied.
- **FR-016**: Only a fixed-over FormatCapability with target mode
  `prior_innings_plus_one` may derive a target. For T20 and one-day, innings 2
  MUST start only after innings 1 completes, its target MUST equal innings 1's
  completed total plus one, and runs required, wickets remaining, and balls
  remaining MUST be derived from active delivery history. The target MUST
  complete the chase automatically; test and other MUST keep target unset.
- **FR-017**: The system MUST derive Match completion from the locked innings
  sequence and the result precedence defined above. Fixed-over Matches MUST
  produce win by runs, win by wickets, or tie from delivery-derived state;
  `no_result` is produced only by Match-level `abandonment`. Test Matches MUST
  produce aggregate win by runs or tie after the required innings, or an
  explicitly permitted `draw`, `declared`, or `manual` outcome; `no_result` is
  likewise produced only by Match-level `abandonment`. Other Matches MUST use
  only their configured `manual` outcome plus Match-level `abandonment` for
  `no_result`. For test, an explicit `draw`, `declared`, or `manual` completion is valid only
  immediately after a completed innings and before an automatic result. For
  `other`, `manual` is valid only at its locked
  `explicit_match_completion_boundary`. `abandonment` is valid from any
  non-terminal Match and produces `no_result`. No explicit completion can
  override an already-derived automatic result, and a manually supplied final
  result MUST NOT silently override completed-innings truth.

#### Batting, bowling, and over state

- **FR-018**: The system MUST track striker and non-striker explicitly and MUST
  reject equal identities, wrong-side identities, dismissed/ineligible
  identities, and participants not fixed to the Match.
- **FR-019**: The system MUST update strike from the canonical delivery-rule
  table and resolve end-of-over exchange from legal-ball completion. An odd
  number of completed runs exchanges the active ends and an even number does
  not; boundaries, penalties, wickets, and every other accepted outcome MUST
  use the same table. Previous deliveries MUST remain unchanged when a scorer
  selects a non-nominal next batter or overrides a bowler suggestion.
- **FR-020**: The current bowler MUST belong to the bowling side, satisfy
  centralized eligibility rules, obey the capability's consecutive-over
  restriction, and remain below the capability's legal-over quota when one is
  configured.
- **FR-021**: The domain MUST expose a reusable eligibility decision for bowler
  selection and MUST calculate quota usage from legal deliveries bowled, not
  from raw attempted-delivery count or decimal over arithmetic.
- **FR-022**: At over completion, the default suggestion MUST use the
  alphabetically first eligible bowler for the first over; thereafter it MUST
  prefer the bowler from the preceding alternate over when still eligible and
  below quota. The immediately completed bowler MUST be excluded where
  consecutive overs are prohibited, and the scorer MUST be able to override
  the suggestion with any eligible bowler.

#### Authoritative delivery and extras records

- **FR-023**: The system MUST store one authoritative active record for every
  attempted delivery, including Innings, stable sequence identity, derivable
  over/ball position, striker, non-striker, bowler, runs off the bat, extras
  quantities, total runs, legal/illegal status, wicket events, scorer and
  correction provenance, timestamps, and version metadata.
- **FR-024**: Delivery ordering MUST use a stable monotonic attempted-delivery
  sequence independent of display notation. Multiple attempts between legal
  balls MUST be supported, and decimal values such as `7.4` MUST NOT be the
  authoritative mathematical representation.
- **FR-025**: A legal delivery MUST increment the Innings legal-ball count; an
  illegal delivery MUST NOT. Over completion MUST be determined from legal
  deliveries rather than the number of delivery records.
- **FR-026**: Runs off the bat MUST be stored separately from extras as a
  non-negative bounded integer. The accepted range MUST include common values
  from zero through six and MUST explicitly permit five runs off the bat and
  other uncommon valid running/overthrow outcomes.
- **FR-027**: Extras MUST be represented as quantities, at minimum separate
  wide, no-ball, bye, leg-bye, and penalty-run quantities. Each quantity MUST
  support multiple runs, including multiple wides, no-ball plus additional
  runs, multiple byes, multiple leg-byes, and penalty runs. A no-ball record
  MUST preserve its required one-run no-ball penalty separately from any
  additional bat, bye, leg-bye, or permitted penalty runs.
- **FR-028**: A centralized scoring-rule layer MUST validate extras
  combinations, legal-ball effect, bowler-conceded effect, batter-balls-faced
  effect, and permitted coexistence. At minimum, wide plus no-ball and bye plus
  leg-bye MUST be rejected, no-ball MUST retain its required penalty while
  permitting only capability-listed additional runs, and a wide MUST support
  more than one wide run.
- **FR-029**: Delivery total runs MUST always equal runs off the bat plus the
  complete extras breakdown. The persisted total MUST not be an independently
  editable value that can disagree with its components.
- **FR-030**: Balls faced MUST be derived from the delivery outcome and MUST
  remain distinct from attempted deliveries and legal deliveries. Wides,
  no-balls, byes, leg-byes, penalty runs, and supported non-standard outcomes
  MUST use the centralized rule table rather than a Boolean shortcut. In the
  matrix-defined initial rules, wides and no-balls do not count as a ball
  faced, while a legal delivery that yields only byes or leg-byes does count;
  any penalty-only case follows its capability-listed rule.
- **FR-031**: Bowler-conceded runs, wides, no-balls, maidens, and legal overs
  MUST be derived using their own scoring rules; byes, leg-byes, and penalty
  runs MUST not be charged to the bowler unless the capability rule table says
  otherwise.

#### Wickets, fielders, and replacement batters

- **FR-032**: Wicket events MUST be explicit records linked to a delivery and
  MUST identify the dismissed batter, dismissal type, team-wicket effect,
  bowler-credit effect, fielder involvement, and any capability-listed
  additional dismissal metadata.
- **FR-033**: The initial T20, one-day, and test capabilities MUST list
  bowled, caught, caught and bowled, LBW, run out, stumped, hit wicket, and
  retired out as valid dismissal types, plus the separate `retired_hurt` and
  `retired_hurt_return` transition types. `retired_hurt` MUST be represented by
  the transition path rather than a team-wicket event. The `other` capability
  MUST list its own dismissal and transition types and their required
  metadata/cardinality before scoring; an unlisted type MUST be rejected.
  `obstructing_the_field`, `hit_the_ball_twice`, and `timed_out` are reserved
  future identifiers, are rejected by every current capability including
  `other`, and MUST NOT appear in the current public dismissal enum.
- **FR-034**: The rule layer MUST distinguish bowler-credited dismissals from
  non-bowler-credited dismissals and team-wicket dismissals from events that do
  not reduce the team's available wickets. Retired hurt MUST be separate from
  retired out and MUST NOT be treated as an ordinary bowler-credited wicket.
  In the initial capability vocabulary, bowled, caught, caught and bowled, LBW,
  stumped, hit wicket, run out, and retired out count as team wickets; retired
  hurt does not. Bowled, caught, caught and bowled, LBW, stumped, and hit
  wicket are bowler-credited; run out and retired out are not. Retired hurt is
  a transition and is never bowler-credited. Every dismissal listed by an
  `other` capability MUST declare its effects before it can be accepted.
- **FR-035**: Fielder involvement MUST be captured only when required or
  meaningful: catches MUST identify a catcher, stumpings MUST identify the
  wicketkeeper/fielder, and run-outs MUST support all fielders required by the
  capability rule table. The ordered `fielders[]` collection is the canonical
  source of fielder relationships. Fielders MUST belong to the fielding side
  and use academy Player references or Match-scoped external participant
  references.
- **FR-036**: Each active delivery revision MUST contain zero or one
  `WicketEvent`; the API schema MUST represent the field as an optional object,
  not an array. Its ordered `fielders[]` collection is persisted as ordered
  `DeliveryFielder` associations. A read-only `primary_fielder_participant_id`
  compatibility pointer, when exposed, MUST equal the first association when
  the collection is non-empty and MUST be null when it is empty; it MUST never
  be separately supplied or independently written. Bowled, LBW,
  hit-wicket, and retired-out require zero fielders; caught, caught-and-bowled,
  and stumped require exactly one fielder with the corresponding role; run-out
  requires at least one fielder and MAY include multiple ordered thrower,
  keeper, assister, or other roles. A single event MAY therefore reference
  multiple fielders only where its capability rule permits it.
  A second wicket object, wicket array, duplicate event, or conflicting wicket
  payload MUST fail closed with validation error 422 and no persisted delivery
  or projection change. A correction replaces the event only by appending a new
  immutable delivery revision. Persistence, replay, and response serialization
  MUST read the ordered association rows; the derived primary pointer MUST NOT
  affect scoring or replay, so replay applies at most one active wicket effect
  per attempted delivery.
- **FR-037**: After a dismissal requiring replacement, the system MUST resolve
  the delivery and wicket before requiring next-batter selection. The scorer
  MUST be able to select any eligible unused batter; batting order MAY provide
  a suggestion but MUST NOT force the nominal next participant.
- **FR-038**: A retired-hurt batter MUST have a distinct status and MUST return
  only through an explicit `retired_hurt_return` transition. The initial T20,
  one-day, and test capabilities permit that transition; an `other` capability
  must list it in its transition set before it can be used. Retired hurt MUST
  not increment team wickets or bowler wickets. A retired-out batter MUST
  remain ineligible to return unless a correction changes the event. The
  innings lifecycle remains `in_progress` after a retired-hurt transition, but
  delivery append MUST be blocked until either an eligible next-batter
  selection or an allowed return restores two active batters; a successful
  selection or return restores `in_progress` scoring with the resulting active
  participant state.

#### Derived state and existing performance compatibility

- **FR-039**: Innings totals MUST be derivable from active delivery history for
  total runs, wickets lost, legal deliveries, structured overs, extras total,
  extras breakdown, current run rate, active batters, current bowler, and
  completion state.
- **FR-040**: Batting summaries MUST derive runs, balls faced, fours, sixes,
  dismissal, and strike rate from delivery and wicket history. A boundary count
  MUST not misclassify five bat runs or extras as a batter boundary.
- **FR-041**: Bowling summaries MUST derive legal balls/overs, maidens, runs
  conceded, bowler-credited wickets, wides, no-balls, and economy from delivery
  and wicket history.
- **FR-042**: Fielding summaries MUST derive catches, stumpings, and run-out
  involvement from wicket and fielder events, including match-scoped external
  fielders where applicable.
- **FR-043**: Existing `MatchBattingPerformance`, `MatchBowlingPerformance`,
  and `MatchFieldingPerformance` data MUST transition toward derived or
  materialized Match summaries for scored Matches. A scorer MUST NOT be required
  to enter delivery truth and aggregate performance truth independently.
- **FR-044**: Existing direct aggregate performance behavior MUST be made
  compatible with scored Matches. A Match with
  `scoring_authority = legacy_aggregate` retains the existing aggregate-only
  read/write path and has no authoritative delivery history. A Match configured
  for scoring is locked to `scoring_authority = delivery_history` before its
  first scoring innings or delivery; every direct aggregate write for that
  Match MUST be rejected with the scoring-authority conflict, even when its
  values happen to equal delivery-derived values. Existing historical
  `legacy_aggregate` Matches remain readable and supported, and no implicit
  migration between authorities is introduced.
- **FR-045**: Scorecard reads MUST expose enough derived data for innings totals,
  batting, bowling, fielding, extras, fall of wickets, over progression,
  target/chase state, and result. Academy Players MUST remain first-class;
  opposition participants MUST remain coherent without becoming academy
  career-stat identities.
- **FR-046**: The system MAY persist current-state/read-model fields for fast
  Match and Innings reads, but every persisted cache MUST be reconcilable from
  active delivery history. Normal reads MUST NOT require replaying the full
  delivery history for every request.

#### Correction, reconstruction, and optimistic concurrency

- **FR-047**: Delivery correction MUST append an immutable replacement
  `DeliveryRevision`, mark the expected active revision `superseded`, preserve
  original provenance, and identify exactly one active representation for
  normal scorecards. Prior revisions and delivery parents MUST not be mutated,
  deleted, or converted to a separate void state. A correction that removes a
  scoring fact MUST use a valid replacement revision containing the corrected
  zero or nonzero observed components. A correction in a `completed` Match is
  the only operation that may enter the transactional internal
  `correction_reprocessing` phase; ordinary scoring, completion, and
  abandonment commands MUST NOT reopen a completed Match.
- **FR-048**: Reconciliation after a correction MUST rebuild affected innings
  state, totals, extras, wickets, strike, current bowler, legal-ball and over
  state, batting/bowling/fielding summaries, target/chase state, innings
  completion, and the delivery-derived Match result from active delivery
  history, while preserving any authoritative persisted Match lifecycle command
  state that remains applicable to the corrected history. It MUST not rely on
  manual counter decrements. A compatible terminal replay
  commits `correction_reprocessing → completed`; a compatible non-terminal
  replay commits `correction_reprocessing → in_progress` with result `pending`.
  An incompatible later transition may commit the Match as `in_progress` with
  the affected Innings in `reconciliation_required`; an unsafe replay rolls
  back the entire correction with HTTP 409.
- **FR-049**: If replay reveals that a later active delivery is incompatible
  with corrected state, the system MUST preserve that delivery's identity and
  provenance, mark the conflict explicitly, and require safe reconciliation or
  a further correction rather than silently rewriting captured actors or
  outcomes.
- **FR-050**: All scoring mutations MUST require the expected current Match,
  Innings, delivery/revision, or sequence version applicable to the operation.
  This includes participant configuration, innings start, delivery entry,
  next-batter selection, next-bowler selection, correction, reopening, and
  completion.
- **FR-051**: A stale scoring mutation MUST use the repository's standard
  optimistic-concurrency conflict behavior, including HTTP 409 at the protected
  API boundary where applicable, and MUST never silently overwrite newer state.
- **FR-052**: Delivery entry MUST be one atomic domain operation. Delivery,
  extras, wickets, fielders, active-batter state, over/legal-ball state,
  summaries, OCC progression, and any completion-triggered downstream intent
  MUST commit together or roll back together.
- **FR-053**: Arbitrary user-facing undo is deferred and no undo endpoint is
  part of this feature. The supported amendment mechanism is delivery
  correction through the immutable revision command. If a future feature adds
  undo, it MUST delegate to this correction/domain-service boundary and reuse
  its validation, OCC, audit, authorization, and reconstruction path rather
  than introducing an independent counter mutation. No undo implementation or
  dedicated undo test suite is required for this feature.

#### Authorization and external identity boundaries

- **FR-054**: Scoring authorization MUST use the authenticated database User,
  current role, and current Team scope. The server MUST ignore or reject
  client-supplied role, User ID, Player ID, Team ID, or scope claims that would
  widen access.
- **FR-055**: Head Coaches MUST have full scoring access. Assistant Coaches
  MUST be able to score a Match when its academy side is within their current
  TeamCoach assignment scope, subject to the same Match and OCC rules. Players
  MUST have read-only access to permitted live and completed Match data.
- **FR-056**: External participants MUST be scoring identities only. They MUST
  never receive authentication, authorization scope, academy permissions,
  Player-profile access, or an implicit User/Player account.
- **FR-057**: View access MUST be checked for Match and scorecard reads as well
  as mutations. A scoped Assistant Coach or Player MUST not gain access to an
  unrelated Team's Match by supplying a different Match or Team identifier.

#### Business Audit, Data Quality, RAG, and background work

- **FR-058**: The scoring-domain Business Audit allowlist contains only these
  successful commands: scoring initialization (successful configuration that
  locks the policy), innings start, innings completion, Match completion
  (including an allowed manual, draw, declared, or abandonment outcome), and
  delivery correction. Each allowlisted event MUST identify the authenticated
  actor, target, action, and safe bounded metadata. A command produces at most
  one Business Audit event for its committed domain action.
- **FR-059**: Ordinary delivery entry, next-batter selection, retirement or
  return selection, next-bowler query or selection, technical recalculation,
  derived-state refresh, background processing, rejected validation, and stale
  conflict MUST NOT create Business Audit events. Existing technical
  request/error logging remains separate from Business Audit.
- **FR-060**: Data Quality MUST be able to identify scoring inconsistencies,
  including delivery-derived totals that disagree with an Innings read model,
  an active batter already dismissed, a bowler on the wrong side, duplicate
  active delivery sequence, invalid Match participant relationships, and
  MatchPerformance rows inconsistent with delivery truth, plus malformed
  historical or legacy scoring state. A reconciliation finding is authoritative
  when an Innings lifecycle is `reconciliation_required`; no Match or Innings
  boolean may independently assert that condition. Data Quality MUST report findings
  without inventing, deleting, or modifying scoring events. Scoring correction
  remains the separate immutable delivery-correction command; existing
  non-scoring Data Quality remediation MUST NOT accept or mutate scoring
  findings. Scoring Data Quality findings are operational/administrative
  information: only Head Coaches may view them through `GET /data-quality`.
  This feature provides no public check-trigger or re-run endpoint; any
  bounded check execution exposed by that read remains Head-Coach-only. No
  role may correct scoring through the Data Quality remediation endpoint.
  Head Coaches and appropriately scoped Assistant Coaches may correct scoring
  only through the normal delivery-correction command, subject to its OCC and
  authorization rules; Players may not correct scoring.
- **FR-061**: Successful Match completion and material delivery correction MUST
  reuse the same existing durable background-processing foundation by staging
  the canonical coalesced current-state refresh intent in the committing
  transaction. That intent may drive derived performance recomputation,
  finalized Match summaries, RAG reconciliation, and future player-stat or
  analytics updates. Live scoring state MUST remain synchronous and atomic.
- **FR-062**: The system MUST NOT enqueue expensive downstream work after every
  ordinary delivery unless a separately demonstrated requirement justifies it.
  A successful Match completion or material correction MUST stage at most one
  bounded, idempotent, coalescible canonical refresh intent per logical
  derived-summary refresh; duplicate staging MUST coalesce rather than create a
  second mechanism or intent.
- **FR-063**: Existing Match and match-performance RAG sources MAY be refreshed
  when meaningful derived summaries change, especially at Match completion or
  material correction. Every Delivery MUST NOT be registered as a standalone
  RAG source in this feature. Ball-by-ball semantic retrieval requires a future
  explicit source-registration change.
- **FR-064**: Background jobs and RAG reconciliation MUST reload current
  authoritative Match/Innings/delivery-derived state, remain safe when
  delivered more than once, and preserve current authorization/source-registry
  boundaries. Technical work MUST not become scoring truth or create Business
  Audit events.

#### Persistence, migration, testing, and documentation

- **FR-065**: Every scoring-domain schema change MUST be delivered through
  versioned, reversible-where-practical Alembic migrations with foreign keys,
  uniqueness constraints, sequence/order indexes, lifecycle constraints, and
  OCC/version columns where concurrent writes are possible.
- **FR-066**: Migration tests MUST run against the project's Docker PostgreSQL
  convention and MUST verify upgrade, required tables/constraints/indexes,
  downgrade where practical, and re-upgrade without manual schema edits.
- **FR-067**: Unit tests MUST cover all new domain and validation logic and
  MUST include an explicit unit-test task for every new public scoring-domain
  service/function and protected API handler. Coverage MUST include innings
  initialization, internal/external participants, striker and non-striker
  validation, bowler eligibility and defaults, quotas, legal-ball progression,
  all required extras and run cases, balls faced, strike rotation, wicket and
  retirement semantics, fielders, next-batter selection, target and completion
  rules, corrections, Data Quality findings, and stale OCC writes.
  `pytest-mock` MUST be used where external services or isolated dependencies
  need mocking, and unit tests MUST run without Internet access.
- **FR-068**: Integration tests MUST cover complete normal limited-overs,
  extras-heavy, wicket/next-batter, chase, correction, concurrent-scoring, and
  external-Match flows, including consistency between persisted read-model
  state and delivery-derived truth.
- **FR-069**: The required backend quickstart test MUST be named
  `backend/tests/integration/quickstart/test_014_quickstart_flow.py` and MUST
  exercise the acceptance flow listed below through committed domain behavior.
- **FR-070**: The feature MUST include at least one Playwright end-to-end
  journey. Because no polished scorer UI is required, the journey MAY use the
  existing authenticated request-level pattern from a browser context and MUST
  cover the primary initialize, score, correct, complete, read, and conflict
  outcomes for both internal and external T20 variants through a parameterized
  shared journey, without building pitch-map, wagon-wheel, or analytics UI.
- **FR-071**: After implementation and verification, the project MUST include
  `docs/match-scoring-domain.md` describing actual implemented authoritative
  architecture, participants, innings, delivery identity, legal/illegal balls,
  runs/extras, wickets/fielders, batting order, bowler selection and quotas,
  strike rotation, target/chase behavior, correction semantics, OCC,
  performance derivation, background/RAG integration, the capability matrix,
  multi-innings ordering, one-wicket-per-delivery policy, benchmark protocol,
  deferred undo boundary, canonical format identifiers, Data Quality
  authorization, ordered fielder mapping, and future scorecard, pitch-map,
  wagon-wheel, and player-stat extension points.
- **FR-072**: Before FR-071 documentation is written or updated, the final
  verification gate MUST run backend Ruff lint/format checks, backend strict
  type checking, backend unit and integration tests, Alembic consistency, and
  the quickstart test; it MUST also run frontend ESLint, strict TypeScript
  checks for the application and Node configurations, and the Playwright
  journey. The application TypeScript configuration MUST include the
  Playwright test files, or an equivalent explicit TypeScript command MUST
  validate those files. T075 MUST run both of these exact commands:

      npx tsc -p tsconfig.app.json --noEmit --pretty false
      npx tsc -p tsconfig.node.json --noEmit --strict --pretty false

  The first covers `e2e` through its include list and the second strictly
  checks the Node/Vite/Vitest/Playwright configuration files.

### Verification Requirements

The unit suite must explicitly cover ordinary runs, boundaries, five bat runs,
single and multiple wides, no-balls with additional runs, byes, leg-byes,
penalty runs, total-run reconciliation, balls-faced derivation, strike rotation,
end-of-over behavior, every capability-listed dismissal category, bowler-credit
rules, catches, stumpings, run-outs, the retired-hurt transition, retired out,
next-batter selection, target/chase calculation, fixed and multi-innings result
derivation, one-wicket-per-delivery validation, dismissal-specific fielder
cardinality/order, reserved future-dismissal rejection, innings/Match
completion boundaries, Match-only abandonment and derived current-Innings state,
correction/revision reopening outcomes, canonical blocking-state precedence,
reconciliation lifecycle clearing, minimum/maximum/below-minimum/above-maximum
component boundaries and aggregate overflow, Data Quality finding
classification and authorization, and stale OCC writes.

The integration suite must include these representative flows:

- A normal limited-overs innings initializes a playing XI, starts, records
  multiple overs and boundaries, rotates strike, changes bowler, and completes.
- An extras-heavy over includes a single wide, a multiple-run wide, a no-ball,
  no-ball plus additional runs, a bye, and a leg-bye, then verifies legal-ball
  count and score.
- A wicket flow records bowled, caught with a fielder, and run-out events,
  selects a replacement batter, and verifies wickets and strike state.
- A parameterized T20 chase completes the first innings for both an internal and
  external Match, derives the target, starts the second, tracks
  runs/balls/wickets remaining, reaches the target, and completes the Match
  automatically.
- A correction changes an earlier delivery and verifies every downstream
  state and derived aggregate is reconciled.
- Two concurrent next-delivery requests use one stale innings version; one
  succeeds, one receives an OCC conflict, and no duplicate active sequence is
  created.
- An external Match uses academy Player records on the academy side and
  match-scoped opposition participants for batting, bowling, and fielding,
  without creating an academy Player or User for opposition identities.
- A Head-Coach-only Data Quality scan reports replay/projection mismatch,
  duplicate or conflicting active event state, invalid participant/lifecycle
  state, and legacy projection divergence without modifying scoring data;
  Assistant Coach and Player requests are rejected.

### Quickstart Acceptance Flow

The executable quickstart must demonstrate the following 25-step sequence for
both a canonical `T20` internal Match and a canonical `T20` external Match. The
implementation may use one parameterized/shared journey rather than
duplicating the steps. The internal run uses two academy sides; the external
run uses one academy side and one match-scoped opposition side with no academy
account fields. The API, domain, policy, and persisted format identifier is
`T20`.

1. Apply migration 016 and verify it is at the database head.
2. Seed two academy Teams and their Players using isolated fixtures.
3. Create the internal Match fixture and the external Match fixture.
4. Configure the internal Match with two academy sides and the external Match
   with one academy side plus one external opponent side.
5. Configure each fixed playing XI/Match squad and verify the participant
   identity rules: academy Players are direct references; opposition entries
   contain only Match-scoped scoring identity fields.
6. Lock the canonical `T20` capability and verify 120 legal balls per innings,
   six-ball overs, 24 legal balls per bowler, ten wickets, two innings in
   `[A, B]` order, automatic target mode, one-wicket-per-delivery validation,
   and the listed completion/result codes.
7. Start innings 1 with explicit striker, non-striker, and bowler participant
   IDs.
8. Record an ordinary legal delivery with ordinary runs.
9. Record a legal boundary and verify bat runs, balls faced, and boundary
   derivation.
10. Record a five-run batter outcome and verify the total is derived without a
    boundary classification.
11. Record a multiple-run wide and verify it is illegal and does not consume a
    legal ball or bowler quota.
12. Record a no-ball with additional permitted runs and verify the one-run
    no-ball penalty is represented separately.
13. Record one caught wicket with exactly one ordered `catcher` in `fielders[]`,
    verify any exposed primary-fielder pointer is derived from that first row,
    then submit a duplicate/conflicting wicket shape and verify the whole
    request is rejected without a partial event.
14. Exercise both retired-hurt branches across the two parameterized fixtures:
    on the internal fixture, record `retired_hurt`, verify no team wicket,
    verify delivery append is blocked while the batting vacancy exists, and
    select an eligible unused next batter so the innings remains `in_progress`
    with two active batters; on the external fixture, record `retired_hurt`,
    verify no team wicket, and commit `retired_hurt_return` so the same
    MatchParticipant becomes active again, the innings remains `in_progress`,
    and no new identity or wicket is created.
15. Complete an over using legal deliveries and verify over state and strike
    transition.
16. Query the next-bowler suggestion and verify quota, previous-over
    preference, and eligibility reasons are deterministic.
17. Continue innings 1 with legal, illegal, extra, and fielding events as
    needed to exercise the read model.
18. Complete innings 1 through the `T20` `all_out` or `legal_ball_limit` path.
19. Read the derived target for innings 2 and verify it equals innings 1's
    completed total plus one.
20. Start innings 2 with the derived target and explicit opening selections.
21. Complete the chase by reaching the target and verify automatic innings and
    Match completion with win-by-wickets details.
22. Read each scorecard and verify totals, extras, wickets, overs, fall of
    wickets, participant summaries, target, result, capability, and projection
    revision are derived from active delivery history.
23. Correct one earlier delivery with an explicit reason and expected active
    revision; verify immutable provenance and deterministic replay rebuild.
24. Submit two concurrent writes using one stale innings version and verify
    exactly one succeeds, the other returns 409, and no duplicate active
    sequence exists.
25. As Head Coach, inspect Data Quality, background/RAG fakes, and audit
    records: ordinary delivery entry performed no provider/queue work;
    completion/correction work is bounded and coalesced; scoring findings are
    visible but read-only; Assistant Coach and Player requests for findings are
    rejected with 403; only allowlisted scoring commands have their expected
    audit events; and the
    external run created or exposed no User, Player, Team membership,
    career-stat, token, or raw unrestricted payload.

### Protected Read and Mutation Boundary

The protected Match boundary must expose configured participants, innings
state, active delivery history or a bounded delivery view, derived summaries,
completion reasons, target/chase state, and Match result with server-managed
versions. Scoring commands must return clear validation, authorization, not
found, and conflict outcomes consistent with existing protected routes. No
client-supplied role, scope, or external identity metadata may widen access.

### Domain Rule Baseline

The scoring rules use the current [MCC Laws of
Cricket](https://www.lords.org/mcc/the-laws) as their baseline. This feature
intentionally implements the capability matrix above, the canonical delivery
component rules, and one WicketEvent per active delivery revision. Retired hurt
uses a retirement transition and does not count as a team wicket. Unsupported
dismissals, format rules, and event combinations return explicit domain errors
or use a capability-listed manual-completion path; they are never inferred.

In this package, an authoritative scoring event is either an active
`DeliveryRevision` containing observed delivery facts or an anchored innings
transition event. A `WicketEvent` is nested detail on one delivery revision,
not a second delivery event; projections and replay use that same terminology.

### Key Entities *(include if feature involves data)*

- **Match**: The existing cricket event, extended with lifecycle and derived
  result semantics while retaining date, format, venue, participant type,
  academy Team references, and external opponent identity.
- **MatchSide**: A stable home/away or equivalent side in one Match, linked to
  an academy Team or external opponent context.
- **MatchParticipant**: A fixed Match-scoped scoring identity. Academy rows
  reference an existing Player; opposition rows contain minimal external
  display and scoring data only.
- **BattingOrderEntry**: The intended position and participation status for a
  selected MatchParticipant, including not-batted, active, dismissed, retired,
  and completed participation states.
- **Innings**: One ordered batting/bowling phase of a Match, its lifecycle,
  current pair and bowler, structured over progress, totals, target, completion
  reason, and version.
- **Delivery**: One attempted delivery with stable sequence, captured batter
  and bowler identities, bat runs, extras, legal-ball status, provenance, and
  revision identity. It is the authoritative scoring record and a stable future
  parent for pitch-map and wagon-wheel data.
- **DeliveryRevision or Amendment**: A preserved correction history for one
  logical delivery, with an unambiguous active version and OCC metadata.
- **WicketEvent**: A delivery-linked dismissal event with dismissal semantics,
  team-wicket and bowler-credit effects, and fielder relationships. There is at
  most one WicketEvent per active delivery revision.
- **DeliveryFielder**: A link between a wicket event and one or more fielding
  participants, supporting catches, stumpings, and run-outs.
- **RetirementTransition**: The explicit innings transition for retired hurt,
  including return eligibility; it is not a team-wicket event.
- **InningsReadModel**: Reconciled current innings state and totals retained for
  efficient reads, never independently editable scoring truth.
- **MatchParticipantPerformance**: Derived batting, bowling, and fielding
  summaries for academy and external Match participants; academy summaries
  remain compatible with existing Match performance models.
- **Target/ChaseState**: Derived target, runs required, wickets remaining,
  balls remaining, and target-reached state for later innings.
- **FormatCapability**: The immutable versioned capability profile selected for a
  Match format, including its canonical identifier, innings sequence, limits,
  completion modes and boundaries, target behavior, and result codes.
- **ScoringRulePolicy**: The locked Match policy instance that stores the
  resolved FormatCapability and its explicit sequence/limit values used to
  decide legal balls, quotas, completion boundaries, extras, dismissal, and
  strike behavior without silently applying unsupported rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all required unit, integration, and quickstart scoring cases,
  100% of accepted innings totals, wicket counts, legal-ball counts, extras,
  and participant summaries equal values independently recomputed from active
  delivery history.
- **SC-002**: For the benchmark fixture defined below, at least 29 of 30
  measured warm current-state reads for an innings containing exactly 1,000
  attempted deliveries MUST complete within one second in the project's local
  integration environment, return the persisted reconciled state, and MUST NOT
  require a full history replay on every read.
- **SC-003**: In the required two-writer concurrent-delivery scenario, exactly
  one request succeeds, the other receives the standard conflict response, and
  the innings contains no duplicate active sequence; this result holds for
  every execution of the acceptance test.
- **SC-004**: Correcting an earlier delivery in an innings of at least 100
  attempted deliveries preserves the original correction history and produces
  totals, strike, over state, wickets, chase state, and derived performance
  values identical to a clean replay of the corrected active history.
- **SC-005**: A scorer can complete the parameterized 25-step backend
  quickstart for both an internal and an external Match without entering
  aggregate batting, bowling, or fielding figures separately, and both resulting
  scorecards are complete enough for a later scorecard feature.
- **SC-006**: 100% of opposition participants created by the external-Match
  acceptance flow remain match-scoped only: no opposition User, academy Player,
  Team membership, authentication identity, or career-stat row is created.
- **SC-007**: Every protected scoring mutation made by a Player or an Assistant
  Coach outside current Team scope is rejected, and no unauthorized request
  changes delivery, innings, Match, summary, or participant state.
- **SC-008**: Ordinary delivery entry performs no required provider, queue, or
  embedding work on the synchronous path; successful Match completion and
  material correction use the same safely coalesced downstream intent and
  create at most one intent per logical derived-summary refresh.
- **SC-009**: The required unit, integration, migration, quickstart, and
  request-level Playwright journeys pass without Internet access, and no
  protected response, audit record, background status, or test log exposes
  external participant account data, credentials, tokens, vectors, or raw
  unrestricted payloads.

### Performance benchmark protocol

The SC-002 benchmark is intentionally a focused acceptance case, not a
separate load-testing system. The test MUST use a pre-seeded `test` innings
with the locked `[A, B, A, B]` capability, exactly 1,000 active attempted
delivery revisions (900 legal and 100 illegal), fixed participants, and a
persisted current projection. Fixture creation, migration, process startup,
and database startup are outside the measured boundary.

The local backend process and PostgreSQL test instance MUST already be
running. The test records one first read with cold application/connection
state for diagnostics, performs five warm-up reads, and then measures 30
consecutive warm authenticated current-state reads from request start through
response completion. The deterministic pass criterion is at least 29 of the
30 individual warm reads completing in one second or less; no percentile
interpolation or rounding convention is used. The response must expose the
expected projection revision and the test must verify that the endpoint uses
the persisted projection rather than invoking a full-history replay. No
provider, queue, embedding, or Internet access is permitted.

## Assumptions

- The existing authenticated User, UserRole, TeamCoach, TeamPlayer, Match,
  performance, OCC, Business Audit, Data Quality, RAG registry, and durable
  background-work foundations remain the integration points for this feature.
- Current Match formats remain `T20`, `one-day`, `test`, and `other`. The
  Match-format Capability Model is normative: T20 uses 120 legal balls and 24
  legal balls per bowler; one-day requires explicit 300-ball and 60-ball policy
  values; test uses four ordered innings with no target; and other requires an
  explicit innings sequence and manual completion.
- A standard innings has a maximum team-wicket count derived from its fixed
  eligible batting participants, with retirement semantics applied separately.
  T20 and one-day use a ten-wicket limit; test and other store the explicit
  policy limit before scoring starts.
- The default bowler suggestion compares normalized display names
  case-insensitively and uses stable participant ID as a deterministic tie-break
  when names match.
- For a fixed-over chase, innings 2 targets the completed innings 1 score plus
  one. Test and other profiles do not derive a target. Follow-on, forfeiture,
  interruption, DLS, and Super Over rules are deferred while the Innings model
  remains extensible.
- A retired-hurt participant is represented by an explicit transition event and
  can return only through an explicit re-entry action at a legal state boundary;
  retirement does not cause an automatic identity swap without a scorer
  decision.
- Existing manually entered performance rows for Matches without delivery truth
  remain readable. Matches that opt into authoritative delivery scoring use
  delivery-derived summaries and cannot accept conflicting aggregate truth.
- Match-scoped external participants are retained only for the Match's scoring,
  scorecard, and correction history. They are never promoted into academy
  identity, authorization, or career-stat domains.
- No new scorer UI is needed in this increment. Any future scorer UI will use
  the existing Product and Design system and will add its own responsive,
  keyboard, loading, empty, error, success, and conflict acceptance coverage.
- Arbitrary user-facing undo is future scope. This feature exposes only the
  immutable delivery-correction mechanism; a later undo feature must delegate
  to that same correction service boundary.
- The documentation file is written after implementation and verification so it
  describes actual behavior rather than aspirational design.
