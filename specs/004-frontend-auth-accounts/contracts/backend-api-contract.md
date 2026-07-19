# Backend API Contract (New & Modified Endpoints)

**Feature**: 004-frontend-auth-accounts
**Date**: 2026-07-19

## Existing Endpoints (from 002-auth-api-security)

All existing auth endpoints are consumed as-is. Refer to `specs/002-auth-api-security/contracts/auth-endpoints.md` for full contract details.

| Endpoint | Method | Used By |
|----------|--------|---------|
| `/api/v1/auth/login` | POST | LoginPage |
| `/api/v1/auth/refresh` | POST | AuthProvider (session restore), apiClient (token refresh) |
| `/api/v1/auth/logout` | POST | LogoutButton |
| `/api/v1/auth/me` | GET | AuthProvider (after login/refresh) |

## New Endpoint: PATCH /api/v1/auth/me

Update the authenticated user's profile (first name and last name).

**Auth**: Required (Bearer token)

### Request

```json
{
  "first_name": "John",
  "last_name": "Smith"
}
```

### Success Response (200)

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

### Error Responses

- `401 Unauthorized`: `{"detail": "Not authenticated"}`
- `422 Unprocessable Entity`: Validation errors (empty first_name or last_name)

### Backend Implementation Notes

- Add `ProfileUpdate` Pydantic schema in `backend/src/schemas/auth.py` with `first_name: str` and `last_name: str` (both required).
- Add route handler in `backend/src/routes/auth.py`.
- Uses existing `get_current_user` dependency for auth.
- Returns the same `UserResponse` shape as `GET /me`.

## Assumed Endpoint: POST /api/v1/users/{id}/change-password

Change the authenticated user's password. The `{id}` is the current user's ID from auth state.

**Auth**: Required (Bearer token)

### Request

```json
{
  "new_password": "NewP@ssw0rd!2026",
  "confirm_password": "NewP@ssw0rd!2026"
}
```

### Success Response (204)

No content. Backend revokes all active sessions for this user.

### Error Responses

- `401 Unauthorized`: `{"detail": "Not authenticated"}`
- `422 Unprocessable Entity`: Password policy violation or confirmation mismatch

### Frontend Usage Notes

- On 204: clear auth state, redirect to `/login` with "Your password was changed. Please sign in again."
- On error: display field-level validation errors; do not clear auth state.
- The `{id}` for the URL is obtained from `user.id` in the auth state.

## CSRF Token Handling

All state-changing requests that use session cookies (refresh, logout) must include:

```
Header: X-CSRF-Token: <value from csrf_token cookie>
```

The `csrf_token` cookie is readable (not HttpOnly). The `refresh_token` cookie is HttpOnly and must not be read by the frontend.

## Credential Inclusion

All requests to `/api/v1/auth/*` endpoints must use `credentials: "include"` to send cookies.
