# Match Scoring API Contract

## Conventions

Base path: /api/v1

All endpoints require the existing bearer authentication and load the current active User from the database. Every response includes identifiers, current lifecycle state, and the relevant Match or innings version. Mutating requests include the caller's expected version. The server owns all derived scoring fields.

Authorization:

| Actor | Read in current team scope | Configure/score/correct/complete |
|---|---|---|
| Head Coach | Yes | Yes |
| Assistant Coach | Yes, when the current TeamCoach assignment covers the academy side | Yes, in that scope |
| Player | Yes, when current TeamPlayer scope covers the academy side | No |
| Other authenticated user | No | No |
| Unauthenticated or inactive user | No | No |

An external opponent side never grants access. External participants are match-scoped display identities and are not User or Player identities.

## Configure a Match

PUT /matches/{match_id}/configuration

Request:

    {
      "match_version_number": 3,
      "format": "T20",
      "policy": {
        "policy_code": "t20",
        "innings_per_side": 1,
        "legal_ball_limit": 120,
        "bowler_quota_legal_balls": 24,
        "wicket_limit": 10,
        "consecutive_overs_prohibited": true,
        "allow_declaration": false,
        "allow_manual_completion": false
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

The real request schema is strict: it rejects unknown fields, missing required fields, duplicate orders, invalid side combinations, player IDs outside the configured academy team, account fields on external participants, and client-supplied derived score fields. The list above is illustrative and must contain the configured XI or the explicit roster policy required by the selected format.

Response: Match configuration summary containing Match ID/version, locked policy, two side snapshots, fixed participants in batting order, lifecycle_state scheduled, scoring_authority delivery_history, and configured_at.

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

The server derives the batting and fielding sides from innings order, checks that the selected participants are fixed and valid, initializes target when a prior innings is complete, and creates the innings plus the opening transition event atomically.

Response: innings ID/version, innings number, side snapshots, active batter/bowler IDs, target if any, zeroed derived totals, and lifecycle_state in_progress.

## Read innings and scorecard

GET /matches/{match_id}/innings/{innings_id}

Returns the persisted current innings projection, active participants, completed overs, participant summaries, target/chase status, reconciliation status, and version. It does not replay the entire delivery history during a normal read.

GET /matches/{match_id}/scorecard

Returns Match metadata, configured sides, innings summaries in order, batting/bowling/fielding/extras summaries, fall of wickets, overs display, target/result, and the authority/projection revision. The response is usable for legacy and scored Matches; legacy Matches identify their legacy aggregate authority and do not fabricate deliveries.

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

The command validates the active-batter vacancy, fixed batting order, participation state, and any retirement restrictions, then records an explicit transition.

POST /matches/{match_id}/innings/{innings_id}/retired-hurt-return

Request:

    {
      "innings_version_number": 21,
      "participant_id": "uuid",
      "reason": "cleared to return"
    }

A return is allowed only when the policy and current active-batter state permit it. A returned participant does not create a new identity or erase prior history.

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
        "fielder_participant_id": "uuid"
      }
    }

All IDs must be fixed Match participants. extras is strict and bye_runs and leg_bye_runs cannot both be nonzero. A no-ball penalty is 0 or 1; a wide component includes its required penalty. The client does not send total_runs, is_legal, over_number, ball_in_over, balls_faced, bowler_conceded_runs, strike_after, or projection totals.

Response: delivery ID, attempted sequence, active revision, server-derived component total, legal status, over/ball position, balls faced, bowler-conceded runs, wicket result, updated active batter/bowler IDs, updated innings totals and version, and any completion/reconciliation state.

The command is one transaction. It validates expected version, attempted sequence, lifecycle, selections, policy, and all cross-field rules; inserts the parent/revision and updates projections; writes allowed audit/outbox records; then commits. A rejected or stale request leaves no delivery, projection, audit, or outbox mutation.

## Correct a delivery

POST /matches/{match_id}/innings/{innings_id}/deliveries/{delivery_id}/correction

Request:

    {
      "innings_version_number": 40,
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

The server appends an immutable revision, supersedes the expected active revision, replays from the corrected attempt, and updates all affected projections. It preserves revision author, timestamp, reason, and predecessor. A completed Match may be reopened only through this explicit correction flow; the response exposes whether the Match is now in progress or reconciliation-required.

If a later explicit batter/bowler transition is incompatible with the replay, the command commits the correction and a reconciliation-required marker only when the state is internally safe to expose; otherwise it rolls back and returns 409. A stale innings version, wrong expected revision, duplicate active revision, or unresolved transition conflict returns 409. No direct revision replacement or deletion endpoint exists.

## Complete innings and Match

POST /matches/{match_id}/innings/{innings_id}/completion

Request:

    {
      "innings_version_number": 55,
      "completion_kind": "automatic_target",
      "reason": null
    }

Automatic target, wicket-limit, and legal-ball-limit completion is server-derived. Manual completion requires the locked policy and a bounded reason. The response contains completion reason, totals, target status, and Match version.

POST /matches/{match_id}/completion

Request:

    {
      "match_version_number": 80,
      "completion_kind": "normal_result",
      "reason": null
    }

The server verifies completed innings and derives result_code, result_details, and compatibility result text. Declaration, draw, no result, and manual outcomes require policy/authorization. Completion stages only the allowed coalesced current-state refresh.

## Legacy performance boundary

Existing Match batting/bowling/fielding performance endpoints remain readable. For a Match with scoring_authority legacy_aggregate, they retain current behavior. For delivery_history Matches, direct aggregate writes return 409 with the scoring-authority boundary; derived projections are available through the scorecard and participant summary resources. Academy-compatible projections may be synchronized to legacy rows but cannot become an alternate scoring source.

## Error envelope

All errors use the repository's existing structured HTTP error shape with a stable code, message, request ID, and optional field details:

| Status | Meaning |
|---|---|
| 401 | Missing, invalid, inactive, or expired authentication |
| 403 | Role or current team-scope denial; Player attempted mutation |
| 404 | Match, innings, participant, or delivery not visible/found |
| 409 | Stale OCC version, duplicate sequence, locked policy, invalid lifecycle transition, revision conflict, or reconciliation conflict |
| 422 | Strict schema, component, participant, policy, or cross-field validation failure |
