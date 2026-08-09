# Data Quality API Contract

Base path: `/api/v1`

All endpoints in this document require an authenticated user with role
`head coach`. Assistant Coaches and Players receive the existing HTTP 403
response (`{"detail":"Not authorized"}`) and do not receive findings.

## `GET /api/v1/data-quality`

Evaluates current academy state, applies optional filters, and returns one
bounded page plus the unfiltered summary. The request does not write domain or
Business Audit data.

### Query parameters

| Parameter | Type | Default/values |
| --- | --- | --- |
| `page` | integer | `1`, minimum `1` |
| `page_size` | integer | `20`, minimum `1`, maximum `100` |
| `severity` | enum | `critical`, `warning`, `info` |
| `domain` | enum | `players`, `teams`, `rosters`, `coaches`, `calendar` |
| `rule_id` | registered rule ID | One of the 17 initial rule IDs; no arbitrary rule execution. |

Filters combine with AND semantics. The summary remains unfiltered so the
Head Coach can distinguish academy health from the current view. Invalid enum,
rule, page, or page-size values use the application’s request-validation
response.

### Response `200`

```json
{
  "findings": [
    {
      "finding_id": "coach.inactive_assigned:coach-uuid:team-uuid",
      "rule_id": "coach.inactive_assigned",
      "severity": "warning",
      "domain": "coaches",
      "entity_type": "coach_assignment",
      "entity_id": "coach-uuid",
      "entity_label": "Alex Morgan — U13 Falcons",
      "title": "Inactive Assistant Coach remains assigned",
      "explanation": "Alex Morgan is inactive but still assigned to U13 Falcons. The assignment can confuse current team responsibility.",
      "recommended_action": "Remove this one Assistant Coach assignment after confirmation, or review it in Coaches Portal.",
      "direct_remediation": {
        "action": "remove_inactive_assistant_assignment",
        "coach_id": "coach-uuid",
        "team_id": "team-uuid",
        "expected_coach_version": 4,
        "confirmation_required": true
      },
      "related_entities": [
        {
          "entity_type": "team",
          "entity_id": "team-uuid",
          "entity_label": "U13 Falcons"
        }
      ]
    }
  ],
  "summary": {
    "total_findings": 1,
    "critical_count": 0,
    "warning_count": 1,
    "info_count": 0,
    "domain_counts": {
      "players": 0,
      "teams": 0,
      "rosters": 0,
      "coaches": 1,
      "calendar": 0
    }
  },
  "page": 1,
  "page_size": 20,
  "total_findings": 1,
  "total_pages": 1,
  "has_previous": false,
  "has_next": false
}
```

`findings` contains no more than `page_size` items. `total_findings` is the
filtered total; `summary.total_findings` and all summary severity/domain counts
are unfiltered. Findings are ordered by severity, domain, entity label,
`rule_id`, and stable finding identifier.

`entity_id` may be null for an academy-level sole Head Coach integrity finding.
Related entities are sorted by entity type and identifier. A healthy academy
returns an empty `findings` list and zero counts rather than a special error.

### Finding contract

Every finding includes:

- stable `finding_id` and `rule_id`;
- severity, domain, entity type, optional primary entity ID, and human label;
- title, explanation, and recommended action;
- optional `direct_remediation`, which is null for navigation/manual findings;
- optional deterministic related entities.

The only direct-remediation action values are:

| Action | Finding eligibility | Version field |
| --- | --- | --- |
| `normalize_roster_order` | Selected team has an ordering defect and 7–15 distinct active players. | `expected_team_version` |
| `remove_inactive_player` | Selected membership is current/inactive and removing it leaves a valid active roster. | `expected_team_version` |
| `remove_inactive_assistant_assignment` | Selected relationship belongs to an inactive Assistant Coach. | `expected_coach_version` |

The sole Head Coach integrity finding, including an inactive or incompletely
assigned Head Coach, never exposes a removal action.

## `POST /api/v1/data-quality/remediations`

Applies exactly one explicitly supported correction through the corresponding
domain service. The request is rejected if the finding is no longer current,
the target changed, the role/status changed, or the expected version is stale.

### Request variants

```json
{
  "finding_id": "roster.order_gap:team-uuid",
  "action": "normalize_roster_order",
  "team_id": "team-uuid",
  "expected_team_version": 7,
  "confirmed": true
}
```

```json
{
  "finding_id": "player.inactive_rostered:player-uuid:team-uuid",
  "action": "remove_inactive_player",
  "team_id": "team-uuid",
  "player_id": "player-uuid",
  "expected_team_version": 3,
  "confirmed": true
}
```

```json
{
  "finding_id": "coach.inactive_assigned:coach-uuid:team-uuid",
  "action": "remove_inactive_assistant_assignment",
  "coach_id": "coach-uuid",
  "team_id": "team-uuid",
  "expected_coach_version": 4,
  "confirmed": true
}
```

The Pydantic request is a discriminated union or equivalent strict typed
allowlist. Extra fields and arbitrary target maps are rejected. `confirmed`
must be true for removal/relationship actions.

### Response `200`

```json
{
  "status": "applied",
  "action": "remove_inactive_assistant_assignment",
  "message": "The inactive Assistant Coach assignment was removed.",
  "affected_entity_id": "coach-uuid",
  "audit_action": "coach.team_assignments_updated"
}
```

The corresponding existing Business Audit action is staged exactly once in the
same transaction as the mutation. Scans and remediation reads never create
Business Audit events.

### Error behavior

| Status | Situation | UI behavior |
| --- | --- | --- |
| `400` | Unsupported action, missing confirmation, or domain precondition rejected before mutation. | Show a safe failure message; retain current findings. |
| `403` | Non-Head-Coach or unauthenticated access under existing auth behavior. | Use the existing Forbidden/session behavior. |
| `404` | Finding target or domain entity no longer exists. | Explain that the data changed and offer refresh. |
| `409` | OCC version mismatch, finding no longer current, role/status changed, or mutation conflict. | Preserve no partial change; refresh/re-evaluate. |
| `422` | Invalid query/body shape or bounds. | Use existing validation presentation. |

The backend must not return database details, SQL, or internal stack traces in
these responses.
