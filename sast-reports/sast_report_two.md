# SAST Security Report — VKCA application repository

Date: 2026-08-22  
Analyzer: llm-sast-scanner v1.3.2  
Scope: Production FastAPI/SQLAlchemy backend, React/TypeScript frontend, background workers, RAG indexing/retrieval, configuration, migrations, and operational scripts. Tests, generated clients, examples, and development-only utilities were inspected for reachability but were not treated as production sinks by themselves.

## Executive Summary

No open Critical, High, Medium, or Low findings remain. The previously confirmed Low-severity player-profile resource-exhaustion finding, VULN-001, was remediated with bounded write validation, bounded legacy response projection, and an application-side request-body limit.

The previously reported unbounded performance batch is fixed by a 30-item schema limit. Authentication, JWT validation, refresh rotation, CSRF handling, role enforcement, SQL construction, RAG authorization, background-job deserialization, frontend rendering, and error normalization did not produce a confirmed finding.

## Critical Findings

None.

## High Findings

None.

## Medium Findings

None.

## Low Findings

None.

## Remediated Findings

### [LOW] VULN-001 — Uncontrolled resource consumption through unbounded player profile fields [REMEDIATED]

File: `backend/src/schemas/player.py:19`

Description: Player writes now limit biographies to 2,000 characters and metadata to 8 KiB of compact UTF-8 JSON, four container levels, 50 keys per object, 100 characters per key, 50 items per array, and 2,000 characters per string. Metadata accepts only JSON-compatible finite values.

Response defense: Compliant values remain unchanged. Oversized legacy biographies are projected to 2,000 characters and legacy metadata violating any current bound is projected to `{}` without mutating the database row.

Request defense: FastAPI rejects mutation bodies above 256 KiB with HTTP 413 before route validation or persistence. A production reverse proxy must enforce the same or a stricter limit to reject oversized traffic before it reaches the application process.

Evidence:

```python
# backend/src/schemas/player.py
PLAYER_BIO_MAX_LENGTH = 2_000
PLAYER_METADATA_MAX_BYTES = 8 * 1_024
PLAYER_METADATA_MAX_DEPTH = 4
PLAYER_METADATA_MAX_KEYS = 50
PLAYER_METADATA_MAX_KEY_LENGTH = 100
PLAYER_METADATA_MAX_ARRAY_ITEMS = 50
PLAYER_METADATA_MAX_STRING_LENGTH = 2_000
```

```python
# backend/src/main.py
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=get_settings().request_body_max_bytes,
)
```

Verification: Create and update use the same annotated schema types and recursive validator before persistence. Boundary tests cover exact-limit acceptance and over-limit rejection. A database integration test bypasses Pydantic, inserts an oversized legacy row, verifies the directory response stays bounded, and verifies storage is unchanged. A route test verifies a 413 response without invoking the player service, and middleware tests cover chunked requests without `Content-Length`.

Reference: `references/denial_of_service.md`

## Informational

None.

## Unverifiable Findings

None.

## Judge Review and Rejected Candidates

- **Development seed credential:** `backend/scripts/seed_dev_head_coach.py:19-20` contains public development credentials, but the executable is explicitly development-scoped and deployment documentation says the values must not be used outside isolated local environments. Under the scanner's demo/local-development guard, this is not reported as a production default-credential finding. The stale documentation still names the removed `scripts/seed_head_coach.py`; production bootstrap should continue to fail closed and must never invoke the development seed.
- **Performance-batch exhaustion:** Rejected because `backend/src/schemas/performance.py:11-13,74-77` now caps each request at 30 records and each notes field at 1,000 characters.
- **SQL injection:** SQLAlchemy expressions bind request values. The Bandit migration warning at `backend/src/migrations/versions/008_rename_staff_role_to_player.py:22` interpolates only module-owned enum literals into a one-time migration; no user-controlled source reaches it.
- **Authentication/JWT:** `backend/src/services/token_service.py:72-90` pins the configured algorithm and requires token claims; `backend/src/middleware/auth.py:44-77` binds tokens to active server-side sessions and current database users; authorization uses the database role rather than the JWT role claim.
- **CSRF and cookies:** Cookie-authenticated refresh and logout validate a double-submit CSRF token. Other mutations require a bearer token. Secure-cookie behavior behind TLS termination remains deployment-sensitive but is not provably exploitable from repository configuration.
- **Brute force:** The public login path has a visible five-failure sliding-window limiter. Its process-local design is a scaling hardening concern, not an absent-limiter finding.
- **RAG authorization and resource bounds:** Retrieval query length and result count are bounded, scope is derived from current database relationships, and authorization is embedded in the SQL predicate before vector ordering. Provider failures are normalized.
- **Background jobs:** Job types and handlers are allowlisted, payloads use strict bounded JSON rather than pickle, queue messages are size-limited, and retry/concurrency settings have finite bounds.
- **XSS/open redirect:** User content is rendered through React JSX escaping; no raw-HTML sink was found. Login redirect helpers accept only single-slash relative paths.
- **File, network, and parser sinks:** No production upload, attacker-controlled file read/write, shell/process execution, outbound-URL fetch, unsafe object deserialization, XML parser, GraphQL, SSTI, JNDI, or expression-language sink was found.

## Verification

- Bandit 1.9.4 scanned 22,833 backend source lines: zero High findings; its one Medium SQL warning and three Low `assert` warnings were manually rejected after reachability review.
- Ruff passed across `src`, `tests`, and `scripts`; mypy passed across 140 source files.
- 59 focused backend player-schema, player-route, and request-limit tests passed; the legacy-row integration test passed against PostgreSQL.
- The full backend suite passed: 761 tests in 20.84 seconds.
- The focused frontend form suite passed: 9 tests. Frontend lint and production build also passed.
- The local `.env` file is ignored by Git and has owner-only mode `0600`; its values were not read or included in this report.

## Remediation Priority

No repository code remediation remains for VULN-001. Production deployments must configure their trusted reverse proxy with a request-body limit of 256 KiB or less.
