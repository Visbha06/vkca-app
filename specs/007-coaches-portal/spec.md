# Feature Specification: Coaches Portal

**Feature Branch**: `007-coaches-portal`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Part 7: Coaches Portal — Build the Coaches Portal for the VK Cricket Academy web application. This specification covers both frontend and backend work required to display, create, filter, paginate, view, activate, deactivate, and manage team assignments for coach accounts."

## Clarifications

### Session 2026-07-27

- Q: How is the temporary password treated after the first login? → A: It is treated like a normal password until manually changed. The coach is NOT required to change it during first login.
- Q: Does a successful team-assignment update increment the coach's version_number? → A: Yes. A successful team-assignment update MUST increment the coach user's version_number.
- Q: Must deactivation (is_active=false + session revocation) be atomic? → A: Yes. Setting is_active=false and revoking all sessions must succeed as one atomic operation.
- Q: What are the fixed placeholder statistic values? → A: "Availability for next practice: Not available" and "Notes made: 0."
- Q: What should the page state look like when no Assistant Coaches exist? → A: An informational message "No Assistant Coaches have been added yet." displayed alongside the Head Coach card. The Head Coach card is always visible when filtered to "Active" or "All."
- Q: Can the Head Coach edit their own team assignments? → A: Yes. The Head Coach may edit their own team assignments. The self-deactivation safeguard does not restrict self-assignment editing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Browse and Filter Coaches (Priority: P1)

As a Head Coach or Assistant Coach, I can visit the Coaches Portal and see a paginated, filterable collection of coach cards so that I can quickly find and review coach accounts across the academy.

**Why this priority**: The coach listing is the entry point for every other coach-management action. Without it, no other workflow can begin.

**Independent Test**: Log in as a Head Coach, navigate to the Coaches Portal, and verify that active coach cards are displayed with correct avatars, names, roles, team assignments, and status. Change the status filter and verify results update.

**Acceptance Scenarios**:

1. **Given** I am a Head Coach viewing the Coaches Portal, **When** the page loads, **Then** I see a responsive grid of coach cards filtered to "Active" by default, with Head Coach cards appearing first followed by Assistant Coach cards ordered by last name ascending.
2. **Given** I am viewing active coaches, **When** I select the "Inactive" filter, **Then** the grid refreshes to show only inactive accounts with muted card styling, and pagination resets to page 1.
3. **Given** I am an Assistant Coach viewing the Coaches Portal, **When** the page loads, **Then** I see the same coach card collection but without the Add Coach button or any status-toggle controls.
4. **Given** I am a Player-role user, **When** I navigate to `/coaches`, **Then** I see a dedicated 403 Forbidden page with no coach data exposed, and the Coaches Portal navigation item is not visible in the sidebar.

---

### User Story 2 — View Coach Details (Priority: P1)

As a Head Coach or Assistant Coach, I can select an active coach card to open a details modal so that I can review their full profile, team assignments, and statistics.

**Why this priority**: Coach details are the primary decision-support view for managing coach accounts.

**Independent Test**: Click an active coach card and verify the modal displays full name, email, role, status, assigned teams, placeholder statistics, and role-appropriate actions. Close with Escape and confirm focus returns to the originating card.

**Acceptance Scenarios**:

1. **Given** I am a Head Coach viewing an active Assistant Coach card, **When** I click the card, **Then** a modal opens showing the coach's full name, email, role badge, active status, assigned teams list, placeholder statistics (availability and notes count), an Edit Assignments control, and a status toggle.
2. **Given** I am an Assistant Coach viewing an active Head Coach card, **When** I click the card, **Then** the modal opens but shows no Edit Assignments control and no status toggle.
3. **Given** I am an Assistant Coach viewing an inactive coach card, **When** I click or press Enter on it, **Then** the card does not open a modal and communicates the account's inactive status non-interactively.
4. **Given** the Coach Details modal is open, **When** I press Escape, **Then** the modal closes, background scroll is restored, and focus returns to the originating card.

---

### User Story 3 — Add an Assistant Coach (Priority: P2)

As a Head Coach, I can create a new Assistant Coach account with optional team assignments so that I can onboard a new coach and immediately place them in the right teams.

**Why this priority**: Account creation is essential but only the Head Coach performs it, making it a P2 relative to the shared browse and view workflows.

**Independent Test**: Click Add Coach, fill in valid details, select team assignments, submit, and verify a success message appears with a one-time temporary password displayed and copyable. Verify the new coach card appears in the grid.

**Acceptance Scenarios**:

1. **Given** I am a Head Coach on the Coaches Portal, **When** I click "Add Coach", **Then** a modal opens with first name, last name, email, and optional team-assignment fields.
2. **Given** I submit valid coach details with team assignments, **When** the backend processes the request, **Then** the coach account and all assignments are created atomically, and the response includes a one-time temporary password that I can copy.
3. **Given** I submit an email that already exists, **When** the backend detects the duplicate, **Then** the form stays open with a field-level error on the email field, non-sensitive data is preserved, and no account is created.
4. **Given** the creation response shows the temporary password, **When** I dismiss the success view, **Then** the password is no longer retrievable and a warning was displayed that it would only be shown once.
5. **Given** I am an Assistant Coach, **When** I view the Coaches Portal, **Then** the Add Coach button is not visible.

---

### User Story 4 — Activate and Deactivate Coaches (Priority: P2)

As a Head Coach, I can deactivate a coach account to revoke access while preserving their data and team assignments, and reactivate them later when they return.

**Why this priority**: Account lifecycle management is a core Head Coach responsibility but does not block the primary browse-and-view flows.

**Independent Test**: Open an active coach's details, deactivate them, confirm the confirmation dialog, verify the card becomes muted and the coach can no longer log in. Reactivate and verify login is restored.

**Acceptance Scenarios**:

1. **Given** I am a Head Coach viewing an active Assistant Coach's details, **When** I toggle their status to inactive and confirm, **Then** the account's sessions are revoked, the card refreshes with muted styling, and the coach cannot log in.
2. **Given** I am a Head Coach viewing an inactive coach's details, **When** I toggle their status to active, **Then** the account is reactivated, the card styling normalizes, and the coach can authenticate again.
3. **Given** I am a Head Coach viewing my own details, **When** I look for the status toggle, **Then** it is disabled or hidden with an explanation that self-deactivation is not permitted.
4. **Given** I am a Head Coach attempting to deactivate another coach, **When** the confirmation dialog appears, **Then** it clearly explains that sessions will be revoked, data will be preserved, and the account can be reactivated later.
5. **Given** an Assistant Coach was deactivated and I reactivate them, **When** they log in again, **Then** their previously-revoked sessions are not restored and they must authenticate fresh.

---

### User Story 5 — Manage Team Assignments (Priority: P2)

As a Head Coach, I can assign coaches to teams and remove assignments so that coaching responsibilities are accurately reflected across the academy.

**Why this priority**: Team-coach mappings are critical for operational visibility but depend on the coach-details view, making this P2.

**Independent Test**: Open an active coach's details, click Edit Assignments, add and remove team assignments, submit, and verify the coach card and details modal reflect the updated assignments.

**Acceptance Scenarios**:

1. **Given** I am a Head Coach viewing an active coach's details, **When** I click "Edit Assignments", **Then** the details modal closes and a Team Assignments modal opens showing all available teams with the coach's current assignments highlighted.
2. **Given** I add and remove team assignments in the modal, **When** I submit, **Then** the complete desired assignment set is applied atomically — no partial changes persist if any validation fails.
3. **Given** a coach is inactive, **When** I open their details, **Then** existing assignments are visible but the Edit Assignments control is disabled or hidden, and I must reactivate the coach first.
4. **Given** I attempt to assign a team that is already assigned, **When** the system detects the duplicate, **Then** a validation error is shown and no assignment is created.
5. **Given** I have unsaved changes in the Team Assignments modal, **When** I try to close it, **Then** a confirmation prompt appears asking if I want to discard changes.

---

### User Story 6 — Handle Concurrent Edits Gracefully (Priority: P3)

As a Head Coach, when I attempt to modify a coach that another user has already changed, I am notified of the conflict and can reload the current state so I do not accidentally overwrite newer data.

**Why this priority**: Concurrency conflicts are rare in a small-academy context but the optimistic-locking mechanism is required by the project constitution.

**Independent Test**: Load a coach's details in two sessions, modify the status in one session, then attempt to modify assignments in the other and verify the HTTP 409 conflict response with a clear message and reload action.

**Acceptance Scenarios**:

1. **Given** I loaded a coach's data that has since been modified by another session, **When** I submit a status or assignment change with the stale `version_number`, **Then** the backend returns HTTP 409, the frontend displays a conflict message, and a "Reload" action is offered.
2. **Given** I receive a conflict message, **When** I click "Reload", **Then** the coach's current data replaces the stale display, the `version_number` is updated, and my unsaved changes are discarded after confirmation.

---

### Edge Cases

- What happens when no Assistant Coaches have been created yet? The Head Coach sees a clear empty state with an Add Coach action; the sole Head Coach card is always visible (filtered to "Active").
- What happens when the "Inactive" filter is selected but all coaches are active? A distinct filtered-no-results message is displayed, different from the true empty state.
- What happens when the "All" filter is selected? Both active (normal styling) and inactive (muted styling) coaches appear together, with Head Coach first.
- What happens when a coach has more than two team assignments? The first two team names are displayed on the card with a "+N more" indicator.
- What happens when a coach has zero team assignments? The card displays an appropriate unassigned state (e.g., "No teams assigned").
- What happens if the backend is unreachable when loading the coaches list? A generic error message with a Retry button is displayed; raw backend errors are not exposed.
- What happens when a network error occurs mid-submission? The form remains open with the user's data preserved; a generic error is shown with a retry option.
- What happens when the Head Coach attempts to submit an empty team-assignments set? The operation proceeds normally — the coach becomes unassigned from all teams.
- What happens when a team referenced in an assignment request does not exist? The backend returns a validation error and the entire atomic operation rolls back.

## Requirements *(mandatory)*

### Functional Requirements

**Portal Access**

- **FR-001**: The Coaches Portal route MUST only be accessible to users with the Head Coach or Assistant Coach role.
- **FR-002**: Player-role users MUST NOT see the Coaches Portal navigation item in the sidebar.
- **FR-003**: Player-role users navigating directly to the Coaches Portal route MUST receive a dedicated 403 Forbidden page with no coach data rendered.
- **FR-004**: The backend MUST serve as the authoritative authorization layer, returning HTTP 403 for all unauthorized coach-endpoint access.

**Coach Listing**

- **FR-005**: The Coaches Portal page MUST display a page heading, a status filter dropdown, an Add Coach button (Head Coach only), and a paginated grid of coach cards.
- **FR-006**: The coach list MUST use server-side pagination with a default page size of 12.
- **FR-007**: Coach cards MUST default to the following ordering: Head Coach before Assistant Coach, then last name ascending, first name ascending, and user ID ascending as tiebreaker.
- **FR-008**: The paginated response MUST include current page, page size, total coaches, total pages, and previous/next page availability.
- **FR-009**: Each coach card MUST display an initials avatar, full name, role badge, assigned teams (up to two with "+N more" overflow), and active/inactive status.
- **FR-010**: Head Coach avatars MUST use light red styling; Assistant Coach avatars MUST use light blue styling.
- **FR-011**: Inactive coach cards MUST use muted or greyed-out styling distinguishable from active cards.
- **FR-012**: Coach cards MUST be keyboard-accessible and open the Coach Details modal on click or Enter/Space activation.

**Status Filter**

- **FR-013**: A status filter dropdown MUST provide "Active", "Inactive", and "All" options, defaulting to "Active".
- **FR-014**: Filtering MUST use server-side filtering, reset pagination to page 1, display a loading state, and preserve the selected filter across page changes.
- **FR-015**: Both Head Coach and Assistant Coach users MUST be able to use all filter options.

**Pagination**

- **FR-016**: Pagination controls MUST prevent navigation beyond available pages, remain keyboard-accessible, display loading state during page changes, and return focus to the coach list after page changes.

**Coach Details Modal**

- **FR-017**: Selecting an active coach card MUST open a Coach Details modal displaying full name, email address, role, status, assigned teams, and placeholder statistics, plus role-appropriate action controls.
- **FR-018**: The modal MUST support keyboard focus trapping, Escape-key closing, a visible close button, background scroll locking, focus restoration on close, responsive sizing, and internal scrolling on small viewports.
- **FR-019**: For Assistant Coach users, inactive coach cards MUST NOT open the Coach Details modal and MUST communicate non-interactive status.
- **FR-020**: For the Head Coach, inactive coach cards MAY be opened; assignments MUST be read-only until reactivation, and a reactivation control MUST be available.

**Placeholder Statistics**

- **FR-021**: The Coach Details modal MUST display placeholder statistics after a visual separator with the fixed values: "Availability for next practice: Not available" and "Notes made: 0."
- **FR-022**: Placeholder statistics MUST be display-only, not stored in the database, not calculated from backend data, and not editable.

**Add Coach**

- **FR-023**: An Add Coach button MUST be visible only to Head Coach users.
- **FR-024**: The Add Coach modal MUST collect first name, last name, email, and optional initial team assignments. The role MUST always be Assistant Coach (not user-selectable).
- **FR-025**: The new account MUST be created with `is_active = true`, role "assistant coach", and a backend-generated secure temporary password.
- **FR-026**: The temporary password MUST satisfy the existing backend password policy, be hashed before storage, never persisted in plaintext, and returned to the frontend only once in the creation response. The temporary password is treated as a normal password thereafter — the coach is NOT required to change it during first login in this specification.
- **FR-027**: The frontend MUST display a clear warning that the temporary password is shown only once, and the Head Coach MUST be able to copy it before dismissing the success view.
- **FR-028**: The temporary password MUST NOT be logged, written to browser storage, included in analytics, or retrievable through any other endpoint.
- **FR-029**: Coach account creation and initial team assignments MUST be atomic — if any part fails, the coach account MUST NOT be created and no assignments MUST persist.
- **FR-030**: Duplicate email submissions MUST display a field-level error, keep the form open, preserve non-sensitive data, and not reveal details about the existing account.

**Team–Coach Relationship**

- **FR-031**: A many-to-many relationship between teams and coaches MUST be established via a dedicated `team_coaches` table referencing team ID and coach user ID with server-generated timestamps.
- **FR-032**: The relationship MUST support adding assignments, removing assignments, listing teams assigned to a coach, and preventing duplicate assignments.

**Manage Team Assignments**

- **FR-033**: An Edit Assignments control MUST be visible in the Coach Details modal only for the Head Coach and only for active coaches. The Head Coach MAY edit their own team assignments — the self-deactivation safeguard (FR-042) does not restrict self-assignment editing.
- **FR-034**: Selecting Edit Assignments MUST close the Coach Details modal and open a separate Team Assignments modal (no stacked modals).
- **FR-035**: The Team Assignments modal MUST display all available teams, show current assignments, allow adding/removing assignments, prevent duplicates, and include loading, empty, validation, submission, success, and error states.
- **FR-036**: Assignment updates MUST submit the complete desired assignment set atomically. If any validation fails, existing assignments MUST remain unchanged. A successful team-assignment update MUST increment the coach user's `version_number`.

**Optimistic Concurrency**

- **FR-037**: Coach status changes and team-assignment changes MUST include the coach user's current `version_number` in the request.
- **FR-038**: If the `version_number` is stale, the backend MUST return HTTP 409, not overwrite newer data, and the frontend MUST display a conflict message with a reload action.

**Activate / Deactivate Coach**

- **FR-039**: The Coach Details modal MUST display an active/inactive toggle only to the Head Coach.
- **FR-040**: Deactivating a coach MUST set `is_active = false` and revoke all active sessions as one atomic operation. After deactivation, the coach MUST be prevented from future login and token refresh. The account, team assignments, and historical references MUST be preserved.
- **FR-041**: Reactivating a coach MUST set `is_active = true`, restore login ability, NOT restore previously revoked sessions, and preserve existing team assignments.
- **FR-042**: The Head Coach MUST NOT be able to deactivate their own account. The frontend MUST disable or hide the toggle for the current user, and the backend MUST independently reject self-deactivation.
- **FR-043**: Deactivation MUST require a confirmation dialog explaining the consequences (no login, sessions revoked, data preserved, reactivation possible).

**Page and Form States**

- **FR-044**: The Coaches Portal MUST support loading (accessible indicator), empty (informational message "No Assistant Coaches have been added yet." displayed alongside the Head Coach card when no Assistant Coaches exist), filtered-no-results (distinct message), error (generic message with retry), and success (confirmation feedback with data refresh) states. The Head Coach card MUST always be visible when filtered to "Active" or "All," regardless of whether Assistant Coaches exist.
- **FR-045**: Add Coach and Edit Assignments forms MUST display field-level validation errors for missing/invalid fields, duplicate email, invalid team selections, and duplicate assignments.
- **FR-046**: During submission, forms MUST disable submission controls to prevent duplicate requests and communicate progress accessibly.
- **FR-047**: Unsaved changes in Add Coach and Edit Assignments forms MUST trigger a confirmation prompt on close or navigation, with options to continue editing or intentionally discard.
- **FR-048**: HTTP 403 responses MUST display a clear permissions message without exposing raw backend details.
- **FR-049**: HTTP 409 responses MUST use the optimistic-concurrency recovery flow (conflict message + reload action).

**Reusability**

- **FR-050**: The Coaches Portal MUST reuse existing card patterns, modal infrastructure, pagination controls, role badges, status indicators, accessible form controls, loading/error components, unsaved-changes patterns, conflict-handling patterns, and team-selection components where appropriate.

**Accessibility**

- **FR-051**: The Coaches Portal MUST support keyboard-accessible cards, visible focus states, semantic headings, accessible modal names/descriptions, focus trapping, focus restoration, accessible status toggles, accessible confirmation dialogs, programmatically associated form labels and errors, accessible loading/success/error messages, accessible pagination, and touch-friendly controls.
- **FR-052**: Inactive cards that are non-interactive for Assistant Coaches MUST NOT appear keyboard-actionable.

**Responsive Behavior**

- **FR-053**: Coach cards MUST reflow into a responsive grid (1 column mobile, 2 columns tablet, 3 columns desktop) without horizontal overflow.
- **FR-054**: Filters, page actions, modals, pagination, and team-assignment controls MUST remain usable on all viewport sizes from 320px to 2560px, with internal modal scrolling on small screens.

**Testing**

- **FR-055**: Frontend tests MUST cover route access per role, 403 behavior, card rendering, avatar styling, team display, filtering, pagination, all UI states, modal behavior, role-based control visibility, form validation, temporary-password flow, duplicate-email handling, status-toggle visibility, deactivation confirmation, reactivation, self-deactivation prevention, assignment management, concurrency handling, 403/409 handling, unsaved-changes confirmation, modal keyboard/focus behavior, and responsive behavior.
- **FR-056**: Backend tests MUST cover coach-list filtering/pagination/ordering, role-based authorization, atomic account creation, password generation and policy compliance, duplicate-email rejection, atomic assignment creation, many-to-many assignment behavior, atomic full-assignment replacement, inactive-coach restrictions, deactivation with session revocation, login/refresh rejection for inactive coaches, reactivation without session restoration, self-deactivation rejection, stale version_number returning 409, and unauthorized changes returning 403.
- **FR-057**: At least one Playwright E2E test MUST cover the full Head Coach journey: login, open Coaches Portal, create Assistant Coach, view temporary password, assign to team, open details, deactivate, confirm card becomes inactive, reactivate, and edit team assignments.

### Key Entities

- **Coach (User — coach role subset)**: Represents a Head Coach or Assistant Coach account. Key attributes: first name, last name, email, role, active status, version number. Already exists in the `users` table with role constraint; this feature adds new coach-specific query filters, a creation endpoint returning a temporary password, and a reactivation endpoint.

- **TeamCoach (new join table)**: Represents a many-to-many assignment between a team and a coach user. Key attributes: team ID, coach user ID, created/updated timestamps. Prevents duplicate assignments through a unique constraint on the pair.

- **CoachCard (display entity)**: A frontend representation of a coach for card rendering, composed from the user record and joined team data. Includes computed display properties: initials, avatar color class, team name list with overflow indicator, and card interactivity state.

- **CoachDetails (display entity)**: A frontend representation for the modal, extending CoachCard with email, full team list, placeholder statistics (availability, notes count), and role-dependent action availability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A Head Coach can navigate to the Coaches Portal and see the complete list of active coaches rendered within 2 seconds under normal network conditions.
- **SC-002**: A Head Coach can create a new Assistant Coach account with team assignments in under 60 seconds from opening the Add Coach modal to seeing the success confirmation.
- **SC-003**: A Head Coach can deactivate or reactivate a coach and see the card update within 3 seconds of confirming the action.
- **SC-004**: A Head Coach can add or remove team assignments for a coach and see the updated assignments on the card and in the details modal within 5 seconds of submission.
- **SC-005**: 100% of coach-management operations (list, create, status toggle, assignment update) correctly enforce role-based authorization, with Player-role users receiving HTTP 403 and a dedicated forbidden page.
- **SC-006**: The Coaches Portal meets WCAG 2.1 AA accessibility criteria, including keyboard-only navigation of all cards, modals, filters, pagination, and forms.
- **SC-007**: The Coaches Portal layout remains fully usable and scroll-free horizontally on viewports from 320px (mobile) to 2560px (desktop).
- **SC-008**: No coach-management operation results in partial data changes — account creation, status changes, and assignment updates are fully atomic under all failure conditions.
- **SC-009**: Concurrent modifications to the same coach record are detected and reported (HTTP 409) 100% of the time when stale version numbers are submitted.

## Assumptions

- The academy has exactly one Head Coach account, created during initial system setup. This feature does not support creating additional Head Coach accounts or promoting users to Head Coach.
- The existing `users` table, `User` model, `UserRole` enum, and authorization middleware (`require_role`, `get_current_user`) are reused without schema changes beyond adding the `team_coaches` join table.
- The existing password service and policy are reused for temporary-password generation during coach creation.
- Existing session-revocation infrastructure (`AuthService.revoke_user_sessions`) is reused for deactivation.
- The existing `version_number` column on the `users` table is reused for optimistic concurrency control.
- The existing `ModalDialog` component, card grid patterns, pagination controls, and form infrastructure from the Player Directory feature are reused or adapted for the Coaches Portal.
- Placeholder statistics (availability, notes count) are static display values only. They do not require backend endpoints, database storage, or editability.
- Email invitations and automatic password delivery (e.g., via email) are out of scope. The Head Coach is responsible for communicating the temporary password to the new coach through an external channel.
- Team deletion, coach deletion, and coach role changes are out of scope.
- The frontend design follows the branding, layout, component, and accessibility guidance defined in `PRODUCT.md` and `DESIGN.md`.
- Coach cards follow the same visual structure as Player Directory cards (profile-card density, identity expansion, single trigger per card) with coach-specific adaptations (role-based avatar color, status styling, team assignment display).
