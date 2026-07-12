# Research: Authentication, Authorization, and API Security

**Feature**: 002-auth-api-security
**Date**: 2026-07-12

## 1. JWT Library: python-jose vs PyJWT

**Decision**: `python-jose` (with `pyca/cryptography` backend)

**Rationale**:
- `python-jose` is the most widely used JWT library in the FastAPI ecosystem and is recommended in FastAPI's own documentation for OAuth2/JWT flows.
- Supports HS256 (HMAC-SHA256) natively via the `cryptography` backend — no additional dependencies beyond `cryptography` (which is already a transitive dependency via other packages).
- `PyJWT` is a lighter alternative but has a history of API instability across major versions. `python-jose` provides a more stable API surface.
- Both libraries are actively maintained. `python-jose` has broader ecosystem support for key rotation patterns (relevant if the project later transitions to RS256).

**Alternatives considered**:
- `PyJWT`: Lighter but less ecosystem support. Rejected due to API instability concerns.
- `authlib`: More fully-featured (OAuth2/OIDC server) but overkill for a simple JWT signing/verification need.

## 2. Password Hashing: Argon2id Parameters

**Decision**: Use `argon2-cffi` with `argon2.PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)`.

**Rationale**:
- `argon2-cffi` is the canonical Python binding for the Argon2 reference implementation. Actively maintained, used by Django and other major frameworks.
- Argon2id variant resists both side-channel and GPU-based attacks.
- `time_cost=3`: ~3 iterations. Balances security with login latency — three iterations take ~100-200ms on modern hardware, well within the 2-second login budget.
- `memory_cost=65536` (64 MiB): Standard OWASP recommendation for Argon2id. Sufficient to make GPU brute-force attacks expensive.
- `parallelism=4`: Matches typical 4-core server configurations; prevents excessive memory contention.
- `hash_len=32` (256-bit output): Standard length; no benefit to longer hashes for password storage.
- `salt_len=16` (128-bit random salt): Standard; prevents rainbow table attacks even across identical passwords.
- These parameters produce hashes of the form `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>` (~100 bytes), fitting easily in the existing `hashed_password VARCHAR(255)` column.

**Alternatives considered**:
- bcrypt: Weaker against GPU attacks; Argon2id is the OWASP-recommended modern standard.
- scrypt: Similar to Argon2 but less widely adopted in the Python ecosystem.
- Higher `time_cost` values: Would increase latency; 3 iterations provides sufficient security for this application's threat model.

## 3. Refresh Token Format and Hashing

**Decision**: Generate 256-bit (32-byte) cryptographically random tokens using `secrets.token_urlsafe(32)`. Store SHA-256 hash server-side.

**Rationale**:
- `secrets.token_urlsafe(32)` produces 43-character base64url-encoded strings. Cryptographically secure (uses OS entropy source).
- 256 bits provides 2^256 possible tokens — brute-force infeasible.
- SHA-256 hashing before storage means a database compromise does not expose valid refresh tokens.
- `hashlib` is stdlib — no additional dependency.
- Storing previous token hashes (for rotation reuse detection) uses the same SHA-256 approach. A separate `rotated_token_hashes` JSON array or a linked `auth_session_rotated_tokens` table stores previous hashes.

**Alternatives considered**:
- UUID4: Only 122 bits of entropy; weaker for security tokens.
- Longer tokens (64 bytes): Unnecessary; 32 bytes already provides >128 bits of security, beyond brute-force reach.
- Bcrypt/scrypt for token hashing: Overkill and too slow; SHA-256 is sufficient because tokens have high entropy (unlike user-chosen passwords).

## 4. CSRF Protection Strategy

**Decision**: Double-submit cookie pattern.

**Rationale**:
- The refresh and logout endpoints rely on HttpOnly cookies (for the refresh token), making them vulnerable to CSRF. The browser automatically sends cookies on cross-origin requests.
- Double-submit cookie: The server sets a non-HttpOnly `csrf_token` cookie (readable by JavaScript) alongside the HttpOnly refresh-token cookie. The client reads the `csrf_token` cookie value and sends it back in a custom header (e.g., `X-CSRF-Token`). The server compares the header value to the cookie value.
- This pattern requires no server-side state — the server simply checks that the header and cookie values match. An attacker on a different origin cannot read the cookie (SameSite helps) and cannot set the custom header (browsers block custom headers on cross-origin requests without CORS preflight).
- The CSRF token cookie is set on login and rotated on each refresh/token-rotation.

**Configuration values** (settled during planning):
- Cookie name: `csrf_token`
- Header name: `X-CSRF-Token`
- SameSite policy: `Lax` (allows top-level navigations like clicking a link to the app; Strict would break these)
- Refresh-token cookie name: `refresh_token`
- Cookie path: `/api/v1/auth` (covers `/refresh` and `/logout`)

**Alternatives considered**:
- Synchronizer Token Pattern: Requires server-side token storage per session. Rejected due to added complexity and state management.
- SameSite=Strict alone: Would work but provides weaker defense-in-depth; `Strict` also breaks some legitimate cross-origin navigations.
- Custom header requirement without cookie: Not possible — the refresh token must be in a cookie (HttpOnly for XSS protection), so CSRF is inherent.

## 5. Rate Limiting Implementation

**Decision**: In-memory rate limiter using a `collections.defaultdict` with time-bucketed counters, wrapped in a FastAPI dependency.

**Rationale**:
- The spec explicitly permits a single-instance in-memory limiter. A database-backed approach would add latency (~10-50ms per check) and violate SC-007's <100ms response time goal.
- In-memory track keys of the form `ratelimit:{normalized_email}:{client_ip}` with a rolling-window counter using a sorted list of timestamps or a sliding-window counter.
- Cleanup: A periodic background task prunes expired entries to prevent memory leaks.
- Normalized email: lowercased and stripped of leading/trailing whitespace. Dot-stripping (Gmail) is NOT applied — the normalization should be consistent with how the database stores and compares emails during login.

**Alternatives considered**:
- Redis: Would support distributed instances but adds an infrastructure dependency. Deferred per spec.
- Database-backed: Adds latency; conflicts with SC-007. Rejected for v1.
- `slowapi` / `fastapi-limiter`: Third-party libraries that add dependencies. In-memory implementation is simple (<100 lines) and avoids external dependency.

## 6. Audit Logging Strategy

**Decision**: Synchronous database insert via SQLAlchemy within the same transaction context as the audited operation, with a dedicated `auth_audit_log` table.

**Rationale**:
- Audit records must be durable — writing to the database ensures they survive process restarts.
- Same-transaction writes ensure that if an operation succeeds, its audit record is committed atomically. If the operation fails and rolls back, the audit record is also rolled back (preventing orphaned audit entries).
- A dedicated `auth_audit_log` table avoids polluting application logs with structured audit data and enables querying/filtering by event type, user, and time range.
- The table uses a simple schema with indexed columns for `event_type`, `user_id`, and `event_timestamp` to support efficient querying.
- No async/background writes — simplicity and durability over latency. Audit writes are small (a single INSERT) and add negligible overhead.

**Alternatives considered**:
- Application log (stdout) with structured logging: Would require log aggregation infrastructure to query. Rejected because structured DB storage enables direct head-coach audit inspection.
- Async/background queue: Adds complexity (message broker, worker). Overkill for this scale.
- Separate audit database: Unnecessary for this scale; same database with separate table is sufficient.

## 7. AuthSession: One Table or Two?

**Decision**: Single `auth_sessions` table with a JSON array column for rotated token hashes.

**Rationale**:
- The spec requires distinguishing (a) current valid token, (b) previously used tokens, and (c) token-family ID. A single table stores all three:
  - `token_family_id` (UUID) — shared by all tokens in a rotation chain
  - `current_token_hash` (VARCHAR) — the single valid refresh token hash
  - `rotated_token_hashes` (JSONB) — array of previously used token hashes for reuse detection
- JSONB in PostgreSQL supports efficient containment queries (`@>`), making reuse detection a single indexed query.
- A separate `rotated_tokens` table would require a JOIN or subquery for every refresh operation, adding latency to the critical refresh path.
- The JSON array typically contains 1-10 entries (refresh tokens rotated over a 30-day session), well within PostgreSQL's JSONB performance envelope.

**Alternatives considered**:
- Two-table approach (auth_sessions + rotated_refresh_tokens): Cleaner relational model but adds a JOIN on every refresh. Rejected for performance.
- Separate column for each rotated token: Inflexible — number of rotations varies per session.

## 8. Authorization Dependency Pattern

**Decision**: FastAPI dependency chain: `get_current_user` → `require_role(roles)`.

**Rationale**:
- `get_current_user`: Extracts JWT from Authorization header, verifies signature and expiry, checks session is active (not revoked, user not disabled), loads User from DB. Returns User ORM instance.
- `require_role(*roles)`: Factory that returns a dependency. Calls `get_current_user`, checks `user.role in roles`, raises HTTP 403 if not authorized.
- Chaining enables composable, testable dependencies. Each dependency does one thing.
- All existing route handlers inject `current_user: Annotated[User, Depends(get_current_user)]` and optionally `_: Annotated[None, Depends(require_role(UserRole.HEAD_COACH))]`.
- Default-deny: Routes without any auth dependency are explicitly listed in a `PUBLIC_ROUTES` set; the auth middleware rejects everything else.

**Alternatives considered**:
- Middleware-level enforcement: Too coarse — cannot express per-endpoint role requirements.
- Decorator-based: Not idiomatic in FastAPI; dependency injection is the standard pattern.

## 9. Email Case Sensitivity

**Decision**: Emails are stored and compared case-insensitively (lowercased at input boundary).

**Rationale**:
- RFC 5321 specifies the local part is case-sensitive but nearly all major email providers treat addresses as case-insensitive. Case-sensitive comparison leads to duplicate accounts (`User@example.com` vs `user@example.com`).
- The existing `User.email` column stores values as-submitted. The migration will normalize existing emails to lowercase and add application-level normalization on create and login.
- The rate limiter uses the same normalization (lowercased + trimmed) for consistency.

## 10. Session Cleanup

**Decision**: Alembic migration adds a database-level partial index for efficient querying of expired/revoked sessions. A lightweight cleanup task is deferred (not in v1 scope) since session volume is low.

**Rationale**:
- For a cricket team management app, session volume is <1000 active sessions — no urgent cleanup needed.
- Expired/revoked sessions are filtered out in queries via WHERE clauses (`revoked_at IS NULL AND expires_at > NOW()`).
- A future task can add a periodic cleanup (e.g., `DELETE FROM auth_sessions WHERE expires_at < NOW() - INTERVAL '30 days'`).
