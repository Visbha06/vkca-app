# Feature Specification: Authentication, Authorization, and API Security

**Feature Branch**: `002-auth-api-security`

**Created**: 2026-07-12

**Status**: Draft

**Input**: User description: "Authentication, Authorization, and API Security — password hashing (Argon2id), JWT access tokens, opaque refresh tokens with rotation and reuse detection, server-side sessions, role-based access control (Head Coach / Assistant Coach / Staff), rate limiting, audit logging, CSRF protection, and secure cookie handling."

## Clarifications

### Session 2026-07-12

- Q: Which JWT signing algorithm should be used? → A: HS256 (HMAC-SHA256) symmetric algorithm.
- Q: How should the AuthSession data model distinguish token states? → A: The model must distinguish (a) the current valid refresh token hash, (b) previously used (rotated) token hashes for reuse detection, and (c) the token-family identifier linking the rotation chain.
- Q: Where should SameSite, cookie names, paths, and CSRF header/cookie names be settled? → A: These are plan-level operational decisions; the planning phase will settle specific values.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - User Login and Session Establishment (Priority: P1)

A user navigates to the application and authenticates with their email address and password. On success, the system creates a server-side session, issues a short-lived access token for API requests, and sets a secure HTTP-only cookie containing a refresh token. The user can now access protected resources according to their role. Failed login attempts receive a generic invalid-credentials response regardless of whether the email exists, the password is wrong, or the account is disabled — no information leakage.

**Why this priority**: Authentication is the gate for all other functionality. Without login, no protected resource can be accessed and no role-based authorization can function.

**Independent Test**: Can be tested in isolation by submitting valid and invalid credentials to the login endpoint and verifying correct token issuance, session creation, and generic error responses.

**Acceptance Scenarios**:

1. **Given** a user with valid credentials exists, **When** the user submits their email and password, **Then** the system creates a new server-side session, returns a JWT access token (valid for 30 minutes), and sets a refresh token cookie with HttpOnly, Secure (outside local development), and SameSite attributes.

2. **Given** a user submits an email that does not exist, **When** the login request is processed, **Then** the system returns a generic "invalid credentials" response with HTTP 401, and the response text is identical to a wrong-password response.

3. **Given** a user submits a correct email but wrong password, **When** the login request is processed, **Then** the system returns a generic "invalid credentials" response with HTTP 401, indistinguishable from a non-existent-email response.

4. **Given** a user account has been disabled by a head coach, **When** the user attempts to log in, **Then** the system returns a generic "invalid credentials" response with HTTP 401 — it does not reveal that the account is disabled.

5. **Given** a user has an active session and logs in again (from the same or a different device), **When** the second login succeeds, **Then** both sessions coexist independently — each with its own access token, refresh token, and session record.

---

### User Story 2 - Session Maintenance via Token Refresh (Priority: P1)

A user's access token is short-lived (30 minutes). When it expires, the browser client uses the refresh token cookie to obtain a new access token without requiring the user to re-enter credentials. The refresh flow rotates the refresh token: the old refresh token is revoked, a new one is issued, and the new refresh token hash is stored. If a previously rotated refresh token is ever reused (indicating token theft), the entire token family is revoked. Refresh sessions expire after 7 days of inactivity and have an absolute lifetime of 30 days.

**Why this priority**: Without refresh, users must re-authenticate every 30 minutes, making the application unusable. Token rotation and reuse detection are critical for security.

**Independent Test**: Can be tested independently by obtaining an access token and refresh token, waiting for the access token to expire (or using a short-lived test token), calling the refresh endpoint, and verifying the new access token works while the old refresh token is revoked.

**Acceptance Scenarios**:

1. **Given** a user has an active session with a valid refresh token, **When** the user's access token expires and they call the refresh endpoint, **Then** the system issues a new access token (30-minute lifetime), rotates the refresh token (new opaque value in a new cookie), and records the refresh event.

2. **Given** a user's refresh session has been inactive for more than 7 days, **When** the user attempts to refresh, **Then** the system rejects the refresh request and the session is expired. The user must log in again.

3. **Given** a refresh session was created more than 30 days ago, **When** the user attempts to refresh, **Then** the system rejects the refresh request regardless of recent activity. The user must log in again.

4. **Given** an attacker obtains a previously rotated refresh token and attempts to use it, **When** the refresh endpoint receives the reused token, **Then** the system detects the reuse, revokes the entire token family (both old and current tokens), records the event in the audit log, and returns an authentication failure.

---

### User Story 3 - Role-Based Access Control (Priority: P2)

Every protected endpoint enforces role-based authorization. The system checks the authenticated user's role against the required permission for the operation. A head coach has full access including user management; an assistant coach can manage cricket data but not users; a staff member has read-only access. Access is denied by default when a route has no explicit authorization rule. Role changes and user disablement take effect immediately. Client-provided roles are never trusted.

**Why this priority**: Authorization enforces the security model. Without it, any authenticated user could perform any action, defeating the purpose of role separation.

**Independent Test**: Can be tested by creating users with each role (head coach, assistant coach, staff) and verifying that each role can only perform operations permitted by the specification — both allowed actions succeed and denied actions return HTTP 403.

**Acceptance Scenarios**:

1. **Given** a head coach is authenticated, **When** they attempt to create a user, change a user's role, disable a user, create a player, create a team, create a match, submit a performance, or view any resource, **Then** all operations succeed.

2. **Given** an assistant coach is authenticated, **When** they attempt to create a user, change a role, disable a user, or manage sessions, **Then** the system returns HTTP 403. When they attempt to create a player, create a team, create a match, submit a performance, or view any resource, those operations succeed.

3. **Given** a staff member is authenticated, **When** they attempt any write operation (create/update player, team, match, performance, user), **Then** the system returns HTTP 403. When they view players, teams, matches, performances, or statistics, those operations succeed.

4. **Given** a head coach changes an assistant coach's role to staff, **When** the affected user makes their next protected request, **Then** their access is limited to staff (read-only) permissions immediately — the role change takes effect without requiring re-login.

5. **Given** an endpoint has no explicit authorization rule, **When** any authenticated user accesses it, **Then** the system denies access by default (HTTP 403).

6. **Given** a malicious client includes a `role` claim in a request body or header, **When** the system processes the request, **Then** the client-provided role is ignored — only the server-side role from the validated JWT is used.

---

### User Story 4 - User Administration by Head Coaches (Priority: P2)

A head coach can create new user accounts, change user roles, and disable user accounts. Creating a user requires providing an email, password, and role. The password is accepted as plain text and hashed server-side using Argon2id — clients never generate or submit password hashes. Disabling a user revokes all their active sessions immediately and prevents future login and token refresh.

**Why this priority**: User administration is essential for managing access to the system. Without it, new coaches and staff cannot be onboarded, and departing personnel cannot be deactivated.

**Independent Test**: Can be tested in isolation by a head coach creating a user, verifying the new user can log in, changing the user's role and verifying the new permissions, disabling the user and verifying all sessions are revoked and login is blocked.

**Acceptance Scenarios**:

1. **Given** a head coach is authenticated, **When** they submit a new user with email, password, and role, **Then** the system creates the user account, hashes the password using Argon2id with a unique salt, and returns the user's profile (without the password hash). The new user can immediately log in.

2. **Given** a head coach changes a user's role (e.g., assistant coach to staff), **When** the role change is saved, **Then** the role takes effect immediately on the user's next protected request, and the change is recorded in the audit log.

3. **Given** a head coach disables a user account, **When** the disable operation completes, **Then** all active sessions for that user are revoked, the user can no longer log in, and their existing refresh tokens are invalidated. All revocations are recorded in the audit log.

4. **Given** a head coach attempts to create a user with a password that violates the password policy (fewer than 12 characters, missing uppercase, lowercase, digit, or special character, or exceeding 128 characters), **When** the request is processed, **Then** the system returns a validation error with HTTP 422, and no user account is created.

5. **Given** a client (not the server) generates a password hash and submits it instead of a plain-text password, **When** the request is processed, **Then** the system rejects the input — the API accepts only a `password` field for the plain-text password, not a pre-hashed value.

---

### User Story 5 - Session Revocation and Security Events (Priority: P3)

Sessions are revoked in response to security-critical events: explicit logout, password changes, and user disablement. Logout revokes only the current session — other active sessions for the same user remain valid. A password change or disablement revokes every active session belonging to that user. A head coach can revoke another user's sessions through user-management operations.

**Why this priority**: Session revocation is a security response mechanism. It is critical for mitigating compromised credentials and enforcing access changes, but the primary authentication and authorization flows must work first.

**Independent Test**: Can be tested by creating multiple concurrent sessions for a user, triggering logout from one session and verifying only that session is revoked, then triggering a password change and verifying all remaining sessions are revoked.

**Acceptance Scenarios**:

1. **Given** a user has three active sessions (e.g., desktop, mobile, tablet), **When** the user logs out from the desktop session, **Then** only the desktop session is revoked — the access token and refresh token for that session are rejected, but the mobile and tablet sessions continue to function normally.

2. **Given** a user changes their password, **When** the password change completes, **Then** every active session belonging to that user is immediately revoked. All access tokens and refresh tokens for that user are rejected.

3. **Given** a head coach disables a user account, **When** the disable operation completes, **Then** every active session belonging to that user is revoked, and the user can neither log in nor refresh tokens.

4. **Given** a revoked session's access token is presented to a protected endpoint, **When** the system processes the request, **Then** it returns HTTP 401.

5. **Given** a revoked session's refresh token is submitted to the refresh endpoint, **When** the system processes the request, **Then** it returns HTTP 401 and does not issue new tokens.

---

### User Story 6 - Rate Limiting on Authentication (Priority: P3)

Login attempts are rate-limited to prevent brute-force attacks. The system permits a maximum of five failed login attempts for the same combination of normalized email address and source IP address within a rolling 15-minute window. Exceeding the limit returns HTTP 429. The rate-limit response must not reveal whether the email exists. A successful login reduces the applicable failed-attempt counter. Rate limiting never permanently locks an account.

**Why this priority**: Rate limiting is a defense-in-depth measure. It protects against attacks but affects only attackers — legitimate users who mistype passwords a few times are not locked out permanently.

**Independent Test**: Can be tested by submitting six failed login attempts from the same IP for the same email within 15 minutes and verifying the sixth attempt returns HTTP 429, then submitting a successful login for a different account from the same IP and verifying it works.

**Acceptance Scenarios**:

1. **Given** no recent failed login attempts exist for an email-and-IP combination, **When** a user submits five failed login attempts within 15 minutes, **Then** all five return generic "invalid credentials" responses, and the sixth attempt within the window returns HTTP 429.

2. **Given** a rate-limited email-and-IP combination, **When** the user successfully logs in with the correct password, **Then** the failed-attempt counter for that combination is substantially reduced or reset.

3. **Given** a rate-limited email-and-IP combination, **When** the rate limiter returns HTTP 429, **Then** the response body must not indicate whether the email address exists in the system.

4. **Given** a legitimate user was rate-limited 30 minutes ago, **When** the rolling window has passed and they attempt to log in, **Then** they can attempt login again — rate limiting does not permanently lock the account.

5. **Given** a rate-limit threshold is exceeded, **When** the HTTP 429 response is returned, **Then** the rate-limit enforcement event is recorded in the authentication audit log with the source IP address and normalized email.

---

### User Story 7 - Authentication Audit Logging (Priority: P3)

All significant authentication and authorization events are recorded in an audit log for security monitoring. Events include successful and failed logins, logouts, token refreshes, refresh-token reuse detection, session revocations, authorization denials, user disablement, password changes, role changes, and rate-limit enforcement. Each record includes identifying information (user ID, session ID, event type, timestamp, result, source IP, user agent) but never contains passwords, tokens, hashes, or signing secrets.

**Why this priority**: Audit logging is essential for security monitoring, incident investigation, and compliance, but the system must be operational (login, authorization, revocation) before logging adds value.

**Independent Test**: Can be tested by performing each auditable event and verifying that the corresponding log record exists with all required fields and no sensitive data (passwords, tokens, hashes).

**Acceptance Scenarios**:

1. **Given** a user successfully logs in, **When** the login completes, **Then** an audit record is created containing the user ID, session ID, event type "login", success result, timestamp, source IP, and user agent — but no password or token data.

2. **Given** a failed login attempt occurs, **When** the system returns HTTP 401, **Then** an audit record is created containing the normalized email, event type "failed-login", failure result, timestamp, source IP, and user agent — but no password or token data.

3. **Given** a head coach disables a user, **When** the operation completes, **Then** an audit record is created containing the acting user ID, target user ID, event type "user-disablement", success result, timestamp, and reason.

4. **Given** a refresh-token reuse is detected (indicating potential token theft), **When** the system revokes the token family, **Then** an audit record is created with event type "refresh-token-reuse", the session ID, token-family ID, timestamp, and source IP — but no raw token or hash values.

5. **Given** any audit record is written, **When** the record is inspected, **Then** it must not contain passwords, password hashes, access tokens, refresh tokens, token hashes, or signing secrets — regardless of event type.

---

### Edge Cases

- **Disabled user with active session**: When a head coach disables a user who has an active session, the next protected request from that user's access token must be rejected (HTTP 401), and all refresh tokens for that user must be invalidated.

- **Role change during active session**: When a user's role is changed, the new role must take effect on the very next protected request. The user does not need to log out and back in. The JWT contains the role at issuance time, so if the role was cached from a previously issued JWT, the new JWT (issued at the next refresh or login) carries the updated role — but the server-side session check also verifies current role on each request.

- **Password change concurrent with active requests**: When a user changes their password, every session is revoked. Any in-flight request using a now-revoked access token is rejected on the next protected endpoint call with HTTP 401.

- **Simultaneous refresh requests**: If a client issues two refresh requests concurrently with the same refresh token, one succeeds and rotates the token, while the second (using the now-revoked refresh token) is detected as a reuse and revokes the entire token family, forcing the user to re-authenticate.

- **Expired access token with revoked session**: An expired access token for a session that has since been revoked (e.g., by logout) must still be rejected at the refresh endpoint — the system must not issue a new access token for a revoked session.

- **Password truncation**: The system must not silently truncate passwords. A password of exactly 128 characters must be accepted; a password of 129 characters must be rejected with a validation error.

- **Rate limiting across account disablement**: A disabled user trying to log in still consumes a rate-limit attempt. The rate limiter must not reveal that the account is disabled versus having a wrong password.

- **CSRF on logout and refresh**: Since refresh and logout endpoints rely on cookies for the refresh token, they must include CSRF protection. A request without a valid CSRF token must be rejected.

- **Local development vs production cookies**: In local development, the `Secure` flag on cookies may be omitted to allow HTTP. In production, `Secure` must be set. The `SameSite` policy must be explicitly defined in both environments.

- **Empty or missing Authorization header**: A request to a protected endpoint without an Authorization header returns HTTP 401, not HTTP 403 — the system cannot determine authorization without authentication.

- **Malformed JWT**: A request with a JWT that is not valid base64url-encoded JSON, has a tampered signature, or uses an unexpected signing algorithm returns HTTP 401 without revealing details about why the token is malformed.

## Requirements *(mandatory)*

### Functional Requirements

#### Password Security

- **FR-001**: The system MUST accept a plain-text `password` field during user creation and MUST hash it server-side using Argon2id with a unique, randomly generated salt before persistence.

- **FR-002**: The system MUST reject any client-submitted `hashed_password` or pre-hashed input. Clients MUST never generate or submit password hashes. The API input schema for user creation MUST accept only a `password` field for the plain-text password.

- **FR-003**: The system MUST enforce a password policy requiring: minimum 12 characters, maximum 128 characters, at least one uppercase letter, at least one lowercase letter, at least one digit, and at least one special character.

- **FR-004**: The system MUST NOT silently truncate passwords. Passwords longer than 128 characters MUST be rejected with a validation error.

- **FR-005**: Password hashes MUST never appear in API responses, audit records, application logs, or error messages — under any circumstances.

- **FR-006**: Changing a user's password MUST immediately revoke all active sessions for that user.

#### Authentication

- **FR-007**: The system MUST authenticate users by email address and password. On success, a new server-side session MUST be created and an access JWT and a refresh token MUST be issued.

- **FR-008**: The system MUST support multiple simultaneous sessions per user. Each login MUST create an independently revocable session. No maximum active session limit is enforced.

- **FR-009**: The system MUST return a generic invalid-credentials response for every authentication failure, regardless of the underlying cause (nonexistent email, incorrect password, disabled account). The response text and HTTP status code MUST be identical across all failure modes.

- **FR-010**: Access tokens MUST be signed JWTs with a 30-minute validity period. Each access token MUST contain at least: `sub` (user ID), `sid` (server-side session ID), `role` (current user role), `jti` (unique token ID), `iat` (issued-at timestamp), and `exp` (expiration timestamp).

- **FR-011**: Access tokens MUST be signed using the HS256 (HMAC-SHA256) symmetric algorithm. The HS256 signing secret MUST be configured through an environment variable and MUST never be committed to source control.

- **FR-012**: The system MUST reject access tokens that are: malformed, expired, incorrectly signed, issued for a revoked session, or associated with a disabled user. Each case MUST return HTTP 401.

#### Refresh Tokens and Session Storage

- **FR-013**: Refresh tokens MUST be cryptographically random opaque values (not JWTs). Raw refresh tokens MUST never be stored server-side. Only a cryptographic hash of the current refresh token MUST be stored in the AuthSession record.

- **FR-014**: The AuthSession record MUST include at minimum: session ID, user ID, token-family ID (shared by all tokens in a rotation chain), current refresh-token hash (the single valid token that can be used for the next refresh), previously used token hashes (stored separately to enable reuse detection — a refresh token that matches a previously used hash indicates token theft and triggers family revocation), creation timestamp, last-used timestamp, inactivity-expiration timestamp, absolute-expiration timestamp, revocation timestamp, revocation reason, IP address (when available), and user agent (when available). The data model MUST distinguish between: (a) the current valid refresh token, (b) previously used (rotated) tokens belonging to the same family, and (c) the token-family identifier that links the rotation chain.

- **FR-015**: Refresh sessions MUST expire after 7 days of inactivity and MUST have an absolute lifetime of 30 days. Expired refresh tokens MUST be rejected.

- **FR-016**: During token refresh, the system MUST: hash the submitted refresh token, locate the matching active session or rotated-token record, verify the user is active, verify the session has not been revoked or expired, revoke/invalidate the submitted refresh token, generate a new refresh token, store the new token hash, issue a new access JWT, return the rotated refresh token, and record the refresh event in the audit log.

- **FR-017**: Reuse of a previously rotated refresh token MUST revoke the entire token family. The system MUST detect this by checking rotated-token identifiers and MUST record the reuse event in the audit log.

#### Browser Token Handling

- **FR-018**: Browser clients MUST keep access tokens in memory (not persistent browser storage such as localStorage or sessionStorage) and MUST send them in the `Authorization: Bearer <token>` header.

- **FR-019**: Browser clients MUST receive refresh tokens through cookies configured with HttpOnly, Secure (outside local development), an explicitly defined SameSite policy, and a restricted cookie path covering only refresh and logout operations where practical.

- **FR-020**: Refresh and logout endpoints MUST include CSRF protection because they rely on cookies for the refresh token.

- **FR-021**: Production deployments MUST use HTTPS, and refresh-token cookies in production MUST have the Secure flag set.

#### Authorization

- **FR-022**: All non-authentication routes MUST be protected and MUST require an authenticated user unless explicitly designated as public. Authorization MUST be enforced server-side through reusable authorization dependencies.

- **FR-023**: The system MUST deny access by default (HTTP 403) when a route has no explicit authorization rule. Client-provided roles or permissions MUST never be trusted.

- **FR-024**: Head Coach users MUST have full access to: create/list/update/deactivate user accounts, change user roles, revoke other users' sessions, create/update player profiles, create teams and modify rosters, create matches, submit match performances, and view all resources.

- **FR-025**: Assistant Coach users MUST be able to: create/update player profiles, create teams and modify rosters, create matches, submit match performances, and view all resources. They MUST NOT be able to: create/update/deactivate/list user accounts, change user roles, or revoke sessions belonging to other users.

- **FR-026**: Staff users MUST have read-only access: view players, teams, matches, performances, and statistics. They MUST NOT perform any write operations or manage users, roles, or sessions.

- **FR-027**: Authorization failures MUST return HTTP 403 without exposing sensitive implementation details such as stack traces, database information, or internal permission structures.

#### User Operations

- **FR-028**: The system MUST provide a current-user endpoint that returns the authenticated user's non-sensitive profile, role, active status, and current session information.

- **FR-029**: Head coaches MUST be able to create users (with email, password, and role), change user roles, and disable user accounts. Disabled users MUST not be able to log in, refresh tokens, or use existing authenticated sessions.

- **FR-030**: Disabling a user MUST revoke all active sessions for that user.

- **FR-031**: Role changes MUST take effect immediately on the next protected request — no re-login required.

- **FR-032**: User self-registration MUST NOT be supported. All user accounts are created by head coaches.

#### Logout and Revocation

- **FR-033**: Logout MUST revoke only the current server-side session. Both the access token and refresh token for that session MUST be rejected thereafter.

- **FR-034**: Revoked sessions MUST NOT be able to issue new access tokens.

- **FR-035**: Session revocation MUST record the revocation timestamp and reason.

- **FR-036**: Head coaches MUST be able to revoke another user's sessions through user-management operations.

#### Rate Limiting

- **FR-037**: The system MUST rate-limit login attempts by both normalized email address and source IP address. No more than five failed login attempts for the same account-and-IP combination within a rolling 15-minute period.

- **FR-038**: Requests exceeding the rate limit MUST return HTTP 429. The response MUST NOT reveal whether the submitted email address exists.

- **FR-039**: A successful login MUST reset or substantially reduce the applicable failed-attempt counter for that account-and-IP combination.

- **FR-040**: Rate limiting MUST NOT permanently lock a user account. After the rolling window passes, login attempts are permitted again.

- **FR-041**: Rate-limit enforcement events MUST be recorded for security auditing.

#### Authentication Audit Logging

- **FR-042**: The system MUST create audit records for: successful login, failed login, logout, token refresh, refresh-token reuse, session revocation, authorization denial, user disablement, password change, role change, and rate-limit enforcement.

- **FR-043**: Each audit record MUST include, when available: user ID, session ID, event type, event timestamp, result (success/failure), failure or revocation reason, source IP address, user agent, and target resource or operation.

- **FR-044**: Passwords, password hashes, access tokens, refresh tokens, token hashes, signing secrets, and other credentials MUST never be written to logs — regardless of event type or log level.

#### Error Handling

- **FR-045**: Invalid or expired access tokens MUST return HTTP 401 with a generic message that does not distinguish between token types or causes.

- **FR-046**: Authenticated users without sufficient permissions MUST receive HTTP 403 with a generic message.

- **FR-047**: Error responses MUST NOT expose password hashes, token contents, session secrets, signing keys, database details, or stack traces.

### Key Entities

- **User**: Represents a person who can authenticate and use the system. Key attributes: unique ID, email address, Argon2id password hash, role (head coach / assistant coach / staff), active/disabled status, creation timestamp, and last-modified timestamp. Relationships: has many AuthSessions; may create/update player profiles, teams, matches, and performances depending on role.

- **AuthSession**: Represents a single login session — not a single token. Key attributes: session ID, user ID (foreign key), token-family ID (shared by all tokens in a rotation chain), current refresh-token hash (the single valid token for the next refresh), previously used token hashes (stored for reuse detection — a match indicates token theft and triggers family-wide revocation), creation timestamp, last-used timestamp, inactivity-expiration timestamp, absolute-expiration timestamp, revocation timestamp (nullable), revocation reason (nullable), source IP address, and user agent. The model explicitly distinguishes: (a) the current valid refresh token, (b) previously used (rotated) tokens within the same family, and (c) the token-family identifier that links the rotation chain. Relationships: belongs to one User; within a token family, rotation chains link successive refresh tokens.

- **AuditRecord**: Represents a logged authentication or authorization event. Key attributes: event ID, event type (enum: login, failed-login, logout, token-refresh, token-reuse, session-revocation, authorization-denial, user-disablement, password-change, role-change, rate-limit), user ID (nullable — not available for failed logins with unknown email), session ID (nullable), event timestamp, result (success/failure), reason (nullable), source IP address, user agent, and target resource/operation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with valid credentials can complete the login flow and receive usable access and refresh tokens in under 2 seconds under normal load.

- **SC-002**: A protected API request with a valid access token is authorized and returns a response in under 500 milliseconds (excluding business logic execution time).

- **SC-003**: A password change immediately invalidates all existing sessions — a previously valid access token is rejected on the very next protected request with zero window of continued access.

- **SC-004**: A role change takes effect on the user's next protected request — no delayed propagation and no re-login required — verified by the immediate behavior change.

- **SC-005**: The system correctly rejects 100% of access tokens that are expired, malformed, incorrectly signed, or tied to a revoked session — no false acceptances in a test suite covering each rejection case.

- **SC-006**: Refresh-token reuse detection revokes the token family within a single refresh operation — no window where a stolen and reused refresh token can successfully obtain new tokens.

- **SC-007**: Rate limiting returns HTTP 429 on the sixth failed login attempt for the same email-and-IP combination within 15 minutes, and the response time for the rate-limited request is under 100 milliseconds (no expensive database operations on a rate-limited path).

- **SC-008**: Every authentication and authorization event produces exactly one corresponding audit record, and 100% of sampled audit records contain no passwords, tokens, hashes, or signing secrets.

- **SC-009**: CSRF protection on refresh and logout endpoints rejects 100% of requests that lack a valid CSRF token.

- **SC-010**: All login failure responses (nonexistent email, wrong password, disabled account) are byte-for-byte identical — an automated comparison of response bodies across failure modes detects zero differences.

## Assumptions

- Existing development users with incompatible or placeholder password hashes may be reset or recreated as part of the migration to the new Argon2id-based authentication system.

- The first rate-limiting implementation may use a single-instance in-memory or database-backed limiter. Distributed rate limiting across multiple application instances is deferred to a future specification.

- Browser-based web clients are the primary client type. Non-browser clients (e.g., mobile apps) that cannot rely on HTTP-only cookies for refresh tokens will be addressed in a future specification.

- The CSRF protection mechanism uses a standard double-submit cookie pattern or a synchronized token pattern — the specific mechanism is an implementation detail, but it must be present and effective.

- The `Secure` cookie flag is disabled in local development (where HTTP is used) and enforced in all staging and production deployments (where HTTPS is required).

- The JWT signing algorithm is HS256 (HMAC-SHA256). The signing secret is configured via an environment variable and generated during deployment — never hardcoded or committed to source control.

- Existing endpoints (players, teams, matches, performances, stats) will have authorization dependencies retrofitted. The current-user endpoint is new.

- Staff write permissions beyond read-only access, logout-all-devices, maximum simultaneous-session limits, and an administrative session dashboard are deferred to future specifications.

- Specific configuration values — the SameSite policy (Lax vs. Strict), refresh-token cookie name, cookie path, CSRF header name, and CSRF cookie name — will be settled during the planning phase. These are operational deployment choices that do not affect the specification's functional requirements.
