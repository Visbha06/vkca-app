# Quickstart: Coaches Portal

**Feature**: 007-coaches-portal
**Date**: 2026-07-28

Validation scenarios that prove the feature works end-to-end. Backend scenarios are runnable via the quickstart integration test (`backend/tests/integration/quickstart/test_007_quickstart_flow.py`). Frontend validation requires a running dev server.

## Prerequisites

- Docker PostgreSQL container running (`docker compose up -d`)
- Backend virtual environment active with `uv sync`
- Database migrations applied (`alembic upgrade head`)
- Head Coach account seeded (`python -m scripts.seed_head_coach`)
- At least one team created (via `POST /teams` or seed data)

## Backend Validation

### 1. List Coaches (Default Filter)

```bash
# Authenticate as Head Coach
HC_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"head.coach@vkca.test","password":"Test1234!"}' \
  | jq -r '.access_token')

# List active coaches
curl -s http://localhost:8000/api/v1/coaches?status=active \
  -H "Authorization: Bearer $HC_TOKEN" | jq '.'
```

**Expected**: `200` with `coaches` array containing the Head Coach (role: "head coach"), `page: 1`, `page_size: 12`, `total_coaches >= 1`, `has_previous: false`.

### 2. Filter Inactive Coaches

```bash
curl -s "http://localhost:8000/api/v1/coaches?status=inactive" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '.'
```

**Expected**: `200` with `coaches` array containing only inactive coach accounts, `total_coaches` matching inactive count.

### 3. Filter All Coaches

```bash
curl -s "http://localhost:8000/api/v1/coaches?status=all" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '.'
```

**Expected**: `200` with both active and inactive coaches.

### 4. Pagination

```bash
curl -s "http://localhost:8000/api/v1/coaches?page=1&page_size=5" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '{page, page_size, total_pages, has_next}'
```

**Expected**: `200` with correct pagination metadata.

### 5. Stable Ordering

```bash
curl -s "http://localhost:8000/api/v1/coaches?status=all" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '[.coaches[] | {role, last_name, first_name}]'
```

**Expected**: Head Coach appears first, followed by Assistant Coaches ordered by last name ascending, then first name ascending.

### 6. Create Assistant Coach

```bash
TEAM_ID=$(curl -s http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $HC_TOKEN" | jq -r '.teams[0].id')

RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/coaches \
  -H "Authorization: Bearer $HC_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"first_name\":\"New\",\"last_name\":\"Coach\",\"email\":\"new.coach@vkca.test\",\"team_ids\":[\"$TEAM_ID\"]}")

echo "$RESPONSE" | jq '{id, role, is_active, temporary_password: (.temporary_password != null), teams: [.teams[].name]}'
```

**Expected**: `201` with `role: "assistant coach"`, `is_active: true`, `temporary_password` present (non-null string), `teams` contains the assigned team name.

### 7. Duplicate Email Rejection

```bash
curl -s -X POST http://localhost:8000/api/v1/coaches \
  -H "Authorization: Bearer $HC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Dup","last_name":"Coach","email":"new.coach@vkca.test"}' | jq '.'
```

**Expected**: `409` with detail containing "already exists".

### 8. Get Coach Details

```bash
COACH_ID=$(curl -s http://localhost:8000/api/v1/coaches?status=all \
  -H "Authorization: Bearer $HC_TOKEN" | jq -r '.coaches[] | select(.role=="assistant coach") | .id' | head -1)

curl -s "http://localhost:8000/api/v1/coaches/$COACH_ID" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '{first_name, last_name, role, is_active, teams}'
```

**Expected**: `200` with full coach details and team assignments.

### 9. Update Team Assignments

```bash
VERSION=$(curl -s "http://localhost:8000/api/v1/coaches/$COACH_ID" \
  -H "Authorization: Bearer $HC_TOKEN" | jq -r '.version_number')

TEAM_ID_2=$(curl -s http://localhost:8000/api/v1/teams \
  -H "Authorization: Bearer $HC_TOKEN" | jq -r '.teams[1].id // .teams[0].id')

curl -s -X PUT "http://localhost:8000/api/v1/coaches/$COACH_ID/teams" \
  -H "Authorization: Bearer $HC_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"team_ids\":[\"$TEAM_ID_2\"],\"version_number\":$VERSION}" | jq '{version_number, teams: [.teams[].name]}'
```

**Expected**: `200` with `version_number` incremented by 1, `teams` reflecting the new assignment set.

### 10. Stale Version Rejection (OCC)

```bash
# Submit with old version number
curl -s -X PUT "http://localhost:8000/api/v1/coaches/$COACH_ID/teams" \
  -H "Authorization: Bearer $HC_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"team_ids\":[\"$TEAM_ID_2\"],\"version_number\":$VERSION}" | jq '.'
```

**Expected**: `409` with "Stale version" detail.

### 11. Deactivate Coach

```bash
curl -s -X POST "http://localhost:8000/api/v1/users/$COACH_ID/disable" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '{is_active, version_number}'
```

**Expected**: `200` with `is_active: false`, `version_number` incremented. The coach cannot log in.

### 12. Reactivate Coach

```bash
curl -s -X POST "http://localhost:8000/api/v1/users/$COACH_ID/reactivate" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '{is_active, version_number}'
```

**Expected**: `200` with `is_active: true`, `version_number` incremented.

### 13. Self-Deactivation Rejection

```bash
HC_ID=$(curl -s http://localhost:8000/api/v1/coaches?status=all \
  -H "Authorization: Bearer $HC_TOKEN" | jq -r '.coaches[] | select(.role=="head coach") | .id')

curl -s -X POST "http://localhost:8000/api/v1/users/$HC_ID/disable" \
  -H "Authorization: Bearer $HC_TOKEN" | jq '.'
```

**Expected**: `403` with "Not authorized" or similar.

### 14. Player-Role Authorization Denial

```bash
# Authenticate as a player (if one exists) or just verify 403 behavior
curl -s http://localhost:8000/api/v1/coaches \
  -H "Authorization: Bearer invalid_or_player_token" | jq '.'
```

**Expected**: `401` (invalid token) or `403` (valid player token with insufficient role).

## Frontend Validation

### Setup

```bash
cd frontend
npm install
# Ensure VITE_API_BASE_URL points to the running backend
npm run dev
```

### Manual Walkthrough

1. **Login as Head Coach**: Navigate to `/login`, authenticate as Head Coach.
2. **Visit Coaches Portal**: Click "Coaches Portal" in sidebar. Verify:
   - Page heading "Coaches Portal" visible
   - Head Coach card displayed (light red avatar)
   - "Add Coach" button visible
   - Status filter defaulting to "Active"
3. **Create Assistant Coach**: Click "Add Coach", fill form, add team assignments, submit. Verify:
   - Success message with temporary password
   - Password is copyable
   - New coach card appears in grid
   - Card shows light blue avatar, proper team names
4. **Open Coach Details**: Click new coach card. Verify:
   - Modal shows full name, email, role, status, teams, placeholder stats
   - Edit Assignments control visible (Head Coach only)
   - Status toggle visible (Head Coach only)
5. **Edit Assignments**: Click "Edit Assignments". Verify:
   - Details modal closes, Team Assignments modal opens
   - Current assignments shown, all teams available
   - Add/remove teams, submit. Card updates.
6. **Deactivate Coach**: Open details, toggle status, confirm. Verify:
   - Card becomes muted
   - Coach cannot log in (test separately)
7. **Reactivate Coach**: Open inactive coach details, toggle status. Verify:
   - Card styling normalizes
8. **Test as Player**: Log in as Player-role user. Verify:
   - "Coaches Portal" nav item not visible
   - Navigate to `/coaches` directly → 403 Forbidden page
9. **Test as Assistant Coach**: Log in as Assistant Coach. Verify:
   - Coach cards visible
   - No Add Coach button
   - No status toggle
   - Inactive cards not interactive

## Quickstart Test

A pytest-based integration test validating all backend scenarios above exists at:

```
backend/tests/integration/quickstart/test_007_quickstart_flow.py
```

Run it with:

```bash
cd backend
uv run pytest tests/integration/quickstart/test_007_quickstart_flow.py -v
```

This test validates the complete backend quickstart flow: list, filter, paginate, order, create, duplicate rejection, detail, assignment update, OCC conflict, deactivate, reactivate, self-deactivation rejection, and authorization enforcement.
