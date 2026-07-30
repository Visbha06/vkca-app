# API Contracts: Coaches Portal

**Feature**: 007-coaches-portal
**Base URL**: `/api/v1`

All endpoints require a valid Bearer token in the `Authorization` header.

---

## GET /coaches

List coaches with server-side filtering and pagination.

**Authorization**: Head Coach, Assistant Coach

### Query Parameters

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `status` | `"active" \| "inactive" \| "all"` | No | `active` | Filter by account status |
| `page` | `integer` (≥1) | No | `1` | Page number |
| `page_size` | `integer` (1–100) | No | `12` | Items per page |

### Response `200`

```json
{
  "coaches": [
    {
      "id": "uuid",
      "first_name": "string",
      "last_name": "string",
      "email": "string",
      "role": "head coach | assistant coach",
      "is_active": true,
      "version_number": 1,
      "created_at": "2026-07-28T00:00:00Z",
      "updated_at": "2026-07-28T00:00:00Z",
      "teams": [
        { "id": "uuid", "name": "string" }
      ]
    }
  ],
  "page": 1,
  "page_size": 12,
  "total_coaches": 3,
  "total_pages": 1,
  "has_previous": false,
  "has_next": false
}
```

### Ordering

1. Head Coach before Assistant Coach
2. Last name ascending
3. First name ascending
4. User ID ascending (tiebreaker)

### Errors

| Status | Detail | Condition |
|--------|--------|-----------|
| `401` | `"Not authenticated"` | Missing/invalid Bearer token |
| `403` | `"Not authorized"` | Player-role user |

---

## POST /coaches

Create an Assistant Coach account with optional team assignments. Returns a one-time temporary password.

**Authorization**: Head Coach only

### Request Body

```json
{
  "first_name": "string (1–100)",
  "last_name": "string (1–100)",
  "email": "string (valid email, 1–255)",
  "team_ids": ["uuid", ...]  // optional, may be empty
}
```

### Response `201`

```json
{
  "id": "uuid",
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "role": "assistant coach",
  "is_active": true,
  "version_number": 1,
  "created_at": "2026-07-28T00:00:00Z",
  "updated_at": "2026-07-28T00:00:00Z",
  "temporary_password": "string (shown once)",
  "teams": [
    { "id": "uuid", "name": "string" }
  ]
}
```

### Errors

| Status | Detail | Condition |
|--------|--------|-----------|
| `400` | `"first_name: ..."` | Validation failure (field-level) |
| `401` | `"Not authenticated"` | Missing/invalid Bearer token |
| `403` | `"Not authorized"` | Not Head Coach |
| `409` | `"A user with email '...' already exists."` | Duplicate email |

---

## GET /coaches/{coach_id}

Get a single coach's details including full team list.

**Authorization**: Head Coach, Assistant Coach (active coaches only for AC)

### Response `200`

Same shape as individual coach in `GET /coaches` response list.

### Errors

| Status | Detail | Condition |
|--------|--------|-----------|
| `401` | `"Not authenticated"` | Missing/invalid Bearer token |
| `403` | `"Not authorized"` | Assistant Coach requesting inactive coach details |
| `404` | `"Coach not found"` | Invalid ID or non-coach user |

---

## PUT /coaches/{coach_id}/teams

Replace a coach's complete team assignment set atomically.

**Authorization**: Head Coach only

### Request Body

```json
{
  "team_ids": ["uuid", ...],
  "version_number": 3
}
```

### Response `200`

Coach object with updated `teams` and incremented `version_number`.

### Errors

| Status | Detail | Condition |
|--------|--------|-----------|
| `400` | `"team_ids: ..."` | Validation failure |
| `401` | `"Not authenticated"` | Missing/invalid Bearer token |
| `403` | `"Not authorized"` | Not Head Coach, or coach is inactive |
| `409` | `"Stale version N for users entity {id}"` | Version mismatch |

---

## POST /users/{user_id}/reactivate

Reactivate a deactivated coach account.

**Authorization**: Head Coach only

### Response `200`

User object with `is_active: true` and incremented `version_number`.

### Errors

| Status | Detail | Condition |
|--------|--------|-----------|
| `401` | `"Not authenticated"` | Missing/invalid Bearer token |
| `403` | `"Not authorized"` | Not Head Coach, or attempting self-reactivation (N/A — self-deactivation prevented) |
| `404` | `"User not found"` | Invalid ID |

---

## POST /users/{user_id}/disable (Modified)

Existing endpoint. **Change**: The `is_active = false` update and session revocation must now be atomic (single transaction). Previously the endpoint committed after each step. Ensure both the `is_active` update, `version_number` increment, and `revoke_user_sessions` call happen within one `session.commit()` boundary.

**Behavior unchanged**: Returns 403 if Head Coach attempts self-disable.
