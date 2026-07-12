# API Contracts: Authentication Endpoints

**Feature**: 002-auth-api-security
**Date**: 2026-07-12

Base URL: `/api/v1/auth`

## Public Endpoints (no authentication required)

### POST /login

Authenticate with email and password. Returns access token in response body and sets refresh token in HttpOnly cookie.

**Request**:
```json
{
  "email": "coach@example.com",
  "password": "SecureP@ss1"
}
```

**Success Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Cookies set**:
- `refresh_token=<opaque-value>; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=2592000`
- `csrf_token=<random-value>; SameSite=Lax; Path=/api/v1/auth; Max-Age=2592000`

**Error Responses**:
- `401 Unauthorized`: `{"detail": "Invalid credentials"}` — identical for wrong email, wrong password, disabled account
- `422 Unprocessable Entity`: `{"detail": [{"loc": ["body", "email"], "msg": "..."}]}` — validation errors
- `429 Too Many Requests`: `{"detail": "Too many login attempts. Please try again later."}` — rate limited. Does not reveal whether email exists.

**Rate Limiting**: Max 5 failed attempts per (email, IP) pair per 15-minute rolling window.

**Audit Events**: `login` (success) or `failed_login` (failure)

---

### POST /refresh

Exchange a valid refresh token cookie for a new access token. Rotates the refresh token (old one revoked, new one issued).

**Request**: No body required. Requires `refresh_token` cookie and `X-CSRF-Token` header matching `csrf_token` cookie.

**Success Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Cookies set**: New `refresh_token` and `csrf_token` cookies (rotated values).

**Error Responses**:
- `401 Unauthorized`: `{"detail": "Invalid or expired session"}` — expired, revoked, or invalid refresh token
- `401 Unauthorized`: `{"detail": "Invalid or expired session"}` — token reuse detected (token family revoked)
- `403 Forbidden`: `{"detail": "CSRF token missing or invalid"}` — missing or mismatched CSRF token

**CSRF Protection**: Requires `X-CSRF-Token` header value to match `csrf_token` cookie value.

**Audit Events**: `token_refresh` (success) or `token_reuse` (reuse detected — triggers family revocation)

---

### POST /logout

Revoke the current session. Invalidates the access token and refresh token for this session only.

**Request**: No body required. Requires `refresh_token` cookie and `X-CSRF-Token` header matching `csrf_token` cookie.

**Success Response** (204): No content.

**Cookies cleared**: `refresh_token` and `csrf_token` cookies deleted (Max-Age=0, same Path).

**Error Responses**:
- `401 Unauthorized`: `{"detail": "Invalid or expired session"}`
- `403 Forbidden`: `{"detail": "CSRF token missing or invalid"}`

**Audit Events**: `logout`

---

## Protected Endpoints (authentication required)

### GET /me

Returns the authenticated user's profile, role, and current session information.

**Request Headers**: `Authorization: Bearer <access_token>`

**Success Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "first_name": "John",
  "last_name": "Smith",
  "email": "john@example.com",
  "role": "head coach",
  "is_active": true,
  "session": {
    "session_id": "660e8400-e29b-41d4-a716-446655440001",
    "created_at": "2026-07-12T10:00:00Z",
    "last_used_at": "2026-07-12T14:30:00Z",
    "expires_at": "2026-08-11T10:00:00Z"
  }
}
```

**Error Responses**:
- `401 Unauthorized`: `{"detail": "Not authenticated"}` — missing, expired, malformed, or revoked token

---

## User Management Endpoints (MODIFIED)

Base URL: `/api/v1/users`

### POST /users (MODIFIED)

Create a new user account. **Head Coach only.**

**Changes from current**:
- `hashed_password` field replaced by `password` (plaintext, validated against password policy)
- Requires `Authorization: Bearer <access_token>` header with Head Coach role

**Request**:
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "email": "jane@example.com",
  "password": "SecureP@ss1",
  "role": "assistant coach"
}
```

**Success Response** (201): Existing `UserResponse` schema (no password hash exposed).

**Error Responses**:
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Authenticated but not Head Coach
- `409 Conflict`: Email already exists
- `422 Unprocessable Entity`: Password policy violation, invalid email, etc.

### GET /users (MODIFIED)

List all users. **Head Coach only.** Requires `Authorization: Bearer <access_token>`.

### PATCH /users/{user_id}/role (NEW)

Change a user's role. **Head Coach only.** Role change takes effect immediately.

**Request**:
```json
{
  "role": "staff"
}
```

**Success Response** (200): Updated `UserResponse`.

**Audit Events**: `role_change`

### POST /users/{user_id}/disable (NEW)

Disable a user account. Revokes all active sessions. **Head Coach only.**

**Success Response** (200): Updated `UserResponse` with `is_active: false`.

**Audit Events**: `user_disablement` + `session_revocation` (one per active session)

## Existing Route Modifications

All existing routes (`/api/v1/players`, `/api/v1/teams`, `/api/v1/matches`, `/api/v1/performances`, `/api/v1/stats`) gain an `Authorization: Bearer <access_token>` header requirement and role-based access:

| Endpoint | Method | Head Coach | Assistant Coach | Staff |
|----------|--------|------------|-----------------|-------|
| `/players` | GET | ✅ | ✅ | ✅ |
| `/players` | POST | ✅ | ✅ | ❌ |
| `/players/{id}` | PUT | ✅ | ✅ | ❌ |
| `/teams` | GET | ✅ | ✅ | ✅ |
| `/teams` | POST | ✅ | ✅ | ❌ |
| `/teams/{id}/roster` | PUT | ✅ | ✅ | ❌ |
| `/matches` | GET | ✅ | ✅ | ✅ |
| `/matches` | POST | ✅ | ✅ | ❌ |
| `/performances` | POST | ✅ | ✅ | ❌ |
| `/stats` | GET | ✅ | ✅ | ✅ |

## Security Headers

All auth responses include:

| Environment | `refresh_token` Cookie | `csrf_token` Cookie |
|-------------|----------------------|---------------------|
| Development | `HttpOnly; SameSite=Lax; Path=/api/v1/auth` | `SameSite=Lax; Path=/api/v1/auth` |
| Production | `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` | `Secure; SameSite=Lax; Path=/api/v1/auth` |

Cookie names, paths, and SameSite policy settled during planning:
- Refresh token cookie: `refresh_token`
- CSRF token cookie: `csrf_token`
- CSRF header: `X-CSRF-Token`
- SameSite: `Lax`
- Path: `/api/v1/auth` (covers `/login`, `/refresh`, `/logout`)
