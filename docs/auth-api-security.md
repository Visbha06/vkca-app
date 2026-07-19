# Authentication, Authorization, and API Security

The VKCA backend authenticates coaches and player with server-hashed passwords,
short-lived access tokens, rotating refresh sessions, role-based permissions,
login throttling, CSRF protection, and a credential-free security audit trail.
There is no self-registration; a Head Coach creates and manages all accounts.

## Key flows

### Initial setup

Apply the database migrations, then seed the first Head Coach from `backend/`:

```bash
uv run alembic upgrade head
uv run python scripts/seed_head_coach.py
```

The development defaults are `headcoach@vkca.test` and
`SuperSecur3!P@ss`. They are intentionally public bootstrap credentials and
must not be used in a deployed environment. Set `HEAD_COACH_EMAIL`,
`HEAD_COACH_PASSWORD`, `HEAD_COACH_FIRST_NAME`, and `HEAD_COACH_LAST_NAME`
before running the script in any shared or production environment. The script
does not overwrite an existing account.

### Login and session use

1. `POST /api/v1/auth/login` accepts an email and password.
2. A successful login creates an independently revocable server-side session,
   returns a 30-minute bearer access token, and sets `refresh_token` and
   `csrf_token` cookies.
3. Clients keep the access token in memory and send it as
   `Authorization: Bearer <token>`. They must not persist it in browser storage.
4. `POST /api/v1/auth/refresh` rotates both cookies and returns a new access
   token. The request must include the CSRF cookie value in `X-CSRF-Token`.
5. Reuse of a rotated refresh token revokes its entire token family.
6. `POST /api/v1/auth/logout` requires the same CSRF header, revokes only the
   current session, and clears both cookies.

Refresh sessions expire after seven days of inactivity or after a 30-day
absolute lifetime. Password changes and account disablement revoke every
active session belonging to the affected user.

### Roles

| Role | Permissions |
|---|---|
| Head Coach | Full cricket-data access plus user, role, and session administration |
| Assistant Coach | Read and write cricket data; no user administration |
| Player | Read-only access to cricket data |

Authorization loads the current role from the database on every request, so a
role change takes effect immediately. Missing authentication returns `401`;
authenticated requests without permission return `403`.

## API surface

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public, rate-limited | Establish a session and issue tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh cookie + CSRF | Rotate the refresh session |
| `POST` | `/api/v1/auth/logout` | Active session + CSRF | Revoke the current session |
| `GET` | `/api/v1/auth/me` | Authenticated | Return profile and current-session metadata |
| `GET` | `/api/v1/auth/audit-log` | Head Coach | Filter and page security audit events |
| `POST` | `/api/v1/users` | Head Coach | Create an account with a plaintext password that is hashed server-side |
| `GET` | `/api/v1/users` | Head Coach | List accounts |
| `PATCH` | `/api/v1/users/{id}/role` | Head Coach | Change an account role |
| `POST` | `/api/v1/users/{id}/disable` | Head Coach | Disable an account and revoke its sessions |
| `POST` | `/api/v1/users/{id}/revoke-sessions` | Head Coach | Revoke every active session for an account |
| `POST` | `/api/v1/users/{id}/change-password` | Self or Head Coach | Replace the password and revoke all sessions |

All cricket-data routes require authentication. Head and Assistant Coaches may
perform writes; Player access is read-only.

## Security behavior

- Passwords must be 12–128 characters and include uppercase, lowercase, digit,
  and special characters. They are stored as Argon2id hashes and never returned.
- Access JWTs use HS256 and include `sub`, `sid`, `role`, `jti`, `iat`, and
  `exp`. The database role and session state remain authoritative.
- Raw refresh tokens are stored only in HttpOnly, SameSite=Lax cookies; the
  database stores SHA-256 hashes. Cookies are marked Secure on HTTPS requests.
- Login permits five failures per normalized email and client IP in a rolling
  15-minute window; further attempts return `429` until the window advances.
- Login failures use the same `401 Invalid credentials` response for unknown
  email, wrong password, and disabled accounts.
- Authentication, authorization, role, password, revocation, refresh, reuse,
  and throttling events are audited without passwords, tokens, hashes, or keys.

## Configuration

Copy `backend/.env.example` to the repository-root `.env` used by the settings
loader and replace all placeholders. `JWT_SECRET` is required and must be a
unique high-entropy value that is never committed.

| Variable | Default | Meaning |
|---|---:|---|
| `DATABASE_URL` | none | Async PostgreSQL connection URL |
| `JWT_SECRET` | none | Required HS256 signing secret |
| `JWT_ALGORITHM` | `HS256` | Access-token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Absolute refresh-session lifetime |
| `REFRESH_INACTIVITY_DAYS` | `7` | Refresh-session inactivity limit |
| `PASSWORD_MIN_LENGTH` | `12` | Minimum accepted password length |
| `PASSWORD_MAX_LENGTH` | `128` | Maximum accepted password length |

Production deployments must terminate HTTPS so authentication cookies receive
the Secure flag. The in-memory login limiter is appropriate for the current
single-instance deployment; multi-instance deployments require a shared
rate-limit store to enforce one global window.
