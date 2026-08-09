# Feature Specification: Academy Data Quality Checks and Remediation

**Feature Branch**: `010-academy-data-quality`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Part 10: Academy Data Quality Checks and Remediation"

## Clarifications

### Session 2026-08-08

- Q: What is the expected Head Coach assignment and remediation behavior? → A: The academy has exactly one active Head Coach assigned to every team; Head Coach integrity failures are Critical/manual-review findings, while ordinary assignment remediation applies only to inactive Assistant Coaches.
- Q: How should performance and usability success criteria be verified? → A: Use automated bounded-pagination, query-efficiency, N+1-regression, realistic-seeded-dataset, responsive, accessibility, and Playwright coverage; treat scan latency as a regression signal rather than a fixed SLA.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review current academy health (Priority: P1)

As a Head Coach, I want one place to inspect current academy data-quality issues so that I can identify operational problems before they affect player and team workflows.

**Why this priority**: The central scan and explanation are the core value of the feature. They give the academy a reliable starting point even when an issue spans more than one existing domain workflow.

**Independent Test**: Seed a known mixture of healthy and unhealthy player, team, roster, coach, and calendar records; sign in as a Head Coach; open Data Quality; verify the severity summary, domain totals, and finding details match the current database state.

**Acceptance Scenarios**:

1. **Given** the academy has Critical, Warning, and Info findings, **When** a Head Coach opens Data Quality, **Then** the page shows total findings and separate counts for each severity, with useful domain counts where findings exist.
2. **Given** a finding is present, **When** the Head Coach reads it, **Then** the page identifies the affected entity, explains the condition in plain language, explains why it matters, and recommends a next action.
3. **Given** the academy is healthy, **When** the Head Coach opens Data Quality, **Then** the page announces “No data quality issues found” with positive supporting text rather than showing a generic empty table.
4. **Given** a finding was resolved in an existing domain workflow, **When** the Head Coach refreshes or revisits Data Quality, **Then** a new evaluation no longer returns that finding.
5. **Given** the sole Head Coach is active and assigned to every team, **When** Data Quality evaluates the academy, **Then** no Head Coach integrity finding is emitted; **given** that invariant is broken, **then** a separate Critical manual-review finding identifies the integrity condition without offering removal of the Head Coach from a team.

### User Story 2 - Filter and navigate to an existing fix workflow (Priority: P1)

As a Head Coach, I want to narrow findings by severity, domain, and rule and open the relevant existing workflow so that I can decide how to correct issues without using a database administration console.

**Why this priority**: Findings are useful only when a coach can quickly understand which work matters and where to perform it. Existing domain screens remain the source of truth for decisions that require human judgment.

**Independent Test**: Render the page with multiple findings, change each filter, verify only matching findings remain, verify the filtered no-results state, and activate a navigation control for player, team, coach, roster, and calendar findings.

**Acceptance Scenarios**:

1. **Given** findings from several severities and domains, **When** the Head Coach selects a severity, domain, or rule filter, **Then** the visible results and result-status text update to the matching set without losing the global summary.
2. **Given** a filter combination has no matches, **When** the Head Coach applies it, **Then** the page shows “No findings match these filters” and offers a clear-filters action.
3. **Given** a finding requires judgment, **When** the Head Coach chooses Navigate to Fix, **Then** the application opens the relevant existing Player Directory, Teams, Coaches Portal, or Calendar workflow and leaves the finding’s entity label visible long enough to identify the record.
4. **Given** a finding concerns a team without a coach or a coach assignment, **When** the Head Coach chooses Navigate to Fix, **Then** the application opens the existing Coaches Portal assignment workflow rather than choosing a coach automatically.

### User Story 3 - Apply one safe direct remediation (Priority: P1)

As a Head Coach, I want to apply a small set of unambiguous corrections from a finding so that I can resolve low-risk integrity issues without re-entering data manually.

**Why this priority**: A narrow direct action can remove avoidable operational friction, but it must preserve the protections of the existing domain workflows.

**Independent Test**: Seed one supported direct-remediation condition, request the action with the current version and required confirmation, verify the normal domain state and business audit event, then evaluate Data Quality again and verify the finding is gone.

**Acceptance Scenarios**:

1. **Given** a roster has an ordering defect but otherwise has a valid 7–15 active-player membership set, **When** the Head Coach confirms Normalize roster order, **Then** the membership positions become contiguous `1..N` in the existing roster order, one normal roster-reorder mutation is recorded, and the ordering findings disappear on re-evaluation.
2. **Given** a roster contains an inactive player and removing that one membership leaves a valid 7–15 active-player roster, **When** the Head Coach confirms Remove inactive player, **Then** only that membership is removed, one normal roster-removal mutation is recorded, and the inactive-roster finding disappears.
3. **Given** an inactive Assistant Coach has a specific team assignment, **When** the Head Coach confirms Remove inactive coach assignment, **Then** only the selected assignment is removed, the Assistant Coach’s other assignments remain unchanged, and the existing coach-assignment audit action is recorded once; **given** the assignment belongs to the Head Coach, **then** no removal action is offered and the condition is routed for manual review.
4. **Given** a finding is no longer current or its expected version is stale, **When** the Head Coach submits a direct remediation, **Then** the application rejects the stale request without a partial change, explains that the findings were updated, and offers to refresh.
5. **Given** a removal action is available, **When** the Head Coach opens it, **Then** an accessible confirmation dialog names the affected relationship and requires an explicit confirmation before the mutation.

### User Story 4 - Preserve role boundaries (Priority: P1)

As a Head Coach, I want Data Quality to be limited to Head Coaches so that quality findings and remediation controls are not exposed to Assistant Coaches or Players.

**Why this priority**: The feature can expose academy-wide operational data and change relationships. It must follow the existing default-deny authorization behavior.

**Independent Test**: Sign in as a Head Coach, Assistant Coach, and Player; verify navigation and direct route behavior in the browser and verify each backend capability returns the application’s existing 403 response for non-Head-Coach roles.

**Acceptance Scenarios**:

1. **Given** the authenticated user is a Head Coach, **When** the application shell renders, **Then** Data Quality appears directly below Audit Log in the sidebar and `/data-quality` is available.
2. **Given** the authenticated user is an Assistant Coach or Player, **When** the application shell renders, **Then** the Data Quality item is absent.
3. **Given** an Assistant Coach or Player requests `/data-quality` directly, **When** the route is evaluated, **Then** the existing 403 Forbidden experience is rendered and the findings API is not requested.
4. **Given** an Assistant Coach or Player calls a Data Quality read or remediation capability directly, **When** authorization runs, **Then** the response is HTTP 403 with the application’s existing permission behavior; any authorization-denial security audit remains separate from the Business Audit Log.

### User Story 5 - Recover from normal operational states (Priority: P2)

As a Head Coach, I want Data Quality to remain understandable while it loads, refreshes, or encounters a recoverable error so that a temporary problem does not hide useful existing results.

**Why this priority**: The product’s operational workflows are expected to feel immediate and dependable. Clear state handling prevents a quality scan from becoming another source of uncertainty.

**Independent Test**: Exercise initial loading, background refresh, initial failure, retry success, background failure with previous results, filtered no-results, remediation success, and remediation failure in frontend tests at narrow and desktop widths.

**Acceptance Scenarios**:

1. **Given** the first scan is pending, **When** the page renders, **Then** it shows a structure-preserving loading state and one accessible status announcement.
2. **Given** a populated result is being refreshed, **When** the refresh is pending, **Then** previous findings remain visible, the results region exposes busy state, and the page does not flash a generic empty state.
3. **Given** the first scan fails, **When** the page renders, **Then** it shows a non-sensitive error message and a keyboard-operable Retry control.
4. **Given** a background refresh fails after a result is visible, **When** the error is shown, **Then** the prior result remains visible and the Head Coach can retry.
5. **Given** a remediation succeeds or fails, **When** the request completes, **Then** the page announces a success or recovery message, refreshes the current findings when appropriate, and never implies success for an uncommitted mutation.

### Edge Cases

- A finding can be resolved between the scan and a navigation or remediation click; navigation still works, while direct remediation is re-evaluated and safely rejected when its precondition no longer holds.
- Multiple findings may affect the same entity. The page keeps each rule identifiable, but one supported direct action must not silently apply to other entities or findings.
- A normalized duplicate-player group can contain more than two records. It is represented as one deterministic group finding with a primary affected ID and related IDs, not as repeated pairwise duplicates.
- Roster ordering defects can overlap. More-specific non-positive, duplicate, and gap findings are emitted deterministically; the general non-contiguous rule is emitted only when it identifies a remaining ordering defect, preventing redundant copies of the same explanation.
- A team without a coach is represented by one canonical team finding. It is not emitted again as a duplicate Coach finding.
- A team can have fewer than 7 or more than 15 memberships because the legacy add-member path and historical data are not protected by the complete-roster validation used by team create/update.
- An inactive player can remain in a roster after a later player-status change; this is an intended lifecycle-quality check, not a foreign-key failure. Each player/team membership is its own actionable finding so one direct removal cannot become an implicit bulk action.
- An inactive Assistant Coach can retain team assignments because account deactivation does not currently remove memberships; the quality feature must not silently reactivate the coach or alter unrelated assignments. Each Assistant Coach/team assignment is its own actionable finding. An inactive Head Coach is handled only by the separate sole Head Coach integrity rule and is never an ordinary assignment-removal target.
- The academy is expected to have exactly one active Head Coach assigned to every team. If the sole Head Coach becomes inactive, loses one or more expected team assignments, or the unique Head Coach invariant cannot be established, Data Quality emits a separate Critical manual-review finding. The feature must not remove the Head Coach from a team or infer a replacement assignment.
- A user with the Player role can appear in a team-coach join row in legacy or manually altered data even though normal coach workflows only expose Head Coach and Assistant Coach accounts.
- Empty calendar scope collections are currently interpreted by the calendar projection as All Academy, while invalid scope-row shapes are protected by database checks. The initial catalogue therefore does not label an empty collection as an audience error.
- A recurring series can contain an end date before its event start because the database shape constraint does not compare the two dates; this can break recurrence projection and is a meaningful calendar finding.
- An occurrence exception can remain persisted after its original date no longer belongs to its series rule. Existing calendar series-edit behavior already knows how to confirmation-gate removal of such exceptions; Data Quality must route to that workflow rather than deleting it automatically.
- Calendar findings must retain existing America/Los_Angeles academy-local date and daylight-saving behavior.
- Missing optional biography and player-metadata values are not findings.
- Basic foreign-key failures, event-type values, timed/all-day shape, recurrence field shape, and duplicate occurrence exceptions are not repeated as quality findings because the current schema already protects them.
- A page-size or page-number request outside the supported bounds is rejected with the existing request-validation behavior; the service never returns an unbounded result collection.

## Requirements *(mandatory)*

### Functional Requirements

#### Access, navigation, and authorization

- **FR-001**: The application MUST expose a Head Coach-only Data Quality page at `/data-quality`.
- **FR-002**: The authenticated application sidebar MUST show a `Data Quality` entry directly under `Audit Log` only for Head Coaches.
- **FR-003**: Assistant Coaches and Players MUST NOT see the Data Quality sidebar entry.
- **FR-004**: Direct frontend navigation to `/data-quality` by an Assistant Coach or Player MUST use the existing role-protected 403 Forbidden experience and MUST avoid loading findings.
- **FR-005**: Every Data Quality backend read and remediation capability MUST require an authenticated Head Coach and MUST return HTTP 403 for authenticated Assistant Coaches and Players using the application’s existing authorization behavior.

#### On-demand evaluation and finding contract

- **FR-006**: The system MUST evaluate the current database state on demand when Data Quality is requested and MUST NOT persist findings, scan history, schedules, queues, notifications, or background scan state in the initial release.
- **FR-007**: The evaluation MUST be implemented as a reusable registry of deterministic, independently testable rules. Adding or removing a rule MUST NOT change the stable identifier or meaning of another rule.
- **FR-008**: Every finding MUST provide a stable `rule_id`, one of `Critical`, `Warning`, or `Info` severity values, a domain/category, affected entity type, affected entity ID when applicable, human-readable entity label, concise issue title, plain-language explanation, recommended remediation, and whether a direct remediation is supported.
- **FR-009**: Findings involving multiple records MUST additionally expose deterministic related entity IDs and labels as needed to explain the relationship. Finding identity MUST be derived from the rule and sorted affected identifiers rather than from request order or scan order.
- **FR-010**: A subsequent evaluation MUST omit a finding once its underlying condition is corrected. A read or scan MUST NOT create a Business Audit Log event.
- **FR-011**: Findings MUST be ordered deterministically by severity (`Critical`, then `Warning`, then `Info`), domain/category, entity label, rule ID, and stable entity or related-entity identifier. Case-insensitive comparisons MUST use the repository’s established normalized comparison behavior, with stable ID tie-breakers.
- **FR-012**: Quality checks MUST use efficient bounded queries and batched related-record reads, avoid N+1 entity lookups, and avoid loading an entire table into application memory when an equivalent aggregate, grouping, or join can be evaluated efficiently. Responses MUST be paginated and bounded; the default page size is 20 and the maximum page size is 100.

#### Initial rule catalogue

The following rules form the initial allowlisted catalogue. Rule IDs are stable API identifiers. A rule is emitted at most once per affected entity or normalized identity group unless the condition explicitly describes a separate rule.

| Rule ID | Domain | Finding condition | Severity | Default remediation path |
| --- | --- | --- | --- | --- |
| `player.active_unassigned` | Players | An active player has no membership in any team roster. | Warning | Navigate to the Teams workflow to choose an appropriate roster. |
| `player.inactive_rostered` | Players | An inactive player remains in one team roster. One finding is emitted per player/team membership so the affected relationship is unambiguous. | Warning | Direct removal only when the selected team remains a valid 7–15 active-player roster; otherwise navigate to Teams. |
| `player.normalized_identity_duplicate` | Players | Two or more player records have equivalent first name, last name, and date of birth after Unicode normalization, trimming, whitespace collapsing, and case-folding, while bypassing the existing exact uniqueness comparison. | Warning | Navigate to Players for human review; never merge or choose a canonical record automatically. |
| `team.roster_below_minimum` | Teams | A team has fewer than 7 roster memberships. | Warning | Navigate to Teams to select the correct active players. |
| `team.roster_above_maximum` | Teams | A team has more than 15 roster memberships. | Warning | Navigate to Teams to decide which players belong. |
| `roster.order_non_positive` | Rosters | A roster membership has a zero or negative persisted position. | Warning | Direct Normalize roster order when direct-action preconditions hold; otherwise navigate to Teams. |
| `roster.order_duplicate` | Rosters | Two or more memberships in one team share a persisted position. | Warning | Direct Normalize roster order when direct-action preconditions hold; otherwise navigate to Teams. |
| `roster.order_gap` | Rosters | Positive roster positions have a missing position between the minimum and maximum. | Warning | Direct Normalize roster order when direct-action preconditions hold; otherwise navigate to Teams. |
| `roster.order_non_contiguous` | Rosters | After excluding the more-specific non-positive, duplicate, and gap conditions, the ordered positions still do not equal contiguous `1..N`. | Warning | Direct Normalize roster order when direct-action preconditions hold; otherwise navigate to Teams. |
| `team.normalized_name_conflict` | Teams | Two teams in the same age group have names that conflict after the existing `lower(trim(name))` comparison, despite bypassing the normal service check. | Warning | Navigate to Teams for a human naming decision; never rename automatically. |
| `team.no_assigned_coach` | Teams | A team has no team-coach assignment. This is the canonical finding for the condition and is not duplicated under Coaches. | Warning | Navigate to the Coaches assignment workflow. |
| `coach.sole_head_coach_integrity` | Coaches | The academy cannot demonstrate exactly one active Head Coach assigned to every current team: the sole Head Coach is inactive, is missing one or more expected team assignments, or the unique Head Coach invariant cannot be established. | Critical | Manual review only; no direct remediation or Head Coach removal action. |
| `coach.inactive_assigned` | Coaches | An inactive Assistant Coach remains assigned to one team. One finding is emitted per Assistant Coach/team assignment. | Warning | Direct removal of one selected Assistant Coach assignment when supported; otherwise navigate to Coaches. |
| `coach.active_assistant_unassigned` | Coaches | An active Assistant Coach has no team assignments. | Info | Navigate to Coaches for a Head Coach to decide whether to assign a team. |
| `coach.assignment_invalid_role` | Coaches | A team-coach assignment references a user whose current role is neither Head Coach nor Assistant Coach. | Critical | Review-only finding; no automatic role change or unverified deletion. Navigate to the existing coach/team administration workflow when it can safely resolve the record. |
| `calendar.recurrence_end_before_start` | Calendar | A recurring series has an end date earlier than its owning event’s first date, a business-level inconsistency not protected by the current database shape checks. | Critical | Navigate to Calendar and choose a valid recurrence termination. |
| `calendar.stale_occurrence_exception` | Calendar | An occurrence exception’s original date no longer corresponds to an occurrence generated by its current recurrence definition. | Warning | Navigate to Calendar and use its existing confirmation-aware series workflow. |

- **FR-013**: The rule evaluator MUST classify a team with no coach only under `team.no_assigned_coach`; the equivalent condition MUST NOT produce a second coach-domain finding.
- **FR-014**: The rule evaluator MUST NOT report optional biography, arbitrary player metadata, intentionally permitted active Assistant Coach records without teams, or any condition already structurally prevented by existing constraints unless it is part of a separate cross-record rule above. The expected active, academy-wide Head Coach assignment state is evaluated only by `coach.sole_head_coach_integrity`; a healthy Head Coach assigned to all teams MUST NOT be reported as an ordinary coach-assignment finding.
- **FR-015**: Severity MUST reflect operational impact. Critical MUST be reserved for a material business invariant or a condition capable of materially incorrect application behavior; Warning MUST represent a review-worthy inconsistency; Info MUST represent incomplete or suboptimal operational data that is not immediately harmful. `coach.sole_head_coach_integrity` MUST be Critical and manual-review-only, and MUST NOT offer ordinary assignment removal.

#### Finding retrieval and filtering

- **FR-016**: The backend MUST provide a bounded, Head Coach-only capability to retrieve current findings with page number, page size, severity, domain/category, and rule filters.
- **FR-017**: The findings response MUST include the filtered findings, stable pagination metadata, filtered total, and a current unfiltered summary containing total findings, Critical count, Warning count, Info count, and counts by Players, Teams, Rosters, Coaches, and Calendar where applicable.
- **FR-018**: Severity, domain/category, and rule filters MUST be allowlisted and validated. Invalid values, invalid page values, and page sizes over 100 MUST receive request-validation errors and MUST NOT execute arbitrary rule names or queries.
- **FR-019**: The response MUST remain bounded even when the academy has more findings than one page. The UI MUST expose pagination or an equivalent bounded navigation control when additional findings exist.

#### Remediation and domain integrity

- **FR-020**: The backend MUST expose only explicitly supported, allowlisted direct remediation actions. It MUST NOT expose arbitrary SQL, arbitrary rule execution, generic entity editing, bulk remediation, or a mutation that accepts an unvalidated field map.
- **FR-021**: The initial direct-remediation allowlist MUST be limited to Normalize roster order, Remove inactive player from one roster, and Remove one inactive Assistant Coach/team assignment. The implementation MAY decline an action when its current preconditions are not satisfied and MUST never include a Head Coach assignment in the removal allowlist.
- **FR-022**: Normalize roster order MUST change only the selected team’s positions to contiguous `1..N`, preserve the existing current roster membership and its deterministic order (persisted position ascending, then player ID ascending), require a current team version, and be available directly only when the roster has 7–15 distinct active players and the normal team domain validation can remain satisfied.
- **FR-023**: Remove inactive player MUST identify exactly one current inactive membership, require explicit confirmation and a current team version, leave at least 7 and at most 15 active players, and remove no other membership.
- **FR-024**: Remove inactive coach-team assignment MUST identify exactly one current assignment for an inactive Assistant Coach, require explicit confirmation and the current coach version, preserve every other assignment, and never reactivate or change the coach role. A Head Coach assignment MUST be rejected or remain manual-review-only, even if the Head Coach is inactive.
- **FR-025**: Every direct remediation MUST re-evaluate the referenced finding and its preconditions inside the normal domain mutation transaction immediately before changing data. If the finding is resolved, the target is missing, the role/status/membership changed, or the expected version is stale, the request MUST be rejected or re-evaluated without a partial change and MUST return a safe conflict/recovery response.
- **FR-026**: All direct remediation MUST reuse the existing Player, Team/Roster, Coach assignment, optimistic-concurrency, authorization, validation, and transaction behavior. A Data Quality route MUST NOT mutate join rows or domain fields directly outside those domain services.
- **FR-027**: No remediation MUST run automatically as a side effect of scanning or viewing. There MUST be no bulk action in the initial release. Any removal or relationship change MUST require explicit user confirmation.
- **FR-028**: One remediation request MUST produce one normal business mutation transaction. A failure MUST roll back the domain change and MUST NOT leave an audit event for an uncommitted mutation.
- **FR-029**: After a successful remediation, the page MUST refresh or re-evaluate current findings so resolved findings disappear and remaining findings reflect the latest state.

#### Business Audit Log behavior

- **FR-030**: Data Quality scans, summary retrieval, filter changes, and finding views MUST NOT create Business Audit Log events.
- **FR-031**: A successful direct roster-order normalization MUST reuse the existing `roster.reordered` business action; inactive-player removal MUST reuse `roster.removed`; inactive Assistant Coach-assignment removal MUST reuse `coach.team_assignments_updated`. No Head Coach removal remediation or corresponding data-quality audit action is permitted.
- **FR-032**: A direct remediation MUST produce the same single audit event the corresponding normal domain workflow would produce, with the authenticated Head Coach actor and request metadata, and MUST NOT add a second generic “data quality remediation” event. A new action identifier is permitted only if the existing catalogue cannot accurately describe a supported mutation.
- **FR-033**: The authentication/security audit system MUST remain separate. Existing authorization-denial security events MUST NOT be surfaced or duplicated as Business Audit Log activity.

#### Data Quality page behavior and accessibility

- **FR-034**: The page MUST present one shared summary band for total, Critical, Warning, and Info counts and may include grouped domain counts without creating a detached hero-card grid. Summary labels MUST remain understandable without color.
- **FR-035**: The page MUST provide keyboard-operable severity, domain, and rule filters; clear filters; deterministic finding navigation; and direct-remediation controls with visible focus states and at least the project’s existing touch-friendly target size.
- **FR-036**: Each finding MUST visibly communicate its severity with text or an equivalent non-color indicator, issue title, affected entity label/type, explanation, recommended action, and either Navigate to Fix or the supported direct-remediation action.
- **FR-037**: The page MUST provide distinct initial loading, initial error with Retry, background-refresh, healthy no-issues, filtered no-results, unauthorized, remediation-success, remediation-failure, and stale-data recovery states using the application’s established accessible status and toast patterns.
- **FR-038**: Confirmation dialogs MUST use the application’s existing modal convention, including semantic labelling, focus containment, Escape handling, focus restoration, clear cancel/confirm actions, and a status announcement while submitting.
- **FR-039**: The page MUST follow `PRODUCT.md` and `DESIGN.md`: direct and plain operational copy; system typography; cool canvas and white surfaces; restrained Academy Teal for focus, wayfinding, and non-text accents; flat containers with boundary lines; 44px-class controls; semantic structure; visible focus; reduced-motion-safe loading; and no color-only status communication.
- **FR-040**: The layout, filters, finding content, dialogs, and controls MUST reflow or stack without page-level horizontal overflow and remain usable at the project-supported 320px viewport through desktop widths.

#### Verification

- **FR-041**: Backend unit tests MUST cover every rule above, including a healthy exactly-one active Head Coach assigned to all teams, inactive or incompletely assigned sole Head Coach integrity failures, and the absence of `coach.inactive_assigned` findings for Head Coaches. Tests MUST also cover healthy data, unhealthy data, severity, serialization, deterministic ordering, normalized comparison, empty/optional states that are intentionally permitted, and omission of database-guaranteed conditions.
- **FR-042**: Backend route tests MUST cover Head Coach access; Assistant Coach and Player HTTP 403 responses; summary counts; severity/domain/rule filtering; healthy empty responses; multiple findings; deterministic ordering; validation errors; and bounded pagination.
- **FR-043**: Remediation integration tests MUST verify successful underlying correction for inactive Assistant Coach assignments, disappearance on re-evaluation, retained domain validation, stale-version rejection, explicit destructive confirmation, rejection or manual-review behavior for Head Coach assignments, the correct existing Business Audit Log event, rollback on failure, and absence of duplicate audit events.
- **FR-044**: Frontend tests MUST cover Head Coach-only sidebar visibility, the entry’s position directly below Audit Log, route protection, summary rendering, all filters, finding rendering, loading, healthy and filtered empty states, error/retry, navigation, confirmation, success refresh, failure recovery, responsive reflow, and keyboard accessibility.
- **FR-045**: The feature MUST include at least one Playwright journey that seeds or creates multiple known issues, including an inactive Assistant Coach assignment, signs in as a Head Coach, opens Data Quality from the sidebar, verifies summary counts, filters findings, reviews an entity, remediates one supported issue, confirms that finding disappears, verifies the underlying domain state, verifies the corresponding Business Audit Log event, and verifies Assistant Coach and Player denial. Where the fixture establishes a broken sole Head Coach invariant, the journey MUST verify the Critical manual-review presentation and absence of a Head Coach removal action.

### Key Entities *(include if feature involves data)*

- **Quality rule**: A stable, deterministic definition of one current academy-domain condition, including its severity, category, explanation, and remediation policy. Rules are registered and versioned by stable identifier but are not user-defined.
- **Data-quality finding**: A non-persisted representation of one rule violation against the current database state. It contains the affected entity identity and user-facing explanation, plus related identities when the condition spans records.
- **Quality summary**: Current aggregate counts for all findings and each severity/domain grouping, calculated from the same on-demand evaluation as the findings response.
- **Remediation command**: A typed, allowlisted request describing one supported correction, its finding identity, expected entity version, and explicit confirmation. It is not a generic entity-editing contract.
- **Existing academy records**: Players, teams, team-player roster memberships, users/coaches, team-coach assignments, calendar events, recurrence series, and occurrence exceptions that supply the state being evaluated.
- **Business Audit Event**: The existing immutable record produced only when a successful remediation changes academy data through a normal domain mutation action.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Automated backend evaluation and route tests demonstrate bounded retrieval: the default page size is 20, the maximum page size is 100, pagination metadata and filtered totals remain consistent, and no response exceeds the supported maximum.
- **SC-002**: For every initial rule, automated healthy and unhealthy fixtures produce the expected finding set, severity, affected identity, and deterministic order across repeated evaluations of unchanged data, including the healthy sole-Head-Coach state and Critical manual-review behavior for a broken sole-Head-Coach invariant.
- **SC-003**: Automated query and regression coverage verifies that applicable rules use efficient bounded access—such as joins, aggregates, grouping, or batched related-record reads where appropriate—and do not introduce N+1 entity lookups. Representative seeded datasets are used where practical; repeated scans record latency and stable result behavior as regression signals, without imposing a fixed production SLA or requiring dedicated load-testing infrastructure.
- **SC-004**: 100% of authenticated Assistant Coach and Player attempts to access Data Quality return the existing forbidden experience in the browser and HTTP 403 from each protected backend capability, with no Business Audit Log event created by the read attempt.
- **SC-005**: 100% of supported direct-remediation acceptance tests require explicit confirmation, reject stale state without a partial write, create exactly one correct existing business audit event on success, and remove the resolved finding on the next evaluation.
- **SC-006**: Head Coaches can identify the affected entity, understand why the issue matters, and reach the appropriate existing fix workflow from every initial finding type without encountering an unbounded result view or generic database-editor control.
- **SC-007**: Automated frontend and Playwright coverage at 320px, 768px, and desktop viewport widths demonstrates that Data Quality content remains horizontally contained, controls remain keyboard operable with visible focus, loading/error/empty/remediation states are announced through established patterns, and severity remains understandable without relying on color.

## Assumptions

- Existing authentication is the source of truth for the current user and role. The existing `require_role(HEAD_COACH)` behavior, frontend `HeadCoachRoute` pattern, Forbidden page, session handling, and authorization-denial security audit behavior remain in use.
- The feature adds no persisted finding tables or finding history. It may add domain-service capabilities needed for the three allowlisted direct remediations, but it does not create a parallel mutation layer or require a finding-state migration.
- Existing domain rules remain authoritative: team create/update accepts 7–15 distinct active players; team names are compared as `lower(trim(name))` within age group; exact player uniqueness remains first name, last name, and date of birth; coach assignment edits normally target active Head Coach or Assistant Coach accounts; the academy has exactly one Head Coach expected to remain active and assigned to every team, while ordinary coach-assignment remediation applies only to inactive Assistant Coaches. Head Coach team-assignment behavior remains structurally distinct from Assistant Coach assignment behavior and is never normalized through ordinary assignment removal; calendar recurrence/timezone behavior remains academy-local.
- Player identity normalization for duplicate detection is limited to Unicode normalization, trimming, collapsing runs of whitespace, and case-folding of first and last names; date of birth is compared as the existing calendar date. It does not infer nicknames, transliterations, or likely human identity.
- An empty persisted calendar scope collection is not independently actionable under current product semantics because the calendar projection treats it as All Academy. A future change to that semantic can add a separate rule without changing the meaning of the initial rule IDs.
- Existing frontend directories are list-and-modal workflows rather than entity-specific URL pages. Navigate to Fix therefore lands on the relevant existing workflow in v1; it does not invent a second edit form or promise a new deep-link selection contract.
- The Business Audit Log remains append-only and immutable. Successful remediation events use the existing action vocabulary and are visible through the existing Head Coach-only Audit Log page.
- Match, performance, player-statistics, authentication-health, infrastructure-health, notifications, scheduled scans, AI/probabilistic detection, custom rules, automatic remediation, bulk remediation, and arbitrary database editing remain out of scope.
- The feature’s implementation and test plan will follow the repository’s existing backend unit/route/integration conventions, frontend Vitest conventions, and Playwright mock/fixture conventions. The implementation phase will also add the required post-implementation feature documentation under `docs/`.
