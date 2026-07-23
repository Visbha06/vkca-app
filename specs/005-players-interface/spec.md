# Feature Specification: Players Interface

**Feature Branch**: `005-players-interface`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "Part 5: Players Interface — Build the Players interface for the VK Cricket Academy web application, covering both frontend and backend work required to display, create, filter, paginate, view, and update active player profiles."

## Clarifications

### Session 2026-07-21

- Q: Data freshness after mutations → A: Players page must refresh or invalidate cached player data after create and edit operations.
- Q: Date display and submission format → A: Dates must be displayed in a consistent, human-readable format (e.g., "24 Apr 1973") and submitted in the exact backend-expected format (YYYY-MM-DD).
- Q: Unsaved changes protection → A: Add a confirmation prompt before exiting Add/Edit forms with unsaved changes.
- Q: Backend 403 permissions failure handling → A: Frontend must handle backend 403 responses gracefully with a clear permissions error message rather than a generic failure.
- Q: Reusable form logic → A: Add Player and Edit Player must share reusable form fields, validation, enum mappings, and metadata controls.
- Q: Default ordering → A: Default player ordering must be by last name ascending.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse and View Active Players (Priority: P1)

A coach or player opens the Players page to see all active academy players, filter them by team, page through the collection, and view any player's full details in a modal.

**Why this priority**: Viewing players is the foundational capability. Without it, no other player workflow (create, edit) has value. Every authenticated user needs this.

**Independent Test**: Log in as any role, navigate to the Players page, verify player cards appear, filter by a team, page through results, open a player detail modal, and dismiss it.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the Players page, **When** the page loads, **Then** a paginated grid of active player cards is displayed with team names, full names, and the page heading, ordered by last name ascending.
2. **Given** an authenticated user on the Players page with players across multiple teams, **When** the user selects a team from the filter, **Then** only players belonging to that team are shown and pagination resets to page 1.
3. **Given** an authenticated user on the Players page with the "Unassigned Players" filter selected, **When** the filter is applied, **Then** only players who belong to no team are shown.
4. **Given** an authenticated user viewing player cards, **When** the user clicks or presses Enter on a card, **Then** a Player Details modal opens showing the player's full name, date of birth (in human-readable format), batting style, bowling style, player type, team membership, and a placeholder statistics message.
5. **Given** a Player Details modal open, **When** the user presses Escape or clicks the close button, **Then** the modal closes, background scroll is restored, and focus returns to the originating card.
6. **Given** an authenticated user on a mobile or tablet screen, **When** the Players page is viewed, **Then** player cards reflow into a responsive grid without horizontal overflow, and modals fit within the viewport with internal scrolling when content is long.

---

### User Story 2 - View Bio and Metadata in Player Details (Priority: P2)

While viewing a player's details, a coach or player can expand a section within the modal to see the player's biography text and structured metadata in readable key-value format, or see an empty-state message when none exists.

**Why this priority**: Bio and metadata enrich the player profile view and support coaching decisions, but the core player identity (name, role, style, team) is already visible in P1.

**Independent Test**: Open a Player Details modal for a player with bio and metadata, expand the bio/metadata section, verify the content is displayed in key-value format, then open a player without bio/metadata and verify an appropriate empty message appears.

**Acceptance Scenarios**:

1. **Given** a Player Details modal open for a player with bio and metadata, **When** the user activates the information control, **Then** an expandable section within the same modal reveals the player's bio text and metadata key-value pairs in readable format.
2. **Given** a Player Details modal open for a player with no bio and no metadata, **When** the user activates the information control, **Then** an appropriate empty message is shown inside the expanded section.
3. **Given** the bio/metadata section is expanded, **When** the user activates the control again, **Then** the section collapses without closing the modal.

---

### User Story 3 - Add a New Player (Priority: P3)

A head coach or assistant coach adds a new player to the academy through a form modal with required fields, enum dropdowns, and optional bio/metadata key-value pairs.

**Why this priority**: Player creation is an essential coaching workflow but depends on the viewing capability established in P1. It is gated to coaching roles only.

**Independent Test**: Log in as a head coach, open the Add Player form from the Players page, fill in all required fields with valid values, submit, and verify the new player appears in the player list without a full page reload.

**Acceptance Scenarios**:

1. **Given** a head coach or assistant coach on the Players page, **When** the page is rendered, **Then** an "Add Player" button is visible.
2. **Given** a player-role user on the Players page, **When** the page is rendered, **Then** no "Add Player" button or create control is visible.
3. **Given** a coach has opened the Add Player form, **When** the form is submitted with valid required fields and optional bio/metadata, **Then** the player is created via `POST /api/v1/players`, the player list refreshes, and success feedback is shown.
4. **Given** the Add Player form open, **When** required fields are empty and the user submits, **Then** field-level validation errors appear and the request is not sent.
5. **Given** the Add Player form submitted, **When** the backend returns an error, **Then** a generic error message is displayed and the form remains open for retry.
6. **Given** the Add Player form submitted, **When** the backend returns a 403 Forbidden response, **Then** a clear permissions error message is displayed rather than a generic failure message.
7. **Given** batting style, bowling style, and player type dropdowns, **When** the coach selects options, **Then** human-readable labels are shown (e.g., "Right Arm Fast") while the original backend enum values (e.g., `right-arm fast`) are sent on submission.
8. **Given** the Add Player form has unsaved changes, **When** the user attempts to close or navigate away, **Then** a confirmation prompt is presented before discarding changes.

---

### User Story 4 - Edit an Existing Player (Priority: P4)

A head coach or assistant coach edits a player's profile from the Player Details modal, with the form pre-filled with current values, human-readable enum labels, and key-value metadata fields.

**Why this priority**: Editing is a routine coaching action but is less frequent than viewing; it builds on the details modal and create form established in P1-P3.

**Independent Test**: Log in as a head coach, open a player's details, activate Edit, verify the form is pre-filled with current values including human-readable enum labels, change a field, submit, and verify the card and details modal reflect the update.

**Acceptance Scenarios**:

1. **Given** a head coach or assistant coach viewing a Player Details modal, **When** the modal is open, **Then** an "Edit Player" control is visible.
2. **Given** a player-role user viewing a Player Details modal, **When** the modal is open, **Then** no Edit Player control is visible.
3. **Given** a coach activates Edit from Player Details, **When** the Edit form opens, **Then** the Player Details modal closes before the Edit form opens (no stacked modals), and the form is pre-filled with the player's current values including human-readable enum labels and dates in the same human-readable format used for display.
4. **Given** the Edit form submitted with changed values and the correct `version_number`, **When** the update succeeds, **Then** the player card updates, the details modal reflects new data, the `version_number` is stored for the next edit, and success feedback is shown.
5. **Given** the Edit form submitted with a stale `version_number`, **When** the backend returns HTTP 409, **Then** a clear conflict message is shown, the user is informed the player was updated elsewhere, a reload action is offered, and after reload the form values and `version_number` are replaced with the latest data without auto-retrying the stale update.
6. **Given** the Edit form submitted, **When** the backend returns a 403 Forbidden response, **Then** a clear permissions error message is displayed rather than a generic failure message.
7. **Given** the Edit form has unsaved changes, **When** the user attempts to close or navigate away, **Then** a confirmation prompt is presented before discarding changes.

---

### User Story 5 - Handle Page and Form States Gracefully (Priority: P5)

The Players page and its forms communicate loading, empty, error, filtered-no-results, validation, submission, success, and conflict states clearly and accessibly.

**Why this priority**: State communication is critical for trust and usability but is layered onto the core workflows established in P1-P4.

**Independent Test**: Trigger each state — loading (slow network), empty (no active players), filtered no-results (select a team with no members), error (API failure), form validation errors, submission loading, success, conflict (concurrent edit), and permissions denial (403) — and verify the UI responds appropriately in each case.

**Acceptance Scenarios**:

1. **Given** the Players page is loading, **When** data is being fetched, **Then** an accessible loading indicator is displayed.
2. **Given** no active players exist, **When** the Players page is rendered, **Then** a clear empty-state message is shown, and coaches see an Add Player action within the empty state.
3. **Given** players exist but none match the selected team filter, **When** the filtered list is rendered, **Then** a no-results message is shown that is distinct from the true empty state.
4. **Given** the player list fails to load, **When** an API error occurs, **Then** a generic error message with a retry action is displayed without exposing raw backend details.
5. **Given** an Add or Edit form is submitting, **When** the request is in flight, **Then** the submit button is disabled, duplicate submissions are prevented, and the loading state is communicated accessibly.
6. **Given** a create or update request returns a 403 Forbidden response, **When** the error is received, **Then** a clear message indicating insufficient permissions is displayed rather than a generic or raw error.
7. **Given** pagination controls are used with an active team filter, **When** the user changes pages, **Then** the filter is preserved, navigation beyond available pages is prevented, a loading state appears during the page change, and focus is returned to the player list.

---

### Edge Cases

- What happens when a player belongs to multiple teams? The player card and details modal must display all team names.
- What happens when the user rapidly clicks pagination controls? The frontend must prevent duplicate requests and only honor the most recent page request.
- What happens when the team filter changes while on page 5, but the new filter has only 2 pages of results? Pagination must reset to page 1.
- What happens when a player is edited by another coach while the current coach has the Edit form open? The conflict (HTTP 409) is presented clearly with a reload action.
- What happens when a coach closes the Add/Edit form without submitting after making unsaved changes? The system must present a confirmation prompt before discarding changes.
- What happens when a user with insufficient permissions somehow submits a create or update request (e.g., via a stale or manipulated UI state)? The system must gracefully handle the 403 response with a clear permissions error message.
- What happens when the backend returns an unexpected enum value not in the frontend's mapping? The enum formatting must fall back to a safe readable format rather than breaking the interface.
- What happens when a player has metadata with special characters or deeply nested keys? The key-value display must handle string keys and values safely without rendering issues.
- What happens with an empty metadata JSONB object (`{}`)? The bio/metadata section must show an empty message, not a blank panel.
- What happens when keyboard-only users navigate the player cards and modals? All interactions must be keyboard-accessible with visible focus states, focus trapping in modals, and focus restoration on modal close.
- What happens when another coach creates or edits a player while the current user is viewing the player list? The list must refresh or be invalidated after the current user performs their own create or edit, ensuring the displayed data reflects the latest server state.

## Requirements *(mandatory)*

### Functional Requirements

#### Player Page

- **FR-001**: The Players page MUST display a page heading consistent with other authenticated routes.
- **FR-002**: The Players page MUST use the existing authenticated application shell (`AppLayout`).
- **FR-003**: The Players page MUST display a paginated collection of player cards in a responsive grid.
- **FR-004**: The Players page MUST support loading, empty (no active players), filtered no-results, and error states.

#### Player Cards

- **FR-005**: Each active player MUST be displayed as a card with slightly rounded edges, consistent spacing, and academy branding per `PRODUCT.md` and `DESIGN.md`.
- **FR-006**: Each player card MUST display the player's full name and the team or teams to which the player belongs, or "Unassigned" when the player is not part of any team.
- **FR-007**: Player cards MUST be keyboard-accessible (focusable, operable via Enter/Space).
- **FR-008**: Selecting a player card MUST open the Player Details modal.

#### Player Details Modal

- **FR-009**: The Player Details modal MUST display: player full name (heading), date of birth in human-readable format, batting style, bowling style, player type, team membership, and the placeholder message "Player statistics deferred to a future specification."
- **FR-010**: The Player Details modal MUST support keyboard focus trapping, Escape-key closing, a visible close button, background scroll locking, and focus restoration after closing.
- **FR-011**: The Player Details modal MUST be accessible, with an accessible name and description.
- **FR-012**: The Player Details modal MUST be responsive, fitting within the viewport and scrolling internally on smaller screens.

#### Date Handling

- **FR-013**: Dates MUST be displayed in a consistent, human-readable format across all interfaces (player cards, player details, and form pre-fills). The recommended display format is "DD MMM YYYY" (e.g., "24 Apr 1973").
- **FR-014**: Dates submitted to the API MUST use the exact backend-expected format (YYYY-MM-DD).

#### Bio and Metadata

- **FR-015**: The player's bio and metadata MUST appear within the Player Details modal via an expandable section, collapsible panel, or tab — not a second stacked modal.
- **FR-016**: An information icon or similar control MUST be used to reveal the bio/metadata section.
- **FR-017**: When no bio or metadata is present, an appropriate empty message MUST be displayed.
- **FR-018**: Player metadata MUST be displayed in a readable key-value format.

#### Add Player

- **FR-019**: An "Add Player" button MUST be visible on the Players page for Head Coach and Assistant Coach users only.
- **FR-020**: The existing "Add player" quick action on the dashboard MUST open the same reusable Add Player form modal.
- **FR-021**: The Add Player form MUST contain fields for: first name, last name, date of birth, batting style (dropdown), bowling style (dropdown), player type (dropdown), optional bio, and optional metadata. Date of birth must accept input in a user-friendly manner and display the selected date in human-readable format.
- **FR-022**: Enum dropdowns (batting style, bowling style, player type) MUST display human-readable, properly capitalized labels (e.g., "Right Arm Fast") while submitting original backend enum values (e.g., `right-arm fast`).
- **FR-023**: Player metadata MUST be edited through repeatable key-value fields and converted to a JSON object compatible with the backend JSONB field before submission.
- **FR-024**: The Add Player form MUST include required-field validation, loading and disabled-submit states, success feedback, field-level validation errors, and generic server-error handling.
- **FR-025**: Successful player creation MUST update or refresh the visible player list without requiring a full browser reload.
- **FR-026**: Player creation MUST use `POST /api/v1/players`.
- **FR-027**: The Add Player form MUST prompt the user for confirmation before discarding unsaved changes when the user attempts to close or navigate away.

#### Edit Player

- **FR-028**: The Player Details modal MUST include an "Edit Player" control visible only to Head Coach and Assistant Coach users.
- **FR-029**: Activating Edit MUST close the Player Details modal before opening the Edit Player form (no stacked modals).
- **FR-030**: The Edit Player form MUST contain the same fields as the Add Player form (via shared reusable components), pre-filled with the player's current values, with enum fields displaying human-readable labels while retaining backend values for submission, and dates displayed in the consistent human-readable format.
- **FR-031**: Player updates MUST use `PUT /api/v1/players/{player_id}` with the player's current `version_number`.
- **FR-032**: After a successful update, the player card and details modal data MUST be refreshed, the new `version_number` stored, success feedback shown, without a full browser reload.
- **FR-033**: The Edit Player form MUST prompt the user for confirmation before discarding unsaved changes when the user attempts to close or navigate away.

#### Reusable Form Logic

- **FR-034**: The Add Player and Edit Player forms MUST share reusable form field components, validation logic, enum display-label mappings, date formatting utilities, and metadata key-value controls. Form behavior differences between create and edit (e.g., pre-filling, version number) MUST be handled through configuration rather than duplicate code.

#### Data Freshness

- **FR-035**: After a successful player create or update operation, any cached player-list data MUST be invalidated or refreshed so that the displayed roster reflects the current server state. The next navigation to or rendering of the player list after a mutation MUST show the updated data.

#### Update Conflicts

- **FR-036**: When a `PUT /api/v1/players/{player_id}` returns HTTP 409, the system MUST display a clear conflict message, inform the user the player was updated elsewhere, ask the user to reload, and provide a reload action.
- **FR-037**: After reloading, the form values and `version_number` MUST be replaced with the latest server data. The stale update MUST NOT be automatically retried.

#### Team Filter

- **FR-038**: The Players page MUST include a team filter with options for "All Players", each available team, and "Unassigned Players".
- **FR-039**: The backend player-list endpoint MUST support filtering via a `team_id` query parameter for specific teams and a mechanism for filtering unassigned players.
- **FR-040**: Changing the team filter MUST request the appropriate player list from the backend, reset pagination to page 1, display a loading state, show a no-results message when no players match, and update cards without a full browser reload.

#### Pagination

- **FR-041**: The player list MUST use server-side pagination with configurable page number, page size (default 20), and team filter support.
- **FR-042**: The paginated response MUST include metadata: current page, page size, total players, total pages, previous page exists, next page exists.
- **FR-043**: The frontend MUST provide accessible pagination controls that preserve the active team filter, prevent navigation beyond available pages, show loading state during page changes, and return focus to the player list after page changes.

#### Data Ordering

- **FR-044**: The default player ordering MUST be by last name ascending, then first name ascending, then player ID ascending as a stable tiebreaker.

#### Enum Display Formatting

- **FR-045**: The frontend MUST provide a consistent, centralized mapping between backend enum values and user-facing labels for batting style, bowling style, and player type.
- **FR-046**: Raw enum values MUST NOT be displayed directly to users.
- **FR-047**: The same labels MUST be used consistently across player cards, details, filters, Add Player forms, and Edit Player forms.
- **FR-048**: API requests MUST continue to send the exact enum values expected by the backend.
- **FR-049**: Unknown enum values MUST fall back to a safe readable format rather than breaking the interface.

#### Role and Authorization

- **FR-050**: All authenticated users MAY view the Players page, player cards, Player Details, and bio/metadata.
- **FR-051**: Head Coach and Assistant Coach users MAY add and edit players.
- **FR-052**: Player-role users MUST NOT see Add Player controls, Edit Player controls, or be able to submit create/update requests through the interface.
- **FR-053**: The backend MUST remain the authoritative authorization layer; frontend control visibility does not replace backend enforcement.
- **FR-054**: When the backend returns a 403 Forbidden response for a create or update attempt, the frontend MUST display a clear permissions error message (e.g., "You do not have permission to perform this action") rather than a generic or raw error message.

#### Backend Changes

- **FR-055**: The backend `GET /api/v1/players` endpoint MUST be extended to support server-side pagination with `page`, `page_size`, and `team_id` parameters, and pagination metadata in responses.
- **FR-056**: The backend MUST support filtering players by team and filtering unassigned players through the player-list endpoint.
- **FR-057**: Player-list responses MUST continue to exclude inactive players.
- **FR-058**: Player-list responses MUST include team membership information required by player cards and details.
- **FR-059**: The default player ordering for paginated responses MUST be by last name ascending, then first name ascending.

#### Accessibility

- **FR-060**: The Players interface MUST support keyboard navigation through player cards, visible focus states, semantic page headings, accessible card labels, and accessible modal names/descriptions.
- **FR-061**: Modals MUST include focus trapping, focus restoration, and Escape-key closing.
- **FR-062**: Form fields MUST have programmatic labels and programmatically associated validation errors.
- **FR-063**: Loading, success, error, and permissions-denied states MUST be communicated accessibly.
- **FR-064**: Pagination controls MUST be keyboard-accessible.
- **FR-065**: Controls MUST be touch-friendly on mobile devices (minimum 44px targets per `DESIGN.md`).

#### Responsive Behavior

- **FR-066**: Player cards MUST reflow into an appropriate responsive grid on desktop, tablet, and mobile screens.
- **FR-067**: Cards MUST NOT cause horizontal overflow.
- **FR-068**: Filters, actions, and pagination controls MUST remain usable on narrow screens.
- **FR-069**: Modals MUST fit within the viewport with internal scrolling for long content.
- **FR-070**: Form controls MUST remain touch-friendly on all screen sizes.

#### Testing

- **FR-071**: Frontend tests MUST cover: rendering the Players page, loading cards, team names and "Unassigned" display, human-readable date display, modal open/close, bio/metadata display, role-based control visibility, Add Player form, successful creation, validation errors, unsaved changes confirmation, Edit Player form, successful update, version_number in update requests, HTTP 409 conflicts, reload after conflict, HTTP 403 permissions handling, team filtering, unassigned-player filtering, server-side pagination, data freshness after mutations, shared form logic between Add and Edit, all page/form states, modal keyboard/focus behavior, and responsive card behavior.
- **FR-072**: Backend tests MUST cover: paginated responses, default page size, default ordering by last name, invalid pagination parameters, team filtering, unassigned-player filtering, pagination metadata, excluding inactive players, Head Coach create/edit, Assistant Coach create/edit, player-role denial of create/update, and version-conflict (HTTP 409).
- **FR-073**: At least one Playwright E2E test MUST cover: login, opening the Players page, filtering players by team, opening a Player Details modal, and creating or editing a player as an authorized user.

### Key Entities

- **Player**: A cricket player profile with identity (first name, last name, date of birth), playing attributes (batting style, bowling style, player type), optional bio and metadata (JSON key-value store), active status, and a version number for optimistic concurrency control. Belongs to zero or more teams via the TeamPlayer relationship.
- **Team**: A named cricket squad for an age group. Has a many-to-many relationship with players through the TeamPlayer join table.
- **TeamPlayer (Roster Membership)**: A join record linking a player to a team, representing roster membership with a joined-at timestamp.
- **User (Authenticated Actor)**: An authenticated academy member with a role (head coach, assistant coach, player) that determines what player operations they may perform.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can browse the full active player roster with team information in under 3 seconds on a standard broadband connection.
- **SC-002**: Users can filter players by team and see results update in under 2 seconds without a full page reload.
- **SC-003**: Coaches can complete the Add Player workflow (open form, fill fields, submit, see result) in under 2 minutes for a typical entry.
- **SC-004**: 100% of player card interactions and modal workflows are operable by keyboard alone without error.
- **SC-005**: The Players interface is usable and readable on viewport widths from 320px (mobile) to 2560px (desktop) without horizontal overflow or loss of functionality.
- **SC-006**: Update conflicts (HTTP 409) are resolved by users without data loss — users can reload and re-apply their changes.
- **SC-007**: All page states (loading, empty, filtered no-results, error, success, permissions denied) are communicated to users within 500ms of the state change.
- **SC-008**: Unsaved changes in Add/Edit forms are never silently discarded — 100% of exit attempts with unsaved changes trigger a confirmation prompt.

## Assumptions

- The existing `GET /api/v1/players` endpoint returns only active players and supports extension with pagination and team-filtering query parameters without breaking existing consumers.
- The existing `POST /api/v1/players` and `PUT /api/v1/players/{player_id}` endpoints and their authorization rules (Head Coach and Assistant Coach only) are sufficient for the create and edit workflows.
- Team membership data for player cards and details can be obtained by joining with the `team_players` and `teams` tables in the backend query, without requiring a new dedicated endpoint.
- The "unassigned players" filter will be implemented as a dedicated query parameter (e.g., `unassigned=true`) on the backend, distinct from `team_id`.
- The `AccountSettingsModal` component's modal pattern (backdrop, focus trapping via `useModalDialog`, aria attributes, close button, Escape handling) will be reused or adapted for the Player Details, Add Player, and Edit Player modals.
- Enum formatting logic will be centralized in a shared frontend utility rather than duplicated across components.
- Date formatting (display and submission) will be handled by shared utility functions used consistently by cards, modals, and forms.
- The existing Tailwind CSS design system, color palette, spacing scale, and component patterns defined in `PRODUCT.md` and `DESIGN.md` will be applied consistently.
- Player statistics, deactivation, reactivation, deletion, roster management, profile images, search, advanced filtering, sorting, bulk operations, CSV import/export, and player-user account linking are explicitly out of scope for this feature.
