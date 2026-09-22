# Match Scoring Domain

This document describes the implemented Match-scoring boundary: a locked
format capability, fixed Match-scoped participants, append-only delivery
history, deterministic innings replay, and persisted read projections. It is a
domain and API reference, not a scorer UI guide. The executable acceptance
journey is [the Match Scoring Quickstart](../specs/014-match-scoring-domain/quickstart.md).

## Capability profiles

The wire, domain, policy, and persisted format identifier is the same exact
string. Capability and policy version 1 uses these profiles:

| Canonical identifier | Ordered innings | Legal-ball limit | Over / bowler quota | Completion and result behavior |
|---|---|---|---|---|
| `T20` | `[home, away]` | 120 per innings | 6 legal balls; 24 legal balls per bowler; no consecutive overs | All out, limit, or target completes an innings. The second innings targets the first total + 1. Automatic result: runs win, wickets win, or tie. |
| `one-day` | `[home, away]` | Supplied positive multiple of 30 | 6 legal balls; quota is derived as `legal_ball_limit / 5`; no consecutive overs | Same limited-overs completion and result behavior as T20. A 240-ball innings derives a 48-ball quota. The client cannot supply the quota. |
| `test` | `[home, away, home, away]` | None | 6 legal balls; no bowler quota; no consecutive overs | Ten wickets per innings. Innings may end all out or by declaration. After innings four, automatic results are `win_by_runs` or `tie`; explicit `draw`, `declared`, or `manual` Match completion is allowed at the `after_completed_innings` boundary. |
| `other` | Explicit ordered sequence | Optional policy value | Explicit over length, optional quota, wicket limit, and consecutive-over rule | No automatic result is inferred. Policy supplies dismissal/transition sets and the `after_completed_innings` or `any_nonterminal_state` Match-completion boundary; version 1 allows manual completion. |

The strings `t20`, `one_day`, and `other_manual` are not aliases. `other`
requires explicit policy values; it does not inherit T20 or Test assumptions.
The locked sequence is expressed in persisted side codes (`home`, `away`); in
descriptions of the matrix, A and B mean the first and second configured sides
and are not necessarily academy sides. The capability is immutable once
scoring starts.

## Participants and authorization

Configuration snapshots two Match sides and their ordered participants before
the first innings. Internal participants refer to an academy Player. External
opposition participants are Match-scoped display identities: they do not
create or refer to a User, Player, team membership, login, or authorization
scope. External fielders follow the same identity rule.

Every protected request reloads the active database User and current role/team
scope. Head Coaches have full scoring access. Assistant Coaches may read or
score only where their current TeamCoach assignment covers an academy side.
Players may read permitted Match, innings, scorecard, and bounded history data
in their current TeamPlayer scope, but cannot configure, score, correct, or
complete. An external side never grants access.

## Delivery history and cricket rules

The client records observed facts: fixed striker/non-striker/bowler IDs,
attempted sequence, expected Match/Innings versions, bat runs, allowed extra
components, and zero or one optional wicket. The server derives total runs,
legal status, ball/over position, balls faced, bowler-conceded runs, strike and
over transitions, wickets, and summaries. Unknown fields and client-supplied
derived values are rejected.

Wides and no-balls are illegal and do not consume a legal ball or bowler quota.
A wide component includes its required penalty. A no-ball penalty is zero or
one and may accompany permitted additional bat, bye, or leg-bye runs. Byes and
leg-byes are mutually exclusive and are not charged to the bowler; penalty
runs are also not bowler-conceded. A legal delivery counts as a ball faced,
including a legal delivery scored only as byes or leg-byes. Completed running
used for strike rotation excludes wide/no-ball penalty and penalty runs. The
end-of-over strike change follows the configured legal-ball length; a new
bowler is explicitly selected and must meet the locked eligibility and quota
rules.

Run components and delivery/innings/Match totals are bounded by
`2,147,483,647`; the no-ball penalty component is bounded by 1. Checked
addition rejects aggregate overflow.

An active delivery revision has at most one `WicketEvent`. The accepted core
dismissals are `bowled`, `caught`, `caught_and_bowled`, `lbw`, `run_out`,
`stumped`, `hit_wicket`, and `retired_out`; `other` may select only current
public values and must declare its set. Reserved future identifiers
`obstructing_the_field`, `hit_the_ball_twice`, and `timed_out` are rejected.
Retired hurt is a participation transition, not a wicket.

The ordered `fielders[]` collection is canonical and references participants
on the fielding side. Bowled, LBW, hit-wicket, and retired-out use no fielders;
caught requires one `catcher`, caught-and-bowled one `bowler`, and stumped one
`keeper`. Run-out requires at least one fielder and can record multiple
ordered thrower/keeper/assister/other roles. The response's
`primary_fielder_participant_id` is read-only and equals the first association,
or null when there are none. It is never client-supplied and does not affect
scoring. A second or conflicting wicket shape fails before the delivery or
projection is persisted.

Dismissals that require a replacement expose an `awaiting_next_batter`
progression block until an eligible fixed-order batter is selected. Retired
hurt does not reduce wickets; the batter may return through the explicit,
policy-checked return command or be replaced. Bowler eligibility is derived
from fielding-side membership, legal balls already bowled, quota, and the
previous-over restriction. No implicit override bypasses those checks.

## Lifecycle, reconciliation, and blocking state

Match lifecycle owns terminal Match state. Innings lifecycle is one of
`pending`, `in_progress`, `completed`, or `reconciliation_required`; it has no
independent `abandoned` state. Match abandonment is an administrative
Match-level command from a non-terminal Match with no unresolved
reconciliation. It sets Match lifecycle to `abandoned` and result code to
`no_result`, blocks further scoring, and leaves a current Innings in its
underlying `pending` or `in_progress` state without completing it.

Innings lifecycle is authoritative for reconciliation. A correction that
makes later deliveries or transitions incompatible preserves their identity
and provenance and marks the affected Innings `reconciliation_required` with a
bounded reason. Match reconciliation is derived from innings; no second
mutable Match reconciliation flag exists. An unsafe correction rolls back
with a conflict rather than changing captured actors or outcomes.

Match and Innings responses share a derived, read-only
`blocking_state = {kind, is_blocked, reason_code}`. `kind` is one of `none`,
`innings_not_started`, `awaiting_next_batter`, `awaiting_next_bowler`,
`reconciliation_required`, `innings_completed`, `match_completed`, or
`match_abandoned`. Only `none` is unblocked and has a null reason. A terminal
Match override takes precedence. For an Innings, remaining precedence is
reconciliation, not-started, completed, awaiting batter, awaiting bowler, then
none. At Match level, after terminal state, the lowest-numbered unresolved
Innings takes precedence, followed by the current innings' batter-before-
bowler blocker and any missing required innings. A completed earlier innings
does not block the Match as `innings_completed`.

## Correction, completion, and optimistic concurrency

Delivery correction is the only supported amendment path. It appends a new
immutable revision, marks the former active revision `superseded`, records the
reason/actor/time/superseded revision, and leaves exactly one active revision
for scorecard reads. A correction must provide the current Match, Innings, and
expected revision versions. All scoring mutations use the relevant optimistic
concurrency version; stale writes return HTTP 409 and cannot create a duplicate
active sequence.

A completed Match can be reopened only inside the transaction-local
`correction_reprocessing` phase. That phase is not externally observable. A
compatible replay preserves a terminal result or commits the Match as
`in_progress` if the corrected history is no longer terminal; incompatible
later state is surfaced as reconciliation-required. Ordinary scoring cannot
reopen a completed Match, and correction does not reopen an abandoned Match.
Delivery rows and prior revisions are not deleted or rewritten. Arbitrary
undo is deferred; any future undo must delegate to this correction/replay
boundary rather than decrementing counters independently.

For T20 and one-day, innings two receives target = completed innings-one total
+ 1. Reaching that target completes the chase and derives a wickets win;
finishing below target derives runs win or tie. The Test sequence is exactly
`[home, away, home, away]`, has no target/follow-on rule, and supports distinct
declaration, draw, and manual completion paths at its locked explicit
boundary. `other` has no automatic result. No profile infers DLS, Super Over,
interruption, follow-on, or automated umpiring. Match-level abandonment yields
no result without altering current-Innings lifecycle.

## Read projections and compatibility

Normal innings and scorecard reads use persisted, rebuildable projections;
they do not replay complete delivery history per request. The scorecard
exposes ordered innings, runs/wickets/legal balls, participant summaries,
batting/bowling/fielding figures, extras, fall of wickets, overs, target/chase,
result, locked capability, authority, projection revision, and blocking state.
Bounded delivery history exposes active facts plus correction provenance; it
does not present superseded facts as active.

Unconfigured legacy Matches retain `legacy_aggregate` authority and existing
aggregate performance reads/writes. Configuring a Match locks it to
`delivery_history`; direct aggregate writes for that Match are rejected.
Compatible academy Player projections may be synchronized to existing
performance tables with derived provenance. The Match-scoped participant
performance projection remains canonical for multi-innings and external
participants; external identities are not written into Player-keyed or career
statistics tables.

## Audit, Data Quality, and background/RAG work

The allowlisted scoring Business Audit actions are `scoring.initialized`,
`scoring.innings_started`, `scoring.innings_completed`,
`scoring.match_completed`, and `scoring.delivery_corrected`. Events are written
with the scoring command in its transaction and contain bounded actor/target,
action, and allowlisted metadata. Ordinary deliveries, next-batter/next-bowler
selections, retirement/return transitions, stale conflicts, and validation
failures do not create Business Audit events.

Scoring Data Quality findings are visible only to Head Coaches through the
read/reporting boundary. They are read-only checks for projection/replay
mismatch, duplicate or conflicting active revisions/sequences, invalid
participant/lifecycle/over/quota/wicket state, reconciliation-required state,
malformed history, and legacy-adapter divergence. Reading findings does not
repair scoring state, emit audit events, or enqueue work. There is no public
scoring-check rerun or scoring remediation endpoint. The existing
Head-Coach-only remediation flow remains separate for supported non-scoring
findings; scoring corrections use the normal authorized correction command.

Ordinary delivery entry is synchronous and stages no provider, queue,
embedding, or RAG work. Successful Match completion and material correction
stage a bounded, coalesced Match-level current-state refresh through the
transactional outbox (coalescing key `rag:match:{match_id}`). The intent carries
identifiers, projection revision, and a bounded reason—not delivery payloads.
The handler reloads committed current state and is safe on duplicate delivery.
The Match RAG builder emits a bounded Match summary; there is no Delivery RAG
source. Refresh/provider failure affects background work only and cannot
change scoring truth or create scoring audit events.

## Performance acceptance protocol

The SC-002 integration benchmark seeds one Test innings with exactly 1,000
active attempted delivery revisions: 900 legal and 100 illegal, plus a
reconciled persisted projection and fixed participants. Fixture creation and
database/process startup are outside the measured boundary. It performs one
cold diagnostic read, five warm-ups, then measures 30 consecutive warm
authenticated scorecard reads from request start through response completion.
The pass criterion is at least 29 individual warm reads at or below 1.000
seconds. The check verifies the expected projection revision and totals, that
the read does not select from delivery/revision history for a full replay, and
that query count stays at or below 20 statements per measured read (600 for
the 30-read measurement block). No percentile interpolation, provider, queue,
embedding, or Internet work is involved.

SC-004 separately corrects and replays a 100-attempt stream and compares the
result with a clean replay of the corrected active stream, including totals,
legal balls, participant summaries, over projection, and blocking state.

## Extension boundaries

The stored Match participant IDs, delivery sequence, revision provenance,
ordered fielder associations, and innings projections provide stable future
extension points for richer scorecards, pitch maps, wagon wheels, and player
statistics. Those visualizations and derived career-stat products are not
implemented here. Nor are scorer UI, public live-feed delivery, arbitrary undo,
external score ingestion, DLS, Super Over, or full competition-specific Test
rules.
