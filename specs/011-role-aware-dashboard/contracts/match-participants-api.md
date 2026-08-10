# Match Participant API Contract

Base path: `/api/v1/matches`. This contract updates the existing backend Match
create/read behavior and adds OCC-aware update support for future callers. It
does not add a frontend Match page, modal, or dashboard Match-entry route.

## Common fields

All Match responses preserve:

```text
id, match_date, format, venue, result,
created_at, updated_at, version_number, participants
```

`format` is one of `T20`, `one-day`, `test`, or `other`.

## External Match

Request participant shape:

```json
{
  "participant_type": "external",
  "academy_team_id": "team-uuid",
  "external_opponent_name": "Northside CC",
  "academy_side": "home"
}
```

The persisted adapter maps `academy_side=home` to `home_team_id` and
`academy_side=away` to `away_team_id`. No internal participant fields are
accepted in the request.

Response participant shape:

```json
{
  "kind": "external",
  "academy_team": {"id": "team-uuid", "name": "U15 Falcons"},
  "opponent_name": "Northside CC",
  "academy_side": "home"
}
```

## Internal Match

Request participant shape:

```json
{
  "participant_type": "internal",
  "home_team_id": "home-team-uuid",
  "away_team_id": "away-team-uuid"
}
```

Response participant shape:

```json
{
  "kind": "internal",
  "home_team": {"id": "home-team-uuid", "name": "U13 Falcons"},
  "away_team": {"id": "away-team-uuid", "name": "U15 Falcons"}
}
```

## Operations

### `POST /api/v1/matches`

Accepts common Match fields plus exactly one participant request variant.
Existing Match mutation authorization is retained until a future Match-
management feature defines a narrower workflow. Invalid mixed, missing,
duplicate-side, blank-opponent, or unknown-Team payloads are rejected before
commit.

### `PUT /api/v1/matches/{match_id}`

Accepts the complete Match replacement plus `version_number`. A stale version
returns `409` and leaves both Match and any audit state unchanged. The endpoint
is backend/domain support only; no dashboard action navigates to it.

### `GET /api/v1/matches`

Retains the existing authenticated read route with the new participant response
shape. Dashboard role isolation is enforced by `DashboardService` and does not
accept client-selected scope.

## Validation and audit behavior

The Pydantic request union and database check constraint both enforce:

```text
external: one academy Team side + nonblank external opponent
internal: two different academy Teams + no external opponent
```

Match reads never create Business Audit events. Match mutations follow existing
Match audit support if one is present; no unrelated Player/account audit action
is reused. Any rejected participant mutation creates no successful Business
Audit event.

