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
   updated according to the supported scoring rules and over-end exchange.
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
5. **Given** an eventual user-facing undo operation, **When** it is invoked,
   **Then** it uses the same validated revision, OCC, audit, and reconstruction
   path as any other correction.

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

1. **Given** a supported limited-overs innings, **When** all available batting
   wickets are lost or the configured legal-ball limit is reached, **Then** the
   innings completes with the corresponding reason and cannot accept normal
   delivery entry.
2. **Given** a later innings with a target from a completed prior innings,
   **When** the batting side reaches the target, **Then** the chase completes
   automatically with runs required equal to zero and the Match completes when
   no required innings remain.
3. **Given** a completed chase that reaches the target before the legal-ball
   limit, **When** the result is read, **Then** it identifies a win by wickets
   with the correct wickets remaining and does not claim unused balls were
   bowled.
4. **Given** equal completed scores, an explicitly supported declaration, or
   an abandonment/no-result event, **When** the applicable completion action is
   committed, **Then** the Match records the supported tie, draw, declaration,
   or no-result outcome without inventing unsupported format rules.
5. **Given** a non-standard `other` Match whose automatic end cannot be safely
   determined, **When** an authorized scorer manually completes it with an
   explicit reason, **Then** the state records that reason and does not pretend
   an automatic format rule was applied.

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
- A no-ball includes additional bat, bye, leg-bye, or permitted penalty runs;
  the scoring rule layer accepts only supported combinations and reconciles the
  total exactly once.
- A delivery contains negative runs, a non-finite value, a value outside the
  documented finite bound, or an impossible total; the delivery is rejected.
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
- A caught, stumped, or run-out event omits required fielder involvement, or a
  run-out needs more than one fielder but only one slot is available; the
  event is rejected or represented using the supported multi-fielder shape.
- A wicket is bowler-credited when its dismissal type is not bowler-credited,
  or a retired-hurt event is counted as a team wicket; the event is rejected.
- A retired-hurt batter is prevented from returning when the supported rules
  permit return, or a retired-out batter is selected again; the state is
  rejected.
- A delivery has multiple wicket events in a rule set that does not support
  them; the complete delivery is rejected rather than silently dropping one.
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
- A failed atomic delivery operation writes a Delivery but not its extras,
  wicket, fielder, state, summary, version, or downstream intent; the whole
  transaction must roll back.
- A direct aggregate performance submission conflicts with delivery-derived
  figures for a scored Match; it is rejected or treated as a controlled legacy
  path, never as a second scoring truth.
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
  result MUST be derived from completed innings wherever the supported rules
  can determine it.
- **FR-003**: The system MUST represent each Match side with a stable side
  identity, side/team or opponent identity, and its fixed selected participants.
  Internal Matches MUST reference two distinct academy Teams; external Matches
  MUST reference one academy Team and one match-scoped opposition side.
- **FR-004**: Internal Match participants MUST reference existing academy
  Player records directly. The feature MUST NOT create match-only duplicate
  identities for academy Players.
- **FR-005**: External opposition participants MUST be match-scoped scoring
  identities containing only a stable participant ID, Match ID, side/opponent
  identity, display name, batting-order position where applicable, and optional
  scoring role data justified by the supported rules. They MUST NOT create or
  require User accounts, academy Player profiles, email, date of birth, Team
  membership, career statistics, authentication data, or arbitrary metadata.
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
  totals, wicket count, legal-ball count, structured overs, target where
  applicable, completion reason, and optimistic-concurrency state.
- **FR-011**: An Innings MUST support multiple innings per Match structurally;
  it MUST NOT hard-code a Match to exactly two innings even though the initial
  supported rule set may focus on limited-overs Matches.
- **FR-012**: An Innings MUST distinguish not started, in progress, and
  completed, and MUST expose a blocking substate or equivalent indicator for
  awaiting next-batter, next-bowler, or reconciliation-required decisions.
- **FR-013**: Starting an Innings MUST require distinct eligible striker and
  non-striker participants from the batting side and an eligible current bowler
  from the bowling side. Normal delivery entry MUST be unavailable before a
  successful start.
- **FR-014**: An Innings MUST support completion for all out, configured maximum
  legal deliveries, target reached, declaration where the supported format
  permits it, abandonment/no result, and explicit manual completion for a
  non-standard format. Unsupported automatic format rules MUST NOT be inferred.
- **FR-015**: The system MUST determine the supported format policy before
  scoring starts, including whether the Match has a fixed legal-ball limit,
  wicket limit, consecutive-over restriction, and bowler quota. The initial
  policy MUST support conventional T20 limits of 20 legal overs per innings and
  four overs per bowler when the Match format is T20, MUST require explicit
  Match configuration before automatic one-day limits are enforced, and MUST
  leave test/other behavior manual or otherwise explicitly configured until its
  rules are supported.
- **FR-016**: For a later innings with a target, the system MUST derive the
  target from the relevant completed prior innings, calculate runs required,
  wickets remaining, and balls remaining from current delivery-derived state,
  and complete the chase automatically when the target is reached.
- **FR-017**: The system MUST derive Match completion from the required innings
  and supported result rules, including win by runs, win by wickets, tie, draw
  where applicable, and no result/abandoned. A manually supplied final result
  MUST NOT silently override completed-innings truth.

#### Batting, bowling, and over state

- **FR-018**: The system MUST track striker and non-striker explicitly and MUST
  reject equal identities, wrong-side identities, dismissed/ineligible
  identities, and participants not fixed to the Match.
- **FR-019**: The system MUST update strike from the supported delivery outcome
  and resolve end-of-over exchange from legal-ball completion. For the initial
  ordinary-running rules, an odd number of completed runs exchanges the active
  ends and an even number does not; boundaries, penalties, wickets, and other
  supported outcomes MUST use the explicit rule table. Previous deliveries MUST
  remain unchanged when a scorer selects a non-nominal next batter or overrides
  a bowler suggestion.
- **FR-020**: The current bowler MUST belong to the bowling side, satisfy
  centralized eligibility rules, obey the consecutive-over restriction where
  applicable, and remain below the applicable legal-over quota.
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
  permitting supported additional runs, and a wide MUST support more than one
  wide run.
- **FR-029**: Delivery total runs MUST always equal runs off the bat plus the
  complete extras breakdown. The persisted total MUST not be an independently
  editable value that can disagree with its components.
- **FR-030**: Balls faced MUST be derived from the delivery outcome and MUST
  remain distinct from attempted deliveries and legal deliveries. Wides,
  no-balls, byes, leg-byes, penalty runs, and supported non-standard outcomes
  MUST use the centralized rule table rather than a Boolean shortcut. In the
  initial supported rules, wides and no-balls do not count as a ball faced,
  while a legal delivery that yields only byes or leg-byes does count; any
  penalty-only or non-standard case follows its explicitly supported rule.
- **FR-031**: Bowler-conceded runs, wides, no-balls, maidens, and legal overs
  MUST be derived using their own scoring rules; byes, leg-byes, and penalty
  runs MUST not be charged to the bowler unless an explicitly supported rule
  says otherwise.

#### Wickets, fielders, and replacement batters

- **FR-032**: Wicket events MUST be explicit records linked to a delivery and
  MUST identify the dismissed batter, dismissal type, team-wicket effect,
  bowler-credit effect, fielder involvement, and any supported additional
  dismissal metadata.
- **FR-033**: The supported dismissal vocabulary MUST include bowled, caught,
  LBW, run out, stumped, hit wicket, retired hurt, and retired out, and SHOULD
  include obstructing the field, hit the ball twice, and timed out where the
  initial rule set can validate them. Known cricket-specific types MUST NOT be
  collapsed into generic `other`.
- **FR-034**: The rule layer MUST distinguish bowler-credited dismissals from
  non-bowler-credited dismissals and team-wicket dismissals from events that do
  not reduce the team's available wickets. Retired hurt MUST be separate from
  retired out and MUST NOT be treated as an ordinary bowler-credited wicket.
  In the initial supported vocabulary, bowled, caught, LBW, stumped, hit wicket,
  run out, and retired out count as team wickets; retired hurt does not. Bowled,
  caught, LBW, stumped, and hit wicket are bowler-credited; run out, retired
  hurt, and retired out are not. Any optional dismissal type MUST declare its
  effects before it can be accepted.
- **FR-035**: Fielder involvement MUST be captured only when required or
  meaningful: catches MUST identify a catcher, stumpings MUST identify the
  wicketkeeper/fielder, and run-outs MUST support all relevant fielders needed
  by the supported rule set. Fielders MUST belong to the fielding side and use
  academy Player references or Match-scoped external participant references as
  appropriate.
- **FR-036**: The data contract MUST support multiple wicket events on one
  delivery. If the initial supported rules intentionally restrict the common
  implementation to one event, the restriction MUST be explicit, validated,
  documented, and fail closed when a second valid event is supplied.
- **FR-037**: After a dismissal requiring replacement, the system MUST resolve
  the delivery and wicket before requiring next-batter selection. The scorer
  MUST be able to select any eligible unused batter; batting order MAY provide
  a suggestion but MUST NOT force the nominal next participant.
- **FR-038**: A retired-hurt batter MUST have a distinct status and MAY return
  when the supported rules permit it. A retired-out batter MUST remain
  ineligible to return unless a correction changes the event.

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
  compatible with scored Matches: a conflicting manual aggregate write MUST be
  rejected or constrained to an explicitly documented legacy/unscored path,
  while existing historical unscored Matches remain readable and supported.
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

- **FR-047**: Delivery correction MUST use an explicit immutable revision,
  supersession, versioned amendment, or void-plus-replacement strategy chosen
  during planning. The selected strategy MUST preserve original provenance,
  identify exactly one active representation for normal scorecards, and avoid
  hard deletion as the default.
- **FR-048**: Reconciliation after a correction MUST rebuild affected innings
  state, totals, extras, wickets, strike, current bowler, legal-ball and over
  state, batting/bowling/fielding summaries, target/chase state, innings
  completion, Match lifecycle, and Match result from active delivery history.
  It MUST not rely on manual counter decrements.
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
- **FR-053**: The same validation, OCC, audit, authorization, and reconstruction
  path MUST be used for future undo operations; undo MUST NOT be an independent
  counter-mutation path.

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

- **FR-058**: Meaningful successful scoring mutations MUST use the existing
  Business Audit conventions, including scoring initialization, innings start,
  innings completion, Match completion, and meaningful delivery correction or
  voiding. Audit records MUST identify the authenticated actor, target, action,
  and safe bounded metadata.
- **FR-059**: Ordinary successful delivery entry, technical recalculation,
  derived-state refresh, background processing, rejected validation, and stale
  conflict MUST not create excessive or misleading Business Audit events. Any
  existing technical conflict logging remains separate from Business Audit.
- **FR-060**: Data Quality MUST be able to identify scoring inconsistencies,
  including delivery-derived totals that disagree with an Innings read model,
  an active batter already dismissed, a bowler on the wrong side, duplicate
  active delivery sequence, invalid Match participant relationships, and
  MatchPerformance rows inconsistent with delivery truth. Data Quality MUST
  report findings without inventing, deleting, or modifying scoring events.
- **FR-061**: Completion and correction flows MUST reuse the existing durable
  background-processing foundation for narrow downstream work such as derived
  performance recomputation, finalized Match summaries, RAG reconciliation,
  and future player-stat or analytics updates. Live scoring state MUST remain
  synchronous and atomic.
- **FR-062**: The system MUST NOT enqueue expensive downstream work after every
  ordinary delivery unless a separately demonstrated requirement justifies it.
  Completion and corrections that change finalized summaries MAY stage bounded,
  idempotent, coalescible work in the same transaction.
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
- **FR-067**: Unit tests MUST cover all new domain and validation logic,
  including innings initialization, internal/external participants, striker and
  non-striker validation, bowler eligibility and defaults, quotas, legal-ball
  progression, all required extras and run cases, balls faced, strike rotation,
  wicket and retirement semantics, fielders, next-batter selection, target and
  completion rules, corrections, and stale OCC writes. `pytest-mock` MUST be
  used where external services or isolated dependencies need mocking, and unit
  tests MUST run without Internet access.
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
  outcomes without building pitch-map, wagon-wheel, or analytics UI.
- **FR-071**: After implementation and verification, the project MUST include
  `docs/match-scoring-domain.md` describing actual implemented authoritative
  architecture, participants, innings, delivery identity, legal/illegal balls,
  runs/extras, wickets/fielders, batting order, bowler selection and quotas,
  strike rotation, target/chase behavior, correction semantics, OCC,
  performance derivation, background/RAG integration, and future scorecard,
  pitch-map, wagon-wheel, and player-stat extension points.

### Verification Requirements

The unit suite must explicitly cover ordinary runs, boundaries, five bat runs,
single and multiple wides, no-balls with additional runs, byes, leg-byes,
penalty runs, total-run reconciliation, balls-faced derivation, strike rotation,
end-of-over behavior, every supported dismissal category, bowler-credit rules,
catches, stumpings, run-outs, retired hurt, retired out, next-batter selection,
target/chase calculation, innings/Match completion, correction/revision, and
stale OCC writes.

The integration suite must include these representative flows:

- A normal limited-overs innings initializes a playing XI, starts, records
  multiple overs and boundaries, rotates strike, changes bowler, and completes.
- An extras-heavy over includes a single wide, a multiple-run wide, a no-ball,
  no-ball plus additional runs, a bye, and a leg-bye, then verifies legal-ball
  count and score.
- A wicket flow records bowled, caught with a fielder, and run-out events,
  selects a replacement batter, and verifies wickets and strike state.
- A chase completes the first innings, derives the target, starts the second,
  tracks runs/balls/wickets remaining, reaches the target, and completes the
  Match automatically.
- A correction changes an earlier delivery and verifies every downstream
  state and derived aggregate is reconciled.
- Two concurrent next-delivery requests use one stale innings version; one
  succeeds, one receives an OCC conflict, and no duplicate active sequence is
  created.
- An external Match uses academy Player records on the academy side and
  match-scoped opposition participants for batting, bowling, and fielding,
  without creating an academy Player or User for opposition identities.

### Quickstart Acceptance Flow

The executable quickstart must demonstrate the following sequence:

1. Apply the scoring-domain migration.
2. Seed two academy Teams and their Players.
3. Create an internal or external Match.
4. Configure the fixed playing XI/match squad.
5. Configure the intended batting order.
6. Start the first innings.
7. Record ordinary runs.
8. Record a boundary.
9. Record a five-run batter outcome.
10. Record a multiple-run wide.
11. Record a no-ball plus additional runs.
12. Record a wicket with fielder involvement.
13. Select the next batter.
14. Complete an over.
15. Verify the next-bowler default suggestion.
16. Continue the innings.
17. Complete the innings.
18. Derive the target.
19. Start the chase.
20. Complete the Match.
21. Verify derived scorecard data.
22. Correct one earlier delivery.
23. Verify scoring state is rebuilt correctly.
24. Verify OCC rejects a stale concurrent write.
25. Verify downstream/background integration remains safe and bounded.

### Protected Read and Mutation Boundary

The protected Match boundary must expose configured participants, innings
state, active delivery history or a bounded delivery view, derived summaries,
completion reasons, target/chase state, and Match result with server-managed
versions. Scoring commands must return clear validation, authorization, not
found, and conflict outcomes consistent with existing protected routes. No
client-supplied role, scope, or external identity metadata may widen access.

### Domain Rule Baseline

The supported scoring subset should use the current [MCC Laws of
Cricket](https://www.lords.org/mcc/the-laws) as its rule baseline. The feature
must document any intentional subset or local academy convention, particularly
for no-ball/wide handling, retirement, multiple wicket events, and format
limits. Unsupported rules remain explicit domain errors or manual-completion
paths rather than inferred behavior.

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
  team-wicket and bowler-credit effects, and fielder relationships.
- **DeliveryFielder**: A link between a wicket event and one or more fielding
  participants, supporting catches, stumpings, and run-outs.
- **InningsReadModel**: Reconciled current innings state and totals retained for
  efficient reads, never independently editable scoring truth.
- **MatchParticipantPerformance**: Derived batting, bowling, and fielding
  summaries for academy and external Match participants; academy summaries
  remain compatible with existing Match performance models.
- **Target/ChaseState**: Derived target, runs required, wickets remaining,
  balls remaining, and target-reached state for later innings.
- **ScoringRulePolicy**: The explicit format/rule capability used to decide
  legal-ball limits, quotas, completion, extras, dismissal, and strike behavior
  without silently applying unsupported rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all required unit, integration, and quickstart scoring cases,
  100% of accepted innings totals, wicket counts, legal-ball counts, extras,
  and participant summaries equal values independently recomputed from active
  delivery history.
- **SC-002**: For an innings containing at least 1,000 attempted deliveries,
  a current-state read returns the persisted reconciled state within one second
  in the project's local integration environment without requiring a full
  history replay on every read.
- **SC-003**: In the required two-writer concurrent-delivery scenario, exactly
  one request succeeds, the other receives the standard conflict response, and
  the innings contains no duplicate active sequence; this result holds for
  every execution of the acceptance test.
- **SC-004**: Correcting an earlier delivery in an innings of at least 100
  attempted deliveries preserves the original correction history and produces
  totals, strike, over state, wickets, chase state, and derived performance
  values identical to a clean replay of the corrected active history.
- **SC-005**: A scorer can complete the 25-step backend quickstart without
  entering aggregate batting, bowling, or fielding figures separately, and the
  resulting internal/external scorecard data is complete enough for a later
  scorecard feature.
- **SC-006**: 100% of opposition participants created by the external-Match
  acceptance flow remain match-scoped only: no opposition User, academy Player,
  Team membership, authentication identity, or career-stat row is created.
- **SC-007**: Every protected scoring mutation made by a Player or an Assistant
  Coach outside current Team scope is rejected, and no unauthorized request
  changes delivery, innings, Match, summary, or participant state.
- **SC-008**: Ordinary delivery entry performs no required provider, queue, or
  embedding work on the synchronous path; completion and material correction
  flows create at most one safely coalesced downstream intent per logical
  derived-summary refresh.
- **SC-009**: The required unit, integration, migration, quickstart, and
  request-level Playwright journeys pass without Internet access, and no
  protected response, audit record, background status, or test log exposes
  external participant account data, credentials, tokens, vectors, or raw
  unrestricted payloads.

## Assumptions

- The existing authenticated User, UserRole, TeamCoach, TeamPlayer, Match,
  performance, OCC, Business Audit, Data Quality, RAG registry, and durable
  background-work foundations remain the integration points for this feature.
- Current Match formats remain `T20`, `one-day`, `test`, and `other`. The
  initial safe policy uses conventional T20 limits of 20 legal overs per
  innings and four overs per bowler. One-day automatic limits require explicit
  Match configuration because the current format enum does not encode an
  innings length; test and other formats default to manual or explicitly
  configured completion until their supported rules are defined.
- A standard innings has a maximum team-wicket count derived from its fixed
  eligible batting participants, with retirement semantics applied separately.
  Local formats may configure a different valid limit before scoring starts.
- The default bowler suggestion compares normalized display names
  case-insensitively and uses stable participant ID as a deterministic tie-break
  when names match.
- For a fixed-over chase, the target is the relevant prior completed score plus
  one. More advanced multi-day, follow-on, forfeiture, and interruption rules
  are deferred while the Innings model remains extensible.
- A retired-hurt participant can return only through an explicit supported
  re-entry action and only at a legal state boundary; retirement does not cause
  an automatic identity swap without a scorer decision.
- Existing manually entered performance rows for Matches without delivery truth
  remain readable. Matches that opt into authoritative delivery scoring use
  delivery-derived summaries and cannot accept conflicting aggregate truth.
- Match-scoped external participants are retained only for the Match's scoring,
  scorecard, and correction history. They are never promoted into academy
  identity, authorization, or career-stat domains.
- No new scorer UI is needed in this increment. Any future scorer UI will use
  the existing Product and Design system and will add its own responsive,
  keyboard, loading, empty, error, success, and conflict acceptance coverage.
- The documentation file is written after implementation and verification so it
  describes actual behavior rather than aspirational design.
