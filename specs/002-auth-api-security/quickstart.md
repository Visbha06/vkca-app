# Quickstart: Authentication, Authorization, and API Security

**Feature**: 002-auth-api-security
**Date**: 2026-07-12

Validation guide for end-to-end testing of the authentication and authorization system.

## Prerequisites

- Docker running (PostgreSQL via `docker-compose up -d`)
- Python 3.12+ with `uv` installed
- `.env` file with `DATABASE_URL` and `JWT_SECRET` set
- Migrations applied (`uv run alembic upgrade head`)

## Setup

```bash
# From repo root
cd backend

# Install dependencies (includes new: python-jose, argon2-cffi)
uv sync

# Apply migrations (creates auth_sessions + auth_audit_log tables)
uv run alembic upgrade head

# Seed a head coach user for initial access
uv run python scripts/seed_head_coach.py
# Creates: headcoach@vkca.test / SuperSecur3!P@ss
```

## Start the Server

```bash
uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

## Validation Scenarios

### Scenario 1: Login (User Story 1)

```bash
# Successful login
curl -v -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"SuperSecur3!P@ss"}' \
  -c cookies.txt

# Expected: 200, access_token in body, refresh_token + csrf_token cookies set
```

```bash
# Failed login - wrong password
curl -v -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"wrong"}'

# Expected: 401, {"detail": "Invalid credentials"}
```

```bash
# Failed login - nonexistent email (response must be byte-identical to wrong password)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"noone@vkca.test","password":"anything"}'

# Expected: 401, {"detail": "Invalid credentials"} — byte-for-byte identical
```

### Scenario 2: Access Protected Resource (User Story 1/3)

```bash
# Extract access token from login response
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"SuperSecur3!P@ss"}' \
  -c cookies.txt | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Access current user
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Expected: 200, user profile with role "head coach", is_active true, session info
```

### Scenario 3: Token Refresh (User Story 2)

```bash
# Login first
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"SuperSecur3!P@ss"}' \
  -c cookies.txt

# Read CSRF token from cookies.txt
CSRF=$(grep csrf_token cookies.txt | awk '{print $NF}')

# Refresh
curl -v -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "X-CSRF-Token: $CSRF" \
  -b cookies.txt -c cookies.txt

# Expected: 200, new access_token, cookies.txt updated with new refresh_token + csrf_token
```

### Scenario 4: Refresh Token Reuse Detection (User Story 2)

```bash
# Save the current refresh token
OLD_REFRESH=$(grep refresh_token cookies.txt | awk '{print $NF}')

# Do a refresh (rotates the token)
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "X-CSRF-Token: $(grep csrf_token cookies.txt | awk '{print $NF}')" \
  -b cookies.txt -c cookies.txt

# Try to use the OLD refresh token (replay attack simulation)
# Write the old token back to cookies
echo -e "127.0.0.1\tFALSE\t/api/v1/auth\tFALSE\t0\trefresh_token\t$OLD_REFRESH" > old_cookies.txt

curl -v -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "X-CSRF-Token: $(grep csrf_token cookies.txt | awk '{print $NF}')" \
  -b old_cookies.txt

# Expected: 401, entire token family revoked, audit log records token_reuse event
```

### Scenario 5: Logout (User Story 5)

```bash
# Login fresh
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"SuperSecur3!P@ss"}' \
  -c cookies.txt

CSRF=$(grep csrf_token cookies.txt | awk '{print $NF}')

# Logout
curl -v -X POST http://localhost:8000/api/v1/auth/logout \
  -H "X-CSRF-Token: $CSRF" \
  -b cookies.txt

# Expected: 204, cookies cleared

# Verify access token is rejected
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"SuperSecur3!P@ss"}' \
  -c cookies2.txt | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/v1/auth/logout \
  -H "X-CSRF-Token: $(grep csrf_token cookies2.txt | awk '{print $NF}')" \
  -b cookies2.txt

curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Expected: 401 (access token from revoked session rejected)
```

### Scenario 6: Role-Based Access Control (User Story 3)

```bash
# Create assistant coach and staff users (requires head coach token)
HC_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"headcoach@vkca.test","password":"SuperSecur3!P@ss"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create assistant coach
curl -s -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $HC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Asst","last_name":"Coach","email":"asst@vkca.test","password":"AsstP@ssword1","role":"assistant coach"}'

# Login as assistant coach
AC_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"asst@vkca.test","password":"AsstP@ssword1"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Assistant coach can create players
curl -s -X POST http://localhost:8000/api/v1/players \
  -H "Authorization: Bearer $AC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Test","last_name":"Player","playing_role":"batter","batting_style":"right","bowling_style":"right-arm off-break"}'
# Expected: 201

# Assistant coach CANNOT create users
curl -s -X POST http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $AC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Bad","last_name":"Actor","email":"bad@vkca.test","password":"BadP@ssword1","role":"staff"}'
# Expected: 403
```

### Scenario 7: Rate Limiting (User Story 6)

```bash
# Submit 6 failed logins in rapid succession
for i in $(seq 1 6); do
  echo "Attempt $i:"
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"ratelimit@vkca.test","password":"wrong"}'
  echo ""
done

# Expected: First 5 return 401, 6th returns 429
```

### Scenario 8: Audit Log Inspection (User Story 7)

```bash
# After running the above scenarios, check audit logs
# (Requires a head coach token)
curl -s http://localhost:8000/api/v1/auth/audit-log \
  -H "Authorization: Bearer $HC_TOKEN" | python3 -m json.tool | head -50

# Expected: Array of audit records. Verify:
# - No passwords, tokens, or hashes in any record
# - event_type values match operations performed
# - result is "success" or "failure"
# - ip_address and user_agent are present where available
```

## Automated Test Suite

```bash
# Run all auth-related tests
cd backend
uv run pytest tests/unit/test_auth_*.py tests/unit/test_password_service.py \
  tests/unit/test_token_service.py tests/unit/test_rate_limiter.py \
  tests/integration/test_auth_flow.py tests/integration/test_rbac.py \
  tests/integration/test_rate_limiting.py -v

# Expected: All tests pass
```

## Expected Outcomes

| Scenario | Expected Result |
|----------|----------------|
| Login (valid) | 200 + access_token + cookies |
| Login (wrong password) | 401, "Invalid credentials" |
| Login (nonexistent email) | 401, identical to wrong password response |
| Login (disabled user) | 401, identical to wrong password response |
| Access protected route | 200 with authorized data |
| Access without token | 401 |
| Access with insufficient role | 403 |
| Token refresh | 200 + new tokens, old refresh token revoked |
| Refresh token reuse | 401, token family revoked |
| Logout | 204, tokens invalidated |
| Password change | All sessions revoked immediately |
| Role change | Takes effect on next request |
| Rate limit (6th attempt) | 429 |
| Audit log | Contains all events, no credentials |
| CSRF (missing header) | 403 |
