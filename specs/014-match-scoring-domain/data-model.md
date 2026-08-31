# Data Model: Match Scoring Domain

## Modeling principles

The existing Match row remains the aggregate anchor. Scoring configuration, innings, participants, delivery attempts, and projections are Match-owned. Delivery history and correction revisions are authoritative; every scorecard, performance summary, target, result, and over state is derived or materialized from that history. Match lifecycle owns abandonment, Innings lifecycle owns reconciliation, and the serialized `blocking_state` is derived read-model output rather than an independent scoring input.

Match format identifiers use the canonical values defined in `spec.md`: `T20`,
`one-day`, `test`, and `other`. The `MatchFormat` domain value, API `format`,
scoring-policy `policy_code`/`capability_profile`, and persisted Match format
are the same value; display labels do not create aliases.

All new mutable roots use the repository UUID, created/updated timestamp, and integer version conventions. Foreign keys use the existing deletion policy for historical data: a configured Match, participant, innings, or delivery is retained and cannot be deleted through ordinary application commands. Database cascades are used only for migration teardown or child records whose parent is being removed before the feature is configured.

## Existing Match extension

Extend Match with:

| Field | Type | Rules |
|---|---|---|
| lifecycle_state | enum | scheduled, in_progress, completed, abandoned, or the transaction-local `correction_reprocessing` phase; the phase is never committed as a standalone public state; legacy rows default to scheduled or a compatible legacy state |
| scoring_authority | enum | `legacy_aggregate` for an unconfigured legacy Match; scoring configuration locks `delivery_history` before the first scoring write, and the authority cannot change afterward |
| result_code | enum | Derived pending, win_by_runs, win_by_wickets, tie, draw, no_result, declared, or manual; `no_result` is emitted only when lifecycle is `abandoned` and is never an independent client input |
| result_details | bounded JSON object | Derived structured result; no raw delivery payload |
| configured_at | timestamp nullable | Set when fixed sides/participants and policy are locked |
| blocking_state | derived response object | Match-level serialization of the canonical Innings blocker or terminal Match state; not independently persisted or writable |

Retain match_date, format, participant_type, home_team_id, away_team_id, external_opponent_name, venue, result, timestamps, and version for compatibility. Existing scalar update behavior is limited once scoring_authority is delivery_history: only explicitly supported lifecycle/result commands may change scoring-owned state.

## Match sides

Table: match_sides

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| match_id | UUID | Required Match foreign key |
| side_code | enum | home or away; unique within Match |
| side_kind | enum | academy or external |
| team_id | UUID nullable | Required for academy; null for external |
| display_name_snapshot | string | Required historical label |
| version | integer | OCC for side configuration if needed |

Constraints:

- A Match has exactly two sides once configured.
- Internal Matches have two academy sides with distinct Team IDs.
- External Matches have one academy side and one external side; the external side has no Team ID.
- An external side's display name is not an account or authorization identity.

## Scoring policies

Table: match_scoring_policies

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| match_id | UUID | One locked active policy per Match |
| policy_code | enum/string | `T20`, `one-day`, `test`, `other` |
| policy_version | positive integer | Historical policy revision |
| capability_profile | enum | `T20`, `one-day`, `test`, `other` |
| capability_version | positive integer | Version of the normative capability matrix |
| innings_sequence | ordered side-code list | `[A, B]` for T20/one-day, `[A, B, A, B]` for test, explicit for other |
| innings_per_side | positive integer | 1 for T20/one-day, 2 for test, explicit for other |
| legal_ball_limit | positive integer nullable | 120 for T20; required positive multiple of 30 for one-day; null for test; explicit/null for other |
| over_length_legal_balls | positive integer | 6 for T20, one-day, and test; explicit for other |
| bowler_quota_legal_balls | positive integer nullable | 24 for T20; server-derived as one fifth of the one-day legal-ball limit; null for test; explicit/null for other |
| wicket_limit | positive integer | 10 for the initial profiles; explicit for other |
| consecutive_overs_prohibited | boolean | True for T20, one-day, and test; policy-supplied for other |
| target_mode | enum | `prior_innings_plus_one` for T20/one-day; `none` for test/other |
| allowed_dismissal_types | bounded enum set | Core set for T20/one-day/test; policy-supplied for other |
| allowed_transition_types | bounded enum set | Core retirement transitions for T20/one-day/test; policy-supplied for other |
| allowed_innings_completion_modes | bounded enum set | Derived from the capability profile; never an arbitrary client set |
| allowed_match_completion_modes | bounded enum set | Derived from the capability profile; never an arbitrary client set |
| allowed_result_codes | bounded enum set | Derived from the capability profile; never an arbitrary client set |
| allow_declaration | boolean | True only for test |
| allow_draw | boolean | True only for test |
| explicit_match_completion_boundary | enum | `none` for T20/one-day, `after_completed_innings` for test, and policy-supplied `after_completed_innings` or `any_nonterminal_state` for other |
| allow_manual_completion | boolean | True for test/other; false for T20/one-day |
| version | integer | OCC |

In the sequence descriptions, `A` and `B` are positional placeholders for the
two configured sides. The persisted `innings_sequence` stores the actual
configured `side_code` values (for example, `home`, `away`) in that order; it
does not store the literal placeholders.

The policy stores the resolved capability and cannot be changed after the first
scoring innings or delivery. `allowed_innings_completion_modes`,
`allowed_match_completion_modes`, `allowed_result_codes`, dismissal types, and
transition types are capability-derived sets; the
`explicit_match_completion_boundary` and `allow_*` fields are denormalized read
fields and cannot contradict those sets. T20 is one innings
per side, 120 legal balls in six-ball overs, 24 legal balls per bowler, and ten
wickets. One-day is one innings per side with a configuration-supplied positive
legal-ball limit divisible by 30 in six-ball overs, a server-derived quota equal
to one fifth of that limit, and ten wickets; the client supplies no separate
quota and the limit is never inferred from an unversioned format string. Test
is two innings per side in `[A, B, A, B]` order with six-ball overs, no innings
limit, no target, no quota, ten wickets, consecutive-over prohibition,
declarations, draws, and manual Match completion. Other has no defaults and requires every sequence,
limit, quota, completion, dismissal, and transition policy before scoring. Its
policy-supplied dismissal and transition sets may select only current public
enum values; they cannot introduce a new runtime enum value or enable the
reserved future dismissal identifiers.

Every resolved `allowed_match_completion_modes` set includes the administrative
`abandonment` path; `allowed_innings_completion_modes` never includes it. The
Match completion endpoint owns that path and the Innings completion endpoint
rejects it.

## Fixed participants

Table: match_participants

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key and stable match-scoped identity |
| match_id | UUID | Required Match foreign key |
| side_id | UUID | Required match_sides foreign key |
| participant_kind | enum | internal or external |
| player_id | UUID nullable | Required for internal; null for external |
| display_name_snapshot | string | Required historical display name |
| batting_order_position | positive integer | Unique within side; fixed after configuration |
| version | integer | OCC for explicit participant state changes |

The participant table intentionally has no User ID, email, login, TeamPlayer membership, or account metadata. Internal participant player IDs must belong to the configured academy side at configuration time. External participants are match-scoped only. No external participant can create an academy account through scoring.

## Innings and batting entries

Table: innings

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| match_id | UUID | Required Match foreign key |
| innings_number | positive integer | Unique within Match |
| batting_side_id | UUID | One configured Match side |
| fielding_side_id | UUID | The other configured Match side |
| lifecycle_state | enum | pending, in_progress, completed, or `reconciliation_required`; reconciliation is entered and cleared only by correction replay |
| reconciliation_reason | bounded string nullable | Required exactly when lifecycle_state is `reconciliation_required`; current code is `incompatible_replay`; diagnostic detail, not an independent state flag |
| striker_participant_id | UUID nullable | Current active batter |
| non_striker_participant_id | UUID nullable | Current active batter |
| current_bowler_participant_id | UUID nullable | Current bowler |
| legal_balls | nonnegative integer | Derived projection |
| total_runs | integer | Derived projection in the inclusive range `0..SCORING_RUN_TOTAL_MAX` |
| wickets_lost | nonnegative integer | Derived projection |
| target_runs | positive integer nullable | Set only for innings 2 of T20/one-day after innings 1 completes |
| completed_at | timestamp nullable | Set by completion command |
| state_snapshot | bounded JSON object | Current scorecard read model, no event history; contains the canonical derived `blocking_state` object |
| projection_revision | integer | Revision of the last successful replay |
| version | integer | Aggregate OCC root |

`state_snapshot.blocking_state` is the one canonical serialized progression
indicator. It has the shape `{kind, is_blocked, reason_code}` with `kind` in
`none`, `innings_not_started`, `awaiting_next_batter`,
`awaiting_next_bowler`, `reconciliation_required`, `innings_completed`,
`match_completed`, or `match_abandoned`. It is recomputed from Match lifecycle,
Innings lifecycle, active batting entries, and bowler eligibility; it is not an
independently writable column. The `reconciliation_required` kind is present
if and only if `lifecycle_state` is `reconciliation_required`, and its
`reason_code` is the `reconciliation_reason` detail. Match-level serialization
uses the same object. A terminal Match emits `match_abandoned` or
`match_completed` for every addressed Innings. Otherwise an Innings emits
`reconciliation_required`, `innings_not_started`, `innings_completed`,
`awaiting_next_batter`, `awaiting_next_bowler`, or `none` in that order, with
the batter blocker preceding the bowler blocker. A Match emits the
lowest-numbered reconciliation blocker first, then the current in-progress
Innings' batter-before-bowler blocker; if no current Innings exists for the
next required sequence position, or the current Innings is completed and the
next position has not started, it emits `innings_not_started` rather than
`innings_completed`. If no blocker exists it emits `none`. A completed prior
Innings does not block starting the next sequence position. This same
derivation is used by replay, snapshot refresh, API serialization, and tests.

There is no independent Innings `abandoned` state. When Match lifecycle becomes
`abandoned`, the current Innings remains `pending` or `in_progress` and
incomplete, while its enclosing Match serialization supplies
`blocking_state.kind = match_abandoned`; completed prior innings remain
completed. `Match.lifecycle_state = abandoned` is the authoritative
abandonment state. `result_code = no_result` is its required derived
serialization, not an independent input.

Table: innings_batting_entries

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| innings_id | UUID | Required innings foreign key |
| participant_id | UUID | Required fixed match participant |
| batting_order_position | positive integer | Copied fixed order |
| participation_state | enum | not_batted, active, dismissed, retired_hurt, retired_out, completed |
| dismissal_delivery_id | UUID nullable | Active delivery that dismissed the participant |
| version | integer | OCC for explicit state transition |

Participant and innings constraints prohibit a participant from appearing in two active batting entries in one innings, permit only two active batters, and require active striker/non-striker references to entries in active state.

## Transition events

Table: innings_transition_events

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| innings_id | UUID | Required innings foreign key |
| event_kind | enum | innings_started, next_batter, next_bowler, retired_hurt, retired_hurt_return, innings_completed |
| participant_id | UUID nullable | Selected participant where applicable |
| anchored_attempted_sequence | positive integer nullable | Delivery boundary for deterministic replay |
| anchored_revision_id | UUID nullable | Exact active revision boundary when applicable |
| over_number | nonnegative integer nullable | Context for human-readable history |
| reason | bounded string nullable | Required for correction-sensitive transitions |
| created_by_user_id | UUID | Current authenticated actor |
| created_at | timestamp | Append-only |

Transitions preserve explicit user selections. Replay may detect incompatibility with a later selection and set reconciliation_required; it does not silently choose a replacement batter or bowler.

## Delivery attempts and revisions

Table: deliveries

| Field | Type | Rules |
|---|---|---|
| id | UUID | Stable attempted delivery identity |
| innings_id | UUID | Required innings foreign key |
| attempted_sequence | positive integer | Unique within innings and immutable |
| created_at | timestamp | First attempt timestamp |

Table: delivery_revisions

| Field | Type | Rules |
|---|---|---|
| id | UUID | Immutable revision primary key |
| delivery_id | UUID | Required delivery parent |
| revision_number | positive integer | Monotonic within delivery |
| revision_state | enum | active, superseded |
| striker_participant_id | UUID | Fixed match participant |
| non_striker_participant_id | UUID | Fixed match participant |
| bowler_participant_id | UUID | Fixed match participant on fielding side |
| runs_off_bat | integer | Observed component in the inclusive range `0..SCORING_RUN_COMPONENT_MAX` |
| wide_runs | integer | Inclusive wide component in the range `0..SCORING_RUN_COMPONENT_MAX` |
| no_ball_penalty_runs | integer | Must be 0 or 1 |
| bye_runs | integer | In the range `0..SCORING_RUN_COMPONENT_MAX`; mutually exclusive with leg_bye_runs |
| leg_bye_runs | integer | In the range `0..SCORING_RUN_COMPONENT_MAX`; mutually exclusive with bye_runs |
| penalty_runs | integer | Explicit component in the range `0..SCORING_RUN_COMPONENT_MAX` |
| total_runs | integer | Server-derived and stored for projection speed in the range `0..SCORING_RUN_TOTAL_MAX` |
| is_legal | boolean | Server-derived |
| completed_runs | integer | Server-derived strike-rotation component in the range `0..SCORING_RUN_TOTAL_MAX` |
| balls_faced | boolean | Server-derived |
| bowler_conceded_runs | integer | Server-derived in the range `0..SCORING_RUN_TOTAL_MAX` |
| over_number | nonnegative integer | Server-derived |
| ball_in_over | positive integer | Server-derived legal-ball position |
| replacement_reason | bounded string nullable | Required for correction revision |
| supersedes_revision_id | UUID nullable | Previous active revision |
| recorded_by_user_id | UUID | Current authenticated actor |
| recorded_at | timestamp | Append-only |

The active revision has a partial unique constraint on delivery_id. A delivery parent is never updated to change scoring facts. A correction appends a revision, marks the prior revision superseded, and replays from the earliest affected sequence.

## Wicket and fielder events

Table: wicket_events

| Field | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| delivery_revision_id | UUID | One-to-zero-or-one wicket event in the initial scope |
| dismissal_type | enum | bowled, caught, caught_and_bowled, lbw, run_out, stumped, hit_wicket, retired_out |
| dismissed_participant_id | UUID | Active batter at the relevant attempt |
| dismissed_end | enum nullable | striker_end or non_striker_end; required for run_out |
| primary_fielder_participant_id | UUID nullable | Materialized/read-model compatibility pointer to the first ordered `delivery_fielders` row; recomputed from that association and never independently supplied or written |
| notes | bounded string nullable | Human explanation without raw payload |

Table: delivery_fielders

| Field | Type | Rules |
|---|---|---|
| delivery_revision_id | UUID | Required revision foreign key |
| participant_id | UUID | Match-scoped fielder participant |
| ordinal | positive integer | Starts at 1; unique within the delivery revision and defines API order |
| role | enum | bowler, catcher, thrower, keeper, assister, other |

There is at most one WicketEvent for an active delivery revision. The API
represents it as one optional object, not an array, and its ordered `fielders[]`
collection is the canonical fielder source. Persistence writes one ordered
`DeliveryFielder` row per item; replay and response serialization read those
rows in ordinal order. If a compatibility read exposes
`primary_fielder_participant_id`, it is recomputed from ordinal 1 in the same
transaction (null when `fielders[]` is empty) and is never an independent input
or scoring source. Bowled, LBW,
hit-wicket, and retired-out require zero fielder rows; caught,
caught-and-bowled, and stumped require exactly one row with role catcher,
bowler, and keeper respectively; run-out requires at least one row and permits
multiple ordered thrower, keeper, assister, or other rows. A second, duplicate,
or conflicting wicket object is rejected before persistence; a correction
creates a new delivery revision rather than mutating the event. Retired hurt is
represented by the `retired_hurt` transition event and is not stored in
`wicket_events`.

The current public dismissal enum does not include the reserved future
identifiers `obstructing_the_field`, `hit_the_ball_twice`, or `timed_out`.
Service and schema validation reject those values for every current capability.

No fielder row may reference an external account, a participant from the
batting side, or a participant outside the Match.

## Derived read models

Table: innings_overs

Stores innings, over number, bowler participant, legal ball count, runs conceded, wickets, completion state, and projection revision. It is rebuilt from active revisions and transition events.

Table: innings_participant_summaries

Stores one row per innings participant with batting runs, balls faced, fours, sixes, dismissal state, bowling legal balls, overs display components, runs conceded, wickets, wides, no-balls, fielding dismissals, and projection revision. Overs are stored as legal-ball count plus display metadata; decimal overs are never the source of truth.

Table: match_participant_performances

Stores Match-scoped, innings-aware batting, bowling, fielding, and extras projections. Rows reference the fixed match participant rather than requiring an academy Player. Academy-only compatibility rows may be synchronized into the existing MatchBattingPerformance, MatchBowlingPerformance, and MatchFieldingPerformance tables with an explicit derived provenance marker.

## Relationships

Match
→ match_sides
→ match_participants
→ match_scoring_policies
→ innings
→ innings_batting_entries
→ innings_transition_events
→ deliveries
→ delivery_revisions
→ wicket_events and delivery_fielders
→ innings_overs and innings_participant_summaries
→ match_participant_performances

The graph is Match-scoped at every scoring node. A scoring read never joins external participants through User, Player, or team membership to determine identity.

## Indexes and integrity constraints

Required indexes include:

- match_sides(match_id, side_code)
- match_participants(match_id, side_id, batting_order_position)
- match_participants(match_id, player_id) for internal lookup
- innings(match_id, innings_number)
- innings(match_id, lifecycle_state)
- innings_batting_entries(innings_id, participation_state)
- deliveries(innings_id, attempted_sequence)
- delivery_revisions(delivery_id, revision_number)
- active delivery revisions by innings and attempted sequence
- unique wicket_events(delivery_revision_id), enforcing zero-or-one wicket
  event for every immutable revision
- unique delivery_fielders(delivery_revision_id, ordinal), preserving one
  canonical deterministic fielder order
- innings_overs(innings_id, over_number)
- participant summaries by innings and participant
- Match reads by academy Team IDs and lifecycle state

Database checks enforce the exact scoring component and total bounds, no
simultaneous bye and leg-bye values, no more than one active revision, valid
side/participant ownership, positive order and sequence values, and legal state
transitions where PostgreSQL checks can express them. Service validation covers
cross-row, checked-aggregate, blocking-state, and replay-dependent rules.

## State transitions

Match: scheduled → in_progress → completed; scheduled or in_progress →
abandoned. A completed Match may enter the transaction-local
`correction_reprocessing` phase only through an authorized delivery correction,
then commits to either `completed` or `in_progress`; the intermediate phase is
never exposed as a committed public state. No ordinary scoring or completion
command can reopen a completed Match, and an abandoned Match is not reopened by
this feature. Configuration moves a legacy/unconfigured Match to scheduled with
a locked capability policy and innings sequence. A scored Match cannot return
to `legacy_aggregate`.

Innings: pending → in_progress → completed; in_progress or completed →
`reconciliation_required` only when correction replay exposes an incompatible
later event; `reconciliation_required` → `in_progress` or `completed` only when
a later authorized correction replay makes the active history compatible. There
is no independent Innings abandonment transition. The next innings may be
created only after the previous sequence position is completed. A
`reconciliation_required` Innings blocks scoring progression and all Match
completion; its `blocking_state` clears only when the lifecycle is rebuilt from
compatible active history.

Delivery revision: active → superseded when replaced. Every correction appends a
new active revision and supersedes the previous one; revisions and delivery
parents are immutable after insertion.

Participant: not_batted → active → dismissed, retired_hurt, retired_out, or completed. Retired hurt may return only through an explicit transition event and valid active-batter capacity.

## Capability-derived innings ordering and results

The policy's `innings_sequence` is the only source for batting and fielding
side selection. For T20 and one-day it contains two entries, and innings 2
gets `target_runs = innings_1.total_runs + 1` only after innings 1 is complete.
An innings projection folds only its own active revisions and transition events;
Match-level aggregates include all completed prior innings in sequence and do
not alter the current innings' legal-ball, over, strike, or wicket counters.
For test it contains four entries in `[A, B, A, B]` order and every innings is
completed before the next begins; targets remain null and the final result is
derived from aggregate side totals after innings 4. Other requires an explicit
sequence and never derives a target or automatic result.

For a fixed-over innings, automatic completion precedence within one replay
step is `target_reached`, then the wicket limit, then the legal-ball limit. Thus
a delivery that satisfies more than one terminal condition is classified as
`target_reached`; all observed wicket and delivery facts remain persisted and
are included in replay.

Match result derivation first blocks on any Innings whose authoritative
lifecycle is `reconciliation_required`, then accepts an administrative
Match-level `abandonment` from any non-terminal Match without unresolved
reconciliation as `no_result`, then applies the profile's automatic target or
aggregate comparison when its precondition is true. For test, `draw`,
`declared`, and `manual` are accepted only immediately after a completed
Innings and before the automatic result; for `other`, `manual` is accepted only
at the locked `explicit_match_completion_boundary`. Neither explicit
completion path can override an automatic result. An incomplete required
Innings blocks automatic completion, while a capability-allowed explicit path
is accepted only at its declared boundary. Replay uses active delivery
revisions and anchored transition events in attempted-sequence order, then
applies the persisted Match lifecycle state and derives the result code; the
same persisted events, locked policy, and Match lifecycle always produce the
same projection and result.
