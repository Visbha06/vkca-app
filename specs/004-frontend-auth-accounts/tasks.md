# Tasks: Frontend Authentication and Account Management

**Input**: Design documents from `/specs/004-frontend-auth-accounts/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Unit tests are MANDATORY per the constitution. One E2E Playwright test per spec is REQUIRED (placed in the Polish phase). Backend unit tests for new `PATCH /me` endpoint are MANDATORY.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `frontend/src/`, `frontend/e2e/`
- **Backend**: `backend/src/`, `backend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new directories and backend schema foundation

- [X] T001 Create frontend directory structure: `frontend/src/auth/` and `frontend/src/api/`
- [X] T002 [P] Add `ProfileUpdate` Pydantic schema in `backend/src/schemas/auth.py` with `first_name: str` and `last_name: str` (both required, non-empty)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core auth infrastructure that MUST be complete before ANY user story UI can be built

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 [P] Define TypeScript types (AuthUser, SessionMeta, AuthState, LoginCredentials, ProfileUpdateRequest, PasswordChangeRequest, ApiError, LoginResponse, RefreshResponse) in `frontend/src/auth/types.ts`
- [X] T004 [P] Implement CSRF cookie reader utility `readCsrfToken()` in `frontend/src/auth/utils.ts`
- [X] T005 [P] Implement `PATCH /api/v1/auth/me` route handler in `backend/src/routes/auth.py` (uses existing `get_current_user` dependency, returns `UserResponse`)
- [X] T006 [P] Add backend unit tests for `PATCH /api/v1/auth/me` in `backend/tests/unit/test_auth_routes.py` (test success, test unauthenticated, test validation errors)
- [X] T007 Implement centralized API client with token injection, credential inclusion, and CSRF header in `frontend/src/api/client.ts`
- [X] T008 Implement AuthContext and AuthProvider with full state management (user, accessToken, isAuthenticated, isInitializing, isLoginPending, isLogoutPending; login/logout/refreshSession actions; session restore on mount) in `frontend/src/auth/AuthContext.tsx` and `frontend/src/auth/AuthProvider.tsx`

**Checkpoint**: Foundation ready — auth state, API client, and backend endpoint available. User story UI can now begin.

---

## Phase 3: User Story 1 - Coach Login and Session Restoration (Priority: P1) 🎯 MVP

**Goal**: A coach can sign in with email/password, be redirected to the home page, and have their session automatically restored on page reload. Unauthenticated users are redirected to `/login`; authenticated users are redirected away from `/login`.

**Independent Test**: Enter valid credentials on login page → redirect to home page → refresh browser → session restored without re-login. Visit `/players` while logged out → redirected to `/login` → after login, redirected to `/players`. Visit `/login` while logged in → redirected to home.

### Tests for User Story 1 (MANDATORY unit tests) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Unit test for AuthContext (login success, login failure, session restore success, session restore failure, logout clearance) in `frontend/src/tests/AuthContext.test.tsx`
- [X] T010 [P] [US1] Unit test for LoginPage (renders form, required-field validation, Enter key submission, password visibility toggle, button disabled during submission) in `frontend/src/tests/LoginPage.test.tsx`
- [X] T011 [P] [US1] Unit test for ProtectedRoute (redirects unauthenticated to /login with redirect param, renders children for authenticated, shows nothing during initialization) in `frontend/src/tests/ProtectedRoute.test.tsx`

### Implementation for User Story 1

- [X] T012 [US1] Build LoginPage with VKCA branding, email/password inputs, show/hide toggle, login button, and Enter-key submission in `frontend/src/pages/LoginPage.tsx`
- [X] T013 [P] [US1] Build ProtectedRoute wrapper (redirects to `/login?redirect=<path>` when unauthenticated, renders children when authenticated, blank during initialization) in `frontend/src/auth/ProtectedRoute.tsx`
- [X] T014 [P] [US1] Build GuestRoute wrapper (redirects authenticated users to `/` or `redirect` param, renders children when unauthenticated) in `frontend/src/auth/GuestRoute.tsx`
- [X] T015 [US1] Restructure routes in `frontend/src/App.tsx`: add `/login` route with GuestRoute, wrap all existing routes with ProtectedRoute + AppLayout
- [X] T016 [US1] Wrap application in AuthProvider in `frontend/src/main.tsx`

**Checkpoint**: User Story 1 fully functional — login, session restore, route protection all working end-to-end.

---

## Phase 4: User Story 2 - Invalid Credentials and Error Handling (Priority: P2)

**Goal**: The login page displays safe, generic error messages for all failure modes. Loading and disabled states prevent duplicate submissions. Raw backend errors are never exposed.

**Independent Test**: Submit wrong password → "Invalid email or password." Submit unknown email → same message. Trigger network error → "Unable to sign in right now. Please try again." Trigger 429 → rate-limit message. Verify button shows loading spinner and is disabled during request.

### Tests for User Story 2 (MANDATORY unit tests) ⚠️

- [X] T017 [P] [US2] Unit test for login error messages in `frontend/src/tests/LoginPage.test.tsx` (extend existing: test invalid-credentials message, test network-error message, test rate-limit message, verify raw errors not displayed)

### Implementation for User Story 2

- [X] T018 [US2] Add error mapping logic to LoginPage: 401/credential errors → "Invalid email or password.", network/5xx → "Unable to sign in right now. Please try again.", 429 → "Too many sign-in attempts. Please wait and try again." in `frontend/src/pages/LoginPage.tsx`
- [X] T019 [US2] Add loading spinner + disabled-submit state to login button with accessible `aria-busy` communication in `frontend/src/pages/LoginPage.tsx`

**Checkpoint**: Login error handling complete — all error paths covered with safe, generic messages.

---

## Phase 5: User Story 3 - Logout (Priority: P2)

**Goal**: A red logout button in the sidebar footer clears the server session and local auth state, redirecting to `/login`. Local state is cleared even if the server request fails.

**Independent Test**: Click logout → redirected to `/login`. Verify access token cleared from memory. Verify revisiting protected route requires re-login. Simulate network failure during logout → still redirected, still appears logged out.

### Tests for User Story 3 (MANDATORY unit tests) ⚠️

- [X] T020 [P] [US3] Unit test for LogoutButton (renders with accessible label, calls logout action on click, handles pending state) in `frontend/src/tests/LogoutButton.test.tsx`

### Implementation for User Story 3

- [X] T021 [P] [US3] Build LogoutButton component (red exit icon, accessible label, calls `POST /api/v1/auth/logout` with CSRF token, clears state on success and failure) in `frontend/src/components/LogoutButton.tsx`
- [X] T022 [US3] Add LogoutButton to sidebar footer in `frontend/src/layouts/AppLayout.tsx` next to User Settings and collapse icons

**Checkpoint**: Logout fully functional — server session revoked, local state cleared, redirect to login.

---

## Phase 6: User Story 5 - Token Refresh and Expired Session Recovery (Priority: P2)

**Goal**: When an API request fails with 401, a transparent token refresh is attempted. On success, the original request is retried. On any failure, auth state is cleared and the user is redirected to `/login`. Multiple simultaneous 401s trigger only one refresh.

**Independent Test**: Mock expired token → trigger API call → verify refresh fires → verify original call retried. Mock refresh failure → verify redirect to `/login` with session-expired message. Trigger 3 simultaneous 401s → verify only 1 refresh request.

### Tests for User Story 5 (MANDATORY unit tests) ⚠️

- [X] T023 [US5] Unit test for token refresh interceptor (successful refresh + retry, failed refresh clears state, deduplication of concurrent refreshes, no infinite loops) in `frontend/src/tests/client.test.ts`

### Implementation for User Story 5

- [X] T024 [US5] Add refresh interceptor to API client: on 401 → queue refresh (single-flight dedup) → retry original request on success OR clear auth state + redirect on failure in `frontend/src/api/client.ts`
- [X] T025 [US5] Add redirect with session-expired message on refresh failure in the API client (integrate with AuthContext logout action)

**Checkpoint**: Token refresh transparently recovers from expired access tokens without user disruption.

---

## Phase 7: User Story 4 - Account Settings Modal (Priority: P3)

**Goal**: A modal dialog opens from the User Settings sidebar link, displaying read-only email/role and editable first/last name. A password-change section enforces policy and matching confirmation. Successful password change clears all sessions and redirects to `/login`.

**Independent Test**: Open settings → verify prefilled profile data → change name → save → verify state update without reload. Enter password policy violations → verify field errors. Enter compliant matching passwords → submit → verify redirect to `/login` with confirmation message. Test Escape close, backdrop click close, focus trap, body scroll lock.

### Tests for User Story 4 (MANDATORY unit tests) ⚠️

- [X] T026 [P] [US4] Unit test for PasswordInput (show/hide toggle, accessible label, keyboard behavior) in `frontend/src/tests/PasswordInput.test.tsx`
- [X] T027 [P] [US4] Unit test for AccountSettingsModal (renders profile fields prefilled, email/role read-only, validation on empty name fields, password policy validation, password confirmation mismatch, successful profile update, successful password change causes logout, focus trap, Escape close, backdrop close) in `frontend/src/tests/AccountSettingsModal.test.tsx`

### Implementation for User Story 4

- [X] T028 [P] [US4] Build PasswordInput component (password field with show/hide toggle, accessible label, keyboard-accessible) in `frontend/src/components/PasswordInput.tsx`
- [X] T029 [US4] Build AccountSettingsModal (dialog semantics, backdrop dim, focus trap, Escape/backdrop close, body scroll lock, accessible title) in `frontend/src/components/AccountSettingsModal.tsx`
- [X] T030 [US4] Implement profile section in modal (read-only email/role, editable first/last name prefilled, validation, save via `PATCH /api/v1/auth/me`, success/error feedback, state update without reload) in `frontend/src/components/AccountSettingsModal.tsx`
- [X] T031 [US4] Implement password-change section in modal (new password + confirm password fields with PasswordInput, frontend policy validation: 12-128 chars, uppercase, lowercase, digit, special char, match check, submission via `POST /api/v1/users/{id}/change-password`, 204 → clear state + redirect with message) in `frontend/src/components/AccountSettingsModal.tsx`
- [X] T032 [US4] Implement responsive modal behavior (fit viewport at 320px, internal scroll, 44px touch targets, no horizontal overflow) in `frontend/src/components/AccountSettingsModal.tsx`
- [X] T033 [US4] Implement accessibility for modal (role="dialog", aria-modal, aria-labelledby, focus trap, aria-describedby on errors, aria-live for success/error announcements, aria-busy during submission) in `frontend/src/components/AccountSettingsModal.tsx`
- [X] T034 [US4] Modify SettingsPage to automatically open AccountSettingsModal and handle close-navigation (return to previous route when known, else home) in `frontend/src/pages/SettingsPage.tsx`

**Checkpoint**: Account settings fully functional — profile editing, password change, modal UX, accessibility.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, and validation

- [ ] T035 [P] Write E2E Playwright test covering login → protected navigation → account settings modal → password change → logout flow in `frontend/e2e/auth-flow.spec.ts`
- [ ] T036 [P] Write feature documentation in `docs/frontend-auth-accounts.md` (concise version of spec, capturing purpose, key flows, API surface, configuration — MANDATORY per constitution)
- [ ] T037 Create quickstart validation test in `backend/tests/integration/quickstart/test_004_quickstart_flow.py` and execute: `cd backend && uv run pytest backend/tests/integration/quickstart/test_004_quickstart_flow.py -v` (validates the 15 scenarios in quickstart.md end-to-end)
- [ ] T038 Manually verify responsive behavior at 320px, 768px, 1280px, and 2560px viewports — confirm login page and settings modal have no horizontal overflow, 44px minimum touch targets, and internal scroll where needed
- [ ] T039 Final code review: verify no localStorage/sessionStorage token storage, no hardcoded px values, no `any` types, all components under 200 lines, dead code removed
- [ ] T040 Run full test suite: `cd frontend && npx vitest run && npx playwright test`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — MVP gate
- **User Story 2 (Phase 4)**: Depends on US1 (Phase 3) — extends LoginPage
- **User Story 3 (Phase 5)**: Depends on US1 (Phase 3) — uses AuthContext logout action
- **User Story 5 (Phase 6)**: Depends on US1 (Phase 3) — extends API client with refresh
- **User Story 4 (Phase 7)**: Depends on US1 + US3 (Phases 3, 5) — uses auth state and logout
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — No dependencies on other stories — 🎯 MVP
- **User Story 2 (P2)**: Depends on US1 (extends LoginPage) — should follow US1 immediately
- **User Story 3 (P2)**: Can start after US1 (uses AuthContext, but LogoutButton is independent component)
- **User Story 5 (P2)**: Can start after US1 (extends api/client.ts)
- **User Story 4 (P3)**: Depends on US1 + US3 (uses auth context for user data, logout action after password change)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Components before page integration
- Core behavior before error handling within the story
- Story complete before moving to next priority

### Parallel Opportunities

- T001 + T002 can run in parallel (Setup phase: frontend dirs vs backend schema)
- T003 + T004 + T005 + T006 can run in parallel (Foundational phase: types, utils, backend route, backend tests — all independent files)
- T009 + T010 + T011 can run in parallel (US1 tests: independent test files)
- T013 + T014 can run in parallel (US1 implementation: ProtectedRoute and GuestRoute are independent components)
- T026 + T027 can run in parallel (US4 tests: PasswordInput and AccountSettingsModal are independent)
- T028 can run in parallel with T027 (PasswordInput component + AccountSettingsModal tests are independent)
- T035 + T036 can run in parallel (Polish phase: E2E test + docs)
- US2, US3, and US5 can theoretically run in parallel after US1 if staffed (they modify different files: LoginPage, AppLayout, api/client)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (they must FAIL first):
Task: "Write unit test for AuthContext in frontend/src/tests/AuthContext.test.tsx"
Task: "Write unit test for LoginPage in frontend/src/tests/LoginPage.test.tsx"
Task: "Write unit test for ProtectedRoute in frontend/src/tests/ProtectedRoute.test.tsx"

# Then implement components in parallel:
Task: "Build LoginPage in frontend/src/pages/LoginPage.tsx"
Task: "Build ProtectedRoute in frontend/src/auth/ProtectedRoute.tsx"
Task: "Build GuestRoute in frontend/src/auth/GuestRoute.tsx"  # can run with ProtectedRoute

# Then integrate:
Task: "Restructure routes in frontend/src/App.tsx"
Task: "Wrap app in AuthProvider in frontend/src/main.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T008) — auth infrastructure
3. Complete Phase 3: User Story 1 (T009–T016) — login, session restore, route protection
4. **STOP and VALIDATE**: Test login, session restore, redirect flows manually
5. Deploy/demo if ready

### Incremental Delivery

| Phase | Stories | Cumulative Value |
|-------|---------|-----------------|
| After Phase 3 | US1 | Login + session restore + route protection (MVP) |
| After Phase 4 | US1 + US2 | Secure error handling, no information leakage |
| After Phase 5 | US1 + US2 + US3 | Full auth lifecycle: login → error → logout |
| After Phase 6 | US1 + US2 + US3 + US5 | Transparent token refresh, no mid-session disruption |
| After Phase 7 | All 5 stories | Profile editing + password change via settings modal |
| After Phase 8 | All + Polish | E2E tested, documented, validated |
