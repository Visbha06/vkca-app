# Final Implementation Brief: Player Directory and Details Modal

Status: approved and refined. No code changes are included.

## Objective

Support both known-player lookup and roster browsing through server-side name search, compact information-dense cards, and a player-details modal that follows the same
information hierarchy.

Preserve the sidebar, application shell, existing API behavior when search is absent, pagination, mutation flows, and role gating.

## Revised toolbar

Keep the page header and coach-only outlined Add Player action.

Below it, provide:

1. Search players — flexible-width field
2. Filter by team — existing native select
3. Result count — quiet supporting text

Desktop places search and team filter beside each other. Mobile stacks search, filter, and count.

### Search behavior

Add an optional server-side search list parameter:

- Omit it when the trimmed query is empty.
- Match partial first names and last names case-insensitively.
- Support partial combined full-name matching where the existing query layer can implement it cleanly.
- Combine search and team filtering using AND logic.
- Apply filtering before pagination.
- Reset to page 1 when either control changes.
- Debounce requests by approximately 250–300ms.
- Cancel stale requests with the existing AbortController pattern.

### Fetching behavior

- Keep existing results visible during the debounce period.
- Keep existing results visible during background fetching.
- Mark the results region aria-busy="true" while fetching.
- Replace results only after the latest request completes.
- Use skeleton cards for initial loading or when no previous result set exists.
- Do not replace populated results with skeletons after every search request.
- If a background request fails, retain the previous results and show a non-destructive error with Retry.
- Use a full error state only when no previous results exist.

### Count copy

The domain model includes is_active, and the current directory represents active players, so “active players” remains valid where that status is meaningful.

Recommended copy:

- Unfiltered directory: “24 active players”
- Search/filter result: “3 players found”
- Empty result: “0 players found”

Avoid unnecessarily repeating “active” in search-result messaging.

## Player-card anatomy

Retain a responsive card grid, reducing card height to approximately 128–152px.

### Identity row

- 40–44px generated initials avatar
- Player name as the strongest text
- Team membership as supporting text
- Restrained trailing details cue

### Profile row

- Player-type badge
- Role-aware cricket-style summary

### Supporting row

- Date of birth
- Use an existing age-group field only if one becomes available through the existing model
- Do not infer academy age groups without domain rules

### Initials avatars

- First-name initial plus last-name initial
- One usable initial when only one name segment exists
- Neutral fallback when no usable initial exists
- One consistent academy-teal treatment
- Decorative to assistive technology; the visible name remains authoritative

### Team display

For multiple teams:

- Use an existing stable or domain-defined team order.
- Preserve API order only when it is contractually stable.
- Do not invent client-side team priority.
- Display the first team followed by “+N more.”
- Show “Unassigned” as neutral supporting text.

### Player-type badge

Use a compact light-teal or teal-outline badge with slate text:

- Batter
- Bowler
- All-rounder
- Wicket-keeper

### Cricket summary

Prefer full labels:

- Batter and wicket-keeper: batting style
- Bowler: bowling style
- All-rounder: batting and bowling styles
- Missing or unknown type: whichever valid style is available
- No empty placeholders

Only shorten labels when space requires it, particularly for all-rounders. Preserve meaning over compactness.

### Interaction

- Entire card remains one accessible details trigger.
- No nested actions.
- Visible teal focus ring.
- Restrained hover border/background change.
- Preserve “View [player name] details” accessible naming.

## Shared information hierarchy

Cards and modal follow the same sequence:

1. Player identity
2. Team membership
3. Player type
4. Role-aware cricket summary
5. Full batting and bowling profile
6. Date of birth
7. Biography
8. Role-gated edit action

The modal should feel like an expansion of the selected card, not a separate information system.

## Modal structure

### Header

- Larger initials avatar
- Player name
- Ordered team membership
- Player-type badge
- Close control

Do not add a generic “Player details” eyebrow.

### Playing profile

Use a responsive definition list for:

- Batting style
- Bowling style
- Date of birth

Use complete domain labels in the modal.

### Biography

Show the biography directly when present. Omit the section when empty rather than adding a large placeholder or collapsed disclosure.

### Actions

- Authorized coaches see Edit Player as the primary footer action.
- Other roles see no unavailable or disabled edit control.
- Preserve all existing role checks and update behavior.

Exclude statistics, development status, placeholder copy, and development-only metadata.

## Modal accessibility and layering

First assess whether the existing modal implementation can be cleanly hardened.

Retain it if it can reliably provide:

- Semantic modal isolation
- Background inertness or equivalent assistive-technology isolation
- Robust focus containment
- Initial focus inside the modal
- Escape dismissal
- Focus restoration to the originating card
- Scroll locking
- Predictable backdrop behavior
- Correct behavior when details transitions to Edit Player
- No collision with the skip link or other overlay layers

Introduce a reusable native <dialog> primitive only if meeting those requirements with the current implementation would require fragile custom focus, inertness, or layering
logic.

A native implementation may use showModal() and a portal root, but the migration is an implementation decision rather than a predetermined requirement.

## Responsive behavior

### Wide desktop

- Three compact card columns
- Flexible search field
- Approximately 256px team filter
- Count aligned with the toolbar
- Modal retains a readable two-column profile layout

### Tablet

- Two card columns
- Search and filter share a row while space allows
- Count may move below the controls
- Avoid compressed labels or truncated player identity

### Mobile

- One compact card column
- Full-width search and filter
- Count below controls
- Near-full-width modal with small viewport margins
- Single-column profile facts
- Internal modal scrolling
- No horizontal overflow at 320px
- Long player and team names wrap safely

## Key states

- Initial loading: compact card skeletons
- Background search/filter fetch: retain results and mark region busy
- Empty directory: existing first-player guidance and role-gated action
- No search results: query-aware message plus Clear Search
- Combined search/filter empty state: explain that both controls affect results
- Background error: retain previous results with Retry
- Initial error: existing full error state
- Mutation success: preserve existing confirmation and refresh behavior

## Accessibility requirements

- Persistent visible labels for search and team filter
- Explicit accessible name for Clear Search
- Polite announcement after result totals update
- No focus movement during ordinary search updates
- Existing focus behavior retained for manual pagination
- One interactive element per card
- Textual player information independent of badge color
- Initials avatars hidden from assistive technology
- Minimum 44px interaction targets
- WCAG 2.1 AA contrast
- Reduced-motion behavior retained
- Modal background unavailable to keyboard and virtual-cursor navigation
- Focus reliably restored after every modal exit path

## Reusable components

- PlayerSearchField
- PlayerInitialsAvatar
- PlayerTypeBadge
- PlayerCricketSummary
- Shared player-identity composition where it reduces duplication
- Compact PlayerCardSkeleton
- Existing TeamFilter and Pagination
- Hardened modal utility or native ModalDialog, based on implementation assessment

## Tokens

Reuse existing color, spacing, radius, typography, and focus tokens first.

Add a token only when it is:

- Semantic, or
- Reused across multiple components

A formal overlay scale is encouraged:

1. Dropdown
2. Sticky interface
3. Modal backdrop
4. Modal
5. Toast
6. Tooltip

Remove reliance on unrelated elements sharing arbitrary overlay values.

## Explicit non-goals

- No table or full-width roster list
- No sidebar or application-shell changes
- No additional filters or sorting controls
- No batch or bulk actions
- No statistics or development status
- No new player fields
- No photographs or upload workflow
- No decorative cricket imagery
- No metadata-display work
- No placeholder-logo work
- No authorization changes
- No behavioral change when search is absent
- No broader Add/Edit form redesign unless required for the shared modal hardening work

The brief is now finalized and ready for implementation.