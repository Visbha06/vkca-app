# Match Scoring API Contract

## Conventions

Base path: /api/v1

All endpoints require the existing bearer authentication and load the current active User from the database. Every response includes identifiers, current lifecycle state, the locked capability/innings sequence where relevant, and the relevant Match or innings version. Mutating requests include the caller's expected version. The server owns all derived scoring fields. Match format values are exactly the canonical `T20`, `one-day`, `test`, and `other` identifiers; the same values are used for `format`, `policy_code`, and `capability_profile`.

Authorization:

| Actor | Read in current team scope | Configure/score/correct/complete |
|---|---|---|
| Head Coach | Yes | Yes |
| Assistant Coach | Yes, when the current TeamCoach assignment covers the academy side | Yes, in that scope |
| Player | Yes, when current TeamPlayer scope covers the academy side | No |
| Other authenticated user | No | No |
| Unauthenticated or inactive user | No | No |

An external opponent side never grants access. External participants are match-scoped display identities and are not User or Player identities.
The scoped read permission in this table applies to Match, innings, scorecard,
and delivery-history resources; it does not grant access to operational Data
Quality findings, which are Head-Coach-only below.

## Canonical progression and reconciliation status

Every Match and Innings response exposes the same read-only `blocking_state`
object:

    {
      "kind": "awaiting_next_batter",
      "is_blocked": true,
      "reason_code": "next_batter_required"
    }

`kind` is one of `none`, `innings_not_started`, `awaiting_next_batter`,
`awaiting_next_bowler`, `reconciliation_required`, `innings_completed`,
`match_completed`, or `match_abandoned`. `is_blocked` is false only for
`none`; `reason_code` is null only for `none`. The allowed reason codes are
`innings_not_started`, `next_batter_required`, `next_bowler_required`,
`no_eligible_bowler`, `incompatible_replay`, `innings_completed`,
`match_completed`, and `match_abandoned`.

For an Innings, the object is derived from its lifecycle and active participant
state: after a terminal Match override, `reconciliation_required`,
`innings_not_started`, `innings_completed`, `awaiting_next_batter`,
`awaiting_next_bowler`, and `none` are considered in that order; the batter
blocker precedes the bowler blocker. For a Match, `match_abandoned` and
`match_completed` take precedence, followed by the lowest-numbered Innings in
`reconciliation_required`, the current in-progress Innings' batter-before-
bowler blocker, and `innings_not_started` when no current Innings exists for
the next required sequence position or a completed current Innings is waiting
for it. A Match never emits `innings_completed` for a completed prior Innings.
There is no separate mutable Match reconciliation flag: Match-level
reconciliation is represented by this derived object when any Innings lifecycle
is `reconciliation_required`.

## Configure a Match

PUT /matches/{match_id}/configuration

Request:

    {
      "match_version_number": 3,
      "format": "T20",
      "policy": {
        "policy_code": "T20",
        "capability_profile": "T20",
        "capability_version": 1,
        "innings_sequence": ["home", "away"],
        "innings_per_side": 1,
        "legal_ball_limit": 120,
        "over_length_legal_balls": 6,
        "bowler_quota_legal_balls": 24,
        "wicket_limit": 10,
        "consecutive_overs_prohibited": true,
        "target_mode": "prior_innings_plus_one",
        "allow_declaration": false,
        "allow_draw": false,
        "allow_manual_completion": false,
        "explicit_match_completion_boundary": "none"
      },
      "sides": [
        {
          "side_code": "home",
          "side_kind": "academy",
          "team_id": "uuid"
        },
        {
          "side_code": "away",
          "side_kind": "external",
          "display_name": "Northside CC"
        }
      ],
      "participants": [
        {
          "side_code": "home",
          "participant_kind": "internal",
          "player_id": "uuid",
          "batting_order_position": 1
        },
        {
          "side_code": "away",
          "participant_kind": "external",
          "display_name": "External Batter 1",
          "batting_order_position": 1
        }
      ]
    }

The real request schema is strict: it rejects unknown fields, missing required fields, duplicate orders, invalid side combinations, an innings sequence that does not match the selected capability, a one-day limit that is missing, non-positive, or not divisible by 30, a non-six-ball one-day over length, any client-supplied one-day quota, player IDs outside the configured academy team, account fields on external participants, unsupported reserved dismissal identifiers, and client-supplied derived score fields. For one-day, the request supplies its legal-ball limit and the response derives the quota as one fifth of that limit (for example, 240 → 48). `format`, `policy_code`, and `capability_profile` must use the exact canonical values above; `t20`, `one_day`, and `other_manual` are rejected with 422. The capability profile derives allowed completion modes, result codes, dismissal types, transition types, the explicit Match-completion boundary, and the one-day quota; callers cannot supply contradictory capability fields or code sets. Policy-supplied `other` values are required before scoring; T20 and test retain their fixed capability values, while one-day supplies only its permitted legal-ball limit. The list above is illustrative and must contain the configured XI.

Response: Match configuration summary containing Match ID/version, the
resolved locked policy, two side snapshots, fixed participants in batting
order, lifecycle_state scheduled, scoring_authority delivery_history, and
configured_at. The resolved policy includes the capability's sequence, legal
ball/over/wicket limits, quota, dismissal/transition sets, innings and Match
completion modes, target mode, explicit Match-completion boundary, and valid result codes; these response values
are the source used by later handlers.

Conflicts: 401 for missing/invalid authentication, 403 for role/scope failure, 404 for unknown Match, 409 for stale Match version or already locked configuration, 422 for invalid configuration.

## Start an innings

POST /matches/{match_id}/innings

Request:

    {
      "match_version_number": 4,
      "innings_number": 1,
      "opening_striker_participant_id": "uuid",
      "opening_non_striker_participant_id": "uuid",
      "opening_bowler_participant_id": "uuid"
    }

The server reads the batting side from the locked `innings_sequence` at the requested position and assigns the other configured side as fielding side. It checks that the selected participants are fixed and valid, initializes a target only for innings 2 of a T20/one-day capability after innings 1 is complete, and creates the innings plus the opening transition event atomically. Test innings follow `[A, B, A, B]`; other requires its explicit sequence. The new innings projection starts with zero current-innings counters; only Match-level aggregate/result state reads completed prior innings.

Response: innings ID/version, innings number, side snapshots, active batter/bowler IDs, target if any, zeroed derived totals, and lifecycle_state in_progress.

## Read innings and scorecard

GET /matches/{match_id}/innings/{innings_id}

Returns the persisted current innings projection, active participants, completed overs, participant summaries, target/chase status, canonical `blocking_state`, and version. It does not replay the entire delivery history during a normal read. A Match-level `match_abandoned` blocker is serialized even though the underlying current Innings lifecycle remains `pending` or `in_progress`; no independent Innings abandonment state is returned.

GET /matches/{match_id}/scorecard

Returns Match metadata, configured sides, innings summaries in order, batting/bowling/fielding/extras summaries, fall of wickets, overs display, target/result, canonical Match-derived `blocking_state`, and the authority/projection revision. The response is usable for legacy and scored Matches; legacy Matches identify their legacy aggregate authority and do not fabricate deliveries.

GET /matches/{match_id}/innings/{innings_id}/deliveries?after_sequence=0&limit=100

Returns a bounded, ordered delivery history with active revision facts and correction provenance. limit has a safe maximum. The endpoint never accepts an unbounded history request and never exposes superseded revision payloads as active facts without their revision state.

## Select the next bowler

GET /matches/{match_id}/innings/{innings_id}/next-bowler

Returns eligible and ineligible fixed fielding-side participants, quota usage, previous-over restriction, and current version. It is read-only and does not select a bowler.

POST /matches/{match_id}/innings/{innings_id}/next-bowler

Request:

    {
      "innings_version_number": 12,
      "bowler_participant_id": "uuid"
    }

The selected bowler must be on the fielding side, active/eligible, and within quota. The command records a transition event and returns the new innings version. An explicit authorized override may be represented by a policy-approved override field with a bounded reason; no implicit quota bypass exists.

## Select the next batter and return from injury

POST /matches/{match_id}/innings/{innings_id}/next-batter

Request:

    {
      "innings_version_number": 18,
      "batter_participant_id": "uuid",
      "replacing_participant_id": "uuid",
      "reason": "dismissal"
    }

The command validates the active-batter vacancy, fixed batting order, participation state, and any retirement restrictions, then records an explicit transition. The innings lifecycle remains `in_progress`; a delivery append is rejected while the vacancy leaves fewer than two active batters, and the selected batter must restore a valid pair before scoring can continue.

POST /matches/{match_id}/innings/{innings_id}/retired-hurt

Request:

    {
      "innings_version_number": 20,
      "participant_id": "uuid",
      "reason": "injury"
    }

The command records the `retired_hurt` transition, changes the participant to
`retired_hurt`, and exposes the resulting batting vacancy without creating a
WicketEvent or incrementing wickets. The innings lifecycle remains
`in_progress`; delivery append is blocked until either a valid next-batter
selection or an allowed return restores two active batters. The command is
accepted for the initial
T20, one-day, and test capabilities, and for `other` only when its locked
transition set lists `retired_hurt`.

POST /matches/{match_id}/innings/{innings_id}/retired-hurt-return

Request:

    {
      "innings_version_number": 21,
      "participant_id": "uuid",
      "reason": "cleared to return"
    }

A return is allowed only when the policy and current active-batter state permit it. A returned participant becomes `active`, the innings remains `in_progress`, and a returned participant does not create a new identity or erase prior history.

## Append a delivery

POST /matches/{match_id}/innings/{innings_id}/deliveries

Request:

    {
      "innings_version_number": 32,
      "attempted_sequence": 27,
      "striker_participant_id": "uuid",
      "non_striker_participant_id": "uuid",
      "bowler_participant_id": "uuid",
      "runs_off_bat": 4,
      "extras": {
        "wide_runs": 0,
        "no_ball_penalty_runs": 0,
        "bye_runs": 0,
        "leg_bye_runs": 0,
        "penalty_runs": 0
      },
      "wicket": {
        "dismissal_type": "caught",
        "dismissed_participant_id": "uuid",
        "fielders": [
          {"participant_id": "uuid", "role": "catcher"}
        ]
      }
    }

All IDs must be fixed Match participants. `extras` is strict and `bye_runs` and `leg_bye_runs` cannot both be nonzero. `runs_off_bat`, `wide_runs`, `bye_runs`, `leg_bye_runs`, and `penalty_runs` accept only integers from `0` through `2,147,483,647`; `no_ball_penalty_runs` accepts only `0` or `1`; the recomputed delivery total and all aggregate totals must not exceed `2,147,483,647`. Negative values, values above those limits, and aggregate overflow return 422 before persistence. A no-ball penalty is 0 or 1; a wide component includes its required penalty. `wicket` is one optional object, never an array; its ordered `fielders[]` collection is canonical and the client never supplies a separate primary-fielder field. Bowled, LBW, hit-wicket, and retired-out require zero fielders; caught, caught-and-bowled, and stumped require exactly one `catcher`, `bowler`, and `keeper` respectively; run-out requires at least one fielder and permits multiple ordered fielders. A second, duplicate, or conflicting wicket payload returns 422 before persistence. Reserved `obstructing_the_field`, `hit_the_ball_twice`, and `timed_out` values return 422 for every current capability. The client does not send total_runs, is_legal, over_number, ball_in_over, balls_faced, bowler_conceded_runs, strike_after, primary_fielder_participant_id, or projection totals.

Response: delivery ID, attempted sequence, active revision, server-derived component total, legal status, over/ball position, balls faced, bowler-conceded runs, wicket result with the ordered `fielders[]` collection, any derived `primary_fielder_participant_id`, updated active batter/bowler IDs, updated innings totals and version, and the canonical `blocking_state`. The primary pointer is derived from the first returned fielder association, or is null when the collection is empty.

The command is one transaction. It validates expected version, attempted sequence, lifecycle, selections, policy, and all cross-field rules; inserts the parent/revision and updates projections; writes allowed audit/outbox records; then commits. A rejected or stale request leaves no delivery, projection, audit, or outbox mutation.

## Correct a delivery

POST /matches/{match_id}/innings/{innings_id}/deliveries/{delivery_id}/correction

Request:

    {
      "innings_version_number": 40,
      "match_version_number": 80,
      "expected_revision_number": 1,
      "reason": "Scorer corrected a caught dismissal",
      "replacement": {
        "striker_participant_id": "uuid",
        "non_striker_participant_id": "uuid",
        "bowler_participant_id": "uuid",
        "runs_off_bat": 0,
        "extras": {
          "wide_runs": 0,
          "no_ball_penalty_runs": 0,
          "bye_runs": 0,
          "leg_bye_runs": 0,
          "penalty_runs": 0
        },
        "wicket": null
      }
    }

The server requires the current Match and Innings versions, then enters the
transaction-local `correction_reprocessing` phase only when the Match is
`completed`. It appends an immutable replacement revision, supersedes the
expected active revision, replays from the corrected attempt through all
affected innings, and updates all affected projections. The phase is not
committed or visible to normal reads; no ordinary scoring, completion,
abandonment, or second correction can run while that transaction holds the
Match boundary. It preserves revision author, timestamp, reason, predecessor,
and supersession history. No void state, direct revision replacement, or hard
deletion is available.

For an eligible `in_progress` Match, the same append/replay operation runs
without reopening the Match lifecycle; only the completed-Match path uses the
transaction-local phase. An abandoned Match is not a correction target.

If the corrected active history remains terminal and compatible, the command
commits `correction_reprocessing → completed`. If it is compatible but no
longer terminal, it commits `correction_reprocessing → in_progress` with
result `pending` and exposes the rebuilt state. If a later explicit
batter/bowler transition is incompatible, it may commit the Match as
`in_progress` with the affected Innings lifecycle
`reconciliation_required`; that Innings' `blocking_state.kind` is then
`reconciliation_required` and blocks scoring and completion until another
authorized correction replay clears it. If a safe projection cannot be
produced, it rolls back and returns 409. An abandoned Match is not reopened by
this feature. A stale Match or Innings version, wrong expected revision,
duplicate active revision, or unresolved transition conflict returns 409. No
direct revision replacement or deletion endpoint exists.

## Complete innings and Match

POST /matches/{match_id}/innings/{innings_id}/completion

Request:

    {
      "innings_version_number": 55,
      "completion_kind": "target_reached",
      "reason": null
    }

`completion_kind` is one of `all_out`, `legal_ball_limit`, `target_reached`,
`declaration`, or `manual`; only values listed by the locked capability are
accepted. Automatic completion is verified from delivery-derived state rather
than trusted from the request. `manual` is an innings mode only for a capability
that lists it, and `declaration` is a test innings mode. `abandonment` is not
accepted by this endpoint and returns 422. The response contains completion
reason, totals, target status, canonical `blocking_state`, and Match version.
For a fixed-over innings, if one delivery satisfies both target reach and a
wicket or legal-ball limit, the server returns `target_reached` as the
completion reason while retaining all observed wicket and delivery facts.

POST /matches/{match_id}/completion

Request:

    {
      "match_version_number": 80,
      "completion_kind": "derived_result",
      "reason": null
    }

`completion_kind` is `derived_result`, `draw`, `declared`, `manual`, or
`abandonment`. For every non-abandonment value, the server verifies the locked
required innings and explicit Match-completion boundary and derives
`result_code`, `result_details`, and compatibility result text.
`derived_result` is accepted only when the automatic target or aggregate
precondition is true. For test, `draw`, `declared`, and `manual` are accepted
only immediately after a completed innings and before an automatic result. For
`other`, `manual` is accepted only at its locked
`explicit_match_completion_boundary`. They cannot override an automatic
result. `abandonment` is accepted from any non-terminal Match without
unresolved reconciliation as the administrative terminal path and produces
`no_result`; it makes the Match
`abandoned` and prevents later scoring or completion. The current Innings keeps
its underlying `pending` or `in_progress` lifecycle, receives no completion
transition, and serializes `blocking_state.kind = match_abandoned`; completed
prior Innings remain completed. `Match.lifecycle_state = abandoned` is the
abandonment source of truth and `result_code = no_result` is derived, not
independently supplied. Completion stages only the allowed
coalesced current-state refresh. No undo endpoint exists in this feature;
amendments use the correction endpoint.

## Data Quality boundary

GET /data-quality

This existing route is Head-Coach-only. It returns bounded scoring findings
without changing scoring rows, projections, revisions, audit, or outbox state.
Head Coaches may view the findings; the authorized GET may evaluate the
bounded current check as part of serving that read. Assistant Coaches and
Players receive 403, even when they have scoped Match read access. No role has
a separate trigger or re-run operation in this feature.
Scoring findings cover replay/projection mismatch, duplicate or conflicting
active sequences, invalid Match/player/team identities, lifecycle/state
violations, an Innings lifecycle of `reconciliation_required`, and legacy-data divergence or
malformed historical state.

The existing `POST /data-quality/remediations` path is also Head-Coach-only and
remains a separate, confirmation-gated remediation surface for its pre-existing
non-scoring quality actions. It MUST NOT repair a scoring finding or mutate a
delivery, delivery revision, innings projection, or Match scoring result.
Scoring data is amended only through the delivery-correction command above,
which follows the normal scoring authorization: Head Coaches and appropriately
scoped Assistant Coaches may correct; Players may not.

## Legacy performance boundary

Existing Match batting/bowling/fielding performance endpoints remain readable.
For a Match with `scoring_authority = legacy_aggregate`, the existing
aggregate-only read/write behavior remains available and no delivery history is
assumed. When scoring configuration locks a Match into
`scoring_authority = delivery_history`, delivery-derived projections become
the sole scoring authority; every direct aggregate write, including one that
happens to equal the derived values, returns 409 with the scoring-authority
boundary. Academy-compatible projections may be synchronized to legacy rows
with derived provenance, but cannot become an alternate scoring source. There
is no implicit migration from `legacy_aggregate` to `delivery_history`.

## Error envelope

All errors use the repository's existing structured HTTP error shape with a stable code, message, request ID, and optional field details:

| Status | Meaning |
|---|---|
| 401 | Missing, invalid, inactive, or expired authentication |
| 403 | Role or current team-scope denial; Player attempted mutation |
| 404 | Match, innings, participant, or delivery not visible/found |
| 409 | Stale OCC version, duplicate sequence, locked policy, invalid lifecycle transition, correction-reprocessing conflict, revision conflict, scoring-authority conflict, or reconciliation conflict |
| 422 | Strict schema, component, participant, policy, or cross-field validation failure |
