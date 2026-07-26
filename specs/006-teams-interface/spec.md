# Feature Specification: Teams Interface

**Feature Branch**: `006-teams-interface`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "Part 6: Teams Interface — Build the Teams interface for the VK Cricket Academy web application, covering both frontend and backend work required to display, create, paginate, view, and edit teams and their ordered rosters."

## Clarifications

### Session 2026-07-25

- Q: Atomic team creation endpoint shape? → A: `POST /api/v1/teams` with a single request body containing team name, age group, and ordered player IDs. (FR-013)
- Q: Should Edit Team update details and roster separately or in one transaction? → A: One atomic backend transaction via `PUT /api/v1/teams/{team_id}` with team name, age group, ordered player IDs, and version number in a single request body. (FR-027, FR-028)
- Q: Should roster retrieval return only active members? → A: Return all existing roster members including inactive ones, with an `is_active` flag. Inactive players are visually distinguishable but cannot be newly selected in the roster form. (FR-031)
- Q: Player search endpoint filtering scope? → A: `GET /api/v1/players` must match first name, last name, and full name against a single query string. (FR-017)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse Teams (Priority: P1)

A head coach, assistant coach, or player opens the Teams page to see all academy teams organized in a card grid. The page loads quickly with empty, loading, error, and retry states clearly handled. Users can navigate between pages when more than 12 teams exist and open any team's details with a click or keyboard activation.

**Why this priority**: The team list is the entry point for all other team operations. Without it, no user can discover which teams exist or reach team details and rosters. This story delivers immediate visibility value to every authenticated user.

**Independent Test**: Log in as any role, navigate to the Teams page, and verify that team cards appear in a responsive grid with team name, age-group badge, roster count, and working pagination when teams exceed one page.

**Acceptance Scenarios**:

1. **Given** multiple teams exist in the system, **When** an authenticated user opens the Teams page, **Then** team cards display with team name, age-group badge, and current roster count (e.g., "12 / 15 players").
2. **Given** fewer than 13 teams exist, **When** a user opens the Teams page, **Then** all teams are visible on the first page without pagination controls.
3. **Given** more than 12 teams exist, **When** a user clicks the Next page button, **Then** the next page of teams loads, focus moves to the team list, and the page state updates.
4. **Given** the Teams page is loading, **When** data has not yet arrived, **Then** an accessible loading indicator is displayed.
5. **Given** no teams exist in the system, **When** a user opens the Teams page, **Then** an empty-state message appears and authorized users see a Create Team action.
6. **Given** the team list request fails, **When** an error occurs, **Then** a generic error message with a retry action is displayed.

---

### User Story 2 - View Team Details and Roster (Priority: P1)

A user selects a team card to open a modal showing the team's full details: name, age group, player count, and the complete ordered roster. Each roster row shows a player's name and an info control to view that player's full details. Opening a player's details replaces (does not stack on) the team details modal.

**Why this priority**: Viewing a roster is the core reason users interact with teams — coaches need to see who is on which team, and players need to see their squad. This story makes rosters visible and navigable.

**Independent Test**: Open a team card, verify the modal displays the correct team name, age group, player count, and ordered roster. Click a player's info icon and confirm the team modal is replaced by the player details modal.

**Acceptance Scenarios**:

1. **Given** a team has 10 players in a saved order, **When** a user opens the team details modal, **Then** the roster displays 10 players in exactly that saved order.
2. **Given** a team has zero players, **When** a user opens the team details modal, **Then** an empty-roster message is displayed.
3. **Given** the team details modal is open, **When** a user clicks a player's information control, **Then** the team details modal closes and the Player Details modal opens for that player.
4. **Given** the team details modal is open, **When** a user presses Escape or clicks the close button, **Then** the modal closes, background scroll is restored, and focus returns to the previously active team card.
5. **Given** the team details modal is open on a small screen, **When** the roster exceeds the viewport height, **Then** the modal content scrolls internally without the background page scrolling.

---

### User Story 3 - Create a Team (Priority: P2)

A head coach or assistant coach opens a team creation form from the Teams page and creates a new team with a name, age group, and an ordered roster of 7–15 players. The entire operation is atomic: if any validation fails, no team or roster data is persisted. After success, the team appears in the list and the modal closes.

**Why this priority**: Team creation is a core operational task that coaches perform regularly. It depends on the browse and detail-view stories (P1) for the full workflow to make sense.

**Independent Test**: Log in as a head coach, click Create Team, fill in a team name, select an age group, select 7–15 distinct active players, reorder them, and submit. Verify the new team appears in the list with the correct roster.

**Acceptance Scenarios**:

1. **Given** a head coach is on the Teams page, **When** they click Create Team, **Then** a modal opens with a form containing team name, age-group dropdown, and 15 ordered player-selection rows.
2. **Given** the first 7 player rows are filled with distinct active players and all fields are valid, **When** the coach submits, **Then** the team and its ordered roster are created atomically and the new team appears in the list.
3. **Given** fewer than 7 players are selected, **When** the coach submits, **Then** a validation error is shown and no team is created.
4. **Given** the same player is selected in two rows, **When** the coach attempts to submit, **Then** a duplicate-player validation error is shown.
5. **Given** the team name "Falcons" already exists in age group U13, **When** a coach submits " falcons " for a new U13 team, **Then** a uniqueness error is returned (case-insensitive, whitespace-normalized).
6. **Given** the team name "Falcons" exists in U13, **When** a coach creates "Falcons" in U15, **Then** creation succeeds (name must only be unique within the same age group).
7. **Given** a player-role user is on the Teams page, **When** they view the page, **Then** the Create Team button is not visible.
8. **Given** the create request is in progress, **When** the coach clicks Submit again, **Then** duplicate submission is prevented and an accessible loading state is communicated.

---

### User Story 4 - Edit Team and Roster (Priority: P2)

A head coach or assistant coach opens a team's details modal, selects Edit Team, and modifies the team name, age group, or roster in a pre-filled form. The form supports adding, removing, replacing, and reordering players. Updates use optimistic concurrency: a stale version number is rejected with a clear conflict message.

**Why this priority**: Roster management is a frequent coaching activity — players join, leave, or move between teams. Editing is paired with creation (P2) because they share the same form infrastructure and validation rules.

**Independent Test**: Open an existing team's details, click Edit, change the team name and reorder two players via Move Up/Move Down controls, submit, and verify the changes persist. Then reload the page and confirm the roster order is stable.

**Acceptance Scenarios**:

1. **Given** a coach opens team details and clicks Edit Team, **When** the edit form opens, **Then** the form is pre-filled with the current team name, age group, ordered roster, and version number.
2. **Given** the coach changes the team name and submits with a valid version number, **When** the request succeeds, **Then** the team list and details reflect the updated name.
3. **Given** the coach removes two players (leaving at least 7) and submits, **When** the request succeeds, **Then** the roster reflects the removal.
4. **Given** the team's version number has changed on the server since the form was opened, **When** the coach submits, **Then** HTTP 409 is returned, a conflict message is shown, and the user is offered a reload action that updates the form with current server data.
5. **Given** a player-role user opens team details, **When** they view the modal, **Then** the Edit Team control is not visible.

---

### User Story 5 - Reorder Roster (Priority: P2)

A coach reorders players in the team form using both drag-and-drop (with a grip icon) and keyboard-accessible Move Up/Move Down controls. The saved roster order persists across page reloads and repeated API requests.

**Why this priority**: Batting order and positional organization matter in cricket teams. Reordering is part of both creation and editing workflows and shares the same form infrastructure.

**Independent Test**: In a team form with 10 players, drag player 5 to position 2 and use Move Up on player 8 to move it to position 7. Submit and verify the saved order matches the displayed order after page reload.

**Acceptance Scenarios**:

1. **Given** 10 players are selected in a team form, **When** a coach drags player 5 to position 2, **Then** the visible order updates immediately and all player data is preserved.
2. **Given** player 3 is selected, **When** the coach activates Move Up, **Then** the player moves to position 2 and the Move Up control becomes disabled since the player is now at position 1.
3. **Given** the last player in the roster is selected, **When** the coach activates Move Down, **Then** the control is disabled because movement in that direction is unavailable.
4. **Given** a team is saved with a specific roster order, **When** the page is reloaded and team details are opened, **Then** the roster displays in exactly the same order.

---

### Edge Cases

- What happens when the team list API returns zero teams? An empty-state message with a Create Team action (for authorized users) is displayed.
- What happens when a user tries to navigate to a page number beyond the available range? Pagination controls prevent navigation outside valid pages.
- What happens when a player selected in the roster is later deactivated? Backend validation during team creation/editing rejects inactive players. Existing rosters with deactivated players remain viewable (with muted styling and an is_active indicator) but the player cannot be re-selected if removed from the roster.
- What happens when a user closes the modal with unsaved changes? A confirmation prompt appears, allowing the user to continue editing or discard changes.
- What happens when the roster-replacement request is a subset of an atomic operation that partially fails? The backend must roll back the entire operation — no partial roster changes persist.
- What happens when two coaches edit the same team simultaneously? The first submitter succeeds; the second receives HTTP 409 and must reload.
- What happens when a player appears in the search dropdown but has already been selected in another row? That player is excluded from the other dropdowns to prevent duplicate selection.
- What happens when the Player Details modal is opened from within the Team Details modal? The Team Details modal closes first so modals never stack.

## Requirements *(mandatory)*

### Functional Requirements

#### Teams Page and Team Cards

- **FR-001**: The system MUST replace the existing Teams placeholder page with a functional Teams interface within the authenticated application shell.
- **FR-002**: The Teams page MUST display a page heading and a Create Team button for authorized users (Head Coach, Assistant Coach).
- **FR-003**: Team cards MUST display the team name, an age-group badge/avatar, and the current roster count in the format "N / 15 players".
- **FR-004**: Team cards MUST use the academy branding (Clubhouse White background, 1px Boundary Line border, rounded corners per DESIGN.md rounded.lg = 12px) and follow the same visual structure as existing Player Directory cards.
- **FR-005**: Team cards MUST be keyboard-accessible and open the Team Details modal when clicked or activated with Enter/Space.
- **FR-006**: Age-group values from the backend (J, U11, U13, U15) MUST be displayed using human-readable, properly capitalized labels: "Juniors", "U11", "U13", "U15".

#### Team Details Modal

- **FR-007**: Selecting a team card MUST open a Team Details modal displaying the team name, age group, current player count, the ordered roster, and an Edit Team control for authorized users.
- **FR-008**: The roster MUST always display players in their saved ascending roster order. If the roster is empty, an empty-roster state MUST be shown.
- **FR-009**: Each roster row MUST display the player's name and an information control that opens that player's details. Opening Player Details MUST close or replace the Team Details modal — stacked modals are forbidden.
- **FR-010**: The Team Details modal MUST support keyboard focus trapping, Escape-key closing, a visible close button, background scroll locking, focus restoration after closing, and responsive sizing with internal scrolling on small screens.

#### Team Creation

- **FR-011**: The Create Team button MUST be visible only to Head Coach and Assistant Coach users. Player-role users MUST NOT see it.
- **FR-012**: The Create Team form MUST contain: a team name text input, an age-group dropdown with backend-supported values and human-readable labels, and 15 ordered player-selection rows.
- **FR-013**: Team creation MUST use `POST /api/v1/teams` with a single request body containing the team name, age group, and an ordered list of player IDs. The backend MUST create the team and its complete ordered roster in one transaction, rolling back entirely if any validation, authorization, or database operation fails.
- **FR-014**: A team MUST have at least 7 and at most 15 players, an age group, a name unique (case-insensitive, whitespace-normalized) within its age group, only active players, and no duplicate players.
- **FR-015**: The frontend MUST submit team details and the ordered roster as one logical operation.

#### Player Selection

- **FR-016**: Each player dropdown MUST allow filtering by first name, last name, or full name; display only active players; handle loading, no-results, and API-error states; and exclude already-selected players from its options.
- **FR-017**: The `GET /api/v1/players` endpoint MUST support filtering by first name, last name, and full name (matching any of the three against a single query string) to power the player-search dropdowns.
- **FR-018**: The information icon on each row MUST be disabled and visually greyed out when no player is selected, and MUST include an accessible label.
- **FR-019**: The remove control MUST clear the selected player, use a red trash icon with an accessible label, and be disabled when the row is already empty.
- **FR-020**: Rows 1–7 are required; rows 8–15 are optional. Empty optional rows are allowed.

#### Roster Ordering

- **FR-021**: Users MUST be able to reorder players via drag-and-drop (six-dot grip icon) and keyboard-accessible Move Up/Move Down controls. Drag-and-drop MUST NOT be the only reordering method.
- **FR-022**: Move controls MUST include accessible labels, be disabled when movement in that direction is unavailable, update the visible row order immediately, and preserve selected player data.
- **FR-023**: The backend roster-membership model MUST store an explicit stable order field (e.g., "position" or "roster_order") and MUST NOT rely on database insertion order.
- **FR-024**: Roster members MUST always be returned in ascending roster-order value, and roster order MUST remain stable across page reloads, detail requests, edits, pagination, and repeated API requests.

#### Team Editing

- **FR-025**: The Edit Team control MUST be visible only to Head Coach and Assistant Coach users in the Team Details modal. Player-role users MUST NOT see it.
- **FR-026**: Selecting Edit Team MUST open the reusable Team form pre-filled with the current team name, age group, ordered roster, and version number. The details modal MUST close before the edit form opens.
- **FR-027**: The edit form MUST allow changing the team name, age group, and roster (add, remove, replace, reorder players), applying the same validation rules as creation (7–15 players, no duplicates, active players only, unique normalized name within age group). The complete Edit Team submission MUST call `PUT /api/v1/teams/{team_id}` (see FR-028).

#### Team Update Endpoints

- **FR-028**: The backend MUST provide `PUT /api/v1/teams/{team_id}` for updating both team details (name, age group) and the full ordered roster in a single atomic transaction. The request body MUST contain the team name, age group, ordered list of player IDs, and the current version number. The endpoint MUST validate the complete roster (7–15 players, no duplicates, active players, version number) and roll back entirely on failure.
- **FR-029**: Team updates MUST use optimistic concurrency via the team's version number. A stale version number MUST return HTTP 409.

#### Team Deletion

- **FR-030**: Team deletion is explicitly out of scope. No delete endpoint, soft-delete mechanism, or deactivation workflow is included in this feature.

#### Team Roster Retrieval

- **FR-031**: The backend MUST provide `GET /api/v1/teams/{team_id}/players` returning existing roster members in ascending roster order. The response MUST include each player's ID, name, and an `is_active` flag. Inactive players MUST be visually distinguishable in the roster display (e.g., muted styling) but MUST NOT be selectable in the player-search dropdowns for new roster entries.

#### Server-Side Pagination

- **FR-032**: The team list endpoint (`GET /api/v1/teams`) MUST support server-side pagination with query parameters for page and page size.
- **FR-033**: The default page size MUST be 12, and default ordering MUST be team name ascending, then age group ascending, then team ID ascending.
- **FR-034**: The paginated response MUST include current page, page size, total teams, total pages, and previous/next page availability.
- **FR-035**: Pagination controls MUST prevent navigation outside available pages, display a loading state during page changes, remain keyboard-accessible, and return focus to the team list after page changes.

#### Authorization

- **FR-037**: All authenticated users MAY view the Teams page, team cards, team details, and rosters, and open Player Details from a roster.
- **FR-038**: Head Coach and Assistant Coach users MAY create teams, edit team details, and manage (add, remove, reorder, replace) rosters.
- **FR-039**: Player-role users MUST NOT see Create Team or Edit Team controls, and the backend MUST reject unauthorized create or update requests with HTTP 403.

#### Form and Page States

- **FR-040**: The Teams interface MUST handle loading state (accessible loading indicator), empty state (clear message with Create action for authorized users), error state (generic message with retry where applicable), validation state (field-level errors for missing name, missing age group, fewer than 7 players, more than 15 players, duplicate players, duplicate normalized name, invalid/inactive player selections), submission state (disable submission, prevent duplicates, communicate progress accessibly), success state (confirmation feedback, data refresh without full reload), permission state (clear message for HTTP 403), and conflict state (HTTP 409 flow with reload action).
- **FR-041**: Create and Edit Team forms MUST detect unsaved changes and display a confirmation prompt if the user attempts to close or navigate away, allowing them to continue editing or discard changes intentionally.

#### Reusable Components

- **FR-042**: Create and Edit Team workflows MUST reuse shared form fields, roster-selection rows, player-search logic, validation, age-group formatting, roster-ordering controls, modal behavior, and error/success messaging, differing through configuration and initial data.

#### Accessibility

- **FR-043**: The Teams interface MUST support: keyboard-accessible cards, visible focus states, semantic headings, accessible card/modal labels, focus trapping in modals, focus restoration after close, accessible dropdowns, accessible remove/info controls, drag alternatives via Move Up/Move Down, programmatically associated validation errors, accessible state messages, accessible pagination, and touch-friendly controls on mobile.

#### Responsive Behavior

- **FR-044**: The Teams interface MUST remain usable on desktop, tablet, and mobile screens. Team cards MUST reflow into a responsive grid without horizontal overflow. Create and Edit forms MUST fit within the viewport with internal scrolling for long rosters. Player-selection rows MUST remain understandable on narrow screens and controls may stack vertically. Pagination and all roster control icons MUST remain touch-friendly on mobile.

#### Backend Data Model

- **FR-045**: The backend MUST add an `AgeGroup` enum (J, U11, U13, U15) and constrain the Team model's `age_group` field to these values.
- **FR-046**: The backend MUST add an explicit integer `roster_order` (or equivalent) field to the `TeamPlayer` model, and roster queries MUST order by this field ascending.

### Key Entities

- **Team**: Represents a named cricket squad for a specific age group. Key attributes: name, age group (J | U11 | U13 | U15), version number (for optimistic concurrency). Relationships: has many team-player memberships.
- **Team Roster Membership**: Links a player to a team with an explicit roster order position. Key attributes: team ID, player ID, roster order (integer, 1-based). The combination of team and player is unique.
- **Player**: (Existing entity, referenced) An active academy player. Key attributes used: ID, first name, last name, active status.
- **Age Group**: (New enum) Supported values: J (Juniors), U11, U13, U15. Displayed with human-readable labels.
- **User Role**: (Existing entity, referenced) Controls authorization. Head Coach and Assistant Coach can create/edit teams; Player can only view.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can browse, create, and view team details on desktop, tablet, and mobile devices without horizontal scrolling or layout breakage.
- **SC-002**: Team page loads and displays the first page of 12 team cards in under 2 seconds. Validated manually during acceptance testing — the academy-scale data volume (tens of teams) makes this a reliably achievable target on the project stack.
- **SC-003**: Coaches can create a complete team with a 15-player ordered roster in under 3 minutes from form open to confirmation.
- **SC-004**: Roster order persists correctly across page reloads and repeated detail requests — saved order always matches displayed order.
- **SC-005**: 100% of unauthorized create/edit attempts are rejected by the backend with HTTP 403, regardless of frontend visibility toggles.
- **SC-006**: When a team update encounters a version conflict, the user receives a clear explanation and a one-click reload action; no stale data overwrites server state.
- **SC-007**: All modal interactions (open, close, escape, focus trap, focus restore) work correctly for keyboard-only users without mouse input.
- **SC-008**: Zero stacked modals occur — opening Player Details from Team Details always closes or replaces the team modal.
- **SC-009**: Pagination navigation between pages completes without losing keyboard focus context on the team list.
- **SC-010**: Users can reorder a full 15-player roster using only the keyboard (Move Up/Move Down) in under 30 interactions.

## Assumptions

- The existing authenticated application shell (sidebar navigation, auth context, role information) is reused as-is. Teams is added as a new route within the existing protected layout.
- The existing `ModalDialog` component provides the foundation for Team Details, Create Team, and Edit Team modals. Additional modal features (confirmation dialogs for unsaved changes, conflict resolution UI) are built on top of it.
- The existing `Pagination` component is reused or extended for server-side team pagination.
- The existing `PlayerDetailsModal` is reused for viewing player details from roster rows without modification.
- The existing `ApiClient` handles token refresh, CSRF, and error parsing uniformly for all new team and roster API calls.
- Player search/filtering for the dropdowns uses the existing `GET /api/v1/players` endpoint with query parameters.
- The backend database is PostgreSQL, and migrations are managed by Alembic (the existing project standard).
- The feature description explicitly excludes team deletion, deactivation, logos, captain/vice-captain assignment, and bulk import — these are not in scope.
- Age groups are fixed at J, U11, U13, U15 and are not user-configurable.
