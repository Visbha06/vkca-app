# Research: Frontend Application Shell

**Feature**: 003-frontend-app-shell
**Date**: 2026-07-18

## Technology Decisions

### 1. Tailwind CSS 4 with Vite

**Decision**: Use Tailwind CSS 4 with the `@tailwindcss/vite` plugin.

**Rationale**: Tailwind CSS 4 is the current major version with a simplified configuration model (CSS-first, no `tailwind.config.js` required). The `@tailwindcss/vite` plugin is the first-party Vite integration that auto-detects content files and injects Tailwind. This aligns with the project constitution (Principles III, XI) which mandate Tailwind's spacing scale and forbid hardcoded pixels.

**Alternatives considered**:
- Tailwind CSS 3 with `tailwind.config.js` — more verbose config; v4 is the current standard.
- CSS Modules — more boilerplate, less consistency with spacing scale enforcement.
- Styled Components — adds runtime overhead; violates constitution preference for Tailwind.

**Setup**: Add `tailwindcss` and `@tailwindcss/vite` as devDependencies. Import in `vite.config.ts` as a plugin. Add `@import "tailwindcss"` to `src/index.css`.

### 2. React Router v7 — Layout Routes

**Decision**: Use React Router v7 with `createBrowserRouter` and layout routes (`<Outlet />`).

**Rationale**: React Router v7 is the latest major version with first-class layout route support. The `<Outlet />` pattern keeps the `AppLayout` (sidebar + main content area) mounted across navigations, satisfying FR-006 and FR-007. `NavLink` provides built-in active-state styling via `className` callback or `aria-current`, satisfying FR-012 and FR-039.

**Alternatives considered**:
- TanStack Router — more type-safe but heavier; overkill for 6 routes.
- Next.js App Router — requires SSR; spec explicitly says no SSR.
- Manual history API + context — more code, less battle-tested.

**Route structure**:
```
/                  → AppLayout > HomePage
/players           → AppLayout > PlayersPage
/teams             → AppLayout > TeamsPage
/coaches           → AppLayout > CoachesPage
/calendar          → AppLayout > CalendarPage
/settings          → AppLayout > SettingsPage
*                  → AppLayout > NotFoundPage
```

### 3. Sidebar State Management

**Decision**: React Context (`SidebarContext`) with `useState` for expand/collapse and mobile overlay state.

**Rationale**: Sidebar state is simple boolean state (`expanded: boolean`, `mobileOpen: boolean`) shared across the layout and its children. React Context avoids prop drilling without adding a state management library. The state persists across route navigations because the `AppLayout` (where context is provided) stays mounted via `<Outlet />`. No persistence across browser restarts is needed per spec assumptions.

**Alternatives considered**:
- Zustand — minimal but adds a dependency; Context is sufficient for 2 boolean values.
- URL search params — overcomplicates; sidebar state is UI preference, not navigation state.
- Redux — massive overkill for this scope.

**Context API surface**:
```typescript
interface SidebarContextValue {
  expanded: boolean;
  mobileOpen: boolean;
  toggle: () => void;
  toggleMobile: () => void;
  closeMobile: () => void;
}
```

### 4. Sidebar Icons

**Decision**: Inline SVG elements for navigation icons and toggle chevrons. No icon library.

**Rationale**: The spec requires icons for each navigation link (FR-009) and chevron/arrow semantics for the toggle (FR-010). With only 6 nav items + 2 toggle states, a full icon library (Lucide, Heroicons, etc.) adds unnecessary dependency weight. Simple inline SVGs (home, users, shield, calendar, settings, chevron-left, chevron-right, menu) keep the dependency count minimal (Constitution IV).

**Alternatives considered**:
- Lucide React — 1000+ icons, tree-shakeable; adds ~50KB dependency for 8 icons.
- Heroicons — similar tradeoff.
- SVG sprite sheet — adds build complexity; inline SVGs are simpler for this scale.

### 5. Home Page Fade-In Animation

**Decision**: CSS `@keyframes` with `opacity` transition, gated by `prefers-reduced-motion: no-preference`.

**Rationale**: CSS-only animation avoids JavaScript animation libraries. The `prefers-reduced-motion` media query (FR-021) is a CSS-native feature. The animation targets `opacity: 0 → 1` over ~600ms with `ease-out` — subtle enough to not block interaction (FR-020) since it's purely visual.

**Implementation**:
```css
@media (prefers-reduced-motion: no-preference) {
  .home-fade-in {
    animation: fadeIn 600ms ease-out both;
  }
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

### 6. Responsive Sidebar Strategy

**Decision**: CSS media query at `md:` (768px) breakpoint controls inline vs. overlay behavior.

**Rationale**: The spec mandates 768px as the breakpoint. On `md:` and above, the sidebar is a collapsible inline panel that resizes content (FR-033). Below `md:`, the sidebar is hidden by default with a hamburger toggle; opening it displays an overlay drawer (FR-034). Tailwind's responsive prefixes (`hidden md:flex`, `md:hidden`, etc.) plus React state for the overlay toggle provide clean separation.

**Desktop/tablet (≥768px)**:
- Sidebar always visible inline (either expanded or collapsed)
- Toggle button shows chevron icons
- Main content area has `ml-` margin that changes with sidebar width

**Mobile (<768px)**:
- Sidebar hidden by default (`translate-x-[-100%]`)
- Hamburger button visible in top bar
- On toggle: sidebar slides in as overlay with backdrop
- Tapping a link or backdrop closes the drawer

### 7. Testing Setup

**Decision**: Vitest 3 + `@testing-library/react` + `jsdom` + `@testing-library/jest-dom`.

**Rationale**: Vitest is the natural test runner for Vite projects — shares the same transform pipeline and config. React Testing Library enforces testing user behavior over implementation details. `jsdom` provides DOM environment. `@testing-library/jest-dom` provides semantic matchers (`toBeInTheDocument()`, `toHaveAttribute()`).

**Alternatives considered**:
- Jest — possible but requires additional config to work with Vite/ESM.
- Playwright Component Testing — real browser environment but heavier; better for E2E.

**Test files** (5 files, mapped to FR-041):
- `AppLayout.test.tsx` — layout rendering, sidebar presence
- `Sidebar.test.tsx` — expand/collapse, keyboard toggle, active state
- `routes.test.tsx` — each route renders correct page, 404 for unknown
- `HomePage.test.tsx` — logo, title, alt text, fade-in
- `ResponsiveNav.test.tsx` — mobile overlay open/close on link tap

### 8. 404 Not Found Page

**Decision**: Catch-all route (`path: "*"`) rendering `NotFoundPage` component within `AppLayout`.

**Rationale**: React Router's `*` path catches all unmatched routes. Rendering within `AppLayout` preserves the sidebar and navigation, allowing users to recover by clicking a valid link (FR-027, SC-007). The page displays a heading "Page Not Found" and a brief message, consistent with placeholder page conventions.

### 9. ESLint & Formatting

**Decision**: Retain existing ESLint flat config with TypeScript and React Hooks plugins. No additional Prettier setup needed.

**Rationale**: The existing `eslint.config.js` already includes `typescript-eslint`, `eslint-plugin-react-hooks`, and `eslint-plugin-react-refresh`. The constitution requires linting to pass. Prettier is not yet configured; ESLint handles style rules adequately for this phase. If needed, Prettier can be added as a separate task.

### 10. TypeScript Strict Mode

**Decision**: Enable `strict: true` in `tsconfig.app.json` (already partially strict).

**Rationale**: The existing config has `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`. Adding `strict: true` enables `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, etc. This satisfies FR-001 and Constitution X. The `any` type is forbidden per Constitution X — use `unknown` with type guards when needed.
