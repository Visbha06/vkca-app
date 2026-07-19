# Research: Frontend Authentication and Account Management

**Feature**: 004-frontend-auth-accounts
**Date**: 2026-07-19

## Research Topics

### 1. Auth State Management Pattern

**Decision**: React Context with `useReducer` for state + `useContext` for consumption.

**Rationale**:
- The project already uses React Context for `SidebarContext`; this is the established pattern.
- `useReducer` handles complex state transitions cleanly (login, logout, refresh, session restore).
- No external state library needed — React built-ins are sufficient for a single shared auth state.
- Avoids the overhead of Redux/Zustand for this scope.

**Alternatives considered**:
- Redux Toolkit: Overkill for a single auth state; adds dependency weight.
- Zustand: Lighter than Redux but still adds a dependency for a single-store use case.
- Prop drilling: Unworkable across the route tree.

### 2. Token Refresh Interceptor Pattern

**Decision**: Centralized `fetch` wrapper in `api/client.ts` that injects Bearer token, detects 401, queues refresh, and retries.

**Rationale**:
- Single point of control for all authenticated requests.
- Prevents scattered token management logic across components.
- Queue-based deduplication: when multiple requests get 401, only one refresh fires; others await its result.
- No external HTTP library needed (`fetch` is native and sufficient).

**Key design**:
```
Request → add Authorization header → fetch → 401?
  → queue refresh (deduped) → success? → retry original request
  → fail? → clear auth state → redirect /login
```

**Alternatives considered**:
- Axios interceptors: Adds dependency; `fetch` + wrapper achieves the same result.
- Per-component refresh: Would scatter logic and risk duplicate refreshes.

### 3. CSRF Token Reading Pattern

**Decision**: Utility function `readCsrfToken()` that reads `document.cookie`, extracts the `csrf_token` cookie value, and returns it.

**Rationale**:
- The `csrf_token` cookie is not HttpOnly (by design) so it is readable from JS.
- `document.cookie` API is standard and sufficient for reading a single named cookie.
- No library needed — a ~5-line utility function covers it.

**Usage**: Called before login (not needed — login creates session, no CSRF), before refresh (send in `X-CSRF-Token` header), and before logout (same).

**Alternatives considered**:
- `js-cookie` library: Adds dependency for trivial cookie parsing.
- Server-side CSRF: Already handled — backend sets the cookie.

### 4. Form Validation Approach

**Decision**: Inline validation with controlled React inputs and local validation state. No form library.

**Rationale**:
- Two forms (login, settings) with straightforward validation rules.
- Login: required fields only (no complexity rules).
- Settings: required fields + password policy (regex-based).
- Adding a form library (Formik, React Hook Form) is unnecessary dependency weight for this scope.
- Tailwind CSS error styling is consistent with existing project patterns.

**Alternatives considered**:
- React Hook Form: Reduces boilerplate but adds dependency for 2 simple forms.
- Formik: Similar tradeoff; heavier than React Hook Form.

### 5. Modal Implementation Pattern

**Decision**: Custom modal component using native `<dialog>` element or ARIA-compliant `<div>` with `role="dialog"`.

**Rationale**:
- The project uses no UI component library; custom components are the established pattern.
- `<dialog>` element provides native focus trapping and `::backdrop` in modern browsers.
- Fallback to ARIA-compliant div if broader browser support needed.
- DESIGN.md specifies "Flat by Default" — backdrop contrast via dimming, not shadow.
- Modal must handle: focus trap, Escape close, backdrop click close, body scroll lock.

**Alternatives considered**:
- `@radix-ui/react-dialog`: Well-tested but adds dependency; `<dialog>` is now well-supported.
- `react-modal`: Adds dependency; native `<dialog>` is sufficient.

### 6. Route Protection Pattern

**Decision**: Two wrapper components: `<ProtectedRoute>` (requires auth) and `<GuestRoute>` (redirects authenticated users).

```tsx
// ProtectedRoute: if !authenticated && !initializing → redirect to /login?redirect=<current>
// GuestRoute: if authenticated → redirect to /
```

**Rationale**:
- Uses existing `react-router-dom` (already in project) — no new library.
- Redirect URL preserved via search param (`?redirect=/players`).
- `initializing` flag prevents flash of login page during session restore.
- Composable with existing `App.tsx` route structure.

**Alternatives considered**:
- Route-level loader guards: React Router v6 loaders run before render, but auth state is client-side.
- Higher-order components: Less idiomatic in modern React; wrapper components are clearer.

### 7. Testing Strategy

**Decision**: Vitest for unit/component tests, Playwright for E2E.

**Rationale**:
- Both already configured in the project (vitest.config.ts, playwright.config.ts).
- Unit tests: auth context, form validation, error message logic, password policy regex.
- Component tests: LoginPage rendering, modal open/close, protection redirects.
- E2E: Full login → protected nav → settings → password change → logout flow.

**Alternatives considered**:
- Jest: Vitest is already configured and faster.
- Cypress: Playwright is already configured; no reason to switch.
