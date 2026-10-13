# Data Model: Live Ball-by-Ball Match Entry

Feature 015 adds no persisted entities. It presents the existing Match and Feature 014 scoring records and holds only short-lived form/view state in the browser. PostgreSQL remains the sole persistent source of Match and score data.

## Existing authoritative entities

### Match

Source: existing Match model and MatchResponse. Identified by Match ID and optimistic-concurrency version. Relevant fields include match date, format, venue, required compatibility result text, lifecycle, scoring authority, result code/details, configured capability, side/participant snapshots, and timestamps.

Relationships: one Match has two stable home/away side identities; a side is anchored to an academy Team or to an external opponent name. A configured Match has the Feature 014 locked capability, fixed Match participants, and an ordered innings sequence.

Validation: create with the existing MatchCreate shape. Internal sides use two distinct academy Team IDs. External sides use one academy Team, its home/away position, and a nonblank opponent name. The initial result text uses the existing Scheduled value. Configuration and scoring readiness come from lifecycle, scoring authority, configuration response, and blocking state; the UI does not infer readiness from local values.

### Match side and Match participant

Source: Feature 014 configuration response and MatchResponse. Sides are stable home/away identities. Configured academy participants reference eligible Players on that side's Team. External opposition participants are Match-scoped display identities and have no User, Player, Team membership, account, or authorization relationship.

Validation: configuration must keep participant side/team assignment and distinct batting-order positions valid according to the API. The configured participant identities are locked once scoring begins. Intended batting order is a selection suggestion; actual batting sequence is determined by committed innings transitions and deliveries.

### Scoring policy and Innings

Source: Feature 014 configuration and InningsResponse. Policy carries the immutable supported format capability and innings order. Each Innings is one permitted position with batting and fielding sides, lifecycle, version, current batter/bowler identities, totals, legal-ball and over projection, target/chase values when supported, completion details, participant figures, and canonical blocking state.

Validation and transitions: the backend determines next innings, legal progress, quotas, eligibility, targets, completion, and allowed actions. The UI reads the returned policy and blocking state, submits the relevant expected Match/Innings versions, and only enables the action the backend state permits.

### Delivery, wicket, active revision, and correction provenance

Source: Feature 014 delivery/history/correction responses. A delivery records one attempted scoring event with observed striker, non-striker, bowler, bat runs, supported extra components, and zero or one supported wicket with ordered fielder roles. The active revision contributes to score projections; superseded revisions remain provenance and are not shown as additional active balls.

Validation and transitions: only the existing API decides legal status, totals, ball/over position, strike, wicket consequences, fielder validity, and replay compatibility. A correction appends an immutable replacement revision and requires its reason plus current Match, Innings, and delivery-revision versions.

### Scorecard projection

Source: Feature 014 ScorecardResponse. It is the read-only Match projection containing lifecycle/result, capability and sides, ordered Innings projections, participant performance, blocking state, Match version, and projection revision. It is the periodic refresh source for an authorized read-only in-progress view.

## Transient browser state

These values are not persisted and cannot be treated as scoring truth:

| State | Contents | Lifetime and rule |
|---|---|---|
| Match creation draft | Internal/external mode, date, format, venue, selected academy Teams or side, opponent display name | Until cancel, route exit, or successful creation. Retain valid values when a recoverable request/validation error occurs. |
| Configuration draft | Selected roster participants, intended batting order, format settings | Until the configuration command succeeds or the coach discards changes. The locked response replaces draft state. |
| Delivery/correction draft | Observed batter/bowler identities, bat runs, extras, optional wicket/fielders, and correction reason | Until commit or discard. Draft and pending states are distinct from confirmed scoring. No derived totals, legality, strike, quota, or result are stored as local authority. |
| Request state | Idle, pending, accepted, rejected/conflicted, or uncertain | A pending non-idempotent write blocks duplicate submission. A conflict/uncertain result triggers an authoritative read before the next write. |
| Read refresh state | Inactive, current, refreshing, stale, terminal, or access lost | Active only on a visible read-only view while Match lifecycle is in progress. It holds the last server response for presentation only and is discarded on scope loss. |

## Authorization and state transitions

- Every read and write is checked using the current backend user and current Team assignments. A Head Coach has full permitted Match scope. An Assistant Coach and Player require scope intersecting an academy side. An external participant/opponent does not grant scope. Players can read only.
- Match configuration, innings starts, deliveries, transitions, corrections, and completion keep the existing Feature 014 lifecycle and version transitions. Feature 015 displays canonical blocking states and routes the user to the supported action.
- For visible read-only views, the refresh state moves from inactive to active only after an authorized in-progress projection is loaded; it pauses while hidden, stops when left/terminal/unauthorized, and reports stale data after a transient read failure without replacing committed state.
