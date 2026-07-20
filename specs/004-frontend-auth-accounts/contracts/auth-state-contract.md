# Auth State Contract

**Feature**: 004-frontend-auth-accounts
**Date**: 2026-07-19

## Interface: AuthContextValue

The `AuthContext` exposes the following shape to all consuming components:

```typescript
interface AuthContextValue {
  // State
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isInitializing: boolean;
  isLoginPending: boolean;
  isLogoutPending: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}
```

## Consumer Contract

### AuthContext.Provider

- Wraps the entire application in `main.tsx` (above `<RouterProvider>`).
- On mount: calls `POST /api/v1/auth/refresh`. On success → calls `GET /api/v1/auth/me`. Sets `isInitializing = false`.
- Exposes state and actions via `useAuth()` hook.

### useAuth() Hook

```typescript
function useAuth(): AuthContextValue
```

- Must only be called within `<AuthProvider>`.
- Throws if used outside provider.
- Returns stable action references (wrapped in `useCallback`).

### useRequireAuth() Hook (optional convenience)

```typescript
function useRequireAuth(): AuthUser
```

- Calls `useAuth()`, throws/redirects if not authenticated.
- Convenience for components that unconditionally require an authenticated user.

## Login Action Contract

```
login(email, password):
  1. Set isLoginPending = true
  2. POST /api/v1/auth/login { email, password }
     - credentials: "include"
  3. On 200: store access_token in memory
  4. GET /api/v1/auth/me (Authorization: Bearer <token>)
  5. Set user, isAuthenticated = true
  6. Redirect to preserved route or "/"
  7. On non-200: set isLoginPending = false, throw with error detail
     - 401 → "Invalid email or password."
     - 429 → "Too many sign-in attempts. Please wait and try again."
     - Network/5xx → "Unable to sign in right now. Please try again."
```

## Logout Action Contract

```
logout():
  1. Set isLogoutPending = true
  2. POST /api/v1/auth/logout
     - credentials: "include"
     - X-CSRF-Token: <csrf_token cookie value>
  3. Clear accessToken, user, isAuthenticated = false
  4. Redirect to /login
  5. On request failure: still clear local state and redirect
```

## Session Restore Contract

```
on mount (AuthProvider):
  1. isInitializing = true
  2. POST /api/v1/auth/refresh
     - credentials: "include"
     - X-CSRF-Token: <csrf_token cookie value>
  3. On 200:
     a. Store access_token in memory
     b. GET /api/v1/auth/me
     c. Set user, isAuthenticated = true
  4. On any failure: user = null, accessToken = null
  5. isInitializing = false
```

## Token Refresh Contract (for API client)

```
apiClient.request(url, options):
  1. Add Authorization: Bearer <accessToken> if available
  2. Add credentials: "include"
  3. fetch(url, options)
  4. On 401:
     a. If no refresh in progress: start refresh
        - POST /api/v1/auth/refresh (credentials + X-CSRF-Token)
        - On success: update accessToken, resolve refresh promise
        - On failure: call logout(), reject
     b. If refresh in progress: await existing refresh promise
     c. On refresh success: retry original request once
     d. On refresh failure: reject
```

## Invariants

- `accessToken` is never written to `localStorage` or `sessionStorage`.
- `refresh_token` cookie is never read by the frontend.
- `csrf_token` cookie is only read at the point of use (refresh, logout); never stored in component state.
- No component outside `auth/` module directly accesses `accessToken`.
