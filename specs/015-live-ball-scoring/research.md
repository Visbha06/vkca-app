# Research: Live Ball-by-Ball Match Entry

**Date**: 2026-10-13  
**Status**: Complete; no unresolved planning questions.

## Existing application and domain facts

- The repository is a React/TypeScript frontend with React Router and Tailwind plus a Python/FastAPI backend. Authenticated API access, token refresh, CSRF handling, error conversion, deferred routes, responsive navigation, shared forms/dialogs, Vitest, pytest, and Playwright already exist.
- Teams and Players are separate frontend feature modules. Team listing is paginated and Team rosters are available through the existing Team API; those are the selection sources for Match creation and internal Match configuration.
- The existing Match API already creates Matches. Its request contains match date, format, venue, required result text, and a discriminated participant object. Internal Matches specify two distinct academy Team IDs. External Matches specify one academy Team ID, a manually supplied opponent name, and which side the academy Team occupies. The existing scheduled result value is Scheduled.
- Feature 014 owns configuration, immutable capability, fixed Match-scoped participants, innings initialization, delivery entry, wicket and extra validation, strike and over progression, next batter/bowler blocks, retirement, correction replay, completion, result, and persisted scorecard/history projections. The interface must submit observed input and display responses without implementing these rules locally.
- Existing scoring reads authorize against current database identity and current Team assignments. A Head Coach can access all Teams. An Assistant Coach or Player may access a Match when their current scope intersects at least one academy side; an external side never grants access. Match detail applies this check, while the current GET /matches list does not.
- Existing Match creation requires a coach role but does not currently apply the assignment check that later Match configuration uses. A scoped Assistant could otherwise create a Match they cannot configure. The existing configuration authorization helper is the appropriate boundary to reuse for creation.
- The scorecard response contains Match lifecycle and ordered innings projections, including current totals, participant IDs/figures, target/chase fields, blocking state, and projection revision. It is sufficient for the read-only periodic refresh; no new read endpoint is needed.

## Decisions

### Reuse the existing Match creation and configuration boundary

**Decision**: Create through POST /api/v1/matches using the existing internal/external union shape, then navigate to Feature 015's pre-match configuration screen. That screen submits the existing Feature 014 configuration contract. Use the returned Match ID/version and current API response to continue; never create a frontend-only Match record.

**Rationale**: Match creation, participant identity, configuration locking, and scoring already have authoritative backend contracts. The current route accepts the required date, format, venue, initial Scheduled value, and side identity information.

**Alternatives considered**: A new Feature 015 Match table or creation endpoint would duplicate existing records and domain behavior. A separate opponent/participant database identity would incorrectly convert external scoring identities into academy Players or Users.

### Enforce current Team scope at existing Match boundaries

**Decision**: Filter the existing Match list using current authenticated scope, consistent with the existing Match detail read policy. Apply the existing configuration-scope policy to Match creation so an Assistant Coach can create only where at least one selected academy side anchors their current assignment; Head Coach access remains unrestricted.

**Rationale**: The existing list is unscoped, and the creation route currently checks role but not the same current assignment scope required by subsequent configuration. Reusing existing authorization context closes these gaps without adding a new policy, endpoint, or data model.

**Alternatives considered**: Client-side filtering is not an authorization boundary. Returning all rows and hiding them in React leaks Match information. Adding a new role/scope model is unnecessary because Feature 014 already loads current assignments and provides the configuration/read scope seam.

### Refresh read-only views from the persisted scorecard projection

**Decision**: While a read-only Match view is visible and lifecycle is in progress, refresh its existing Match scorecard response on the specified 10-second cadence. Do not refresh the scorer-entry route. Avoid concurrent refreshes; stop on terminal lifecycle, hidden/leaving view, or authorization failure. Keep last committed response during transient read errors and show that it is stale.

**Rationale**: The scorecard response contains the authoritative Match lifecycle and innings projections needed for live read-only viewing. A bounded single request per cadence meets the clarified requirement without recalculating or caching scoring state separately.

**Alternatives considered**: Manual refresh does not meet the requirement. Polling every scoring or history endpoint independently adds redundant work. WebSockets, public streaming, and offline replay are explicitly out of scope.

### Follow established frontend and test conventions

**Decision**: Add a feature module under frontend/src/features/matches, register a deferred authenticated route and navigation item, call the shared apiClient, and use existing Team APIs, components, Tailwind tokens, Vitest, and Playwright. Add no dependency.

**Rationale**: Teams and Players demonstrate the existing feature boundary and API/hooks/components/pages split. The shared request client already handles bearer tokens, CSRF, refresh, session-expiry redirection, and typed errors. Existing scripts cover frontend, backend, and E2E validation.

**Alternatives considered**: Introducing a new data-fetching, form, router, or polling library is not required for this bounded workflow and conflicts with the minimal dependency principle.

## External documentation

No external library behavior drives the design. Existing repository code, the Feature 014 API contract, match-scoring documentation, and product/design/constitution documents establish the contracts. Context7 lookup is therefore not required under Constitution Principle XIII.

## Resolved clarifications

The clarified creation form, Internal/External selection, manual external-opponent name, post-create configuration route, and ten-second visible read-only polling behavior are incorporated from the Feature 015 specification. No unresolved questions remain.
