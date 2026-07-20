# Feature Specification: Frontend Authentication and Account Management

**Feature Branch**: `004-frontend-auth-accounts`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Part 4: Authentication and Account Management Interface — Build the frontend authentication and account management interface for the VK Cricket Academy web application. This specification adds the login page, protected-route behavior, session restoration, logout, current-user state, and user settings modal. It integrates with the existing backend authentication API and existing frontend application shell."

## Clarifications

### Session 2026-07-19

- Q: What is the password-change endpoint? → A: `POST /api/v1/users/{id}/change-password`.
- Q: Does the password-change form require the current password? → A: No — only new password and confirm password are required.
- Q: Where should the user go when the settings modal closes after direct navigation to `/settings`? → A: Return to the previously active route when known; otherwise the home page.
- Q: What response codes from a refresh attempt should clear authentication state? → A: Any unsuccessful response (401, 403, 429, network error, server error) clears authentication state and redirects to `/login`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coach Login and Session Restoration (Priority: P1)

A coach opens the VK Cricket Academy portal, enters their email and password on the login page, and is taken to the home page. On subsequent visits, their session is restored automatically without re-entering credentials, so they can resume work immediately.

**Why this priority**: Login is the gateway to every other feature. Without authentication, no protected route is usable. Session restoration eliminates daily friction for returning users.

**Independent Test**: Can be fully tested by entering valid credentials on the login page, verifying redirect to home, closing the browser, reopening, and confirming automatic restoration to the authenticated home page without seeing a login screen.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user on the login page, **When** they enter a valid email and password and submit, **Then** they are redirected to the home page and see the authenticated sidebar with their role.
2. **Given** a previously authenticated user who closed their browser, **When** they reopen the application, **Then** their session is restored and they land on the home page without seeing the login form.
3. **Given** a user with an expired session who reopens the application, **When** session restoration fails, **Then** they see the login page with a "Your session has expired. Please sign in again." message.
4. **Given** an authenticated user, **When** they navigate to `/login`, **Then** they are redirected to the home page.
5. **Given** an unauthenticated user who attempts to visit `/players`, **When** the page loads, **Then** they are redirected to `/login` and after successful login return to `/players`.

---

### User Story 2 - Invalid Credentials and Error Handling (Priority: P2)

A coach mistypes their password or enters an unregistered email. The login page shows a single clear, safe error message without revealing whether the account exists or the password was wrong. Rate-limiting and network errors are communicated with equally safe, non-revealing messages.

**Why this priority**: Security-appropriate error handling prevents user enumeration while keeping legitimate users informed. It must ship with login, but the happy path (P1) delivers more immediate value.

**Independent Test**: Can be tested by submitting wrong credentials, empty fields, and triggering network failures, then verifying that error messages are generic, safe, and displayed accessibly.

**Acceptance Scenarios**:

1. **Given** the login form, **When** a user submits an email with a wrong password, **Then** the message "Invalid email or password." is displayed — not "incorrect password" or "account not found".
2. **Given** the login form, **When** a user submits an email that is not registered, **Then** the same "Invalid email or password." message is displayed.
3. **Given** the login form, **When** the backend is unreachable or returns a server error, **Then** "Unable to sign in right now. Please try again." is displayed.
4. **Given** a user has made too many login attempts, **When** they submit again, **Then** "Too many sign-in attempts. Please wait and try again." is displayed — without revealing whether the submitted account exists.
5. **Given** the login form, **When** a user submits with an empty email or password field, **Then** field-level validation errors appear and the form is not submitted.

---

### User Story 3 - Logout (Priority: P2)

A coach finishes their session and clicks a clearly visible logout button in the sidebar. Their server-side session is revoked, their local authentication state is cleared, and they are returned to the login page. Even if the server request fails, the local state is cleaned up so the interface does not appear authenticated.

**Why this priority**: Logout is a fundamental security boundary. It must be reliable and visually discoverable alongside login.

**Independent Test**: Can be tested by logging in, clicking the logout control, and verifying redirection to `/login`, cleared in-memory state, and that revisiting a protected route requires re-authentication.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they click the logout button in the sidebar, **Then** their access token is cleared, they are redirected to `/login`, and the backend session is revoked.
2. **Given** an authenticated user, **When** the logout API call fails (e.g., network error), **Then** local authentication state is still cleared, they are redirected to `/login`, and the interface does not appear authenticated.
3. **Given** an authenticated user with multiple active sessions on different devices, **When** they log out on one device, **Then** only that device's session is revoked; other devices remain authenticated.
4. **Given** the application sidebar in its expanded and collapsed states, **When** viewed on desktop or mobile, **Then** a red logout control is visible in the sidebar footer next to the User Settings and collapse icons.

---

### User Story 4 - Account Settings Modal (Priority: P3)

A coach opens the User Settings from the sidebar. A modal dialog overlays the current page, displaying their profile information. They can update their first and last name, change their password, and close the modal to return to their previous page. The modal supports keyboard navigation, focus trapping, and responsive display.

**Why this priority**: Profile management is important for personalization and security, but the application is usable without it. Login and protected routing (P1-P2) deliver the core authentication experience first.

**Independent Test**: Can be tested by opening the settings modal, verifying prefilled profile data, submitting a name change, toggling password visibility, changing the password, verifying logout after password change, and testing modal close via button, Escape key, and backdrop.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they click "User Settings" in the sidebar, **Then** a modal opens over a dimmed background showing their email (read-only), role (read-only), prefilled first name, and prefilled last name.
2. **Given** the settings modal is open, **When** the user presses Escape or clicks the close button, **Then** the modal closes and focus returns to the sidebar trigger.
3. **Given** the settings modal is open, **When** the user changes their first name and saves, **Then** a success message appears, the displayed name updates in the shared auth state, and no full page reload occurs.
4. **Given** the profile form, **When** the user clears a required field and tries to save, **Then** a field-level validation error is shown and submission is blocked.
5. **Given** the password-change section, **When** the user enters a new password that meets all policy requirements and a matching confirmation, **Then** the password is updated, all active sessions are revoked, and the user is redirected to `/login` with the message "Your password was changed. Please sign in again."
6. **Given** the password-change form, **When** the new password and confirmation do not match, **Then** a field-level error is shown on the confirmation field.
7. **Given** the password-change form, **When** the new password violates any policy rule (too short, missing uppercase, etc.), **Then** the corresponding field-level validation error is displayed and submission is blocked.
8. **Given** the settings modal, **When** viewed on a mobile device (320px wide), **Then** the modal fits within the viewport, content scrolls internally if needed, and controls remain large enough for touch targets.
9. **Given** the settings modal is open, **When** the user presses Tab repeatedly, **Then** focus cycles within the modal and never escapes to the background page.

---

### User Story 5 - Token Refresh and Expired Session Recovery (Priority: P2)

While a coach is actively using the application, their access token expires. A queued API request triggers a transparent token refresh. If the refresh succeeds, the original request is retried without the coach noticing any interruption. If the refresh fails (e.g., refresh token expired), the coach is redirected to login with a clear session-expired message.

**Why this priority**: Silent token refresh maintains the illusion of a persistent session during normal use, which is critical for a smooth coaching workflow. It must be paired with login (P1) to avoid users being logged out mid-task.

**Independent Test**: Can be tested by mocking an expired access token response, triggering an API call, and verifying that a refresh occurs, the original call is retried, and the UI never flashes to an unauthenticated state. Refresh-failure behavior can be tested by mocking a failed refresh and verifying redirection to login.

**Acceptance Scenarios**:

1. **Given** an authenticated user whose access token has expired, **When** an API request returns 401, **Then** a single token refresh is attempted; upon success, the original request is retried and the user sees the expected data.
2. **Given** multiple API requests that fail with 401 simultaneously, **When** the first triggers a refresh, **Then** subsequent requests wait for the same refresh, avoiding duplicate refresh calls.
3. **Given** a refresh attempt that returns any unsuccessful response (401, 403, 429, network error, or server error), **When** the response is received, **Then** authentication state is cleared and the user is redirected to `/login` with "Your session has expired. Please sign in again."
4. **Given** a refresh is already in progress, **When** a second 401 occurs, **Then** no duplicate refresh request is sent and no infinite loop occurs.

---

### Edge Cases

- What happens when the login form is submitted while Enter is held (key repeat)? The button is disabled after the first submission, preventing duplicate requests.
- What happens when the user's browser has cookies disabled? Session restoration will fail; the user sees the login page with a generic network-error message.
- What happens when the backend returns a malformed or unexpected response during login? The generic "Unable to sign in right now" message is shown; raw errors are not displayed.
- What happens when the user navigates to `/settings` directly via URL? The authenticated shell loads and the settings modal opens automatically. If unauthenticated, they are redirected to `/login` first.
- What happens if the user clicks the sidebar navigation while the settings modal is open? The modal closes (returning to the previously active page), then navigation proceeds to the clicked route.
- What happens when the modal closes after direct navigation to `/settings` (e.g., via URL)? The user returns to the previously active route when one is known; otherwise they are sent to the home page.
- What happens during password change when the user's session was already expired? The password change request fails with 401, triggering a refresh attempt. If refresh also fails, authentication state is cleared and the user is redirected to login.
- What happens when the access token is stored in memory and the page is hard-refreshed? The in-memory token is lost; session restoration via refresh cookie is attempted as part of application initialization.
- What happens on the `/login` page when a CSRF token cookie is absent? The login request is still sent; the backend requires CSRF only for state-changing operations that use the session cookie. Login creates a new session so no pre-existing CSRF token is required.

## Requirements *(mandatory)*

### Functional Requirements

**Login Page**

- **FR-001**: The application MUST provide a login page at the `/login` route that renders outside the authenticated application shell.
- **FR-002**: The login page MUST display the VK Cricket Academy branding, an email input, a password input, a show/hide password toggle, and a login button.
- **FR-003**: The login form MUST require both email and password fields before submission.
- **FR-004**: Pressing Enter while focused on either input field MUST submit the login form.
- **FR-005**: The login button MUST display a loading state and be disabled during submission to prevent duplicate requests.
- **FR-006**: For all credential-related failures (wrong password, unknown email, disabled account), the system MUST display the identical generic message: "Invalid email or password."
- **FR-007**: For network errors or unexpected server failures during login, the system MUST display: "Unable to sign in right now. Please try again."
- **FR-008**: For rate-limited login attempts (HTTP 429), the system MUST display: "Too many sign-in attempts. Please wait and try again." without revealing whether the submitted account exists.
- **FR-009**: Raw backend errors, stack traces, and internal details MUST NOT be displayed to the user.
- **FR-010**: The password visibility toggle MUST be keyboard-accessible and include an accessible label.

**Successful Login**

- **FR-011**: On successful login, the returned access token MUST be stored only in memory (never in localStorage or sessionStorage).
- **FR-012**: On successful login, the system MUST load the current authenticated user via `GET /api/v1/auth/me` and update the shared authentication state.
- **FR-013**: On successful login, the user MUST be redirected to the originally requested protected route when one was preserved; otherwise to the home page.
- **FR-014**: Authenticated users who navigate to `/login` MUST be redirected to the home page.

**Authentication State**

- **FR-015**: The system MUST provide a shared authentication state layer that tracks: current user, current role, access token, initialization status, authenticated status, and login/logout in-progress flags.
- **FR-016**: The authentication state MUST be accessible to all components that need routing, role display, or API request decisions.
- **FR-017**: Access tokens MUST be stored in memory only and MUST NOT be persisted in localStorage or sessionStorage.
- **FR-018**: Refresh tokens MUST remain in backend-managed Secure, HttpOnly cookies. The frontend MUST NOT read, store, or log refresh tokens.

**Session Restoration**

- **FR-019**: When the application loads or reloads, the system MUST attempt to restore the user's session by calling `POST /api/v1/auth/refresh` with credentials included.
- **FR-020**: The refresh request MUST include the `X-CSRF-Token` header with the value read from the `csrf_token` cookie.
- **FR-021**: If session restoration succeeds, the new access token MUST be stored in memory and the current user MUST be loaded via `GET /api/v1/auth/me`.
- **FR-022**: If session restoration fails, authentication state MUST be cleared.
- **FR-023**: Protected pages MUST NOT render before session restoration has been resolved; a loading indicator MUST be displayed during initialization.

**Token Refresh**

- **FR-024**: When an API request fails with HTTP 401, the system MAY attempt one token refresh via `POST /api/v1/auth/refresh`.
- **FR-025**: After a successful refresh, the original failed request MAY be retried once.
- **FR-026**: The system MUST prevent infinite refresh loops by limiting to a single refresh attempt per 401 chain.
- **FR-027**: Multiple simultaneous 401 responses MUST NOT trigger duplicate refresh requests; in-flight requests MUST share a single refresh operation.
- **FR-028**: Any unsuccessful refresh response (including 401, 403, 429, network errors, and server errors) MUST clear authentication state and redirect the user to `/login` with the message: "Your session has expired. Please sign in again."
- **FR-029**: All protected API requests MUST include credentials so that refresh-token cookies are sent automatically.

**Protected Routes**

- **FR-030**: The following routes are public and do not require authentication: `/login`.
- **FR-031**: All other routes (`/`, `/players`, `/teams`, `/coaches`, `/calendar`, `/settings`, and any catch-all) MUST require authentication.
- **FR-032**: Unauthenticated users accessing protected routes MUST be redirected to `/login`, preserving the originally requested route.
- **FR-033**: After successful login, the user MUST be returned to the preserved route.
- **FR-034**: Protected content MUST NOT flash before the redirect to `/login`.
- **FR-035**: Frontend route protection does not replace backend authorization; backend endpoints remain the authoritative gate.

**Logout**

- **FR-036**: The authenticated application sidebar MUST include an accessible logout control displayed as a red exit button in the sidebar footer, next to the User Settings and collapse icons.
- **FR-037**: The logout request MUST call `POST /api/v1/auth/logout` with credentials included and the `X-CSRF-Token` header set from the `csrf_token` cookie.
- **FR-038**: On logout, the in-memory access token MUST be cleared, current-user state MUST be cleared, and the user MUST be redirected to `/login`.
- **FR-039**: Logout MUST revoke only the current server-side session; other active sessions for the same user MUST remain unaffected.
- **FR-040**: If the backend logout request fails, local authentication state MUST still be cleared and the user MUST be redirected to `/login`.

**User Settings Modal**

- **FR-041**: The `/settings` route MUST render the authenticated application shell and automatically open the account settings modal.
- **FR-042**: The settings modal MUST appear above the current page with a dimmed or blurred background.
- **FR-043**: The modal MUST trap keyboard focus while open and restore focus to the triggering element when closed.
- **FR-044**: The modal MUST prevent background page scrolling while open.
- **FR-045**: The modal MUST be closable via a close button, the Escape key, and by clicking the backdrop.
- **FR-046**: The modal MUST include an accessible title and use appropriate dialog semantics (`role="dialog"` or equivalent, `aria-modal`, `aria-labelledby`).
- **FR-047**: Closing the modal MUST return the user to the previously active page or the home page if no prior page exists.

**Profile Settings**

- **FR-048**: The profile section MUST display the user's email address and current role as read-only fields.
- **FR-049**: The profile section MUST allow the user to edit their first name and last name with prefilled current values.
- **FR-050**: Profile update MUST submit to a new backend endpoint `PATCH /api/v1/auth/me` that accepts `first_name` and `last_name` fields.
- **FR-051**: The profile form MUST validate that first name and last name are not empty before submission.
- **FR-052**: The save button MUST be disabled while the update request is in progress.
- **FR-053**: After a successful profile update, the shared authentication state MUST be updated without requiring a full page reload.
- **FR-054**: Success and failure feedback MUST be displayed after a profile update attempt.

**Password Change**

- **FR-055**: The settings modal MUST include a password-change section with fields for new password and confirm new password.
- **FR-056**: The frontend MUST enforce the same password policy as the backend: minimum 12 characters, maximum 128 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character.
- **FR-057**: New password and confirmation MUST match before submission.
- **FR-058**: Field-level validation errors MUST be displayed for each policy violation and mismatch.
- **FR-059**: Submission MUST be disabled while the password-change request is running.
- **FR-060**: Password values MUST NOT be logged, persisted in browser storage, or retained in component state after submission.
- **FR-061**: On successful password change, authentication state MUST be cleared and the user MUST be redirected to `/login` with the message: "Your password was changed. Please sign in again."
- **FR-062**: The password-change request MUST call the backend `POST /api/v1/users/{id}/change-password` endpoint. The form requires only the new password and confirm password; the current password is not required.

**Role Awareness**

- **FR-063**: The frontend MAY display the authenticated user's role for informational and navigation purposes.
- **FR-064**: Role values from request bodies, query parameters, browser storage, or other client-controlled sources MUST NOT be trusted for authorization decisions.
- **FR-065**: Hiding a frontend UI control based on role does not replace backend permission enforcement.

**Responsive Behavior**

- **FR-066**: The login page and account settings modal MUST be usable on viewports from 320px to 2560px wide.
- **FR-067**: Forms MUST NOT cause horizontal overflow at any supported viewport width.
- **FR-068**: The modal MUST fit within small viewports (320px wide) and scroll long content internally.
- **FR-069**: Interactive controls MUST maintain minimum 44px touch targets as specified by the design system.

**Accessibility**

- **FR-070**: All form inputs MUST have associated `<label>` elements.
- **FR-071**: Error messages MUST be programmatically associated with their corresponding fields (via `aria-describedby` or equivalent).
- **FR-072**: Interactive controls MUST display visible focus states, using the 2px Academy Teal ring as specified in the design system.
- **FR-073**: Password visibility controls MUST have accessible names.
- **FR-074**: Loading states MUST be communicated to assistive technologies (via `aria-busy`, `aria-live` regions, or equivalent).
- **FR-075**: The settings modal MUST use appropriate dialog semantics with `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`.
- **FR-076**: Authentication and account-management flows MUST be fully operable with a keyboard.
- **FR-077**: Success and error messages SHOULD be announced to assistive technologies via live regions.

### Key Entities

- **Authenticated User**: Represents the currently logged-in user. Key attributes: user ID, first name, last name, email (read-only), role, active status. Source: `GET /api/v1/auth/me` response.
- **Auth State**: Client-side representation of the authentication session. Tracks: access token (in-memory only), current user object, initialization flag, authenticated flag, login/logout in-progress flags, and session-restoration status. Not persisted to browser storage.
- **Session**: Server-side concept referenced but not directly manipulated by the frontend. Identified by a session ID within the `/me` response. Expiration and revocation handled server-side.
- **Login Credentials**: Email and password submitted by the user. Transient — not stored after the login request completes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with valid credentials can sign in and reach the home page in under 5 seconds on a typical broadband connection.
- **SC-002**: Returning users with a valid session are restored to the authenticated home page without seeing a login form in under 3 seconds from page load.
- **SC-003**: 100% of credential-related error messages use only the two approved generic messages ("Invalid email or password." and "Unable to sign in right now."); no backend-specific error details are exposed.
- **SC-004**: Access tokens are never written to localStorage or sessionStorage, verified by automated test.
- **SC-005**: A user can complete the profile name update flow (open modal, change name, save, see confirmation) in under 30 seconds.
- **SC-006**: The password change flow (open modal, enter matching compliant passwords, submit, redirect to login) completes in under 45 seconds.
- **SC-007**: All interactive controls on the login page and settings modal meet WCAG 2.1 AA accessibility criteria, including keyboard operation, focus visibility, and screen-reader compatibility.
- **SC-008**: The login page and settings modal are fully usable and free of horizontal overflow on viewports from 320px to 2560px wide.
- **SC-009**: A single simultaneous token expiration across multiple in-flight API requests triggers at most one refresh call.
- **SC-010**: Logout clears local state and redirects to `/login` within 2 seconds even when the backend request fails.

## Assumptions

- The backend authentication API (`POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`) is implemented and available as specified in the 002-auth-api-security feature.
- The backend `POST /api/v1/users/{id}/change-password` endpoint exists or will be created alongside this feature to support the password-change flow. The endpoint accepts `new_password` and `confirm_password` fields; current password is not required.
- The new `PATCH /api/v1/auth/me` endpoint (for name updates) will be created as part of this feature's backend scope.
- CSRF token cookie name is `csrf_token` and the corresponding request header is `X-CSRF-Token`, as established in the 002-auth-api-security contracts.
- Refresh token cookie is HttpOnly and the frontend cannot read it; all cookie-bearing requests use `credentials: "include"` or equivalent.
- The existing React 18+ and TypeScript frontend stack remains unchanged.
- The existing application shell (AppLayout, SidebarContext, navigation, design tokens) is reused without structural changes beyond adding the logout control.
- The `react-router-dom` library already in use handles routing; no additional routing library is introduced.
- The existing Tailwind CSS theme with Academy Teal (`#559eac`) and the design system in `DESIGN.md` provide all styling primitives.
- All authentication and account-management pages and components follow the design guidance in `PRODUCT.md` and `DESIGN.md`.
- The `/login` route is not currently defined in the frontend route table; it will be added as a top-level route outside the authenticated `AppLayout`.
- The user settings modal replaces the current placeholder `SettingsPage` content. The `/settings` route itself remains within the authenticated shell.
- Users have stable internet connectivity. Offline operation is out of scope.
- This spec does not cover: self-registration, forgot-password, email verification, multi-factor authentication, OAuth/social login, head-coach user administration, profile photos, email changes, role changes via the frontend, theme preferences, notification preferences, or remember-me functionality.
