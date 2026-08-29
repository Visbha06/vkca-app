# Data Model: Match Scoring Domain

## Modeling principles

The existing Match row remains the aggregate anchor. Scoring configuration, innings, participants, delivery attempts, and projections are Match-owned. Delivery history and correction revisions are authoritative; every scorecard, performance summary, target, result, and over state is derived or materialized from that history.

All new mutable roots use the repository UUID, created/updated timestamp, and integer version conventions. Foreign keys use the existing deletion policy for historical data: a configured Match, participant, innings, or delivery is retained and cannot be deleted through ordinary application commands. Database cascades are used only for migration teardown or child records whose parent is being removed before the feature is configured.

## Existing Match extension

Extend Match with:

| Field | Type | Rules |
|---|---|---|
| lifecycle_state | enum | scheduled, in_progress, completed, abandoned; legacy rows default to scheduled or a compatible legacy state |
| scoring_authority | enum | legacy_aggregate or delivery_history; immutable once the first scoring innings/delivery exists |
| result_code | enum | pending, win_by_runs, win_by_wickets, tie, draw, no_result, declared, manual |
| result_details | bounded JSON object | Derived structured result; no raw delivery payload |
| configured_at | timestamp nullable | Set when fixed sides/participants and policy are locked |

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
| policy_code | enum/string | t20, one_day, test, other |
| policy_version | positive integer | Historical policy revision |
| innings_per_side | positive integer nullable | Required for bounded formats |
| legal_ball_limit | positive integer nullable | Required for bounded formats |
| bowler_quota_legal_balls | positive integer nullable | Required where a quota applies |
| wicket_limit | positive integer nullable | Defaults from configured XI when applicable |
| consecutive_overs_prohibited | boolean | True for limited-overs defaults |
| allow_declaration | boolean | Explicit policy behavior |
| allow_manual_completion | boolean | Required for test/other |
| version | integer | OCC |

T20 defaults are one innings, 120 legal balls, 24 legal balls per bowler, and a configured-XI wicket limit. One-day settings are explicit. Test/other require explicit manual completion behavior and may leave legal-ball limits null.

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
| lifecycle_state | enum | pending, in_progress, completed, abandoned, reconciliation_required |
| blocking_reason | bounded string nullable | Required for reconciliation_required |
| striker_participant_id | UUID nullable | Current active batter |
| non_striker_participant_id | UUID nullable | Current active batter |
| current_bowler_participant_id | UUID nullable | Current bowler |
| legal_balls | nonnegative integer | Derived projection |
| total_runs | nonnegative integer | Derived projection |
| wickets_lost | nonnegative integer | Derived projection |
| target_runs | positive integer nullable | Set only when chasing a completed prior innings |
| completed_at | timestamp nullable | Set by completion command |
| state_snapshot | bounded JSON object | Current scorecard read model, no event history |
| projection_revision | integer | Revision of the last successful replay |
| reconciliation_required | boolean | Read-model marker |
| version | integer | Aggregate OCC root |

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
| revision_state | enum | active, superseded, void |
| striker_participant_id | UUID | Fixed match participant |
| non_striker_participant_id | UUID | Fixed match participant |
| bowler_participant_id | UUID | Fixed match participant on fielding side |
| runs_off_bat | nonnegative integer | Observed component |
| wide_runs | nonnegative integer | Inclusive wide component |
| no_ball_penalty_runs | nonnegative integer | Must be 0 or 1 |
| bye_runs | nonnegative integer | Mutually exclusive with leg_bye_runs |
| leg_bye_runs | nonnegative integer | Mutually exclusive with bye_runs |
| penalty_runs | nonnegative integer | Explicit bounded penalty component |
| total_runs | nonnegative integer | Server-derived and stored for projection speed |
| is_legal | boolean | Server-derived |
| completed_runs | nonnegative integer | Server-derived strike-rotation component |
| balls_faced | boolean | Server-derived |
| bowler_conceded_runs | nonnegative integer | Server-derived |
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
| dismissal_type | enum | bowled, caught, caught_and_bowled, lbw, run_out, stumped, hit_wicket, obstructing_the_field, timed_out, retired_out |
| dismissed_participant_id | UUID | Active batter at the relevant attempt |
| dismissed_end | enum nullable | striker_end or non_striker_end; required for run_out |
| fielder_participant_id | UUID nullable | Required where the dismissal needs one |
| notes | bounded string nullable | Human explanation without raw payload |

Table: delivery_fielders

| Field | Type | Rules |
|---|---|---|
| delivery_revision_id | UUID | Required revision foreign key |
| participant_id | UUID | Match-scoped fielder participant |
| role | enum | catcher, thrower, keeper, assister, other |

No fielder row may reference an external account, a participant from the batting side, or a participant outside the Match.

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
- innings_overs(innings_id, over_number)
- participant summaries by innings and participant
- Match reads by academy Team IDs and lifecycle state

Database checks enforce nonnegative component values, no simultaneous bye and leg-bye values, no more than one active revision, valid side/participant ownership, positive order and sequence values, and legal state transitions where PostgreSQL checks can express them. Service validation covers cross-row and replay-dependent rules.

## State transitions

Match: scheduled → in_progress → completed; scheduled or in_progress → abandoned. Configuration moves a legacy/unconfigured Match to scheduled with a locked policy. A scored Match cannot return to legacy_aggregate.

Innings: pending → in_progress → completed; pending or in_progress → abandoned; in_progress or completed → reconciliation_required only when a correction exposes an incompatible later event. Reconciliation-required state must be explicitly resolved by a future authorized command before final completion.

Delivery revision: active → superseded when replaced; active → void only through a correction command that records why the attempt has no active scoring revision. Superseded and void revisions are immutable.

Participant: not_batted → active → dismissed, retired_hurt, retired_out, or completed. Retired hurt may return only through an explicit transition event and valid active-batter capacity.
