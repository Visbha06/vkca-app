# Data Model: Authentication, Authorization, and API Security

**Feature**: 002-auth-api-security
**Date**: 2026-07-12

## Entity Changes

### User (MODIFIED)

**Table**: `users`

Changes from existing model:

| Field | Old | New | Migration |
|-------|-----|-----|-----------|
| `hashed_password` | `VARCHAR(255)` — stored any client-submitted value | `VARCHAR(255)` — stores Argon2id hash output (`$argon2id$v=19$...`, ~100 bytes). Semantics change: column kept, storage format changes. | No DDL change needed; existing dev users must be recreated with properly hashed passwords. |
| `email` | Stored as-submitted | Stored lowercased. Application-level normalization on create. | Data migration: `UPDATE users SET email = LOWER(email)`. |

No column additions to the `users` table. No column removals.

Schema changes:
- `UserCreate.hashed_password` field → `UserCreate.password` field (plaintext, validated by password policy)
- `UserCreate` adds `@field_validator` for password policy (min 12, max 128, uppercase, lowercase, digit, special char)
- `UserResponse` unchanged — already excludes password hash

### AuthSession (NEW)

**Table**: `auth_sessions`

Represents a single login session. Owned by one User. Each login creates one AuthSession row. Token rotation updates the row rather than creating new rows.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `UUID` | PK, `gen_random_uuid()` | Session ID (appears as `sid` in JWT) |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL, INDEX | Owning user |
| `token_family_id` | `UUID` | NOT NULL, INDEX | Shared by all tokens in rotation chain |
| `current_token_hash` | `VARCHAR(64)` | NOT NULL | SHA-256 hex digest of the current valid refresh token |
| `rotated_token_hashes` | `JSONB` | NOT NULL, DEFAULT `'[]'` | Array of SHA-256 hex digests of previously used tokens. Used for reuse detection. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()` | Session creation time |
| `last_used_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()` | Last token refresh time (for inactivity expiration) |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | Absolute expiration: `created_at + 30 days` |
| `revoked_at` | `TIMESTAMPTZ` | NULLABLE | Set on logout, password change, disablement, or token reuse |
| `revocation_reason` | `VARCHAR(50)` | NULLABLE | Enum: `logout`, `password_change`, `user_disabled`, `token_reuse`, `admin_revocation` |
| `ip_address` | `VARCHAR(45)` | NULLABLE | Source IP (IPv4 or IPv6) at login |
| `user_agent` | `VARCHAR(512)` | NULLABLE | User-Agent header at login |
| `version_number` | `INTEGER` | NOT NULL, DEFAULT 1 | OCC version for concurrent refresh detection |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()` | Duplicate of `created_at` — this row is also a `TimestampMixin` |

**Inactivity check**: `last_used_at > NOW() - INTERVAL '7 days'` for active sessions.
**Absolute expiry**: `expires_at > NOW()`.
**Active session**: `revoked_at IS NULL AND expires_at > NOW() AND last_used_at > NOW() - INTERVAL '7 days'`.

**Indexes**:
- `idx_auth_sessions_user_id` on `user_id` — for "revoke all user sessions" operations
- `idx_auth_sessions_token_family` on `token_family_id` — for token family lookup
- `idx_auth_sessions_current_hash` on `current_token_hash` — for refresh token lookup
- `idx_auth_sessions_rotated_hashes` GIN index on `rotated_token_hashes` — for reuse detection via `@>` operator

**Token States** (as required by FR-014 clarification):
1. **(a) Current valid**: `current_token_hash` column — the single refresh token that can be used for the next refresh
2. **(b) Previously used**: `rotated_token_hashes` JSONB array — tokens that have been rotated; a match triggers family revocation
3. **(c) Token family**: `token_family_id` — links all tokens in a rotation chain; used for family-wide revocation on reuse

**Lifecycle**:
```
Login → CREATE (new session, new token_family_id, first current_token_hash)
Refresh → UPDATE (current_token_hash → push to rotated_token_hashes, new current_token_hash, bump last_used_at)
Logout → UPDATE (set revoked_at, revocation_reason='logout')
Password change → UPDATE (revoked_at, revocation_reason='password_change') for ALL user's sessions
User disable → UPDATE (revoked_at, revocation_reason='user_disabled') for ALL user's sessions
Token reuse → UPDATE (revoked_at, revocation_reason='token_reuse') for ALL sessions with same token_family_id
Expiry → No update needed; queries filter WHERE expires_at > NOW()
```

### AuthAuditLog (NEW)

**Table**: `auth_audit_log`

Append-only log of all authentication and authorization events. Never updated, never deleted.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `UUID` | PK, `gen_random_uuid()` | Unique audit record ID |
| `event_type` | `VARCHAR(30)` | NOT NULL, INDEX | Enum: `login`, `failed_login`, `logout`, `token_refresh`, `token_reuse`, `session_revocation`, `authorization_denial`, `user_disablement`, `password_change`, `role_change`, `rate_limit` |
| `user_id` | `UUID` | NULLABLE, FK → `users.id` | Target user (NULL for failed logins with unknown email) |
| `session_id` | `UUID` | NULLABLE, FK → `auth_sessions.id` | Related session (NULL for non-session events like failed login) |
| `result` | `VARCHAR(10)` | NOT NULL | `success` or `failure` |
| `reason` | `VARCHAR(100)` | NULLABLE | Failure or revocation reason (e.g., `invalid_password`, `account_disabled`, `rate_limited`) |
| `ip_address` | `VARCHAR(45)` | NULLABLE | Source IP address |
| `user_agent` | `VARCHAR(512)` | NULLABLE | User-Agent header |
| `target_resource` | `VARCHAR(255)` | NULLABLE | API path or operation that triggered the event |
| `event_timestamp` | `TIMESTAMPTZ` | NOT NULL, DEFAULT `NOW()`, INDEX | When the event occurred |

**Indexes**:
- `idx_audit_event_type` on `event_type`
- `idx_audit_user_id` on `user_id`
- `idx_audit_timestamp` on `event_timestamp`
- Composite: `(event_type, event_timestamp)` for filtered time-range queries

**What is NOT stored**: Passwords, password hashes, access tokens, refresh tokens, token hashes, signing secrets, or other credentials (enforced by FR-044 and FR-005).

## Entity Relationship Diagram

```
User (1) ────< (many) AuthSession
  │                    │
  │                    │ (nullable FK for session events)
  │                    │
  ├──< (many) AuthAuditLog (nullable user_id for unknown-email events)
  │
  └── (existing relationships: players, teams, etc.)
```

## Migration Notes

### Migration 007: Create Auth Tables

Creates `auth_sessions` and `auth_audit_log` tables with all indexes.

### Data Migration: Email Normalization

```sql
UPDATE users SET email = LOWER(email);
```

Run as part of migration 007 or as a separate data-only migration.

### Existing Users

Development users with placeholder `hashed_password` values must be recreated. The migration script should:
1. Drop all existing users (dev environment only)
2. Document that a head coach must create new users via the API after deployment

Production deployments: this is a greenfield app; no production user data exists.
