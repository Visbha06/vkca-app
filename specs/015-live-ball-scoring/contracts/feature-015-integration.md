# Feature 015 Frontend Integration Contract

This document maps Feature 015 workflows to existing APIs. Feature 014's
specification and contracts remain normative for detailed scoring request,
response, validation, lifecycle, and error schemas. Feature 015 does not add a
scoring endpoint or frontend-owned scoring rules.

## Authentication and API types

Use the shared authenticated apiClient for all requests. It owns bearer
authorization, cookie credentials, CSRF headers, token refresh, session-expiry
handling, and ApiClientError status/body parsing. Frontend types must be
generated from or kept synchronized with the backend OpenAPI/Pydantic schemas.
Do not accept client-supplied roles, Team scope, derived totals, legal status,
strike, over position, bowling figures, or Match result as authoritative.

## Match discovery and creation

| Operation | Existing endpoint | Feature 015 use |
|---|---|---|
| List Matches | GET /api/v1/matches | Return only records readable by the current authenticated scope, ordered as the existing service defines. The response stays a list of MatchResponse objects. |
| Read Match | GET /api/v1/matches/{match_id} | Existing detail read, which checks current Team scope and conceals inaccessible Matches. |
| Create Match | POST /api/v1/matches | Existing coach-authorized creation route, returning 201 and MatchResponse. Add current configuration-scope validation for Assistant Coaches at this existing boundary. |
| List academy Teams | GET /api/v1/teams?page={page}&page_size={page_size} | Use the existing paginated Team API; do not assume one page contains every Team. |
| Read Team roster | GET /api/v1/teams/{team_id}/players | Load eligible internal roster candidates for the configured academy side. |

Match creation request fields are match_date, format, venue, result, and
participants. The required initial result value is Scheduled. For an internal
Match, participants is the existing internal union variant with distinct
home_team_id and away_team_id. For an external Match, it is the existing
external variant with academy_team_id, external_opponent_name, and
academy_side. The response Match ID is passed into the Feature 015 pre-match
configuration screen, which uses the existing Feature 014 configuration API;
no new Match storage or participant API is introduced.

## Feature 014 configuration and scoring APIs

Base path is /api/v1. All calls remain protected and use the current Feature 014
authorization, schema, OCC, and status behavior.

| Workflow | Existing API surface |
|---|---|
| Configure sides, participants, policy, batting order | PUT /matches/{match_id}/configuration |
| Start innings | POST /matches/{match_id}/innings |
| Read innings projection | GET /matches/{match_id}/innings/{innings_id} |
| Read Match scorecard | GET /matches/{match_id}/scorecard |
| Read bounded active delivery history | GET /matches/{match_id}/innings/{innings_id}/deliveries?after_sequence={n}&limit={n} |
| Read next-bowler options | GET /matches/{match_id}/innings/{innings_id}/next-bowler |
| Select next bowler | POST /matches/{match_id}/innings/{innings_id}/next-bowler |
| Select next batter | POST /matches/{match_id}/innings/{innings_id}/next-batter |
| Retired-hurt and return transitions | POST /matches/{match_id}/innings/{innings_id}/retired-hurt and /retired-hurt-return |
| Append observed delivery facts | POST /matches/{match_id}/innings/{innings_id}/deliveries |
| Correct an active delivery revision | POST /matches/{match_id}/innings/{innings_id}/deliveries/{delivery_id}/correction |
| Complete an innings or Match | POST /matches/{match_id}/innings/{innings_id}/completion and /matches/{match_id}/completion |
| Abandon Match | Existing protected administrative Match abandonment workflow |

The exact payloads, canonical formats, supported extras/dismissals,
fielders, capabilities, blocking_state values, response projections, and
version fields are defined in
specs/014-match-scoring-domain/contracts/match-scoring-api.md. Client writes
must include the current relevant versions and submit only observed facts.
HTTP 409 requires a conflict explanation and an authoritative refresh. An
uncertain delivery result must not be blindly retried. A reconciliation_required
response blocks normal scoring until an already-supported recovery command is
available.

## Read-only polling

Use GET /api/v1/matches/{match_id}/scorecard for the authoritative read-only
refresh. Its Match lifecycle, ordered Innings projections, blocking state,
results, target/chase values, participant summaries, and projection revision
provide the Match and innings state shown by the operational viewer. Use a
separate existing read only if the selected read-only panel requests data that
the scorecard does not include; do not poll identical resources redundantly.

Poll at ten-second intervals only while the Match is in progress and the
read-only view is visible. Do not poll on the delivery-entry view. At most one
refresh for a view may be in flight. Stop on terminal state, view exit, hidden
view, or authorization failure (401 after shared session handling, or
scope-denied 403/404). On transient read failure, keep the last committed
projection, communicate its freshness, and wait for the next normal interval.
There is no WebSocket, public feed, or offline synchronization contract.

## Required authorization-only contract changes

1. GET /matches must apply current role and Team scope before returning Match
   records. Head Coaches retain full access; scoped Assistant Coaches and
   Players receive only Matches anchored by at least one academy Team in their
   current assignment. An external side does not widen the scope. Match detail
   and scoring reads continue to enforce their existing scope checks.
2. POST /matches must retain its existing MatchCreate shape and coach role
   guard, and apply the existing configuration-scope policy to the selected
   academy Team IDs. Head Coaches retain full access; an Assistant Coach must
   have current scope for at least one academy side. External opponent names
   are never authorization anchors.

These changes add no endpoint, request field, response field, database table,
scoring rule, or migration. Inaccessible reads remain concealed according to
the existing Match/scoring authorization conventions; invalid creation scope
is rejected by the protected backend boundary.
