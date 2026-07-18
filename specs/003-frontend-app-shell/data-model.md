# Data Model: Frontend Application Shell

**Feature**: 003-frontend-app-shell
**Date**: 2026-07-18

## Entities

### 1. Application Route

Represents a navigable page within the application. Defined statically at build time — no runtime route registration.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `string` | URL path pattern (e.g., `"/"`, `"/players"`, `"*"`) |
| `label` | `string` | Human-readable navigation label (e.g., "Home", "Player Directory") |
| `icon` | `JSX.Element` | Inline SVG icon for sidebar navigation |
| `element` | `React.ReactNode` | Page component rendered at this route |
| `showInSidebar` | `boolean` | Whether this route appears in the sidebar navigation (false for 404) |

**Validation rules**:
- All `path` values must be unique within the route configuration
- Routes shown in sidebar (`showInSidebar: true`) must have a non-empty `label` and `icon`
- The catch-all route (`"*"`) must appear last in the route array

**Predefined routes**:

| path | label | showInSidebar |
|------|-------|---------------|
| `/` | Home | true |
| `/players` | Player Directory | true |
| `/teams` | Teams | true |
| `/coaches` | Coaches Portal | true |
| `/calendar` | Calendar | true |
| `/settings` | User Settings | true |
| `*` | — | false |

### 2. Navigation Item

Represents a single link rendered in the sidebar. Derived from Application Route entries with `showInSidebar: true`.

| Field | Type | Description |
|-------|------|-------------|
| `to` | `string` | Target route path |
| `label` | `string` | Display text (visible when sidebar expanded) |
| `icon` | `JSX.Element` | Icon element (always visible) |
| `isActive` | `boolean` | Whether this link points to the current route (derived at render time via `NavLink`) |

**Relationships**: Each Navigation Item maps 1:1 to an Application Route with `showInSidebar: true`.

**Display states**:
- **Expanded sidebar**: Icon + label visible
- **Collapsed sidebar**: Icon visible; label hidden but accessible via `title` attribute (tooltip) and `aria-label`

### 3. Sidebar State

Tracks the UI state of the sidebar within a browser session. Managed via React Context, not persisted.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `expanded` | `boolean` | `true` | Whether the sidebar shows labels (expanded) or icons only (collapsed) |
| `mobileOpen` | `boolean` | `false` | Whether the mobile overlay drawer is currently open |

**State transitions**:

```
Desktop/tablet (≥768px):
  expanded=true  ──[click toggle]──→  expanded=false
  expanded=false ──[click toggle]──→  expanded=true

Mobile (<768px):
  mobileOpen=false ──[click hamburger]──→  mobileOpen=true
  mobileOpen=true  ──[click nav link]────→  mobileOpen=false
  mobileOpen=true  ──[click backdrop]────→  mobileOpen=false
  mobileOpen=true  ──[press Escape]──────→  mobileOpen=false
```

**Constraints**:
- `expanded` and `mobileOpen` are independent — toggling `expanded` on desktop does not affect `mobileOpen`
- On viewport resize across the 768px breakpoint, the sidebar should gracefully transition (CSS handles this; state persists)
- The `expanded` state persists across route navigations (the context provider lives above the `<Outlet />`)
- The `mobileOpen` state resets to `false` on navigation (link click handler closes drawer)

## TypeScript Type Definitions

```typescript
// Route configuration type
interface RouteConfig {
  path: string;
  label: string;
  icon: React.ReactNode;
  element: React.ReactNode;
  showInSidebar: boolean;
}

// Sidebar context value
interface SidebarContextValue {
  expanded: boolean;
  mobileOpen: boolean;
  toggleExpanded: () => void;
  openMobile: () => void;
  closeMobile: () => void;
}

// Navigation link props
interface SidebarNavLinkProps {
  to: string;
  label: string;
  icon: React.ReactNode;
}
```
