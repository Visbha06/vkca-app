# Tasks: Authentication, Authorization, and API Security

**Input**: Design documents from `/specs/002-auth-api-security/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit tests are MANDATORY per the constitution. The spec explicitly enumerates security-focused test coverage requirements for all 47 functional requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `backend/tests/` at repository root
- All paths below assume `backend/` as the working directory

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dependencies, configure environment, apply database migration

- [X] T001 Add python-jose and argon2-cffi dependencies via `uv add python-jose[cryptography] argon2-cffi` in `backend/pyproject.toml`
- [X] T002 [P] Add JWT and auth configuration fields (JWT_SECRET, JWT_ALGORITHM=HS256, ACCESS_TOKEN_EXPIRE_MINUTES=30, REFRESH_TOKEN_EXPIRE_DAYS=30, REFRESH_INACTIVITY_DAYS=7, PASSWORD_MIN_LENGTH=12, PASSWORD_MAX_LENGTH=128) to Settings class in `backend/src/config.py`
- [X] T003 [P] Create Alembic migration 007 for auth_sessions and auth_audit_log tables in `backend/src/migrations/versions/007_create_auth_tables.py`
- [X] T004 Run `uv run alembic upgrade head` to apply migration and verify tables exist in PostgreSQL

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core security infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Models

- [X] T005 [P] Create AuthSession SQLAlchemy model (id, user_id FK, token_family_id, current_token_hash, rotated_token_hashes JSONB, last_used_at, expires_at, revoked_at, revocation_reason, ip_address, user_agent, version_number) with UUIDMixin, TimestampMixin, VersionMixin in `backend/src/models/auth_session.py`
- [X] T006 [P] Create AuthAuditLog SQLAlchemy model (id, event_type, user_id FK nullable, session_id FK nullable, result, reason, ip_address, user_agent, target_resource, event_timestamp) with UUIDMixin in `backend/src/models/auth_audit_log.py`
- [X] T007 Register AuthSession and AuthAuditLog models in `backend/src/models/__init__.py`
- [X] T008 Modify User model: update docstring for hashed_password column (now stores Argon2id output), add email lowercasing note in `backend/src/models/user.py`

### Schema updates

- [X] T009 Modify UserCreate schema: replace `hashed_password` field with `password` field (plaintext str, min_length=12, max_length=128), add password policy `@field_validator` (uppercase, lowercase, digit, special char check) in `backend/src/schemas/user.py`
- [X] T010 [P] Create auth request/response schemas (LoginRequest, TokenResponse, RefreshRequest, CSRFTokenResponse) in `backend/src/schemas/auth.py`

### Core services

- [X] T011 [P] Implement PasswordService: Argon2id hash_password(plaintext) → str, verify_password(plaintext, hash) → bool, validate_password_policy(password) → None|ValueError, using argon2-cffi with time_cost=3, memory_cost=65536, parallelism=4 in `backend/src/services/password_service.py`
- [X] T012 [P] Implement TokenService: create_access_token(user_id, session_id, role) → JWT str (HS256, 30min expiry, claims: sub, sid, role, jti, iat, exp), decode_and_verify_access_token(token) → dict (raises on invalid/expired), generate_refresh_token() → str (secrets.token_urlsafe(32)), hash_token(token) → str (SHA-256 hex), verify_csrf_token(header_value, cookie_value) → bool in `backend/src/services/token_service.py`
- [X] T013 Implement AuditService: log_event(session, event_type, user_id=None, session_id=None, result, reason=None, ip_address=None, user_agent=None, target_resource=None) → None, in `backend/src/services/audit_service.py`

### Unit tests for foundational services

- [X] T014 [P] Write unit tests for PasswordService: test_hash_password_different_salts, test_verify_correct_password, test_verify_wrong_password, test_policy_validation_too_short, test_policy_validation_no_uppercase, test_policy_validation_no_lowercase, test_policy_validation_no_digit, test_policy_validation_no_special, test_policy_validation_too_long, test_no_truncation_129_chars, test_argon2id_format in `backend/tests/unit/test_password_service.py`
- [X] T015 [P] Write unit tests for TokenService: test_create_access_token_has_required_claims, test_decode_valid_token, test_reject_expired_token, test_reject_malformed_token, test_reject_wrong_signature, test_refresh_token_length_43, test_refresh_token_uniqueness, test_hash_token_deterministic, test_hash_token_not_reversible in `backend/tests/unit/test_token_service.py`
- [X] T016 [P] Write unit tests for AuditService: test_log_event_creates_record, test_log_event_no_sensitive_fields in `backend/tests/unit/test_audit_service.py`

### Unit tests for schemas

- [X] T017 [P] Write unit tests for auth schemas: test_login_request_validation, test_login_request_missing_fields, test_token_response_structure in `backend/tests/unit/test_auth_schemas.py`
- [X] T018 Write unit tests for UserCreate schema changes: test_password_field_accepted, test_hashed_password_field_rejected, test_password_policy_enforced in `backend/tests/unit/test_user_schemas.py`

**Checkpoint**: Foundation ready — all core models, services, and schemas exist with passing unit tests. User story implementation can now begin.

---

## Phase 3: User Story 1 — User Login and Session Establishment (Priority: P1) 🎯 MVP

**Goal**: Users authenticate with email+password, receive a JWT access token and HttpOnly refresh-token cookie. A server-side AuthSession is created. Failed logins return generic "Invalid credentials" (byte-identical across all failure modes). Users can log out (revoke current session only). Protected endpoints verify the JWT and active session.

**Independent Test**: Submit valid credentials → receive 200 + access_token + cookies. Submit wrong password → receive 401 "Invalid credentials". Submit nonexistent email → receive byte-identical 401. Submit disabled account credentials → receive byte-identical 401. Access /me with valid token → 200 with profile. Access /me without token → 401.

### Tests for User Story 1 (MANDATORY unit tests) ⚠️

- [X] T019 [P] [US1] Write unit tests for login route: test_login_success_returns_tokens_and_cookies, test_login_wrong_password_returns_401_generic, test_login_nonexistent_email_returns_401_generic, test_login_disabled_user_returns_401_generic, test_responses_byte_identical_across_failure_modes in `backend/tests/unit/test_auth_routes.py`
- [X] T020 [P] [US1] Write unit tests for /me route: test_me_returns_profile_with_session, test_me_without_token_returns_401, test_me_with_expired_token_returns_401, test_me_with_malformed_token_returns_401, test_me_with_wrong_signature_returns_401 in `backend/tests/unit/test_auth_routes.py`
- [X] T021 [P] [US1] Write unit tests for logout route: test_logout_revokes_session, test_logout_clears_cookies, test_access_token_rejected_after_logout in `backend/tests/unit/test_auth_routes.py`

### Implementation for User Story 1

- [X] T022 [US1] Implement AuthService: login(session, email, password, ip, user_agent) → (User, AuthSession, access_token, refresh_token, csrf_token), verify user exists (lowercased email lookup), verify password via PasswordService, verify user is_active, create AuthSession row with token hashes, issue JWT and refresh token, record audit event in `backend/src/services/auth_service.py`
- [X] T023 [US1] Implement get_current_user FastAPI dependency: extract Bearer token from Authorization header, decode and verify JWT via TokenService, verify session is active (not revoked, not expired) via AuthSession lookup, verify user is_active, return User + AuthSession, raise HTTP 401 with generic message on any failure in `backend/src/middleware/auth.py`
- [X] T024 [US1] Implement POST /api/v1/auth/login endpoint: accepts LoginRequest, calls AuthService.login, returns TokenResponse, sets refresh_token and csrf_token cookies (HttpOnly, SameSite=Lax, Path=/api/v1/auth; Secure in production), handles rate-limited and disabled accounts with generic 401, in `backend/src/routes/auth.py`
- [X] T025 [US1] Implement GET /api/v1/auth/me endpoint: depends on get_current_user, returns user profile (id, first_name, last_name, email, role, is_active, created_at, updated_at) plus current session info (session_id, created_at, last_used_at, expires_at), in `backend/src/routes/auth.py`
- [X] T026 [US1] Implement POST /api/v1/auth/logout endpoint: depends on get_current_user (uses refresh_token cookie for session lookup when access token expired), sets revoked_at + revocation_reason='logout' on AuthSession, clears refresh_token and csrf_token cookies (Max-Age=0), records audit event, returns 204, in `backend/src/routes/auth.py`
- [X] T027 [US1] Register auth router (prefix=/api/v1/auth, tags=["auth"]) and include in api_router in `backend/src/main.py`

### Integration tests for User Story 1

- [X] T028 [US1] Write integration test: full login → access protected resource → logout → verify token rejected flow in `backend/tests/integration/test_auth_flow.py`

**Checkpoint**: Users can log in, receive tokens, access protected endpoints, and log out. Generic error responses are byte-identical across failure modes. MVP is functional.

---

## Phase 4: User Story 2 — Session Maintenance via Token Refresh (Priority: P1)

**Goal**: Users exchange a refresh-token cookie for a new access token without re-entering credentials. The refresh token is rotated (old revoked, new issued in cookie). Previously rotated refresh token reuse is detected and revokes the entire token family. Refresh sessions expire after 7 days of inactivity and have a 30-day absolute lifetime.

**Independent Test**: Login → wait/expire access token → call /refresh → receive new access token + new cookies. Try old refresh token → 401. Verify new access token works. Fast-forward 7+ days → refresh rejected. Fast-forward 30+ days → refresh rejected.

### Tests for User Story 2 (MANDATORY unit tests) ⚠️

- [X] T029 [P] [US2] Write unit tests for refresh route: test_refresh_returns_new_access_token, test_refresh_rotates_refresh_token, test_refresh_rotates_csrf_token, test_refresh_updates_last_used_at, test_refresh_rejects_expired_session_inactivity, test_refresh_rejects_expired_session_absolute, test_refresh_rejects_revoked_session, test_refresh_rejects_disabled_user in `backend/tests/unit/test_auth_routes.py`
- [X] T030 [P] [US2] Write unit tests for token reuse detection: test_reuse_rotated_token_revokes_family, test_reuse_returns_401, test_reuse_logs_audit_event, test_valid_token_still_works_after_rotation in `backend/tests/unit/test_auth_routes.py`
- [X] T031 [P] [US2] Write unit tests for CSRF protection: test_refresh_without_csrf_header_returns_403, test_refresh_with_mismatched_csrf_returns_403, test_logout_without_csrf_header_returns_403, test_csrf_token_set_on_login in `backend/tests/unit/test_auth_routes.py`

### Implementation for User Story 2

- [X] T032 [US2] Extend AuthService.refresh: read refresh_token from cookie, hash it, look up AuthSession by current_token_hash OR by rotated_token_hashes containment (via JSONB @>), if found in rotated_token_hashes → revoke entire token family (all sessions with same token_family_id), audit token_reuse, raise 401; if found in current_token_hash → verify session active (not revoked, not expired, user active), push current_token_hash to rotated_token_hashes, generate new refresh token + hash, bump last_used_at and version_number (OCC), issue new access JWT, rotate csrf_token cookie, audit token_refresh, return TokenResponse in `backend/src/services/auth_service.py`
- [X] T033 [US2] Implement POST /api/v1/auth/refresh endpoint: reads refresh_token cookie (no body), verifies X-CSRF-Token header matches csrf_token cookie, calls AuthService.refresh, sets new cookies, returns TokenResponse, in `backend/src/routes/auth.py`
- [X] T034 [US2] Add CSRF token validation to POST /logout: reject with 403 if X-CSRF-Token header missing or mismatched, in `backend/src/routes/auth.py`

**Checkpoint**: Token refresh works with rotation, reuse detection revokes token families, CSRF protection enforced on both /refresh and /logout.

---

## Phase 5: User Story 3 — Role-Based Access Control (Priority: P2)

**Goal**: Every protected endpoint enforces role-based authorization. Head Coach = full access. Assistant Coach = cricket data management only. Staff = read-only. Default-deny for routes without explicit authorization rules. Role changes take effect on next request. Client-provided roles never trusted.

**Independent Test**: Authenticate as each role → verify allowed operations succeed and denied operations return 403. Change a user's role → verify new permissions take effect on next request without re-login.

### Tests for User Story 3 (MANDATORY unit tests) ⚠️

- [X] T035 [P] [US3] Write unit tests for require_role dependency: test_head_coach_access_to_admin_operations, test_assistant_coach_denied_admin_operations, test_staff_read_only_enforcement, test_default_deny_no_rule, test_role_from_jwt_not_trusted, test_role_change_takes_effect_next_request in `backend/tests/unit/test_auth_routes.py`
- [X] T036 [P] [US3] Write unit tests for retrofitted routes: test_players_get_all_roles, test_players_post_staff_denied, test_teams_post_staff_denied, test_matches_post_staff_denied, test_performances_post_staff_denied, test_stats_get_all_roles in `backend/tests/unit/test_auth_routes.py`

### Implementation for User Story 3

- [X] T037 [US3] Implement require_role(*roles) dependency factory: calls get_current_user, checks user.role in roles, raises HTTP 403 with generic message if not authorized, in `backend/src/middleware/auth.py`
- [X] T038 [P] [US3] Add `current_user: Annotated[User, Depends(get_current_user)]` to all existing route handlers in `backend/src/routes/players.py`
- [X] T039 [P] [US3] Add `current_user: Annotated[User, Depends(get_current_user)]` to all existing route handlers in `backend/src/routes/teams.py`
- [X] T040 [P] [US3] Add `current_user: Annotated[User, Depends(get_current_user)]` to all existing route handlers in `backend/src/routes/matches.py`
- [X] T041 [P] [US3] Add `current_user: Annotated[User, Depends(get_current_user)]` to all existing route handlers in `backend/src/routes/performances.py`
- [X] T042 [P] [US3] Add `current_user: Annotated[User, Depends(get_current_user)]` to all existing route handlers in `backend/src/routes/stats.py`
- [X] T043 [US3] Add role-based restrictions: POST/PUT operations on players/teams/matches/performances require `require_role(UserRole.HEAD_COACH, UserRole.ASSISTANT_COACH)` (Staff denied); GET operations on stats/players/teams/matches require authenticated user only, in each route file

**Checkpoint**: Role-based access control enforced on all existing routes. Each role has correct permissions per spec.

---

## Phase 6: User Story 4 — User Administration by Head Coaches (Priority: P2)

**Goal**: Head coaches can create users (with plaintext password that is Argon2id-hashed server-side), change user roles, and disable user accounts. Client-submitted password hashes are rejected. Disabled users cannot log in or refresh tokens.

**Independent Test**: Head coach creates a user → new user can log in. Head coach changes role → new permissions take effect. Head coach disables user → user cannot log in, existing sessions revoked.

### Tests for User Story 4 (MANDATORY unit tests) ⚠️

- [ ] T044 [P] [US4] Write unit tests for user creation: test_create_user_with_password_hashes_correctly, test_reject_client_hash_input, test_password_policy_enforced_on_create, test_non_head_coach_denied, test_duplicate_email_returns_409 in `backend/tests/unit/test_user_routes.py`
- [ ] T045 [P] [US4] Write unit tests for role change: test_head_coach_can_change_role, test_role_change_audited, test_assistant_coach_cannot_change_role, test_invalid_role_rejected in `backend/tests/unit/test_user_routes.py`
- [ ] T046 [P] [US4] Write unit tests for user disable: test_disable_user_sets_is_active_false, test_disabled_user_cannot_login, test_disabled_user_sessions_revoked, test_non_head_coach_cannot_disable in `backend/tests/unit/test_user_routes.py`

### Implementation for User Story 4

- [ ] T047 [US4] Modify UserService.create_user: hash password via PasswordService.hash_password before storing, normalize email to lowercase, accept password field (not hashed_password), reject hashed_password input in `backend/src/services/user_service.py`
- [ ] T048 [US4] Modify POST /api/v1/users: add `_require_hc: Annotated[None, Depends(require_role(UserRole.HEAD_COACH))]` dependency, update docstring, in `backend/src/routes/users.py`
- [ ] T049 [US4] Modify GET /api/v1/users: add `_require_hc: Annotated[None, Depends(require_role(UserRole.HEAD_COACH))]` dependency, in `backend/src/routes/users.py`
- [ ] T050 [US4] Implement PATCH /api/v1/users/{user_id}/role: head coach only, updates user.role, commits, records role_change audit event, returns UserResponse, in `backend/src/routes/users.py`
- [ ] T051 [US4] Implement POST /api/v1/users/{user_id}/disable: head coach only, sets user.is_active=False, revokes all active AuthSessions for that user (sets revoked_at, revocation_reason='user_disabled'), records user_disablement audit event + one session_revocation per revoked session, returns UserResponse, in `backend/src/routes/users.py`
- [ ] T052 [US4] Implement POST /api/v1/users/{user_id}/change-password: authenticated user (self or head coach), validates new password against policy, hashes new password, saves, revokes all active sessions for the user, records password_change audit event, returns 204, in `backend/src/routes/users.py`

**Checkpoint**: Head coaches can fully manage users (create, role change, disable, password change). Password hashing is server-side with Argon2id. Client hash submission is rejected.

---

## Phase 7: User Story 5 — Session Revocation and Security Events (Priority: P3)

**Goal**: Sessions are revoked on explicit logout, password change, and user disablement. Logout revokes only the current session. Password change and disablement revoke ALL sessions for the user. Head coaches can revoke another user's sessions. Revoked sessions cannot issue new access tokens or refresh tokens.

**Independent Test**: Create 3 concurrent sessions → logout from one → verify only that one is revoked, others still work. Change password → verify all 3 are revoked. Disable user → verify all sessions revoked, login blocked.

### Tests for User Story 5 (MANDATORY unit tests) ⚠️

- [ ] T053 [P] [US5] Write unit tests for session isolation: test_logout_revokes_only_current_session, test_multiple_sessions_independent, test_password_change_revokes_all_sessions, test_user_disable_revokes_all_sessions, test_refresh_rejected_for_revoked_session in `backend/tests/unit/test_auth_service.py`

### Implementation for User Story 5

- [ ] T054 [US5] Extend AuthService.logout: revoke only the current session (set revoked_at + reason), do not touch other sessions for same user, in `backend/src/services/auth_service.py`
- [ ] T055 [US5] Add session revocation to password change flow: after password hash is updated in T052, revoke all AuthSession rows where user_id matches and revoked_at IS NULL, in `backend/src/services/auth_service.py`
- [ ] T056 [US5] Add session revocation to user disable flow: after is_active=False in T051, revoke all AuthSession rows for that user, in `backend/src/services/auth_service.py`
- [ ] T057 [US5] Implement admin session revocation: extend POST /users/{id}/disable or add POST /api/v1/users/{user_id}/revoke-sessions endpoint, head coach only, revokes all sessions, records session_revocation audit event per session, in `backend/src/routes/users.py`

### Integration tests for User Story 5

- [ ] T058 [US5] Write integration test: multiple sessions → selective logout → full revocation on password change in `backend/tests/integration/test_auth_flow.py`

**Checkpoint**: Session revocation works correctly — logout is scoped, password change/disable are global, revoked tokens are rejected.

---

## Phase 8: User Story 6 — Rate Limiting on Authentication (Priority: P3)

**Goal**: Login attempts are rate-limited to 5 failed attempts per (email, IP) pair per 15-minute rolling window. Exceeding returns HTTP 429. Response must not reveal whether email exists. Successful login reduces the counter. Rate limiting never permanently locks an account.

**Independent Test**: Send 6 failed logins within 15 minutes → first 5 return 401, 6th returns 429. Successful login resets counter. Different email+IP pair is independently counted.

### Tests for User Story 6 (MANDATORY unit tests) ⚠️

- [ ] T059 [P] [US6] Write unit tests for rate limiter: test_five_failures_allowed, test_sixth_returns_429, test_429_response_no_email_disclosure, test_successful_login_resets_counter, test_different_email_ip_independent, test_rolling_window_expires, test_rate_limit_not_permanent_lock, test_rate_limit_audit_event in `backend/tests/unit/test_rate_limiter.py`

### Implementation for User Story 6

- [ ] T060 [US6] Implement InMemoryRateLimiter: track failed attempts as dict keyed by "email:ip" → list of attempt timestamps, sliding_window_check(key, max_attempts=5, window_seconds=900) → bool (True=blocked), record_failure(key), record_success(key) (clears or resets counter), periodic cleanup of expired entries, in `backend/src/services/rate_limiter.py`
- [ ] T061 [US6] Integrate rate limiter into AuthService.login: before password verification, check rate limit for (normalized_email, client_ip); if blocked → audit rate_limit event, raise HTTP 429; if password correct → call rate_limiter.record_success; if password wrong → call rate_limiter.record_failure, in `backend/src/services/auth_service.py`
- [ ] T062 [US6] Register rate limiter as a FastAPI app-level dependency or singleton for consistent state across requests in `backend/src/main.py`

### Integration tests for User Story 6

- [ ] T063 [US6] Write integration test: 6 rapid failed logins → verify 429, successful login → verify reset, different account → verify independent rate limit in `backend/tests/integration/test_rate_limiting.py`

**Checkpoint**: Login rate limiting active. Brute-force attacks are throttled without information leakage.

---

## Phase 9: User Story 7 — Authentication Audit Logging (Priority: P3)

**Goal**: All significant auth/authz events are recorded in the audit log with user ID, session ID, event type, timestamp, result, IP, and user agent. No passwords, tokens, hashes, or secrets are ever written to logs.

**Independent Test**: Perform each auditable event → verify corresponding audit record exists with all required fields and zero sensitive data.

### Tests for User Story 7 (MANDATORY unit tests) ⚠️

- [ ] T064 [P] [US7] Write unit tests for audit logging: test_login_success_logged, test_login_failure_logged, test_logout_logged, test_token_refresh_logged, test_token_reuse_logged, test_role_change_logged, test_user_disable_logged, test_password_change_logged, test_rate_limit_logged, test_authorization_denial_logged in `backend/tests/unit/test_audit_service.py`
- [ ] T065 [P] [US7] Write unit tests for audit data integrity: test_no_passwords_in_audit, test_no_token_hashes_in_audit, test_no_access_tokens_in_audit, test_no_refresh_tokens_in_audit, test_no_signing_secrets_in_audit, test_all_required_fields_present_when_available in `backend/tests/unit/test_audit_service.py`
- [ ] T066 [P] [US7] Write integration test: perform full auth flow → inspect audit log → verify all events recorded in `backend/tests/integration/test_audit_logging.py`

### Implementation for User Story 7

- [ ] T067 [US7] Ensure AuditService.log_event is called at every audit point: AuthService.login (success + failure), AuthService.refresh (success + reuse), AuthService.logout, user role change, user disable, password change, rate limit enforcement, authorization denial (in require_role dependency), in all relevant service and middleware files
- [ ] T068 [US7] Implement GET /api/v1/auth/audit-log endpoint: head coach only, returns paginated audit records filtered by optional event_type, user_id, and time range query parameters, in `backend/src/routes/auth.py`

**Checkpoint**: Complete audit trail for all security events. Zero credential leakage in logs.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, seed scripts, validation, and hardening

- [ ] T069 [P] Create seed script for initial head coach user: generates Argon2id hash for a default password, inserts into users table, in `backend/scripts/seed_head_coach.py`
- [ ] T070 [P] Write feature documentation: concise version of spec capturing purpose, key flows, API surface, configuration, in `docs/auth-api-security.md` (MANDATORY per constitution — written after implementation, reflects what was built)
- [ ] T071 Run all unit tests: `uv run pytest backend/tests/unit/ -v` — all must pass
- [ ] T072 Run all integration tests: `uv run pytest backend/tests/integration/ -v` — all must pass
- [ ] T073 Validate against quickstart.md: execute all 8 validation scenarios from `specs/002-auth-api-security/quickstart.md` and verify expected outcomes
- [ ] T074 Run linters: `uv run ruff check backend/src/` and `uv run mypy backend/src/` — all must pass
- [ ] T075 [P] Run security scanner: `uv run bandit -r backend/src/` — no high-severity findings
- [ ] T076 Verify no hardcoded secrets: grep for secret patterns (JWT_SECRET, signing keys) in committed files — none found
- [ ] T077 Verify .env.example includes JWT_SECRET placeholder with documentation
- [ ] T078 [P] Run performance smoke tests: time login endpoint (<2s per SC-001), authorization check (<500ms per SC-002), rate-limit response (<100ms per SC-007) using `time` or `hyperfine` against a running local server

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 — Login & Session (Phase 3)**: Depends on Foundational — 🎯 **MVP**
- **US2 — Token Refresh (Phase 4)**: Depends on US1 (needs login flow + session model)
- **US3 — RBAC (Phase 5)**: Depends on US1 (needs get_current_user dependency; can parallel with US2)
- **US4 — User Admin (Phase 6)**: Depends on US3 (needs require_role dependency)
- **US5 — Session Revocation (Phase 7)**: Depends on US1 + US4 (needs session model + user management)
- **US6 — Rate Limiting (Phase 8)**: Depends on US1 (integrates with login flow)
- **US7 — Audit Logging (Phase 9)**: Depends on US1-US6 (audits all events; can be integrated incrementally)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
Phase 3 (US1: Login) ──┬──→ Phase 4 (US2: Refresh)
                       │
                       ├──→ Phase 5 (US3: RBAC) ──→ Phase 6 (US4: User Admin)
                       │                                    ↓
                       ├──→ Phase 8 (US6: Rate Limit)  Phase 7 (US5: Revocation)
                       │
                       └──→ Phase 9 (US7: Audit Logging) [spans all]
                              ↓
                        Phase 10 (Polish)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration tests

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel
- **Phase 2**: T005, T006 (models) can run in parallel; T010, T011, T012 (schemas/services) can run in parallel; T014-T018 (tests) can run in parallel after service implementations
- **Phase 3**: T019-T021 (tests) can run in parallel
- **Phase 4**: T029-T031 (tests) can run in parallel
- **Phase 5**: T038-T042 (route retrofits) can run in parallel — all are independent file edits
- **Phase 6**: T044-T046 (tests) can run in parallel
- **Phase 7**: T053 can run in parallel with T054 (service + tests)
- **Phase 8**: T059 can run in parallel with T060 (tests + implementation)
- **Phase 9**: T064-T066 (tests) can run in parallel
- **Phase 10**: T069, T070, T075, T078 can run in parallel
- **Across phases**: US3 and US2 can run in parallel after US1; US6 and US7 can run in parallel after US1

### Parallel Example: Phase 5 (RBAC Retrofit)

```bash
# All 5 route files can be updated simultaneously:
Task T038: "Add get_current_user to backend/src/routes/players.py"
Task T039: "Add get_current_user to backend/src/routes/teams.py"
Task T040: "Add get_current_user to backend/src/routes/matches.py"
Task T041: "Add get_current_user to backend/src/routes/performances.py"
Task T042: "Add get_current_user to backend/src/routes/stats.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T018)
3. Complete Phase 3: User Story 1 (T019-T028)
4. **STOP and VALIDATE**: Run quickstart scenarios 1, 2, and 5 (login, access protected, logout)
5. Deploy/demo if ready

**MVP delivers**: Users can log in with email+password, receive JWT tokens, access protected endpoints, and log out. This is a functioning authentication system.

### Incremental Delivery

| Stage | Adds | Cumulative Value |
|-------|------|-----------------|
| MVP (US1) | Login, logout, protected endpoints | Users can authenticate |
| +US2 | Token refresh, rotation, reuse detection | Sessions persist without re-login; stolen-token detection |
| +US3 | Role-based access control | Different roles have different permissions |
| +US4 | User administration | Head coaches can manage user accounts |
| +US5 | Session revocation on security events | Password changes and disable immediately revoke access |
| +US6 | Rate limiting | Brute-force protection |
| +US7 | Audit logging | Complete security event trail |
| +Polish | Documentation, seed script, validation | Production-ready |
