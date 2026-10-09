# Scoring Rules Contract

## Format capabilities and innings sequence

The scoring-rule layer receives the locked, versioned `FormatCapability`; it
does not infer behavior from a raw format string. The profile identifier is
also the canonical API, domain, and persisted Match format value: `T20`,
`one-day`, `test`, or `other`. Human display labels do not introduce aliases.

| Profile | Ordered innings | Innings legal-ball limit / over length | Bowler quota | Wicket limit | Consecutive-over rule | Declaration / draw / manual | Target | Explicit Match-completion boundary | Innings completion modes | Match completion modes / result codes |
|---|---|---|---|---|---|---|---|---|---|---|
| `T20` | `[A, B]` | 120 / 6 legal balls | 24 legal balls | 10 | Prohibited | No / No / No | innings 2 = innings 1 total + 1 | None | `all_out`, `legal_ball_limit`, `target_reached` | Automatic `win_by_runs`, `win_by_wickets`, `tie`; Match `abandonment` → `no_result` |
| `one-day` | `[A, B]` | policy-supplied positive multiple of 30 / 6 legal balls | derived as one fifth of the locked innings limit | 10 | Prohibited | No / No / No | innings 2 = innings 1 total + 1 | None | `all_out`, `legal_ball_limit`, `target_reached` | Automatic `win_by_runs`, `win_by_wickets`, `tie`; Match `abandonment` → `no_result` |
| `test` | `[A, B, A, B]` | no innings limit / 6 legal balls | None | 10 | Prohibited | Yes / Yes / Yes | none | `after_completed_innings` before automatic result | `all_out`, `declaration` | Automatic after innings 4 `win_by_runs`/`tie`; explicit `draw`, `declared`, `manual`; Match `abandonment` → `no_result` |
| `other` | policy-supplied sequence | policy-supplied over length; limit nullable | policy-supplied or none | policy-supplied | policy-supplied | No / No / Yes | none | Locked policy selects `after_completed_innings` or `any_nonterminal_state` | `manual` | `manual` → `manual`; Match `abandonment` → `no_result` |

`A` and `B` in the table are positional placeholders. The locked persisted
sequence contains the configured side-code values, such as `home` and `away`,
not literal `A`/`B` values.

`pending` is the non-terminal result code for every profile before Match
completion. It is not a completion mode and cannot be submitted as a final
result.

For `one-day`, configuration supplies the legal-ball limit only. It must be a
positive multiple of 30 so it represents complete six-ball overs and supports
the initial quota policy. The server derives
`bowler_quota_legal_balls = legal_ball_limit / 5`; for example, 240 legal balls
resolves to 48 quota balls. A missing, non-divisible, or client-supplied quota
fails validation. Test has no quota, but its immediately completed bowler is
ineligible for the next over.

The side at each sequence position bats and the other configured side fields.
An incomplete or reconciliation-required innings blocks the next sequence
position and automatic Match completion. Replay applies the same locked
sequence and capability after folding each innings, so side selection, target,
aggregate result, and result precedence are deterministic. The initial T20,
one-day, and test profiles use the core dismissal set
`bowled`, `caught`, `caught_and_bowled`, `lbw`, `run_out`, `stumped`,
`hit_wicket`, and `retired_out`, plus the separate `retired_hurt` and
`retired_hurt_return` transitions. `other` must list every dismissal and
transition type it accepts from the current public vocabularies; an unlisted
type fails validation and the policy cannot add a new runtime enum value. The reserved
future dismissal identifiers `obstructing_the_field`, `hit_the_ball_twice`, and
`timed_out` are rejected by every current capability and are not in the current
public enum. An innings rule fold reads only that innings' active revisions and
transitions; Match
aggregate rules read all completed prior innings in sequence, without carrying
prior innings' legal-ball, over, strike, or wicket counters into the current
innings.

## Delivery classification

Each active delivery revision stores observed components and server-derived facts.

| Delivery class | Legal ball | Total formula | Balls faced | Bowler-conceded |
|---|---:|---:|---:|---:|
| Ordinary ball | Yes | runs_off_bat + byes + leg_byes + penalty_runs | Yes | runs_off_bat + penalty components allowed by policy |
| Wide | No | wide_runs; the initial profiles require runs_off_bat = 0 | No | wide_runs |
| No-ball | No | runs_off_bat + no_ball_penalty_runs + byes + leg_byes + penalty_runs | No | runs_off_bat + no_ball_penalty_runs |
| Legal bye | Yes | byes + penalty_runs | Yes | 0 |
| Legal leg-bye | Yes | leg_byes + penalty_runs | Yes | 0 |
| Legal penalty event | Yes when policy allows | penalty_runs | Yes | 0 |

The implementation must use one canonical classifier so total, legal-ball state, balls faced, bowler figures, strike, over state, and projections cannot disagree.

## Component validation

For every attempt, use the fixed constants from `spec.md`:

- `SCORING_RUN_COMPONENT_MAX = 2,147,483,647` for `runs_off_bat`,
  `wide_runs`, `bye_runs`, `leg_bye_runs`, and `penalty_runs` (inclusive).
- `no_ball_penalty_runs` is an integer from `0` through `1` (inclusive).
- `SCORING_RUN_TOTAL_MAX = 2,147,483,647` for the recomputed delivery total
  and every Innings/Match aggregate run total (inclusive).

For every attempt:

- runs_off_bat, wide_runs, bye_runs, leg_bye_runs, and penalty_runs are
  integers from `0` through `SCORING_RUN_COMPONENT_MAX`; negative values and
  values above the constant fail validation.
- no_ball_penalty_runs is either zero or one.
- bye_runs and leg_bye_runs cannot both be nonzero.
- A wide has at least one wide run and its mandatory penalty is included in wide_runs.
- A no-ball has no less than one no-ball penalty run.
- Wides and no-balls cannot be simultaneously nonzero.
- Penalty runs are represented explicitly and cannot be smuggled into bat, bye, or leg-bye fields.
- A total is recomputed by the server and must be in the inclusive range
  `0..SCORING_RUN_TOTAL_MAX`; a component sum above that bound fails with 422
  before persistence. Checked addition applies the same bound to Innings and
  Match aggregates.
- Unknown request fields and client-supplied derived fields are rejected.

The initial API records zero or one wicket event per delivery revision. The
request shape is one optional `wicket` object, not an array. Its ordered
`fielders[]` collection is canonical and is persisted as ordered
`DeliveryFielder` associations; any exposed `primary_fielder_participant_id` is
derived from ordinal 1 (or is null when the collection is empty) and is never
independently supplied. Bowled, LBW,
hit-wicket, and retired-out require zero fielders; caught,
caught-and-bowled, and stumped require exactly one catcher, bowler, and keeper
respectively; run-out requires at least one fielder and permits multiple
ordered fielders. A second, duplicate, or conflicting wicket payload fails
validation with 422 and does not persist a delivery. A correction replaces the
event only by appending a new immutable revision and superseding the old one;
replay folds the ordered fielder associations from the active revision, ignores
any derived primary-fielder pointer, and applies at most one active wicket
effect per attempted delivery.

## Derived metrics

For an active revision:

- total_runs is the canonical sum of its components.
- is_legal is false when wide_runs or no_ball_penalty_runs is nonzero, as determined by the locked capability classifier.
- legal_ball_index is the innings legal-ball count before the attempt plus one when legal.
- over_number and ball_in_over are derived from legal-ball count and the policy over length.
- completed_runs is the running distance used for strike rotation; it excludes the mandatory wide/no-ball penalty and penalty runs.
- balls_faced is true for a legal delivered ball and false for a wide/no-ball.
- bowler_conceded_runs excludes byes and leg-byes and follows the no-ball/wide rules.
- fours and sixes count bat runs of exactly four or six when no conflicting component invalidates the boundary observation.
- fall-of-wicket uses the active wicket event sequence and score at dismissal.

Overs are calculated from legal-ball counts. An API may display overs and remaining balls as a formatted value, but decimal overs are never used for arithmetic or persistence.

## Strike and over progression

At the start of an innings and after a batter replacement, striker/non-striker are explicit fixed participant IDs.

After each delivery:

1. Apply the delivery's completed_runs parity to swap ends when odd.
2. Apply any wicket dismissal end and replacement transition.
3. If the delivery completes the configured legal-ball limit for the over, mark the over complete and swap ends once for the over boundary.
4. Require an explicit next bowler before the next legal delivery when the policy disallows the previous bowler or the current over is complete.

Illegal wides and no-balls do not advance ball_in_over. Runs completed on an illegal delivery may affect strike according to completed_runs. A single wide or no-ball penalty alone does not rotate strike.

The service validates that striker and non-striker are distinct active batting-side participants and that the bowler is an eligible fielding-side participant. It never trusts a client-provided post-delivery state.

## Bowler quota and eligibility

For a quota-bearing limited-overs policy:

- The quota is counted in legal balls bowled, not delivery attempts.
- A bowler cannot exceed the configured quota.
- A new over cannot use the previous over's bowler when consecutive overs are prohibited.
- A no-ball or wide does not consume quota.
- The next-bowler query reports eligibility and reason for exclusion.
- An authorized, policy-approved override requires an explicit bounded reason and creates no Business Audit event.

Test/other formats without a quota require an explicit current bowler selection but do not invent a hidden quota.

## Wicket rules

| Dismissal | Required input | Fielder cardinality and role | Initial validation |
|---|---|---|---|
| bowled | dismissed participant | Zero | Dismissed participant is the active striker |
| caught | dismissed participant, catcher | Exactly one `catcher` | Catcher is a fielding-side participant |
| caught_and_bowled | dismissed participant | Exactly one `bowler` | Fielder is the current bowler |
| lbw | dismissed participant | Zero | Dismissed participant is active striker |
| run_out | dismissed participant, dismissed_end | At least one; additional ordered `thrower`, `keeper`, `assister`, or `other` fielders are allowed | End is required; every fielder is a fielding-side participant |
| stumped | dismissed participant, wicketkeeper/fielder | Exactly one `keeper` | Fielder is on the fielding side and is keeper-capable in the configured role |
| hit_wicket | dismissed participant | Zero | Dismissed participant is the active striker |
| retired_out | dismissed participant | Zero | Explicit retirement command/context; not confused with retired hurt |

The dismissed participant must be active in the innings and cannot already
have a dismissal. The API `fielders[]` order is persisted as the
`DeliveryFielder.ordinal` order; `primary_fielder_participant_id`, when exposed,
is the derived ordinal-1 participant and is not an independent input. A
WicketEvent increments `wickets_lost` exactly once.
Retired hurt is an `innings_transition_event` that changes participation state,
does not increment `wickets_lost` or bowler wickets, and can return only through
the explicit return transition.

## Completion and result rules

For T20 and one-day, an innings completes automatically when
`wickets_lost` reaches the capability wicket limit, legal balls reach the
capability innings limit, or innings 2 reaches its derived target. The result is
win_by_wickets on target reach, win_by_runs when innings 2 ends below target and
the defending score is higher, and tie when fixed-over scores are equal. If a
single folded delivery reaches the target and also reaches the wicket or
legal-ball limit, `target_reached` is the completion reason; the wicket and
delivery facts remain part of the persisted active history.

For test, the four ordered innings have no target. A declaration completes the
current innings and advances the sequence. After innings 4, aggregate side
totals produce `win_by_runs` or `tie`. Before an automatic result occurs and
immediately after a completed innings, an authorized scorer may explicitly
complete the Match as `draw`, `declared`, or `manual`, using the corresponding
bounded reason. For `other`, no automatic completion or result is inferred; an
authorized scorer must use `manual` at the locked explicit completion boundary.

Match-level `abandonment` is the only abandonment path for every capability. It
is accepted from any non-terminal Match without unresolved reconciliation,
sets Match lifecycle to `abandoned` and result code to `no_result`, and blocks
later scoring or completion. It does not complete or abandon the current
Innings: the current Innings retains its underlying `pending` or `in_progress`
lifecycle, while the serialized `blocking_state` is `match_abandoned`.
An incomplete required Innings or an Innings lifecycle of
`reconciliation_required` blocks automatic completion, and an explicit
completion outside its locked boundary is rejected. No Super Over, DLS,
follow-on, interruption rule, or hidden tiebreak is inferred.

## Correction and replay invariants

- Attempted sequence identifies the observed delivery slot and never changes.
- Active revisions form exactly one ordered replay stream.
- Revisions are append-only; a correction appends a replacement revision and
  marks the previous active revision `superseded`, preserving predecessor,
  reason, actor, and time.
- Replay from a correction point produces the same state as replay from the beginning.
- A correction cannot mutate or delete a prior revision.
- All downstream projections are rebuilt from the active stream and explicit transition events.
- Later incompatible transitions set the affected Innings lifecycle to
  `reconciliation_required` with a reason and affected boundary; Match-level
  status remains `in_progress` and derives its reconciliation blocker from that
  Innings.
- A successful correction updates projections, version, audit/outbox behavior,
  and status atomically. A completed Match uses the transaction-local path
  `completed → correction_reprocessing → completed` when terminal, or
  `completed → correction_reprocessing → in_progress` when the corrected
  history is compatible but non-terminal. The intermediate state is never
  committed or externally visible; an unsafe replay rolls back with 409.
- A stale or invalid correction changes nothing.
- A replay-equivalence test compares a corrected full replay with a fresh replay of the final active stream.

## Read-model invariants

For every innings projection:

- total_runs equals the sum of active revision totals;
- legal_balls equals the count of active legal revisions;
- wickets_lost equals the count of active wicket events;
- each over's legal balls are within the policy over length except an explicitly completed short final over;
- participant summaries equal the fold of active revisions and transitions;
- target and result are derived from completed innings, never client-supplied totals;
- projection_revision identifies the active replay boundary used to build the read model.
