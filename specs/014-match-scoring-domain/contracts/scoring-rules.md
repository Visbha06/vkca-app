# Scoring Rules Contract

## Delivery classification

Each active delivery revision stores observed components and server-derived facts.

| Delivery class | Legal ball | Total formula | Balls faced | Bowler-conceded |
|---|---:|---:|---:|---:|
| Ordinary ball | Yes | runs_off_bat + byes + leg_byes + penalty_runs | Yes | runs_off_bat + penalty components allowed by policy |
| Wide | No | wide_runs + runs_off_bat only when the policy explicitly permits bat contact semantics; initial validator rejects impossible combinations | No | wide_runs |
| No-ball | No | runs_off_bat + no_ball_penalty_runs + byes + leg_byes + penalty_runs | No | runs_off_bat + no_ball_penalty_runs |
| Legal bye | Yes | byes + penalty_runs | Yes | 0 |
| Legal leg-bye | Yes | leg_byes + penalty_runs | Yes | 0 |
| Legal penalty event | Yes when policy allows | penalty_runs | Yes | 0 |

The implementation must use one canonical classifier so total, legal-ball state, balls faced, bowler figures, strike, over state, and projections cannot disagree.

## Component validation

For every attempt:

- runs_off_bat, wide_runs, no_ball_penalty_runs, bye_runs, leg_bye_runs, and penalty_runs are integers at or above zero and below the configured safety bound.
- no_ball_penalty_runs is either zero or one.
- bye_runs and leg_bye_runs cannot both be nonzero.
- A wide has at least one wide run and its mandatory penalty is included in wide_runs.
- A no-ball has no less than one no-ball penalty run.
- Wides and no-balls cannot be simultaneously nonzero.
- Penalty runs are represented explicitly and cannot be smuggled into bat, bye, or leg-bye fields.
- A bounded total is recomputed by the server and persisted only as a projection convenience.
- Unknown request fields and client-supplied derived fields are rejected.

The initial API records only one wicket event per delivery revision. A future rule extension may model multiple events without changing the delivery parent identity.

## Derived metrics

For an active revision:

- total_runs is the canonical sum of its components.
- is_legal is false when wide_runs or no_ball_penalty_runs is nonzero, subject to the explicit policy classifier.
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
- An authorized, policy-approved override requires an explicit bounded reason and creates a meaningful audit event.

Test/other formats without a quota require an explicit current bowler selection but do not invent a hidden quota.

## Wicket rules

| Dismissal | Required input | Initial validation |
|---|---|---|
| bowled | dismissed participant | Dismissed participant is active striker unless a future rule policy says otherwise |
| caught | dismissed participant, catcher | Catcher is a fielding-side participant |
| caught_and_bowled | dismissed participant | Bowler is the fielder |
| lbw | dismissed participant | Dismissed participant is active striker |
| run_out | dismissed participant, dismissed_end | End is required; thrower/other fielder may be recorded |
| stumped | dismissed participant, wicketkeeper/fielder | Fielder is on the fielding side and is keeper-capable in the configured role |
| hit_wicket | dismissed participant | Dismissed participant is the active striker |
| obstructing_the_field | dismissed participant | Explicit authorized observation; no automatic inference |
| timed_out | dismissed participant | Completion/transition context is valid |
| retired_out | dismissed participant | Explicit retirement command/context; not confused with retired hurt |

The dismissed participant must be active in the innings and cannot already have a dismissal. A wicket increments wickets_lost exactly once. Retired hurt changes participation state and is not a wicket.

## Completion and result rules

An innings can complete automatically when:

- the chasing innings reaches target_runs;
- wickets_lost reaches the configured wicket limit;
- legal balls reach the configured innings limit;
- a declaration or other manual completion is allowed by policy and explicitly commanded.

The target for a chasing innings is the prior completed innings total plus one. The Match result projection compares completed innings and supports:

- win_by_runs when the defending side has more runs after the chase is complete;
- win_by_wickets when the chasing side reaches target before its wicket/ball limit;
- tie when totals are equal under the selected policy;
- draw, no_result, declared, or manual when explicitly completed with that outcome.

No Super Over, DLS, or hidden tiebreak is inferred.

## Correction and replay invariants

- Attempted sequence identifies the observed delivery slot and never changes.
- Active revisions form exactly one ordered replay stream.
- Revisions are append-only and preserve the predecessor, reason, actor, and time.
- Replay from a correction point produces the same state as replay from the beginning.
- A correction cannot mutate or delete a prior revision.
- All downstream projections are rebuilt from the active stream and explicit transition events.
- Later incompatible transitions produce reconciliation_required with a reason and affected boundary.
- A successful correction updates projections, version, audit/outbox behavior, and status atomically.
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
