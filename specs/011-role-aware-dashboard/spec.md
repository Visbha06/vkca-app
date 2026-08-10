# Feature Specification: Dynamic Role-Aware Dashboard and Operational Summary

**Feature Branch**: `011-role-aware-dashboard`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Part 11: Dynamic Role-Aware Dashboard and Operational Summary"

## Clarifications

### Session 2026-08-10

- Q: What Match creation scope belongs to this feature? → A: Add backend/domain participant support only; omit Match creation/editing UI and defer any dashboard Create match action without an existing workflow.
- Q: What happens when a linked Player profile becomes inactive? → A: Apply the existing deactivated Assistant Coach session invariant: revoke sessions, log out, reject login, and follow existing reactivation conventions.
- Q: Which Business Audit actions may account-link mutations use? → A: Reuse only semantically accurate existing actions; otherwise add explicit linked, unlinked, and reassigned actions, exactly once per successful transaction.
- Q: How should Assistant Coach quick actions be determined? → A: Inspect existing backend permissions and workflows during planning; expose only already-authorized actions and add none solely for this dashboard.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review a live academy briefing (Priority: P1)

As a Head Coach, Assistant Coach, or Player, I want the home dashboard to
show a current operational briefing based on the academy records I am allowed
to see, so that I can understand the next useful action without checking every
workflow separately.

**Why this priority**: The dashboard is the first authenticated route and is
currently a static example. Live, correctly scoped information is the core
value of this feature.

**Independent Test**: Seed training events, external and internal Matches,
teams, memberships, and recent activity; authenticate separately as each role;
open `/`; verify the preserved dashboard structure, live values, role scope,
and role-specific panel without using any other page.

**Acceptance Scenarios**:

1. **Given** a Head Coach with academy records, **When** the Head Coach opens
   the dashboard, **Then** the greeting uses the authenticated name, the three
   summary slots use live academy-wide values, Upcoming Events is chronologically
   populated, and Recent Academy Activity contains at most four eligible
   Business Audit events with a link to the existing Audit Log.
2. **Given** an Assistant Coach assigned to two teams, **When** the Assistant
   Coach opens the dashboard, **Then** training, Matches, active-player counts,
   scoped events, and My Teams are derived only from those assignments plus
   explicitly all-academy events.
3. **Given** a Player with an explicitly linked Player profile and multiple
   TeamPlayer memberships, **When** the Player opens the dashboard, **Then** the
   dashboard uses those memberships for training, Matches, events, and My Teams
   and does not expose another Player's context or Business Audit activity.
4. **Given** live dashboard loading fails, **When** the user retries, **Then**
   the interface shows a clear retryable state, never restores the old hardcoded
   example data, and retains already usable sections where the failure is
   isolated.
5. **Given** any supported dashboard role and content state, **When** the
   dashboard renders, **Then** it shows exactly one designated primary action
   that uses only an already permitted destination. If no permitted
   administrative shortcut is available, the action is View Upcoming Events.
   When there are no relevant Upcoming Events, it deterministically becomes
   View Teams only when the user is already authorized for the existing Teams
   workflow and has at least one scoped Team; otherwise View Upcoming Events
   remains available and focuses its explicit empty state. No primary action
   may expose an unauthorized destination.

### User Story 2 - Correctly represent upcoming Match participants (Priority: P1)

As an academy operator, I want a Match to identify its academy participant(s)
and home/away semantics unambiguously, so that the dashboard and future match
workflows can determine relevance without guessing from an opponent string.

**Why this priority**: The current Match record has only an opponent name and
cannot distinguish an external match from an internal academy match. The
dashboard cannot safely scope the Next Match summary until ownership is explicit.

**Independent Test**: Submit valid and invalid external and internal Match
payloads through the domain contract, then request a role-scoped dashboard and
verify that each valid Match appears exactly once for every role/team scope it
should serve.

**Acceptance Scenarios**:

1. **Given** one academy Team playing an external opponent, **When** a valid
   external Match is created or updated, **Then** the record preserves the
   academy Team, external opponent name, and whether the academy Team is home or
   away, and no internal participant fields are present.
2. **Given** two different academy Teams, **When** a valid internal Match is
   created or updated, **Then** the record preserves the home and away academy
   Teams and has no external opponent representation.
3. **Given** a payload that mixes internal and external fields, omits a required
   participant, or uses the same Team on both internal sides, **When** it is
   submitted, **Then** validation rejects it before persistence and no Match or
   Business Audit success event is created.
4. **Given** an internal Match where both Teams belong to the same Assistant
   Coach or Player, **When** the dashboard is loaded, **Then** the Match appears
   once rather than once per relevant side.

### User Story 3 - Link a Player account to the correct Player profile (Priority: P1)

As a Head Coach, I want to explicitly link, unlink, or correct a Player-role
login account against a Player profile from the Player Directory, so that Player
dashboard scope is based on a verified relationship rather than an identity
guess.

**Why this priority**: A Player account cannot safely receive team-specific
information without an explicit association, and the association is a durable
academy-domain relationship that needs clear correction and audit behavior.

**Independent Test**: Open an existing Player profile edit flow as a Head Coach,
link an eligible unlinked Player-role account, reload the profile, unlink it
with confirmation, and verify authorization, uniqueness, rollback, and audit
outcomes through the user interface and API tests.

**Acceptance Scenarios**:

1. **Given** an unlinked Player profile and an eligible unlinked Player-role
   account, **When** a Head Coach selects Link account, chooses the exact account,
   and confirms, **Then** the association is saved and the profile shows the
   linked account without exposing credentials.
2. **Given** a linked Player profile, **When** a Head Coach selects Unlink account
   and confirms, **Then** the association is removed, neither record is deleted,
   and the profile shows No account linked.
3. **Given** an account or profile already linked elsewhere, **When** a Head Coach
   attempts to link it, **Then** the request is rejected without silently
   overwriting the existing relationship.
4. **Given** an Assistant Coach or Player, **When** that user attempts to access
   or mutate account/profile linking, **Then** the server returns a forbidden
   response and the frontend does not provide the linking controls.
5. **Given** a Player-role account with no linked profile, **When** that Player
   signs in and opens the dashboard, **Then** the Player can authenticate normally
   but sees a limited unlinked state, no academy-wide fallback information, and
   instructions to contact the Head Coach.

### User Story 4 - Work with role-specific dashboard context (Priority: P2)

As a dashboard user, I want the right-side panel to show context useful to my
role without disappearing or revealing restricted information, so that the
dashboard remains an operational overview for everyone.

**Why this priority**: The existing layout reserves a meaningful right column.
Replacing it with a role-appropriate panel preserves the established visual
hierarchy and makes the dashboard useful beyond Head Coaches.

**Independent Test**: Seed recent audit events, assigned teams, team rosters,
coaches, and relevant events; render the dashboard for all three roles; verify
the right panel, bounds, navigation, empty states, and denied data separately.

**Acceptance Scenarios**:

1. **Given** a Head Coach, **When** the dashboard loads, **Then** the panel is
   Recent Academy Activity and contains the latest bounded eligible Business
   Audit events only.
2. **Given** an Assistant Coach with assigned teams, **When** the dashboard loads,
   **Then** the panel is My Teams and each entry includes team name, age group,
   active-player count, and the next relevant event when available.
3. **Given** a linked Player with current memberships, **When** the dashboard
   loads, **Then** the panel is My Teams and each entry includes permitted team,
   age-group, coach, and next-event context when available.
4. **Given** an Assistant Coach with no assigned teams or a linked Player with no
   current memberships, **When** the dashboard loads, **Then** the panel remains
   in place and shows a specific no-team state rather than academy-wide data.

### Edge Cases

- There is no future Practice event in the user's scope: show an explicit no
  upcoming training state.
- There is no future Match in the user's scope: show an explicit no upcoming
  match state.
- There are no Calendar occurrences in scope: show an explicit no upcoming
  events state.
- A recurring Calendar event is moved into the requested range, deleted, or
  replaced: use the effective occurrence once and omit deleted occurrences.
- The same Calendar occurrence is relevant through multiple teams or age-group
  memberships: show it once using its stable occurrence identity.
- A Player belongs to more than one assigned team: active-player counts remain
  distinct and the Player summary uses a concise multi-team representation.
- A Player profile is inactive, has no TeamPlayer memberships, or has stale
  historical roster rows: do not fabricate a current team context. When a
  linked Player profile becomes inactive, revoke all active sessions for the
  associated Player-role User and reject future login attempts until
  reactivation, following the existing deactivated Assistant Coach account
  conventions; authenticated use must not enter a separate inactive-Player
  dashboard state.
- A Head Coach or Assistant Coach has no relevant training, Match, or Calendar
  data: each affected summary or section shows its own empty state.
- An internal Match has both teams relevant to one viewer: it is one Match, not
  two rows or two summary candidates.
- A Match has an academy-local date equal to today: because Match records are
  date-based in the current domain, it is eligible as the next Match for that
  day and is ordered deterministically.
- The Player account is linked after the dashboard was previously unlinked:
  the next authenticated dashboard load uses the association without requiring
  the Player to claim or refresh a guessed identity.
- A link, unlink, or reassignment request races with another Head Coach: the
  stale relationship is rejected safely and the user is asked to reload before
  retrying.
- A section fails while another section has loaded: retain the usable section,
  identify the failed section, and provide a section-level retry when practical.
- A dashboard request is unauthorized, unauthenticated, or receives stale role
  data: use the existing authentication/session-expiry and forbidden behavior;
  never use client-supplied scope values.
- A narrow viewport causes event metadata or team names to wrap: content must
  remain readable without page-level horizontal overflow or inaccessible
  truncation.

## Requirements *(mandatory)*

### Functional Requirements

#### Live dashboard and role scope

- **FR-001**: The dashboard MUST preserve the existing composition substantially:
  greeting/header and quick actions, one three-part summary strip, a larger
  left Upcoming Events section, a right contextual panel, and the existing
  responsive stacking relationship.
- **FR-002**: The dashboard MUST replace all hardcoded sample greetings, summary
  values, event rows, and role-specific panel data with current authenticated
  user and academy records. It MUST never fall back to the old example values
  when live loading fails.
- **FR-003**: The greeting MUST use the authenticated user's current name from
  the existing current-user/authentication flow and use wording appropriate to
  the user's role. The general subtitle and visual hierarchy MUST remain intact.
- **FR-004**: The dashboard MUST render exactly one designated primary action
  for every permitted role and content state. The action MUST be chosen only
  from destinations and capabilities already exposed by the corresponding
  backend authorization and existing workflow; it MUST NOT grant or imply a
  new permission. When an administrative quick action is already permitted,
  select the first permitted action in this deterministic order: Schedule
  event, then Add player. A Create match action MUST be omitted or deferred
  unless an existing Match creation workflow and route already exist. When no
  administrative quick action is permitted, use View Upcoming Events to focus
  the existing dashboard section. If that section has no relevant events, use
  View Teams only when the user is already authorized for the existing Teams
  workflow and has at least one scoped Team; otherwise retain View Upcoming
  Events and focus its explicit empty state. Assistant Coaches and Players
  MUST NOT receive an administrative mutation shortcut solely to populate the
  dashboard, and no primary action may expose an unauthorized destination.
- **FR-005**: The backend MUST expose an authenticated current-user dashboard
  capability under the existing versioned API boundary. The server MUST derive
  the scope from the database-loaded authenticated User and MUST reject any
  attempt to supply an arbitrary User ID, Player ID, coach ID, or team set to
  select another dashboard scope.
- **FR-006**: The dashboard response MUST be strongly typed, role-aware, bounded,
  deterministically ordered, and limited to data needed for the authenticated
  user's dashboard. It MUST represent populated, empty, unlinked, and
  section-unavailable states without ambiguous nulls or fabricated values.
- **FR-007**: The dashboard projection MUST be calculated from current source
  records at read time. It MUST NOT persist dashboard summaries, calculated
  counts, event projections, My Teams projections, or role-specific snapshots;
  it MUST NOT add background aggregation, refresh queues, or notification
  infrastructure.
- **FR-008**: The dashboard service MUST be reusable by the dashboard capability
  and related role-scoped operational projections. It MUST use bounded, set-based
  loading and avoid N+1 loading of Teams, Players, memberships, Calendar
  occurrences, Matches, coaches, or audit events.
- **FR-009**: Head Coach scope MUST include academy-wide operational data and
  the existing bounded Recent Academy Activity projection.
- **FR-010**: Assistant Coach scope MUST be derived only from active TeamCoach
  relationships for the authenticated User, plus Calendar events explicitly
  scoped to all academy users where current permissions allow. It MUST NOT
  return unrelated team, Player, Match, or age-group-only data.
- **FR-011**: Player scope MUST resolve only through the explicit chain
  authenticated User → linked Player profile → TeamPlayer memberships → Teams.
  It MUST NOT infer identity from name, email, date of birth, or any approximate
  match, and it MUST NOT return another Player's profile or team context.
- **FR-012**: A Player-role User without a linked Player profile MUST receive a
  typed limited dashboard state. The state MUST omit academy-wide player/team
  information and include clear contact-the-Head-Coach guidance. The Player MUST
  remain able to authenticate and MUST not be able to claim a profile.
- **FR-012a**: A Player-role User whose linked Player profile becomes inactive
  MUST follow the existing deactivated Assistant Coach security behavior: all
  active sessions for that User MUST be revoked, the User MUST be logged out,
  and future login attempts MUST be rejected while the profile remains inactive.
  Reactivation MUST follow the repository's existing account/session
  conventions. Authenticated use MUST NOT expose a separate inactive-Player
  dashboard state.

#### Summary strip

- **FR-013**: The three summary slots MUST retain the current shared summary-band
  layout and replace each hardcoded value with live data or an explicit empty
  state.
- **FR-014**: Upcoming training MUST be selected from Calendar occurrences whose
  classification is Practice (`event_type = practice` in the current Calendar
  domain), never from free-text event names. It MUST be the chronologically
  nearest applicable future occurrence in the user's scope.
- **FR-015**: Next match MUST be selected from Match records, not Calendar Game
  events. Head Coaches MUST consider any valid academy Match; Assistant Coaches
  MUST consider Matches involving an assigned Team; Players MUST consider Matches
  involving a Team in their current memberships.
- **FR-016**: Active players MUST count active Player profiles. Head Coaches MUST
  receive the academy-wide count; Assistant Coaches MUST receive the distinct
  count across assigned Teams; Players MUST receive the third slot as My team or
  My teams rather than an academy-wide active-player count. Exactly one current
  membership MUST show that Team; multiple current memberships MUST show a
  concise aggregate that fits the existing card; and no memberships MUST show
  an explicit no-team state.
- **FR-017**: Assistant Coach summaries MUST show explicit no-assigned-team
  states and MUST never fall back to academy-wide counts or events. A Player with
  no current TeamPlayer memberships MUST show an explicit no-team state.
- **FR-018**: The summary MUST represent an internal Match as one Match even when
  both home and away Teams are relevant. External and internal participant
  labels MUST preserve home/away semantics and distinguish academy Teams from
  outside opponents.

#### Upcoming Events

- **FR-019**: Upcoming Events MUST be projected from the existing Calendar
  effective-occurrence behavior, remain bounded, and be ordered chronologically
  using deterministic tie-breaking.
- **FR-020**: Event rows MUST show only useful operational details such as academy
  date, academy-local time, event name, event category, and relevant Team or age
  group context. They MUST omit location/venue from the dashboard rows.
- **FR-021**: Head Coach event scope MUST include applicable academy Calendar
  events across all scopes. Assistant Coach and Player event scope MUST include
  all-academy events and only age-group events matching their assigned/current
  Teams. Overlapping relevance MUST be deduplicated by effective occurrence.
- **FR-022**: Dashboard event selection MUST reuse Calendar recurrence, occurrence
  exception, moved-occurrence, deleted-occurrence, scope, academy-local timezone,
  and daylight-saving semantics. It MUST NOT introduce a second recurrence
  engine or treat Calendar events and Match records as interchangeable. Calendar
  game events MAY appear in Upcoming Events when present, but Next match MUST
  always be selected from Match records.

#### Role-aware contextual panel

- **FR-023**: Head Coach Recent Academy Activity MUST retain the existing bounded
  feed behavior, display at most four eligible Business Audit events, retain
  View all activity navigation to the Audit Log, and remain Head Coach-only.
- **FR-024**: Dashboard reads, refreshes, retries, and role-aware projections
  MUST NOT create Business Audit events. Business Audit activity MUST remain
  separate from authentication/security audit data.
- **FR-025**: Assistant Coach My Teams MUST show a bounded list of assigned Teams,
  each with team name, age group, active-player count, and next relevant event
  when one exists. Navigation MUST point to the existing Teams workflow only
  where the Assistant Coach has permission.
- **FR-026**: Player My Teams MUST use only Teams from the linked Player's current
  memberships and show team name, age group, permitted assigned coach/coaches
  where appropriate, and next relevant event when one exists. It MUST show a
  clear no-team state when there are no memberships.
- **FR-027**: The bounded panel projections MUST use deterministic ordering and
  MUST not expose Business Audit data to Assistant Coaches or Players.

#### Player account/profile association and linking

- **FR-028**: Player profiles MUST support an optional one-to-one association to
  a User account through a nullable Player-side account reference. Existing
  Player profiles without an account MUST remain valid; a linked account and a
  linked Player profile MUST each be unique.
- **FR-029**: The relationship MUST be explicit and MUST never be created or
  corrected from name, email, date of birth, or other approximate identity
  information.
- **FR-030**: The existing Player Directory profile/edit experience MUST contain
  an Account section showing the linked account or No account linked and, for a
  Head Coach, Link account, Unlink account, and explicit correction/reassignment
  actions. The flow MUST remain inside the existing Player management workflow;
  it MUST NOT add a new top-level page or sidebar destination.
- **FR-031**: Because the repository currently has no frontend user-management
  page exposing Player-role accounts, the Player Directory linking dialog MUST
  provide the canonical Head Coach entry point and use a reusable eligible
  Player-account lookup. If a user-management surface later exposes unlinked
  Player accounts, its Link player profile action MUST call the same capability,
  validation, confirmation, and audit contract.
- **FR-032**: The linking dialog MAY support search, filtering, and advisory
  likely-match suggestions, but the Head Coach MUST explicitly choose the exact
  account/profile pair and confirm before a relationship is changed.
- **FR-033**: The backend linking service MUST validate that the target User
  exists, has the player role, is not linked to another Player profile, that the
  target Player exists, that the Player is not linked to another User, and that
  the authenticated actor is a Head Coach. Database uniqueness and service
  validation MUST both enforce one-to-one behavior.
- **FR-034**: Unlinking MUST require explicit confirmation, MUST preserve both
  records, and MUST not silently overwrite an existing relationship. Reassignment
  MUST be an explicit correction workflow that validates the prior and next
  associations and handles optimistic-concurrency conflicts safely.
- **FR-035**: Assistant Coaches and Players MUST be forbidden from listing
  eligible account-linking targets or creating, removing, or correcting links.
  Player users MUST never claim, change, or remove their own association.
- **FR-036**: Successful link, unlink, and reassignment operations MUST create
  exactly one appropriate Business Audit event in the same successful domain
  transaction. An existing Business Audit action MAY be reused only when it
  accurately describes the mutation; unrelated actions MUST NOT be overloaded
  merely to avoid a new identifier. If no accurate existing action exists, the
  implementation MUST add explicit actions for player account linked, player
  account unlinked, and player account reassigned. Rejected, unauthorized,
  stale, or rolled-back operations MUST NOT create a successful Business Audit
  event. Audit metadata MUST be allowlisted business data and MUST exclude
  passwords, password hashes, tokens, CSRF values, credentials, and
  security-audit details.
- **FR-037**: Player-linking request and response contracts MUST expose only safe
  account/profile information needed by the Head Coach flow and MUST not leak
  password or session data. Normal Player responses MUST not expose another
  user's account details.

#### Match participant domain

- **FR-038**: Match records MUST support exactly one participant structure:
  external, with one academy Team, a nonblank external opponent name, and an
  academy-Team home/away side; or internal, with two different academy Teams
  identified as home and away. A Match MUST always involve at least one academy
  Team.
- **FR-039**: Match create, update, and read contracts MUST expose consistent
  participant information suitable for dashboard projections and future
  performance workflows. External and internal fields MUST be mutually
  exclusive, internal home and away Team IDs MUST differ, and invalid structures
  MUST be rejected before persistence.
- **FR-040**: Match domain changes MUST preserve the existing Match metadata that
  remains meaningful, use the repository's optimistic-concurrency conventions for
  updates, and provide the participant foreign keys, indexes, and constraints
  needed for bounded role-scoped lookup.
- **FR-041**: Future Match and performance capabilities MUST reuse this participant
  representation. This feature MUST NOT add a second Match-to-Team relationship
  solely for dashboard or future performance projections.
- **FR-042**: Match mutation auditing MUST follow the repository's normal
  Business Audit transaction conventions when Match auditing is already supported
  or is extended as part of the mutation work. Dashboard reads MUST never audit.

#### Backend capability, migration, and API boundary

- **FR-043**: The implementation MUST include affected backend domain models,
  schemas, services, routes, authorization dependencies, and tests for Player
  account linking, Match participants, and the role-aware dashboard projection.
  It MUST extend existing service and route patterns rather than create parallel
  identity, team-scope, Calendar, or audit abstractions.
- **FR-043a**: This feature MUST add the backend/domain Match participant model
  changes, schemas, validation, services, API contracts, migrations, and tests
  required to make Match data usable by the dashboard, including external and
  internal participant semantics. It MUST NOT add a Match management page,
  modal, or user-facing create/edit entry workflow; a future Match-management
  feature owns that experience.
- **FR-044**: The dashboard capability MUST enforce role isolation on the server
  for Head Coaches, Assistant Coaches, linked Players, and unlinked Players. A
  frontend-hidden action or field MUST never be the only authorization control.
- **FR-045**: The Player account association and Match participant changes MUST
  include a versioned, reversible-where-practical Alembic migration. The
  migration MUST add nullable unique Player/User association support, the final
  external/internal Match participant representation, foreign keys, uniqueness,
  indexes, and database constraints where practical. Existing Player rows MUST
  remain valid without a linked account. No temporary legacy Match compatibility
  period is required solely for current records because the repository contains
  no meaningful Match data to preserve.
- **FR-046**: The authenticated dashboard response, Player-account-linking
  contracts, and Match create/update/read contracts MUST be represented at the
  repository's established strongly typed OpenAPI-to-TypeScript boundary. Any
  generated TypeScript artifacts MUST have a repeatable drift check, and frontend
  feature code MUST not introduce parallel hand-maintained copies of generated
  response shapes.
- **FR-047**: Dashboard reads and account-linking reads MUST use bounded query
  limits and deterministic ordering. The implementation MUST include practical
  query/performance regression coverage for no N+1 loading, bounded Upcoming
  Events, bounded My Teams, bounded Recent Activity, and role-scoped lookups.

#### UX, operational states, and accessibility

- **FR-048**: The frontend MUST preserve the existing dashboard's visual language
  and proportions from `PRODUCT.md` and `DESIGN.md`: the Disciplined Clubhouse
  tone, cool canvas, flat white shared surfaces, fine boundary lines, deep
  navigation, restrained academy teal, system typography, and no decorative
  analytics or sports-betting treatment.
- **FR-049**: The summary strip MUST remain one shared surface split by dividers;
  Upcoming Events MUST remain the larger left section and the contextual panel
  MUST remain visible for all roles. The layout MUST reflow from 320px through
  desktop without page-level horizontal overflow, inaccessible truncation, or
  layout jumps caused by hidden role sections.
- **FR-050**: The dashboard MUST cover initial loading, populated results, no
  upcoming training, no upcoming Match, no upcoming events, no assigned teams,
  no Player memberships, unlinked Player account, initial failure, retryable
  refresh failure, and partial section failure. Existing populated data MUST
  remain visible during background refresh where that pattern applies.
- **FR-051**: Dashboard and linking controls MUST use existing accessible
  operational patterns: semantic headings and regions, visible focus, keyboard
  operation, live status/error announcements, explicit Retry actions, non-color-
  only state communication, reduced-motion-safe loading, 44px interactive
  targets, and safe focus restoration.
- **FR-052**: The Player account section and linking/correction flow MUST use the
  existing modal/dialog conventions, including modal isolation, Escape handling,
  focus containment, initial focus, focus restoration, internal scrolling on
  narrow viewports, explicit confirmation for destructive or corrective changes,
  and unsaved/error/conflict handling consistent with Player, Teams, Coaches,
  and Calendar workflows. The linking/correction dialog MUST track whether the
  user has unsaved changes. A clean dialog MUST dismiss normally without an
  additional warning. When dirty, a close-control click, Escape key, or a
  backdrop interaction permitted by the existing dialog convention MUST open an
  unsaved-changes confirmation instead of dismissing. Continue Editing MUST
  preserve all entered values and keep the linking/correction dialog open;
  Discard Changes MUST close the dialog, clear transient unsaved state, and
  perform no link, unlink, reassignment, or other save operation. The
  confirmation MUST preserve modal isolation and focus containment; Continue
  Editing returns focus to the initiating dismissal control when focusable (or
  the dialog's initial focus otherwise), and Discard Changes restores focus as a
  normal dialog dismissal.

#### Verification and documentation

- **FR-053**: Backend tests MUST cover nullable unique Player.user_id behavior,
  one-to-one link enforcement, wrong-role rejection, valid/invalid external and
  internal Match structures, internal Team inequality, mixed participant
  rejection, dashboard service projections for all roles, authorization, audit
  behavior, Calendar scope/recurrence/exception semantics, bounded queries,
  deterministic ordering, and the inactive linked Player authentication/session
  invariant including session revocation, logout, login rejection, and
  repository-consistent reactivation behavior. They MUST also verify that
  successful link, unlink, and reassignment mutations emit exactly one
  semantically accurate Business Audit action, using explicit player account
  linked/unlinked/reassigned actions when no accurate existing action exists,
  and that rejected, stale, unauthorized, or rolled-back mutations emit none.
- **FR-054**: Frontend tests MUST cover the unchanged dashboard structure,
  current-user greeting, role-aware actions, dynamic summaries, all role-specific
  panels and empty states, event rows without location, unlinked Player state,
  loading/error/retry/partial-failure behavior, responsive layout, keyboard
  accessibility, visible focus, account-linking modal confirmation/conflict and
  clean/dirty-dismissal behavior, and consistency between rendered Assistant
  Coach actions and the backend permissions of the existing workflows.
- **FR-055**: The feature MUST include at least one Playwright journey covering
  Head Coach, Assistant Coach, and Player dashboard behavior with representative
  training, external Match, internal Match, assignments, memberships, Calendar
  scopes, account linking, and Head Coach Recent Activity. The journey MUST
  verify that unauthorized team, Player, and audit information is not shown.
- **FR-056**: Alembic upgrade/downgrade behavior and an isolated backend
  integration quickstart MUST be covered using the repository's existing
  PostgreSQL/Docker and `test_<spec_num>_quickstart_flow.py` conventions. The
  quickstart MUST validate association persistence, participant invariants,
  role-scoped dashboard data, inactive linked Player session enforcement, and
  rollback/no-audit behavior for failed linking.
- **FR-057**: After implementation and verification, documentation under
  `docs/` MUST describe role-specific dashboard behavior, Player account/profile
  linking, internal versus external Match semantics, dashboard API behavior,
  authorization boundaries, and operational verification. Documentation MUST
  describe implemented behavior rather than planned behavior.

### Key Entities *(include if feature involves data)*

- **User**: An authenticated academy account with one database-authoritative
  role: Head Coach, Assistant Coach, or Player.
- **Player**: An academy cricket profile that may optionally link to exactly one
  Player-role User account while remaining valid without an account.
- **Team**: An academy squad with a name, age group, and current roster count.
- **TeamPlayer**: A Player-to-Team membership used to resolve Player dashboard
  scope and distinct active-player counts.
- **TeamCoach**: A User-to-Team assignment used to resolve Assistant Coach
  dashboard scope.
- **Match**: A dated cricket fixture with exactly one external or internal
  participant structure and explicit home/away semantics.
- **Calendar occurrence**: An effective standalone or recurring Practice/Game/
  Miscellaneous event instance after recurrence and occurrence exceptions are
  applied in academy-local time.
- **Business Audit Event**: An immutable record of a successful business-domain
  mutation, separate from authentication/security audit data.
- **Dashboard projection**: A bounded, non-persisted role-specific operational
  summary containing summary slots, Upcoming Events, and the role's contextual
  panel.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the completed feature test suite, 100% of dashboard summary,
  event, team, and activity values are sourced from current seeded records or
  explicit empty/error states; none display the current hardcoded example values.
- **SC-002**: Role-isolation tests pass for 100% of Head Coach, Assistant Coach,
  linked Player, and unlinked Player scenarios, with zero returned records from
  an unrelated team, Player profile, age-group scope, or Business Audit feed.
- **SC-003**: A Head Coach can link an eligible account from the existing Player
  Directory profile flow in no more than three intentional interaction stages:
  open Account, choose the exact account, and confirm; unlinking and correction
  require an explicit confirmation stage.
- **SC-004**: 100% of valid external/internal Match fixtures project to the
  correct eligible roles, while every invalid participant combination is rejected
  before persistence and produces no successful business-audit record.
- **SC-005**: Seeded dashboard projections demonstrate fixed, bounded loading
  behavior as the number of Teams, Players, memberships, Calendar records, and
  audit events grows; query regression tests show no N+1 loading and enforce the
  agreed event, team, and activity bounds.
- **SC-006**: In the documented local regression fixture, the 95th percentile
  of normal populated dashboard opens MUST be at most 2.0 seconds, without
  defining a production SLA or requiring background aggregation. The fixed
  fixture is an authenticated Head Coach with a current name, three populated
  summary slots, a next Practice, a next Match, five Upcoming Events, and four
  Recent Academy Activity entries. After fixture and authentication setup, run
  ten unmeasured warm-up opens followed by 100 sequential measured opens. For
  each measured open, start the timer immediately before navigating to the
  dashboard and stop when the greeting, all three summary slots, seeded Upcoming
  Events, and the populated contextual panel are visible. Sort the 100 measured
  durations ascending and use the 95th value (nearest-rank p95) as the result;
  the regression check MUST fail when that value exceeds 2.0 seconds. This is a
  local deterministic regression check and does not represent production
  network performance.
- **SC-007**: Responsive and keyboard verification passes at 320px, tablet, and
  desktop widths with zero page-level horizontal overflow, visible focus for all
  interactive controls, and no status meaning conveyed by color alone.
- **SC-008**: For every tested partial-failure scenario, unrelated populated
  sections remain usable and the failed section exposes a clear retry path; no
  failed live request restores fabricated dashboard data.
- **SC-009**: Dashboard viewing, loading, refreshing, and retrying create zero
  Business Audit events. Every successful link, unlink, and reassignment creates
  exactly one appropriate business event, and every rejected or rolled-back
  association mutation creates none.
- **SC-010**: The new migration applies cleanly to a database at revision `012`,
  preserves existing Player rows without accounts, supports the final Match
  invariants, and downgrades according to the repository's reversible migration
  convention.

## Assumptions

- The existing authentication system remains the source of the current User's
  name and database-authoritative role; JWT role claims are not trusted for
  dashboard scope.
- "Upcoming" uses the academy-local `America/Los_Angeles` clock. Calendar
  occurrences use their existing effective recurrence/exception semantics, and
  date-only Match records with today's academy date are eligible for the Next
  Match slot.
- The current Match model remains date-based unless planning identifies an
  already-supported time field; the dashboard will not invent a Match time that
  the source record does not contain.
- Existing TeamPlayer rows represent current memberships because the repository
  has no membership end-date model. Inactive Player profiles are not treated as
  current active dashboard memberships or active-player counts.
- The dashboard uses practical bounds consistent with existing workflows: at
  most five Upcoming Events, at most twelve My Teams entries, and at most four
  Recent Academy Activity events. The exact response constants may be finalized
  during planning without changing the user-visible bounded behavior.
- Existing Calendar age groups (`J`, `U11`, `U13`, `U15`) are the complete set
  for this release, and an age-group event is relevant when its scope intersects
  at least one assigned/current Team age group.
- Player-role User accounts already exist before linking. Account creation,
  registration, invitations, onboarding, verification, and Player self-service
  claiming remain out of scope.
- The Player Directory is the only current frontend account/profile-linking
  entry point because repository review found no frontend user-management page;
  no new sidebar destination is required.
- During planning, the repository's actual Assistant Coach backend permissions
  and existing workflows will determine whether any Assistant Coach quick
  action is suitable; this feature does not expand those permissions.
- Existing Head Coach, Assistant Coach, Player, Teams, Coaches Portal, Calendar,
  Audit Log, modal, toast, loading, retry, and optimistic-concurrency patterns
  remain the source of interaction behavior and error copy.
- Linked Player-profile deactivation reuses the repository's existing
  deactivated Assistant Coach account/session enforcement and reactivation
  conventions; this feature does not introduce a separate inactive-Player
  authenticated state or alternate session lifecycle.
- OpenAPI-generated TypeScript contracts and drift checks are the authoritative
  frontend/backend boundary for newly added dashboard, account-linking, and
  Match shapes; no untyped or parallel API model is acceptable.
- This release does not add customizable widgets, analytics, notifications,
  background aggregation, bulk linking, Player performance cards, or a separate
  Match-management redesign.
