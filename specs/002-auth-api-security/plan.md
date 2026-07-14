# Implementation Plan: Authentication, Authorization, and API Security

**Branch**: `002-auth-api-security` | **Date**: 2026-07-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-auth-api-security/spec.md`

## Summary

Add password-based authentication with Argon2id hashing, HS256 JWT access tokens (30-minute TTL), opaque refresh tokens with rotation and reuse detection, server-side AuthSession storage, role-based access control (Head Coach / Assistant Coach / Staff), login rate limiting, CSRF protection on cookie-based endpoints, and comprehensive authentication audit logging. Replace the existing plaintext `hashed_password` field with proper server-side Argon2id password handling. Retrofits authorization dependencies on all existing protected routes.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI 0.139+, SQLAlchemy 2.0+ (async), Pydantic 2.13+, Alembic, asyncpg, python-jose (JWT), argon2-cffi (password hashing), secrets (stdlib — refresh token generation), hashlib (stdlib — refresh token hashing)

**Storage**: PostgreSQL — new `auth_sessions` table, new `auth_audit_log` table, migration to alter `users.hashed_password` column and `UserCreate`/`UserResponse` schemas

**Testing**: pytest 9.1+, pytest-asyncio 1.4+, pytest-mock 3.15+, httpx 0.28+ (existing stack)

**Target Platform**: Linux server (Docker-hosted PostgreSQL per docker-compose.yml)

**Project Type**: web-service (FastAPI backend API, React frontend consumer)

**Performance Goals**: login <2s (SC-001), auth check <500ms (SC-002), rate-limit response <100ms (SC-007)

**Constraints**: No credentials in API responses, logs, or error messages (FR-005, FR-044, FR-047). Generic error messages for all auth failures (FR-009). CSRF protection on refresh and logout endpoints (FR-020). No hardcoded secrets (FR-011).

**Scale/Scope**: Small-scale cricket team management app (handful of coaches/staff per organization). Single-instance rate limiter acceptable per spec assumption.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Code | ✅ PASS | New services/auth.py, models separated by concern. Single-responsibility functions for token creation, validation, hashing. |
| II. Simple UX | ✅ PASS | Login endpoint: email + password → tokens. Logout: revoke session. No complex multi-step flows. |
| III. Responsive Design | N/A | Backend-only feature; frontend auth components handled separately. |
| IV. Minimal Dependencies | ⚠️ REVIEW | Two new dependencies: `python-jose` (JWT) and `argon2-cffi` (password hashing). Both are well-established, actively maintained, and solve problems stdlib cannot: HS256 JWT signing/verification requires a JWT library; Argon2id requires the argon2-cffi binding. No stdlib alternatives exist. Justified in research.md. |
| V. Testing Discipline | ✅ PLAN | 47 FRs each map to unit/integration tests. Spec already enumerates test coverage requirements. Pytest fixtures for test client with auth headers. |
| VI. MCP Server Priority | N/A | Use when exploring code structure; not blocking. |
| VII. Database Migrations | ✅ PLAN | New migration: `007_create_auth_tables.py` (auth_sessions, auth_audit_log). Migration: alter users table (hashed_password semantics change — column kept, storage format changes to Argon2id). |
| VIII. UX Completeness | ✅ PASS | Spec covers error states (401/403/429), cookie behavior, and generic error messages. Frontend components are out of scope for this backend spec. |
| IX. Optimistic Concurrency | ✅ PLAN | AuthSession uses version column for OCC during token refresh (concurrent refresh detection). `check_and_increment_version` from `src/services/occ.py` reused. |
| X. Strongly-Typed API | ✅ PLAN | All auth request/response schemas are Pydantic models. Frontend will mirror types from OpenAPI schema. |
| XI. Frontend State | N/A | Backend feature; frontend auth integration is a separate task. |
| XII. Documentation | ✅ PLAN | `docs/auth-api-security.md` to be written after implementation, per constitution. |

**Gate result (pre-design)**: All applicable principles pass. Dependency additions justified. Proceed to Phase 0.

**Gate result (post-design, Phase 1)**: Re-evaluated after data-model.md, contracts/, and quickstart.md generated. No new violations introduced. The data model uses OCC for AuthSession (IX), all schemas are strongly typed Pydantic models (X), migration script is planned (VII), and new dependencies (`python-jose`, `argon2-cffi`) remain the only additions. Two new tables (`auth_sessions`, `auth_audit_log`) follow existing conventions. All 12 principles remain passing or N/A.

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-api-security/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── auth-endpoints.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── user.py              # MODIFY: hashed_password now stores Argon2id output
│   │   ├── auth_session.py      # NEW: AuthSession ORM model
│   │   └── auth_audit_log.py    # NEW: AuthAuditLog ORM model
│   ├── schemas/
│   │   ├── user.py              # MODIFY: hashed_password → password (plaintext input)
│   │   ├── auth.py              # NEW: LoginRequest, TokenResponse, RefreshRequest, CurrentUserResponse
│   │   └── audit.py             # NEW: AuditLogResponse (for head coach inspection)
│   ├── services/
│   │   ├── user_service.py      # MODIFY: hash password with Argon2id before storage
│   │   ├── auth_service.py      # NEW: login, logout, refresh, session mgmt, token creation/verification
│   │   ├── password_service.py  # NEW: Argon2id hashing & verification, password policy validation
│   │   ├── token_service.py     # NEW: JWT creation/verification, refresh token generation/hashing
│   │   ├── rate_limiter.py      # NEW: in-memory or DB-backed login rate limiter
│   │   └── audit_service.py     # NEW: audit log writer
│   ├── routes/
│   │   ├── users.py             # MODIFY: add authorization dependencies, password handling
│   │   ├── auth.py              # NEW: /login, /logout, /refresh, /me endpoints
│   │   ├── matches.py           # MODIFY: add auth dependency
│   │   ├── performances.py      # MODIFY: add auth dependency
│   │   ├── players.py           # MODIFY: add auth dependency
│   │   ├── stats.py             # MODIFY: add auth dependency
│   │   └── teams.py             # MODIFY: add auth dependency
│   ├── middleware/
│   │   └── auth.py              # NEW: FastAPI dependency for JWT verification + session check
│   ├── migrations/
│   │   └── versions/
│   │       └── 007_create_auth_tables.py  # NEW: auth_sessions, auth_audit_log tables
│   ├── config.py                # MODIFY: add JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, etc.
│   └── main.py                  # MODIFY: register auth router, add CSRF middleware
└── tests/
    ├── unit/
    │   ├── test_auth_routes.py       # NEW
    │   ├── test_auth_schemas.py      # NEW
    │   ├── test_auth_service.py      # NEW
    │   ├── test_password_service.py  # NEW
    │   ├── test_token_service.py     # NEW
    │   ├── test_rate_limiter.py      # NEW
    │   ├── test_audit_service.py     # NEW
    │   └── test_user_routes.py       # MODIFY: add auth + password tests
    └── integration/
        ├── test_auth_flow.py         # NEW: full login→refresh→logout flow
        ├── test_rbac.py              # NEW: role-based access tests
        ├── test_rate_limiting.py     # NEW: rate limit integration tests
        └── test_audit_logging.py     # NEW: audit log integration tests
```

**Structure Decision**: Web application structure (backend + frontend). This feature is backend-only; frontend auth integration is separate. New files follow the existing pattern: models in `src/models/`, schemas in `src/schemas/`, services in `src/services/`, routes in `src/routes/`. Authorization middleware in `src/middleware/auth.py` follows the existing `src/middleware/error_handlers.py` convention.

## Complexity Tracking

No constitution violations to justify. All principles pass or are N/A for this feature.
