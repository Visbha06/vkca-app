# Background, Audit, RAG, and Compatibility Contract

## Transaction boundary

Every scoring command runs in one database transaction:

1. Authenticate and resolve current role/team scope.
2. Load the Match and innings roots with their expected versions.
3. Validate policy, lifecycle, fixed participants, and observed delivery facts.
4. Insert immutable event/revision rows.
5. Replay the affected innings and update derived projections.
6. Write one allowlisted Business Audit event for a command listed in the
   Business Audit table; ordinary delivery, rejected, stale, and technical
   failure paths write none.
7. Stage only allowed background/outbox work using bounded identifiers.
8. Commit, or roll back every domain, projection, audit, and outbox change together.

The ordinary delivery path does not call an external provider, publish a queue job, or stage a RAG mutation. The request returns after the authoritative delivery and live projection are durable.

## Business Audit

Extend the existing audit enums and registry with the closed scoring allowlist:

| Command | Audit behavior |
|---|---|
| Configure scoring policy and fixed participants | One event on success |
| Start innings | One event on success |
| Select next batter/bowler or approved quota override | No event |
| Retired hurt/return | No event |
| Explicit manual completion | One event on success |
| Complete innings or Match | One event on success |
| Correct a delivery revision | One event on success, with bounded reason and revision IDs |
| Ordinary delivery append | No event |
| Validation failure, rejected scope, stale version, technical failure | No event |

Audit target metadata contains Match/innings/delivery identifiers, action, actor context, and bounded reason. It does not contain raw delivery payloads, account secrets, or an unbounded scorecard snapshot. Audit insertion remains caller-owned and must roll back the domain change if it fails.

## Background and outbox

Successful Match completion and material correction stage the same canonical coalesced Match scoring refresh through the existing transactional outbox. The payload contains only Match ID, affected innings ID, projection revision, and a bounded reason. The work item is idempotent and coalesces repeated refresh requests for the same stable source.

The handler reloads committed Match and scoring projections at execution time. It never trusts mutation-time snapshots and never creates an ordinary-ball job. Retries are safe because the source and projection revision are stable and the operation is current-state based.

If synchronous projection rebuild is sufficient for the expected bounded innings size, a separate scoring recomputation job is not needed. The outbox remains the integration point for expensive completion/correction RAG refresh and any future bounded downstream work.

## RAG integration

Use existing Match-level RAG mutation staging for completion/correction only. Add scoring fields to the Match builder only when the builder can load bounded current-state summaries without exposing raw event history or external account data.

Rules:

- No Delivery RAG source.
- No per-delivery source reference, provider request, or queue work.
- Completion/correction source references are stable and coalescible.
- Background reload uses current committed state.
- Scope and privacy filters continue to use the existing Match/team rules.
- RAG tests cover registration, dependency closure, source loading, scope, privacy, coalescing, and correction replay if a new source is added.

## Legacy performance compatibility

Legacy MatchBattingPerformance, MatchBowlingPerformance, and MatchFieldingPerformance rows remain readable for all Matches. Their existing manual write path remains available only when Match scoring_authority is legacy_aggregate.

`scoring_authority` is the compatibility boundary. A legacy Match remains
`legacy_aggregate` when it has no authoritative delivery history; its existing
aggregate-only reads and writes remain available. Scoring configuration locks a
Match to `delivery_history` before the first scoring innings or delivery. This
feature does not implicitly migrate legacy rows or infer delivery history from
aggregate values.

For `delivery_history` Matches:

- scorecard and participant summary projections are authoritative;
- every direct write to legacy aggregate rows is rejected with a
  scoring-authority conflict, even when the submitted values happen to equal
  the delivery-derived values;
- academy participant projections may synchronize compatible fields into existing rows with a derived provenance marker;
- external participants remain in match_participant_performances and are not inserted into Player or legacy player-keyed tables;
- multi-innings statistics retain innings identity in the new projection even if a legacy compatibility row is flattened for display;
- a reconciliation check can compare adapter output with the canonical projection.

The adapter is a read/compatibility projection, never a second scoring input.

## Data Quality

Scoring quality rules are read-only and belong in the existing Data Quality registry and generated type flow. Findings include:

- active revision count is not exactly one per delivery;
- delivery component total does not equal its derived total;
- legal-ball count differs from active legal revisions;
- over contains too many legal balls or a bowler exceeds policy quota;
- striker, non-striker, bowler, wicket, or fielder is not a fixed Match participant;
- participant state and dismissal history disagree;
- innings or Match lifecycle is inconsistent with completion/result;
- persisted projection differs from a replay;
- an Innings lifecycle is `reconciliation_required` (the Match-level blocker is
  derived from that Innings state; there is no independent reconciliation
  boolean);
- legacy compatibility projection differs from canonical scoring projection;
- legacy or historical scoring state is malformed or diverges from the current
  capability/identity model.

Scoring rules only report findings. They do not repair scoring projections,
insert scoring revisions, write scoring audit events, or stage scoring
background work. Any existing non-scoring Data Quality remediation remains a
separate Head-Coach-only, confirmation-gated path and cannot accept or mutate
scoring findings. The scoring Data Quality read is also Head-Coach-only; no
public trigger or re-run endpoint is introduced. Scoring amendments use the
normal delivery-correction command, with Head Coach or appropriately scoped
Assistant Coach authorization, never the Data Quality remediation path.

## Observability and failure behavior

Scoring command logs should include request ID, Match ID, innings ID, attempted sequence where relevant, expected version, resulting version, and outcome category. Raw delivery payloads and external display names should not be logged outside the authorized response/audit boundaries.

Failures map to the API error contract:

- authorization and visibility failures are 401/403/404;
- stale versions, sequence uniqueness, lifecycle/revision conflicts, and reconciliation conflicts are 409;
- request and cross-field validation failures are 422.

No failure path may leave a delivery, revision, projection, audit event, or outbox row partially committed.
