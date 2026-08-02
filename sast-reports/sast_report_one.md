# VKCA Static Application Security Audit

Date: 2026-08-01  
Analyzer: `llm-sast-scanner` v1.3.2  
Scope: FastAPI/SQLAlchemy backend, React frontend, seed/configuration files, and relevant tests.  
Method: read-only source-to-sink review followed by judge verification. No application source files were modified.

## Executive summary

Two application findings remain after false-positive review:

- High: a documented, hard-coded Head Coach bootstrap password is used as the CLI fallback and is accepted by the public login flow.
- Medium: the authenticated performance-batch endpoint has no application-level maximum batch size, allowing oversized requests to drive unbounded parsing, database `IN` parameters, writes, and aggregate recalculation.

One additional low-severity, environment-dependent observation is recorded separately: the current ignored `.env` file contains active configuration secrets and is mode `0644`. It is not tracked in Git and is not reachable through an application endpoint.

No Critical findings were confirmed. JWT verification, server-side session state, refresh-token rotation and reuse handling, CSRF protection, password hashing, role checks, account disablement, SQL construction, and frontend token handling passed the judge review.

## High findings

### SAST-001 — Known default Head Coach bootstrap credential

**Severity:** High  
**Status:** CONFIRMED at code level; exploitation requires the deployment to use the fallback.  
**Priority:** P1

**Affected files and code path**

- `backend/scripts/seed_head_coach.py:19-20` defines a predictable email and hard-coded password.
- `backend/scripts/seed_head_coach.py:25-31` supplies those values as function defaults.
- `backend/scripts/seed_head_coach.py:57-63` falls back to those values when `HEAD_COACH_EMAIL` or `HEAD_COACH_PASSWORD` is unset.
- `backend/scripts/seed_head_coach.py:42-50` hashes the fallback and creates an active `HEAD_COACH` account.
- `backend/src/routes/auth.py:158-189` exposes the public login endpoint; `backend/src/services/auth_service.py:82-104` loads the account and verifies the supplied password.
- `docs/auth-api-security.md:19-24` publishes the same bootstrap pair and relies on an operator not using it in a deployed environment.

**Impact and exploitability conditions**

An attacker who knows the public source/docs can authenticate as a full Head Coach if all of these conditions hold:

1. The seed command or `seed_head_coach()` is run without a replacement password.
2. The predictable bootstrap account has not already been changed or removed.
3. The API is reachable by the attacker.

The resulting account can administer users, roles, sessions, passwords, and cricket data. The password is hashed before storage, but hashing does not remove the risk of a known password.

**Judge verification**

- Reachability: PASS — the seed path creates an active account and the public login route accepts it.
- Sanitization/mitigation: FAIL — environment variables are optional and have a hard-coded fallback.
- Exploitability: PASS under the stated deployment condition; no remote control of configuration is needed once an operator runs the default bootstrap.
- Verdict: CONFIRMED, not a test-only or unreachable demo credential.

**Minimal remediation**

Remove the password fallback and fail closed unless `HEAD_COACH_PASSWORD` is supplied through a secret manager or protected environment. A safer alternative is a cryptographically random, one-time bootstrap secret delivered out of band. Remove operational documentation that presents a reusable login pair; keep any local-only fixture explicitly isolated from production setup.

**Tests needed to verify the fix**

- Run the seed command with the environment variable absent and assert that it refuses to create an account.
- Run it with an injected password and assert that the account is created and the injected password authenticates.
- Assert that the old published pair cannot authenticate against a freshly initialized deployment.
- Add a static/CI check preventing known credential literals from returning to executable seed/configuration code.

## Medium findings

### SAST-002 — Unbounded authenticated performance batches enable resource exhaustion

**Severity:** Medium  
**Status:** CONFIRMED in the application layer; practical impact can be reduced by an external proxy body limit, but no such limit is present in the repository.  
**Priority:** P2

**Affected files and code path**

- `backend/src/routes/performances.py:22-42` accepts the request for any authenticated Head or Assistant Coach.
- `backend/src/schemas/performance.py:63-75` constrains `performances` to non-empty and duplicate-free, but has no `max_length`.
- `backend/src/services/performance_service.py:67-78` converts all submitted UUIDs into a set and sends the complete set to a database `IN` query.
- `backend/src/services/performance_service.py:80-107` creates database records for every item.
- `backend/src/services/performance_service.py:111-123` performs aggregate recalculation for every submitted item inside one transaction.

**Impact and exploitability conditions**

A valid Assistant Coach or Head Coach can submit a very large JSON list, including many unique random UUIDs. With a valid match identifier, the request can consume application memory, Pydantic parsing time, database parameter/query capacity, transaction time, and repeated aggregate-query capacity before it is rejected or committed. A request containing only unknown players still reaches the large `IN` query before the missing-player error.

The endpoint is authenticated, so the severity is downgraded. A reverse proxy or API gateway may impose a body limit, but the backend itself does not enforce a cardinality or payload-size bound.

Related fields such as performance notes and player `bio`/`player_metadata` are also unbounded (`backend/src/schemas/performance.py:20,33,43` and `backend/src/schemas/player.py:19,23,36,40`); they were not counted as separate findings because their practical impact depends more heavily on deployment body limits and storage policy.

**Judge verification**

- Reachability: PASS — the route is exposed and guarded only by a normal authenticated role check.
- Sanitization/mitigation: FAIL for the batch cardinality; only minimum length and duplicate rejection exist.
- Exploitability: PASS with valid coach credentials; no ownership or special database privilege is required.
- Verdict: CONFIRMED application-level resource-exhaustion risk.

**Minimal remediation**

Enforce a documented maximum batch size at the Pydantic boundary (likely the maximum supported match roster, or another small explicit limit), and enforce maximum lengths/serialized sizes for notes, bios, and metadata. Add a server/request body-size limit and reject oversized requests before database work. If larger imports are required, process bounded chunks with a job/queue and per-principal throttling; deduplicate aggregate recalculation within a batch.

**Tests needed to verify the fix**

- Assert that a batch at the limit is accepted and a batch at limit plus one returns `422` without database work.
- Add an API test with many unique unknown UUIDs and verify bounded validation and no large database query is issued.
- Add boundary tests for notes, bio, metadata depth/count, and serialized size.
- Add a deployment/integration test for the configured request-body limit.
- Add a bounded-load test confirming aggregate recalculation and transaction time scale only with the accepted maximum.

## Low / contextual observation

### SAST-003 — Active `.env` file is world-readable in the audited workspace

**Severity:** Low  
**Status:** LIKELY/context-dependent; confirmed local file state, but not a remotely reachable application vulnerability.  
**Priority:** P3

**Affected files and code path**

- `.env` is present with non-placeholder database and JWT configuration values and has mode `0644`.
- `backend/src/config.py:24-25` loads the file directly.
- `backend/src/services/token_service.py:31-45` consumes `JWT_SECRET`; `backend/src/database.py:16` consumes the database URL.

**Impact and exploitability conditions**

On a multi-user host, or in a deployment that preserves these permissions, another local user/process able to read the workspace can obtain the database credentials and JWT signing secret. This does not establish a web exploit. The file is ignored by `.gitignore`, is not tracked, and was not found in Git history; no repository secret leak was confirmed.

**Judge verification**

- Local reachability: PASS — the file is readable by group/other users under its current mode.
- Remote reachability: FAIL — no endpoint returns the file.
- Exploitability: UNCERTAIN and host/deployment-dependent.
- Verdict: retain as a low-priority environment hygiene observation, not as an application endpoint finding.

**Minimal remediation**

Use a secret manager or protected deployment secret, set the file to owner-only permissions (`0600`) where a file is unavoidable, avoid baking it into images, and rotate the database/JWT values if the workspace or host was shared.

**Tests/checks needed to verify the fix**

- Deployment check that the secret file is not group/world-readable.
- CI check that `.env` is not tracked and no secret values are present in build artifacts.
- Startup test using the secret manager/injected environment rather than a repository file.
- Key-rotation validation proving old JWTs and database credentials are no longer accepted after rotation.

## Judge-verification decisions and rejected false positives

### Authentication, JWT, sessions, and account lifecycle

- `backend/src/services/token_service.py:72-90` verifies the signature with the configured algorithm and requires `sub`, `sid`, `jti`, `iat`, and `exp`; the algorithm is operator configuration, not attacker input.
- `backend/src/middleware/auth.py:44-72` binds `sub` and `sid` to the server-side session, checks revocation/expiry, and checks `User.is_active` on every request.
- `backend/src/middleware/auth.py:87-123` authorizes from the database role, not the JWT role claim. Existing tests explicitly challenge a forged elevated role.
- `backend/src/services/auth_service.py:202-348` performs rotating refresh-token updates with optimistic version checks and revokes the token family on reuse. Refresh tokens are random opaque values; their SHA-256 database digests are appropriate for that use and are not password hashes.
- `backend/src/routes/users.py:109-186` prevents self-disablement, revokes sessions on disablement, and reactivation does not restore revoked sessions. Head Coach-only administration is intended privilege, not privilege escalation.

No JWT algorithm-confusion, role-trust, stale-session, refresh-replay, user-reactivation, or password-storage finding survived judge review.

### CSRF and cookies

- `backend/src/routes/auth.py:114-124,192-223,285-303` requires a matching double-submit token for refresh and logout, the only endpoints that authenticate with cookies.
- Other state-changing routes require a bearer token and do not rely on cookies as their authority, so they are not CSRF-vulnerable under the scanner’s bearer-only rule.
- The refresh cookie is HttpOnly and SameSite=Lax. The CSRF cookie is intentionally not HttpOnly because the browser client must copy it into the header.
- `_cookie_secure()` is false for local HTTP and true when the request scheme is HTTPS. This is intentional for development and documented as a production HTTPS requirement. If a TLS terminator fails to pass the external HTTPS scheme, treat that deployment condition as a separate low-severity insecure-cookie issue and add a proxy integration test; it is not confirmed from this repository alone.

### Brute force, secrets, and error disclosure

- Login has a visible five-failure rolling-window limiter in `backend/src/services/rate_limiter.py:11-112`, keyed by normalized email and client IP, and the targeted tests confirm the sixth attempt receives `429`.
- A shared limiter is required for multi-instance deployments, and multiple source IPs can reduce the effectiveness of the composite key. The repository documents this limitation. The scanner’s brute-force guard therefore rejects a missing-limiter finding; this remains a hardening item, not a confirmed unlimited-attempt vulnerability.
- The public Argon2id dummy hash is used only to equalize unknown-account timing. It is not a usable credential.
- `.env.example`, Docker Compose substitutions, and README placeholders are templates, not tracked production secrets. The only credential fallback that reaches a login path is SAST-001.
- Errors are normalized by `backend/src/middleware/error_handlers.py:99-124`; no stack traces or database details are returned. Public OpenAPI docs are intentional and contain no credentials.

### SQL, authorization boundaries, input handling, and frontend trust

- Database access uses SQLAlchemy expressions and bound values. Search wildcard escaping is explicit in `backend/src/services/player_service.py:108-124`; no user-controlled raw SQL sink was found.
- Shared academy cricket-data reads are intentional. Admin/user-management routes and coach write routes have server-side role dependencies; no IDOR or client-controlled role decision was confirmed.
- Calendar ranges are capped at 45 dates and recurrence expansion is range-bounded. No upload, file-read, path-join, SSRF, shell, eval, unsafe deserialization, XML, or template-code execution path was found.
- React renders user fields through normal JSX escaping; no `dangerouslySetInnerHTML`, `innerHTML`, storage-persisted access token, or client-side authorization-only backend path was found.
- Login redirect helpers require a relative path. The installed React Router version also normalizes slash/backslash separators before history navigation, so the `/\\evil.com` style open-redirect probe does not reach an external origin. No open redirect finding survived verification.

## Verification executed

- Backend targeted security/auth tests: `90 passed`.
- Frontend test suite: `57` files, `305 passed`.
- `git diff --check`: passed.
- Source worktree was clean before the report artifact was created; no application source files were modified.
