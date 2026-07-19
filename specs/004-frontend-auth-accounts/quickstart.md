# Quickstart: Frontend Authentication and Account Management

**Feature**: 004-frontend-auth-accounts
**Date**: 2026-07-19

## Prerequisites

- Docker running with PostgreSQL (via `docker-compose up -d db`)
- Backend API running on `http://localhost:8000`
  ```bash
  cd backend && uv run uvicorn src.main:app --reload
  ```
- Frontend dev server running on `http://localhost:5173`
  ```bash
  cd frontend && npm run dev
  ```
- A seeded head coach user (existing: `cd backend && uv run python scripts/seed_head_coach.py`)
- Node.js 18+ and npm installed

## Validation Scenarios

### 1. Unauthenticated User Lands on Login Page

**Command**:
```bash
# Open browser to http://localhost:5173
# Verify you are redirected to /login
```

**Expected**: The login page displays with VK Cricket Academy branding, email input, password input, show/hide password toggle, and Login button. No sidebar is visible.

### 2. Required Field Validation

**Steps**:
1. Click Login with both fields empty.
2. Enter an email but no password, click Login.

**Expected**: Field-level validation errors appear. Form is not submitted. Login button remains enabled but validation blocks submission.

### 3. Invalid Credentials (Generic Error)

**Steps**:
1. Enter `wrong@example.com` / `wrongpassword`.
2. Click Login.

**Expected**: Message "Invalid email or password." appears. Does not say "account not found" or "incorrect password."

### 4. Successful Login

**Steps**:
1. Enter valid head coach credentials (from seed script).
2. Click Login.
3. Observe redirect.

**Expected**: Redirected to home page. Sidebar appears with navigation items. User's role is displayed in the sidebar or header.

### 5. Session Restoration (Page Reload)

**Steps**:
1. After successful login, refresh the page (F5).

**Expected**: No flash of login page. Home page loads directly with authenticated sidebar. No re-login required.

### 6. Protected Route Redirect

**Steps**:
1. Log out (if authenticated).
2. Navigate directly to `http://localhost:5173/players`.

**Expected**: Redirected to `/login?redirect=%2Fplayers`. After successful login, redirected to `/players`.

### 7. Authenticated User Redirected from /login

**Steps**:
1. Log in.
2. Navigate to `http://localhost:5173/login`.

**Expected**: Redirected to home page immediately.

### 8. Logout

**Steps**:
1. Log in.
2. Click the red logout icon in the sidebar footer.
3. Observe redirect.

**Expected**: Redirected to `/login`. Sidebar disappears. Attempting to navigate to `/` redirects to `/login`.

### 9. Account Settings Modal

**Steps**:
1. Log in.
2. Click the User Settings icon in sidebar footer.
3. Observe modal.

**Expected**: Modal opens above dimmed background. Shows email (read-only), role (read-only), first name (editable), last name (editable). Password change section below.

### 10. Profile Update

**Steps**:
1. Open account settings modal.
2. Change first name to "UpdatedName".
3. Click Save.

**Expected**: Success feedback displayed. Sidebar/user display reflects new name without page reload.

### 11. Password Change (Validation)

**Steps**:
1. Open account settings modal.
2. Enter "short" in new password field.
3. Enter mismatched confirm password.

**Expected**: Field-level errors: password too short, password policy violations listed, confirmation mismatch.

### 12. Password Change (Success → Logout)

**Steps**:
1. Open account settings modal.
2. Enter compliant new password and matching confirmation.
3. Click Change Password.

**Expected**: Redirected to `/login` with message "Your password was changed. Please sign in again." Attempting to log in with old password fails; new password works.

### 13. Modal Keyboard & Accessibility

**Steps**:
1. Open account settings modal.
2. Press Tab repeatedly — focus cycles within modal.
3. Press Escape — modal closes.

**Expected**: Focus trapped in modal while open. Escape closes modal. Focus returns to sidebar trigger upon close.

### 14. Responsive Login Page

**Steps**:
1. Resize browser to 320px wide.
2. View login page.

**Expected**: Form fits without horizontal overflow. Inputs and button are at least 44px tall. Password toggle is tappable.

### 15. Responsive Settings Modal

**Steps**:
1. Log in on a 320px-wide viewport.
2. Open settings modal.

**Expected**: Modal fits within viewport. Content scrolls internally if taller than viewport. Close button accessible.

## Automated Test Execution

### Backend Tests (PATCH /me)

```bash
cd backend
uv run pytest tests/unit/test_auth_routes.py -k "test_patch_me" -v
```

### Frontend Unit Tests

```bash
cd frontend
npx vitest run src/tests/
```

### Frontend E2E Test

```bash
cd frontend
npx playwright test e2e/auth-flow.spec.ts
```
