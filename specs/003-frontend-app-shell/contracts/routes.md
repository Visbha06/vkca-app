# Route Contracts: Frontend Application Shell

**Feature**: 003-frontend-app-shell
**Date**: 2026-07-18

## Route Table

All routes render within the shared `AppLayout` (sidebar + main content area).

| # | Path | Page Component | Heading | Status |
|---|------|---------------|---------|--------|
| 1 | `/` | `HomePage` | "Welcome to VK Cricket Academy!" | Home page with logo + fade-in |
| 2 | `/players` | `PlayersPage` | "Player Directory" | Placeholder |
| 3 | `/teams` | `TeamsPage` | "Teams" | Placeholder |
| 4 | `/coaches` | `CoachesPage` | "Coaches Portal" | Placeholder |
| 5 | `/calendar` | `CalendarPage` | "Calendar" | Placeholder |
| 6 | `/settings` | `SettingsPage` | "User Settings" | Placeholder |
| 7 | `*` (catch-all) | `NotFoundPage` | "Page Not Found" | 404 — HTTP semantics not sent; this is client-side rendering |

## Layout Contract

### AppLayout

The `AppLayout` component wraps all pages and provides:

**Slots**:
- `sidebar`: Left panel containing navigation links and toggle controls
- `main`: Right/content area rendering the active page via `<Outlet />`

**Provided Context**:
- `SidebarContext`: exposes `expanded`, `mobileOpen`, `toggleExpanded`, `openMobile`, `closeMobile`

**Responsive behavior**:
- `≥768px`: Sidebar rendered inline; `<main>` has left margin equal to sidebar width
- `<768px`: Sidebar hidden by default; hamburger button in a top bar; sidebar opens as overlay

### Sidebar Component Contract

**Props**: None (consumes `SidebarContext` internally)

**Renders**:
- 6 `SidebarNavLink` components (one per route with `showInSidebar: true`)
- `SidebarToggle` (desktop collapse/expand)
- `MobileNavToggle` (mobile hamburger, visible only <768px)

### SidebarNavLink Props

```typescript
interface SidebarNavLinkProps {
  to: string;       // Route path (e.g., "/players")
  label: string;    // Display text (e.g., "Player Directory")
  icon: ReactNode;  // SVG icon element
}
```

**Behavior**:
- Renders as `<NavLink>` from React Router
- Active state: applies academy color (#559eac) background/text and `aria-current="page"`
- Collapsed state: hides label, shows icon only; `title` attribute on link for tooltip

### Page Component Contract

Every page component:
- Receives no props (data passed via context or URL params in future specs)
- Renders an `<h1>` with the page heading
- For placeholder pages: renders a `<p>` with "This section will be available in a future update."
- Must not import or reference backend services

### 404 Page Contract

- Rendered at any path not matching routes 1–6
- Displays `<h1>Page Not Found</h1>`
- Displays `<p>The page you are looking for does not exist.</p>`
- Sidebar remains fully functional for navigation recovery
