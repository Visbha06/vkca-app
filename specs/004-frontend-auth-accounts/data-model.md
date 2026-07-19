# Data Model: Frontend Authentication and Account Management

**Feature**: 004-frontend-auth-accounts
**Date**: 2026-07-19

## Client-Side Entities

### AuthUser

Represents the currently authenticated user as returned by `GET /api/v1/auth/me`.

| Field | Type | Read-only | Notes |
|-------|------|-----------|-------|
| `id` | `string` (UUID) | Yes | Unique user identifier |
| `first_name` | `string` | No | Editable via `PATCH /api/v1/auth/me` |
| `last_name` | `string` | No | Editable via `PATCH /api/v1/auth/me` |
| `email` | `string` | Yes | Displayed in settings; cannot be changed by user |
| `role` | `"head coach" \| "assistant coach" \| "player"` | Yes | Backend-authoritative; displayed for informational purposes only |
| `is_active` | `boolean` | Yes | Whether the account is enabled |
| `session` | `SessionMeta` | Yes | Current session metadata |

### SessionMeta

Nested within the `GET /api/v1/auth/me` response.

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | `string` (UUID) | Current session identifier |
| `created_at` | `string` (ISO 8601) | Session creation timestamp |
| `last_used_at` | `string` (ISO 8601) | Last token refresh timestamp |
| `expires_at` | `string` (ISO 8601) | Absolute session expiration |

### AuthState

Client-side state object managed by React Context. **Not persisted to any storage.**

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `user` | `AuthUser \| null` | `null` | Current authenticated user |
| `accessToken` | `string \| null` | `null` | In-memory only; never written to storage |
| `isAuthenticated` | `boolean` | `false` | Derived: `user !== null && accessToken !== null` |
| `isInitializing` | `boolean` | `true` | True during session restoration; prevents redirect flash |
| `isLoginPending` | `boolean` | `false` | Login request in flight |
| `isLogoutPending` | `boolean` | `false` | Logout request in flight |

### AuthActions

Actions available to consumers of the auth context:

| Action | Signature | Effect |
|--------|-----------|--------|
| `login(email, password)` | `(email: string, password: string) => Promise<void>` | POST /login → store token → GET /me → update state → redirect |
| `logout()` | `() => Promise<void>` | POST /logout → clear token + user → redirect /login |
| `refreshSession()` | `() => Promise<boolean>` | POST /refresh → update token → GET /me; returns success |

### LoginCredentials

Transient; never stored after submission.

| Field | Type | Validation |
|-------|------|------------|
| `email` | `string` | Required, non-empty |
| `password` | `string` | Required, non-empty |

### ProfileUpdateRequest

Sent to `PATCH /api/v1/auth/me`.

| Field | Type | Validation |
|-------|------|------------|
| `first_name` | `string` | Required, non-empty |
| `last_name` | `string` | Required, non-empty |

### PasswordChangeRequest

Sent to `POST /api/v1/users/{id}/change-password`.

| Field | Type | Validation |
|-------|------|------------|
| `new_password` | `string` | 12–128 chars, uppercase, lowercase, digit, special char |
| `confirm_password` | `string` | Must match `new_password` |

## State Transitions

```
[App Load]
    │
    ▼
┌──────────────┐
│ INITIALIZING │ ← isInitializing=true, user=null, token=null
│  (loading)   │
└──────┬───────┘
       │ POST /refresh
       ├── success ──► ┌──────────────────┐
       │               │ AUTHENTICATED    │ ← user set, token set
       │               │ (on any route)   │
       │               └──┬───────┬───────┘
       │                  │       │
       │                  │       │ POST /logout or
       │                  │       │ refresh failure
       │                  │       │
       │                  │       ▼
       │                  │  ┌──────────────┐
       │                  │  │ LOGGING OUT  │
       │                  │  └──────┬───────┘
       │                  │         │ clear state
       │                  │         ▼
       ├── failure ───────┼──► ┌──────────────┐
       │                  │   │ UNAUTHENTICATED│ ← user=null, token=null
       │                  │   │  (/login page) │
       │                  │   └───────┬───────┘
       │                  │           │ POST /login success
       │                  │           └──────► back to AUTHENTICATED
       │                  │
       │                  │ password change success
       │                  └──────► clear state → UNAUTHENTICATED
       │
       └── (never happens: initial load always attempts /refresh)
```

## API Response Types (mirroring backend Pydantic schemas)

### LoginResponse

```typescript
interface LoginResponse {
  access_token: string;
  token_type: "bearer";
}
```

### RefreshResponse

```typescript
interface RefreshResponse {
  access_token: string;
  token_type: "bearer";
}
```

### ApiError

```typescript
interface ApiError {
  detail: string;
}
```

## Relationships

- **AuthState** wraps **AuthUser** — 1:1 while authenticated.
- **AuthUser** contains **SessionMeta** — 1:1 per session.
- **LoginCredentials** → POST /login → **LoginResponse** → **AuthState** (transient flow).
- **ProfileUpdateRequest** → PATCH /me → updated **AuthUser** (in-place mutation of state).
- **PasswordChangeRequest** → POST /users/{id}/change-password → clear **AuthState** (terminal transition).
