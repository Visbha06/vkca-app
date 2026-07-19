# Frontend Authentication and Account Management

The VK Cricket Academy portal uses backend-authoritative authentication to protect all operational routes. Coaches sign in through `/login`; successful authentication restores the requested destination, while an existing session redirects guests back into the application.

## User flows

- **Sign in and restore:** Email and password are submitted to the auth API. The access token remains in memory, and the HttpOnly refresh-token cookie restores the session after a reload.
- **Protected navigation:** Every application route requires authentication. Logged-out visitors are sent to `/login?redirect=<path>`, and authenticated visitors cannot remain on `/login`.
- **Refresh recovery:** A protected request that returns 401 triggers one shared refresh request. Successful refreshes retry the original request; failures clear local auth state and show the session-expired sign-in notice.
- **Profile settings:** User Settings opens an accessible modal with read-only email and role fields. First and last names can be updated without reloading the application.
- **Password change:** Passwords must contain 12–128 characters with uppercase, lowercase, numeric, and special characters. A successful change revokes sessions and returns the user to sign-in with a confirmation.
- **Logout:** The red sidebar action revokes the server session when possible and always clears in-memory authentication state.

The login page and settings modal support keyboard operation, visible focus, focus containment, Escape and backdrop closing, 44px minimum controls, internal modal scrolling, and layouts from 320px through 2560px.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Authenticate credentials and issue an access token plus session cookies. |
| `POST` | `/api/v1/auth/refresh` | Rotate the cookie-backed session and issue a new access token. |
| `POST` | `/api/v1/auth/logout` | Revoke the current session and clear auth cookies. |
| `GET` | `/api/v1/auth/me` | Load the current user and session metadata. |
| `PATCH` | `/api/v1/auth/me` | Update the current user's first and last name. |
| `POST` | `/api/v1/users/{id}/change-password` | Change a password and revoke the user's active sessions. |

Refresh and logout requests include credentials and the `X-CSRF-Token` header read from the `csrf_token` cookie. The refresh token is never exposed to JavaScript, and neither token is written to `localStorage` or `sessionStorage`.

## Configuration and verification

`VITE_API_BASE_URL` optionally overrides the API origin. During local development it defaults to `http://localhost:8000`; production defaults to the current origin. No new runtime dependencies or persistent frontend storage are required.

Run the verification gates with:

```bash
cd frontend
npm run lint
npm run build
npx vitest run
npx playwright test
```

The feature-specific browser journey is `frontend/e2e/auth-flow.spec.ts`. The quickstart integration entry point is `backend/tests/integration/quickstart/test_004_quickstart_flow.py`.
