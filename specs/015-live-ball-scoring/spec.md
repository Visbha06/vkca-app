# Feature Specification: Live Ball-by-Ball Match Entry

**Feature Branch**: `015-live-ball-scoring`

**Created**: 2026-10-11

**Status**: Draft

**Input**: User description: "Feature 015 — Live Ball-by-Ball Match Entry"

## Scope and Domain Boundary

Feature 015 gives coaches an operational web workflow for creating or finding a
Match, preparing it, and scoring it, then lets permitted users review its
scoring information. Match creation uses the existing Match domain and
creation boundary; it does not create another Match store or scoring record.
Feature 014 remains the sole authority for participants, capability rules,
delivery facts, derived totals, strike and over progression, bowler
eligibility, innings and Match lifecycle, results, corrections, authorization,
and concurrency. The interface presents those decisions, submits observed
scoring facts through the existing protected scoring boundary, and renders
committed projections.

The workflow covers internal Matches with two academy Teams and external
Matches with one academy Team and Match-scoped opposition identities. It adds a
lightweight frontend path into the existing Match creation workflow, but no
parallel Match domain, a frontend cricket rules engine, a second scoring
cache, or a separate scorecard product. A legacy Match whose scoring authority
is still `legacy_aggregate` must be visibly distinguished from a Match
configured for delivery-history scoring. The interface must not fabricate ball
history for a legacy Match or imply that it is ready for live scoring until the
existing configuration workflow accepts it.

The current Match-list read returns Match records without applying the team
scope enforced for individual scoring reads. The discovery workflow must close
that authorization gap in the existing Match listing/read boundary before it
shows records to scoped Assistant Coaches or Players. Any such change is
limited to authorized discovery of existing Matches and the information
needed to choose an allowed action; it does not add Match storage or scoring
rules.

## Clarifications

### Session 2026-10-11

- Q: Should Feature 015 include Match creation in the Matches experience? → A:
  Yes. Coaches can create an internal or external Match through a lightweight
  form using the existing Match domain and creation boundary, then continue
  directly to participant and batting-order configuration.
- Q: Should read-only viewers receive automatic updates during an active
  Match? → A: Yes. Refresh authoritative scoring information periodically
  while an authorized read-only Match view is visible; stop when it is hidden,
  left, terminal, or unauthorized, and do not add WebSockets, public streaming,
  or offline synchronization.

## User Scenarios & Testing

### User Story 1 - Create, Find, and Prepare a Match (Priority: P1)

A Head Coach or appropriately assigned Assistant Coach needs to create a new
internal or external Match, or find an existing one, then prepare its fixed
sides, participants, format policy, and intended batting order before the
first innings begins.

**Why this priority**: Scoring depends on a configured Match with stable
participant identities. Coaches must be able to prepare both internal and
external fixtures without creating a parallel Match record.

**Independent Test**: From Matches, create an internal Match and an external
Match, verify each saved Match opens its pre-match configuration workflow,
choose eligible participants and batting order, and confirm each becomes ready
for innings initialization. Also open an existing Match and prepare it through
the same configuration workflow.

**Acceptance Scenarios**:

1. **Given** an authenticated user with permission to read a Match, **When**
   the user opens Matches, **Then** scheduled, in-progress, and terminal
   Matches are grouped or filterable by lifecycle and show the teams or
   opponent, date, format, venue, and current state.
2. **Given** a Head Coach or Assistant Coach, **When** the user opens Matches,
   **Then** a Create Match action is available and opens a lightweight form.
3. **Given** the coach chooses Internal in the creation form, **When** the
   coach selects two distinct academy Teams and supplies the required Match
   details, **Then** the form accepts an internal Match and rejects selecting
   the same Team on both sides.
4. **Given** the coach chooses External in the creation form, **When** the
   coach selects one academy Team, its home/away position, and enters the
   external opponent name and required Match details, **Then** the form accepts
   the external Match without creating an academy identity for the opponent.
5. **Given** a creation form is submitted, **When** required details are
   missing or the existing Match service rejects the request, **Then** the
   error is associated with the relevant fields or shown clearly and the coach
   can correct and resubmit without losing valid draft input.
6. **Given** a new Match is created successfully, **When** the create response
   is received, **Then** the coach is directed to pre-match configuration to
   select participants and batting order before starting an innings.
7. **Given** an Assistant Coach or Player, **When** Matches are listed,
   **Then** only Matches in that user's current Team scope are discoverable;
   an external opponent does not widen that scope.
8. **Given** a scheduled internal Match with two academy Teams, **When** an
   authorized coach configures it, **Then** each side offers eligible roster
   participants from its own Team and rejects duplicate or cross-Team
   selections.
9. **Given** a scheduled external Match, **When** an authorized coach
   configures it, **Then** the academy side uses eligible academy Players and
   the opposition side accepts minimal participant names without creating
   academy Player, User, or Team membership records.
10. **Given** either side has selected participants, **When** the coach sets
   intended batting order and confirms configuration, **Then** each selected
   participant has a distinct position, the intended order is visible, and the
   fixed identities remain unchanged after configuration is locked.
11. **Given** a Match format, **When** a coach prepares its scoring policy,
   **Then** only the current Feature 014 capability and permitted settings are
   offered: T20 uses two innings of 120 legal balls, six-ball overs, and a
   24-legal-ball bowler quota; one-day accepts a positive innings limit
   divisible by 30 and displays the backend-derived one-fifth quota; Test
   follows its four-innings sequence without a bowler quota or consecutive
   overs; and Other requires its explicit supported policy.
12. **Given** a legacy or incomplete Match, **When** a coach opens it, **Then**
   the interface identifies its scoring authority/readiness and offers only
   actions permitted by the current Match state and backend response.

### User Story 2 - Start or Resume an Innings and Score Routine Deliveries (Priority: P1)

A coach needs to begin the next permitted innings or resume the active one,
see the current scoring state at a glance, and record ordinary batter runs
quickly during play.

**Why this priority**: Fast, dependable entry of routine deliveries is the
central live-scoring task.

**Independent Test**: Configure an existing Match, select distinct opening
batters and an eligible bowler, start an innings, record ordinary outcomes,
and verify that the displayed score, participants, figures, and history match
the committed innings projection.

**Acceptance Scenarios**:

1. **Given** a configured Match with a next permitted innings, **When** an
   authorized coach starts it, **Then** the interface identifies batting and
   fielding sides, the innings sequence position, available target information,
   and eligible opening participants.
2. **Given** the opening selections are incomplete, duplicate, or ineligible,
   **When** the coach submits the start action, **Then** clear validation is
   shown and the innings does not start.
3. **Given** innings initialization succeeds, **When** the response is
   received, **Then** the coach is taken directly to live scoring and the
   current striker, non-striker, bowler, score, and innings state come from the
   committed response.
4. **Given** an active innings after reload or navigation, **When** the coach
   returns to the Match, **Then** the interface restores the current backend
   state and permits continuation only when its blocking state allows it.
5. **Given** an active innings, **When** the scorer selects 0, 1, 2, 3, 4, 5,
   or 6 runs off the bat, **Then** the selected observed outcome can be
   submitted without a routine confirmation step; a five-run batter outcome
   remains distinct from a boundary.
6. **Given** the backend accepts an ordinary delivery, **When** the updated
   state is displayed, **Then** totals, wickets, legal-ball progress, strike,
   bowler figures, current over, and recent history reflect the committed
   backend projection.

### User Story 3 - Record Extras, Wickets, and Resolve Scoring Blocks (Priority: P1)

A coach needs to record less common delivery outcomes and dismissals clearly,
then follow the backend's required next-batter, retirement, or bowler action
before scoring resumes.

**Why this priority**: Cricket scoring regularly includes extras, dismissals,
and over changes; incorrect entry or an unclear blocker stops a live innings.

**Independent Test**: Record a multi-run wide or permitted no-ball combination,
a fielder-assisted wicket, an eligible replacement batter, and a completed
over; select a recommended or alternative eligible bowler and verify the
innings unblocks only after the required action succeeds.

**Acceptance Scenarios**:

1. **Given** the scorer opens extra-delivery controls, **When** the scorer
   enters wides, no-balls, byes, leg-byes, penalty runs, or a supported
   combination, **Then** batter runs and each extra component have distinct
   labels and the intended components are reviewable before submission.
2. **Given** a five-run bat outcome or multiple-run extra, **When** it is
   entered, **Then** the displayed input preserves the entered component and
   does not silently relabel it as a boundary or obscure mandatory extra
   penalties.
3. **Given** a wicket is entered, **When** the coach selects a dismissal,
   dismissed batter, and any required fielder roles, **Then** only dismissal
   and fielding shapes supported by the locked capability are selectable,
   caught-and-bowled remains distinct where supported, and a run-out can
   include multiple fielders when permitted.
4. **Given** a dismissal requires a replacement, **When** the backend reports
   `awaiting_next_batter`, **Then** delivery controls are blocked and the
   interface offers eligible unused batters, using batting order as a
   suggestion without excluding another valid participant.
5. **Given** a batter retires hurt, **When** an authorized coach enters a
   reason and confirms, **Then** the interface distinguishes retired hurt from
   retired out, reports the resulting vacancy, and offers return only when the
   backend permits it.
6. **Given** legal-ball progression completes an over, **When** the backend
   reports `awaiting_next_bowler`, **Then** the interface retrieves the
   backend's recommendation and eligibility details, lets the coach choose
   another eligible bowler, and resumes entry only after selection succeeds.
7. **Given** wides or no-balls occur within an over, **When** the over display
   updates, **Then** they remain visible in history without advancing legal-ball
   progress; eligibility and quota restrictions are shown from backend state.
8. **Given** no eligible bowler remains or another required participant is
   unavailable, **When** the innings is blocked, **Then** the reason and
   available recovery action are stated in text and no invalid delivery can be
   submitted.

### User Story 4 - Review and Correct a Recorded Delivery (Priority: P1)

A coach needs to inspect recent or older deliveries, find an entry mistake,
and correct it with a reason while preserving the scoring history and all
derived effects.

**Why this priority**: Corrections are part of routine live scoring, and
untracked edits can invalidate later state and the final scorecard.

**Independent Test**: Record several deliveries, browse history, correct an
earlier delivery with a reason, and verify that the displayed active history,
innings, Match, scorecard, and correction provenance agree with the backend.

**Acceptance Scenarios**:

1. **Given** an authorized scorer opens delivery history, **When** deliveries
   are shown, **Then** they appear in attempted scoring order, group by over
   where useful, show runs, extras, wicket and relevant participant details,
   and preserve ordering for illegal deliveries at the same legal-ball
   position.
2. **Given** a long innings, **When** the scorer requests older history,
   **Then** the interface loads bounded pages in order and does not present
   superseded revisions as active scoring events.
3. **Given** a correctable delivery, **When** the coach chooses correction,
   **Then** its recorded facts are prepopulated, a correction reason is
   required, and submission replaces the active facts through the supported
   immutable correction workflow.
4. **Given** a correction commits, **When** it changes strike, over progress,
   target, or completion, **Then** every affected view refreshes from the
   returned authoritative state and preserves revision provenance.
5. **Given** correction replay returns `reconciliation_required`, **When** the
   interface refreshes, **Then** normal delivery entry and completion are
   blocked, the reason is explained, and only recovery actions supported by
   the existing correction workflow are offered.
6. **Given** a delivery is already recorded, **When** a coach views it,
   **Then** the interface offers correction and does not hard-delete it or
   provide a counter-decrement undo action.

### User Story 5 - Complete the Match and Review Its Scorecard (Priority: P1)

A coach needs to finish permitted innings and Match actions, follow limited-
overs chase progress, and review the resulting figures and derived result.

**Why this priority**: The workflow must take a Match from preparation through
its authoritative terminal result and provide a useful operational record.

**Independent Test**: Complete a supported internal or external Match using
its permitted completion path, then switch between innings and verify the
scorecard, target information, and final result against the Match projection.

**Acceptance Scenarios**:

1. **Given** an innings completes automatically or through a permitted
   explicit action, **When** the backend confirms completion, **Then** the
   interface shows the completion reason and summary and offers the next
   permitted innings when one remains.
2. **Given** a limited-overs chase is active, **When** the coach views scoring,
   **Then** target, runs required, wickets remaining, and balls remaining are
   shown when provided by the backend, and target completion is reflected as
   soon as confirmed.
3. **Given** the Match reaches a terminal state, **When** the coach views it,
   **Then** the derived result and lifecycle are prominent, normal scoring
   controls are unavailable, and the Match remains available for review.
4. **Given** explicit innings completion, Match completion, or abandonment is
   not permitted by the locked capability or current lifecycle, **When** a
   user opens the relevant view, **Then** the action is unavailable; sensitive
   permitted completion or abandonment requires a clear confirmation.
5. **Given** a coach opens the operational scorecard, **When** innings are
   selected, **Then** each selected innings shows totals, extras, individual
   batting and bowling figures, available fielding and wicket details,
   fall-of-wickets, overs, target or chase state, and the final result when
   applicable.
6. **Given** a legacy aggregate Match is viewed, **When** its scorecard is
   shown, **Then** existing aggregate figures may be displayed with the legacy
   authority clearly identified and no ball history is invented.

### User Story 6 - Review a Match as a Player or Authorized Viewer (Priority: P2)

A Player or other authorized read-only viewer needs access to permitted Match
details, innings, delivery history, and scorecard information for the current
Team scope, including automatic updates while viewing an active Match.

**Why this priority**: Players benefit from seeing Match performance while
coaches retain control of configuration and scoring.

**Independent Test**: Sign in as a Player assigned to a participating Team,
open a permitted in-progress Match in a read-only view, verify that committed
score and innings updates appear periodically without a reload, then verify
polling stops on navigation, terminal state, or loss of authorization. Confirm
all configuration and mutation controls are absent and protected mutations are
rejected.

**Acceptance Scenarios**:

1. **Given** a Player with current Team scope for a Match, **When** the Player
   opens it, **Then** Match, innings, history, and scorecard information are
   readable.
2. **Given** the Player is viewing a Match, **When** the Player views
   configuration, delivery, correction, retirement, completion, or abandonment
   actions, **Then** those mutations are not available and cannot be performed
   through the protected service boundary.
3. **Given** the Player's Team assignment changes while the Match is open,
   **When** a protected read is refreshed, **Then** current authorization is
   enforced and the interface explains loss of access without exposing further
   Match information.
4. **Given** a visible, in-progress Match in a permitted read-only view,
   **When** another scorer commits a delivery, **Then** authoritative score,
   innings state, and relevant scorecard information refresh within the
   specified polling interval without a manual reload or disruptive loss of
   reading position.
5. **Given** the read-only Match view is hidden, left, becomes terminal, or
   receives an authorization failure, **When** the condition is detected,
   **Then** automatic refresh stops; authorization loss also removes protected
   Match information from the view.
6. **Given** an automatic refresh is still pending or a transient read fails,
   **When** another refresh would otherwise be due, **Then** no overlapping
   duplicate request is started, the last known committed information remains
   stable with its freshness state communicated, and retry follows the normal
   polling cadence.

### Edge Cases

- A Match has an unknown, unauthorized, or stale list/detail state; the page
  shows an access-denied or unavailable state without leaking other Match
  information.
- A coach cancels Match creation or the existing creation service rejects its
  request; no partial Match is treated as created, and valid form values remain
  available for correction where the page is still authorized.
- A legacy Match has aggregate figures but no delivery-history authority; the
  interface does not show a fabricated innings, delivery sequence, or live
  scoring action.
- An existing Match's Team roster changes after configuration; the configured
  Match participants and batting order remain fixed.
- A Match uses an unsupported format option or an invalid one-day limit; the
  invalid choice is rejected with a useful explanation and no scoring policy
  is silently substituted.
- A delivery combines unsupported extra components, has invalid run values,
  or contains a second wicket event; the scorer receives validation feedback
  and the committed score remains unchanged.
- A batter and non-striker selection are the same participant or one belongs
  to the wrong side; innings start is rejected without creating an innings.
- A wicket dismisses a participant other than an eligible active batter, or
  supplies an invalid fielder side, role, or count; the delivery is rejected.
- A wicket leaves no eligible unused batter; the interface explains the
  backend blocker and prevents another delivery.
- A retired-hurt participant is selected to return when the current innings
  state or capability disallows it; return remains unavailable and no
  participation state changes.
- The bowler has reached quota, has just bowled the preceding over where
  prohibited, or no eligible alternative remains; the interface shows the
  backend restriction and does not invent an override.
- Several wides or no-balls share a legal-ball position; their attempted order
  remains stable in the over and history views.
- A correction changes a prior dismissal, target, or terminal result, or makes
  later transitions incompatible; all projections refresh and normal scoring
  stays blocked when reconciliation is required.
- A completed Match is corrected through the supported correction path; the
  UI follows the newly returned completed or in-progress state and never
  reopens it through ordinary scoring.
- Two scorers submit against the same Match or innings version; the stale
  submission receives a conflict, refreshes authoritative state, and does not
  silently overwrite the other scorer.
- A network timeout occurs after a delivery may have committed; the interface
  does not blindly resubmit a non-idempotent delivery and instead retrieves
  current Match and innings state before offering the next action.
- Authentication expires or permissions change during scoring; mutation
  controls are removed or disabled, the user receives an actionable message,
  and backend authorization remains decisive.
- A read-only poll fails temporarily; the last committed view remains visible
  with an indication that it may be stale, no immediate retry loop starts, and
  the next scheduled refresh can recover it.
- A read-only view becomes hidden, is left, or becomes terminal while polling
  is pending; no further periodic requests are started after the pending
  request resolves, and terminal state ends polling.
- A screen is narrowed to 320px or contains long Team, opponent, venue, or
  participant names; essential scoring controls and text remain usable without
  horizontal overflow.

## Requirements

### Functional Requirements

#### Match discovery and preparation

- **FR-001**: The system MUST provide an authenticated Matches destination
  integrated with the existing application navigation and route-protection
  conventions. Head Coaches and Assistant Coaches MUST have a Create Match
  action; Players MUST NOT have Match-creation controls.
- **FR-002**: The Matches experience MUST show or filter existing and newly
  created Matches by
  scheduled/upcoming, in-progress, and terminal lifecycle, including a clear
  abandoned state where applicable. Each entry MUST identify its sides or
  opponent, Match date, format, venue, lifecycle, and available next action.
- **FR-003**: Match discovery MUST return only Matches the current authenticated
  user may read under current Team scope. The scope MUST be checked using
  current backend identity and assignments; an external participant or
  client-supplied role MUST NOT widen access.
- **FR-004**: From Matches, an authorized coach MUST be able to open a
  lightweight Match-creation form and create a Match through the existing
  Match domain and Match creation API. The form MUST collect the required date,
  format, venue, and participant-type details; reuse existing academy Team
  selection where available; use the existing initial `Scheduled` result
  value where required by the creation contract; validate required inputs; and
  preserve draft values after recoverable errors. After successful creation,
  it MUST direct the coach to the existing pre-match configuration flow to
  select participants and batting order before innings can start. It MUST NOT
  introduce a parallel Match domain or storage workflow or collect participant
  performance figures or final Match results.
- **FR-005**: For an internal Match, the creation form MUST allow selection of
  two distinct existing academy Teams. During pre-match configuration, the
  system MUST present eligible academy roster participants for their assigned
  sides and prevent duplicate participants or invalid cross-Team selection.
- **FR-006**: For an external Match, the creation form MUST allow selection of
  one academy Team, its home/away side, and a manually entered opponent name.
  During pre-match configuration, opposition participants MUST be entered as
  minimal Match-scoped scoring identities. The system MUST NOT create academy
  Players, Users, accounts, or Team memberships for the opponent or its
  participants.
- **FR-007**: The system MUST let a coach define the intended batting order
  before locking Match configuration and MUST distinguish intended order from
  actual batting sequence. During play, a coach MUST be able to select any
  eligible unused batter the backend permits; intended order may inform
  suggestions but MUST NOT exclude another valid participant.
- **FR-008**: The system MUST present only Match formats, policies, and settings
  supported by the existing scoring capability. It MUST explain consequential
  restrictions, preserve the backend-resolved immutable capability, and never
  invent DLS, Super Over, follow-on, interruption, or unsupported Test/Other
  behavior. T20 MUST use its existing 120 legal-ball innings and 24-ball
  bowler quota; one-day MUST accept only a positive legal-ball limit divisible
  by 30 and show the backend-derived one-fifth quota; Test MUST follow its
  four-innings sequence; and Other MUST require its explicit supported policy.
- **FR-009**: The system MUST distinguish `legacy_aggregate` Matches from
  `delivery_history` Matches and use backend lifecycle, configured capability,
  and current state to determine whether to configure, start, resume, or view a
  Match. It MUST NOT fabricate ball history for legacy records.

#### Innings and live scoring

- **FR-010**: The system MUST identify the next innings from the configured
  backend sequence and MUST NOT assume that every Match has exactly two
  innings.
- **FR-011**: Before starting an innings, the system MUST show the batting and
  fielding sides and allow selection of two distinct eligible opening batters
  and an eligible opening bowler. It MUST show target information when the
  backend supplies it and explain rejected selections.
- **FR-012**: After successful innings initialization, the system MUST take a
  scorer directly to the active scoring view and render the committed innings
  state.
- **FR-013**: The live scoring view MUST prominently display the Match sides,
  innings, runs, wickets, legal-ball and over progress, striker,
  non-striker, current bowler, relevant current figures, current over,
  recent delivery history, and backend-provided target/chase information.
- **FR-014**: The system MUST provide direct entry controls for 0 through 6
  bat runs, including a distinct five-run outcome, and an accessible way to
  enter other non-negative bat-run totals accepted by the backend. Routine
  legal deliveries MUST NOT require a confirmation step.
- **FR-015**: The system MUST provide clearly separated entry for wides,
  no-balls, byes, leg-byes, penalty runs, additional run quantities, and
  supported combinations. Before submission, complex entry MUST identify each
  entered component in plain language. Any preview MUST be clearly
  provisional; official totals and legality MUST come from the backend.
- **FR-016**: The system MUST offer only wicket types supported by the locked
  capability, collect the dismissed batter and required fielder identities and
  roles, allow multiple fielders for supported run-outs, and enforce the
  existing one-wicket-event-per-delivery limitation through the scoring
  boundary.
- **FR-017**: The system MUST submit only observed delivery facts and MUST
  display committed results after the scoring service confirms them. It MUST
  prevent repeated submission while a request is pending and refresh the
  innings projection, scorecard, and recent history after success.
- **FR-018**: The system MUST use the backend's canonical `blocking_state` to
  determine the next permitted action. If the state is `awaiting_next_batter`,
  it MUST block delivery entry and present eligible replacement choices until
  a valid pair is restored.
- **FR-019**: The system MUST support the existing retired-hurt and
  retired-hurt-return transitions with a reason and suitable confirmation,
  show resulting participation state, and distinguish retired hurt from
  retired out.
- **FR-020**: The system MUST use backend legal-ball progress and
  `awaiting_next_bowler` state to present the suggested next bowler and
  eligibility restrictions, accept another eligible bowler, and resume scoring
  only after a successful selection. It MUST NOT calculate a competing quota
  or eligibility result.
- **FR-021**: If the backend reports no eligible bowler, missing active batter,
  completed innings, terminal Match, or another blocking condition, the system
  MUST show the reason and only recovery actions supported by the existing
  scoring boundary.

#### History, corrections, and completion

- **FR-022**: The system MUST display active delivery history in chronological
  attempted order, group it by over where useful, preserve multiple attempts at
  the same legal-ball position, and identify runs, extras, wickets, and
  relevant participants. Older history MUST be browsable in bounded portions.
- **FR-023**: The system MUST distinguish active delivery facts from
  correction provenance and MUST NOT display superseded revisions as
  additional active deliveries.
- **FR-024**: An authorized scorer MUST be able to correct an eligible
  delivery through the existing immutable correction workflow. The correction
  view MUST be prepopulated with current facts, require a reason, and support
  the applicable run, extras, wicket, and fielder changes.
- **FR-025**: After correction, the system MUST refresh all affected innings,
  Match, scorecard, and history views. It MUST reflect any changed strike,
  over progression, target, completion, or Match result. When the backend
  reports `reconciliation_required`, it MUST explain the block, prevent normal
  scoring, and expose only supported correction recovery actions.
- **FR-026**: The system MUST reflect automatic innings and Match completion
  from backend state, show completion reason and summary, and offer explicit
  completion only where the capability and lifecycle permit it. Sensitive
  permitted completion or abandonment actions MUST require confirmation.
- **FR-027**: The system MUST show target, runs required, wickets remaining,
  balls remaining, and chase completion when supplied by the backend. It MUST
  display the authoritative derived Match result and leave terminal Matches
  available for read-only review.
- **FR-028**: The operational scorecard MUST allow switching between current
  and completed innings and show authoritative totals, extras, batting,
  bowling, available fielding and wicket information, fall of wickets, overs,
  chase information, and final result.

#### Access, reliability, and experience quality

- **FR-029**: Head Coaches MUST have all permitted Match configuration,
  scoring, correction, completion, and review actions. Assistant Coaches MUST
  be limited to their current Team assignment scope. Players MUST have
  permitted read-only access. Client role checks MUST be treated as
  presentation only; the backend MUST authorize every protected read and
  mutation.
- **FR-030**: Every scoring mutation MUST use the relevant current Match,
  innings, and delivery revision versions required by the existing contract.
  On an HTTP 409 conflict, the interface MUST retrieve authoritative state,
  explain that another update made the submission stale, and prevent silently
  overwriting that update.
- **FR-031**: The system MUST distinguish draft input, pending submission,
  confirmed scoring, and uncertain network outcome. It MUST NOT blindly retry a
  delivery after an uncertain response; it MUST refresh authoritative state
  before offering another scoring action.
- **FR-032**: The system MUST restore the latest committed scoring state after
  page refresh or navigation, present useful loading, empty, request-error,
  access-denied, success, and recovery states, and handle expired
  authentication without retaining active mutation controls.
- **FR-033**: Match discovery, configuration, scoring, history, dialogs, and
  scorecard MUST remain usable from 320px to 2560px, prioritize tablet and
  mobile touch workflows, retain essential controls without horizontal
  overflow, and continue to support desktop review.
- **FR-034**: All controls and state changes MUST meet the project's WCAG 2.1
  AA target: keyboard operation, semantic labels, visible focus, deliberate
  dialog and route focus handling, accessible notifications, non-color-only
  status communication, readable contrast, and reduced-motion support.
- **FR-035**: Automated verification MUST cover lifecycle actions, internal
  and external Match creation/configuration, batting order, innings
  initialization, standard and uncommon runs, supported extras, wickets and
  fielders, next batter, retirement, bowler changes, history paging,
  correction and reconciliation, chase and completion, role-aware access,
  read-only polling, conflicts, failures, and duplicate submission prevention.
- **FR-036**: An isolated Playwright end-to-end scoring journey MUST start on
  Matches, create an internal Match, configure sides and order, start an
  innings, record ordinary and uncommon runs, a multi-run extra and a
  fielder-assisted wicket, resolve the next batter, complete an over and
  select a bowler, correct a prior delivery, complete an innings, start the
  next innings, chase a target, complete the Match, and verify the derived
  result and scorecard. End-to-end acceptance coverage MUST also open and
  configure an existing Match, create/configure an external Match, and verify
  Player read-only polling and authorization behavior.
- **FR-037**: Any backend change required by Feature 015 MUST be narrowly
  limited to existing Match/scoring boundaries, preserve Feature 014 scoring
  invariants and optimistic concurrency, and include the unit or integration
  coverage required for that change. Backend scope MUST follow the repository's
  quickstart and test-isolation conventions, and any schema change MUST include
  its required migration. No independently editable frontend scoring data may
  be introduced.
- **FR-038**: The feature MUST pass the applicable repository quality gates
  and include a realistic browser scoring journey with representative internal
  and external Match coverage.
- **FR-039**: After implementation and verification, feature documentation MUST
  describe the verified scoring workflow, its interaction with Feature 014,
  configuration, delivery and wicket entry, bowler changes, corrections,
  completion, recovery behavior, contract changes, known limitations, and
  future extension points.
- **FR-040**: Authorized users in a read-only Match or scorecard view MUST
  receive periodic authoritative score, innings-state, and relevant scorecard
  refreshes while the Match is in progress and the browser view is visible and
  current. The initial refresh interval MUST be 10 seconds. Polling MUST stop
  when the Match is terminal, the view is hidden or left, or authorization is
  lost. It MUST NOT run on the active delivery-entry view. Automatic refreshes
  MUST NOT overlap or duplicate a pending refresh. Temporary read failures
  MUST preserve the last committed view, communicate its freshness, and wait
  for the next scheduled interval. This MUST NOT add WebSockets, public
  live-score streaming, or offline synchronization.

### Key Entities

- **Match**: An existing academy cricket event with date, format, venue,
  participating sides, lifecycle, scoring authority, and derived result.
- **Match Side**: One of the stable home/away sides, represented by an academy
  Team or an external opponent.
- **Match Participant**: A fixed scoring identity for a Match. Academy
  participants refer to existing Players; external participants carry only
  Match-scoped display identity.
- **Intended Batting Order**: The coach's configured order for eligible
  participants on a side; it informs recommendations while actual participation
  follows committed innings events.
- **Innings**: One position in the Match's configured innings sequence, with
  batting and fielding sides, current participants, lifecycle, target when
  applicable, authoritative totals, and blocking state.
- **Delivery and Active Revision**: An attempted ball's observed batter,
  bowler, run, extra, and optional wicket facts; only its active revision
  contributes to current scoring projections.
- **Wicket and Fielding Detail**: A supported dismissal and its dismissed
  batter and ordered fielding participants/roles when required.
- **Participation Transition**: A backend-recorded change such as next batter,
  retired hurt, or retired-hurt return that affects who may take part next.
- **Blocking State**: The backend-derived reason the Match or innings cannot
  accept the next ordinary scoring operation.
- **Scorecard Projection**: The backend-provided current and completed innings
  totals, participant figures, extras, wickets, overs, target/chase state, and
  Match result shown for operational review.
- **Correction Provenance**: The preserved reason, actor, revision, and
  supersession details associated with a corrected delivery.

## Success Criteria

### Measurable Outcomes

- **SC-001**: In the required end-to-end scoring journey, every displayed
  committed total, wicket count, over state, participant figure, target state,
  and final result matches the authoritative Match and scorecard state after
  each accepted operation.
- **SC-002**: Once an innings is active, a scorer can submit a routine 0–6
  batter-run outcome with one scoring choice and no additional confirmation;
  pending state prevents a second submission until the first request resolves.
- **SC-003**: 100% of stale-write acceptance cases show a conflict explanation
  and refreshed authoritative state, with no silent overwrite or duplicate
  active delivery sequence.
- **SC-004**: A coach can start from Matches, create an internal or external
  Match, configure its participants and batting order, and score a supported
  Match through its derived terminal result without manual API requests,
  database edits, or separate score-entry tools. The full internal scoring
  journey and representative existing and external Match paths pass.
- **SC-005**: Head Coach, in-scope Assistant Coach, and in-scope Player
  acceptance cases produce the permitted actions for each role; out-of-scope
  Match reads and Player mutations are rejected by the protected service
  boundary.
- **SC-006**: At viewport widths of 320px, 768px, and 2560px, users can
  reach the active score, current participants, required next action, and
  primary delivery controls without horizontal page scrolling.
- **SC-007**: The feature's keyboard and assistive-technology acceptance
  review passes all applicable WCAG 2.1 AA requirements in FR-034.
- **SC-008**: In an authorized, visible, read-only view of an in-progress
  Match, committed score and innings changes appear within 10 seconds. No more
  than one automatic refresh is active at a time, and polling stops after the
  view is hidden or left, the Match is terminal, or authorization is lost.

## Assumptions

- A coach can begin with an existing Match or create a new Match from the
  Matches page. The creation form reuses existing Match fields and uses the
  accepted `Scheduled` initial result value when the current creation contract
  requires a result string.
- Feature 014's protected scoring and read contract is available and remains
  the source of accepted formats, transitions, eligibility, projections,
  results, and correction behavior.
- A Match can be configured only when the existing backend lifecycle and
  scoring authority permit it. The interface follows the backend response
  when a legacy or incomplete record cannot be configured.
- The configured participant set may contain the playing XI or another squad
  size permitted by Feature 014; the frontend does not introduce a separate
  participant-count rule.
- A working authenticated network connection is required for live scoring.
  Offline-first entry, automatic replay of uncertain writes, and public live
  broadcasting are outside this increment.
- Read-only polling uses an initial 10-second interval while the Match view is
  visible and in progress. Polling remains inactive on the delivery-entry
  view.
- Feature 016 owns pitch-map and wagon-wheel entry. Feature 017 owns a polished
  standalone scorecard. Advanced analytics, career statistics, and unsupported
  cricket rules remain future work.
