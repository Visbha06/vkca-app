# Frontend Application Shell

## Purpose

The frontend application shell provides the persistent, responsive frame for the VK Cricket Academy web application.

It is responsible for:

- Client-side routing
- Authentication-aware page access
- Role-aware navigation
- Desktop and mobile navigation
- Shared page layout
- Route-level page titles
- Focus management between routes
- Accessible mobile drawer behavior
- Session-aware logout access
- Rendering feature pages inside a consistent application frame

The shell is implemented with React, React Router, TypeScript, and Tailwind CSS.

---

## Application Structure

The authenticated application is rendered through a shared `AppLayout`.

The layout contains:

- A persistent desktop sidebar
- A mobile navigation drawer
- Academy branding
- Primary application navigation
- User Settings access
- Logout control
- Collapsible desktop navigation
- A shared main-content region
- Route content rendered through React Router's `Outlet`

The layout surrounds all authenticated feature routes.

---

## Routing Model

The application uses React Router with a protected application route tree.

The top-level routes are:

| Path | Page | Access |
|---|---|---|
| `/login` | Login | Guest route |
| `/` | Home | Authenticated users |
| `/players` | Player Directory | Authenticated users |
| `/teams` | Teams | Authenticated users |
| `/coaches` | Coaches Portal | Head Coach and Assistant Coach |
| `/calendar` | Calendar | Authenticated users |
| `/audit-log` | Business Audit Log | Head Coach only |
| `/settings` | User Settings | Authenticated users |
| Any unmatched authenticated path | Page Not Found | Authenticated users |

The application shell itself is wrapped in the authenticated route boundary.

The Audit Log route has an additional Head Coach authorization boundary.

---

## Authentication-Aware Shell

The application shell is only rendered after authentication succeeds.

Unauthenticated users are handled by the authentication routing layer rather than receiving access to the normal application layout.

The shell consumes the authenticated user through the shared authentication context.

Authentication state is used for:

- Navigation visibility
- Role-aware feature access
- Logout behavior
- Session-aware application rendering

Frontend role filtering improves usability, but backend authorization remains authoritative.

---

## Primary Navigation

The main navigation contains:

- Home
- Player Directory
- Teams
- Coaches Portal
- Calendar
- Audit Log

User Settings is separated into the sidebar footer alongside Logout and the sidebar-collapse control.

Each navigation item includes an icon and text label when the sidebar is expanded.

The currently selected destination is communicated through the navigation-link state and exposed accessibly with `aria-current="page"`.

---

## Role-Aware Navigation

Navigation visibility is derived from the authenticated user's role.

### Head Coach

The Head Coach can see:

- Home
- Player Directory
- Teams
- Coaches Portal
- Calendar
- Audit Log
- User Settings

### Assistant Coach

Assistant Coaches can see:

- Home
- Player Directory
- Teams
- Coaches Portal
- Calendar
- User Settings

The Audit Log navigation item is hidden.

### Player

Players can see:

- Home
- Player Directory
- Teams
- Calendar
- User Settings

The Coaches Portal and Audit Log navigation items are hidden.

Navigation filtering is a presentation-layer convenience. Restricted routes and APIs still enforce authorization independently.

---

## Desktop Sidebar

At desktop widths, navigation is displayed in a persistent sidebar.

The sidebar supports two visual states:

- Expanded
- Collapsed

### Expanded State

The expanded sidebar displays:

- Academy branding
- Navigation icons
- Navigation labels
- Settings
- Logout
- Collapse control

### Collapsed State

The collapsed sidebar retains icon-based navigation while reducing the horizontal space occupied by the application shell.

The main content area's left margin adjusts to match the current sidebar width.

Sidebar expansion state is maintained through `SidebarContext`.

---

## Sidebar State

The shell uses a dedicated `SidebarProvider` to manage:

```text
expanded
mobileOpen
```

and the associated actions:

```text
toggleExpanded()
openMobile()
closeMobile()
```

Desktop expansion and mobile drawer visibility are intentionally represented as separate state.

Desktop sidebar state is currently maintained in React memory rather than persisted externally.

---

## Mobile Navigation

Below the desktop breakpoint, the persistent sidebar becomes an overlay navigation drawer.

The mobile application header contains:

- A navigation toggle
- The VK Cricket Academy title

Opening mobile navigation exposes the sidebar as a modal-style drawer.

While the drawer is open:

- Background page content becomes inert
- Background content is hidden from assistive technology
- Body scrolling is disabled
- Keyboard focus is contained within the drawer
- Escape closes the drawer
- The backdrop closes the drawer when activated
- Focus is restored after the drawer closes

The drawer also closes automatically when the viewport transitions back to desktop size.

---

## Focus Management

The shell manages keyboard focus as users move through the application.

### Route Changes

When the user navigates between application routes, the shell attempts to move focus to the new page's primary heading.

Feature-page headings are expected to support programmatic focus where required.

This gives keyboard and assistive-technology users a clear indication that route content has changed.

### Mobile Navigation

When the mobile drawer opens:

1. The previously focused element is recorded.
2. Focus moves into the navigation drawer.
3. Tab and Shift+Tab remain within the drawer.
4. Escape closes the drawer.
5. Focus is restored to the appropriate previous control when the drawer closes.

When the viewport changes from mobile to desktop while the drawer is open, the drawer closes and focus is moved to the active navigation item.

---

## Skip Navigation

The layout includes a:

```text
Skip to main content
```

link targeting:

```text
#main-content
```

This allows keyboard users to bypass repeated navigation and move directly into the active page.

The main application content region is programmatically focusable to support navigation and accessibility behavior.

---

## Page Titles

The shell maintains route-specific browser document titles.

Current mappings include:

| Path | Browser Title |
|---|---|
| `/` | `Home | VK Cricket Academy` |
| `/players` | `Player Directory | VK Cricket Academy` |
| `/teams` | `Teams | VK Cricket Academy` |
| `/coaches` | `Coaches Portal | VK Cricket Academy` |
| `/calendar` | `Calendar | VK Cricket Academy` |
| `/audit-log` | `Audit Log | VK Cricket Academy` |
| `/settings` | `User Settings | VK Cricket Academy` |
| Unknown route | `Page Not Found | VK Cricket Academy` |

Trailing slashes are normalized before resolving the title.

---

## Feature Integration

The shell now hosts real feature modules rather than placeholder pages.

The frontend currently contains feature-oriented modules for:

```text
audit
auth
calendar
coaches
players
settings
teams
```

Each feature owns its domain-specific:

- API integration
- Components
- Hooks
- Types
- Pages
- Utilities

where applicable.

The shell remains intentionally domain-neutral and delegates feature behavior to these modules.

---

## Home

The Home route acts as the application's main landing page after authentication.

It is rendered inside the same authenticated shell as the rest of the application and serves as the academy's main application entry point.

---

## Player Directory

The Player Directory is implemented as a feature module under:

```text
frontend/src/features/players
```

The shell provides navigation and layout only.

Player-specific behavior such as:

- Directory rendering
- Searching
- Filtering
- Player details
- Player management
- Loading and error states

is owned by the Players feature.

---

## Teams

Team functionality is implemented under:

```text
frontend/src/features/teams
```

The shell exposes the Teams route and shared layout, while team listing, roster management, modals, state, and API behavior remain within the Teams feature.

---

## Coaches Portal

The Coaches Portal is implemented under:

```text
frontend/src/features/coaches
```

It is visible only to coaching roles.

Player users do not see the Coaches Portal navigation item.

The feature itself owns:

- Coach listing
- Coach cards
- Filtering
- Coach details
- Account management
- Team assignments
- Role-specific controls

---

## Calendar

The Calendar feature is implemented under:

```text
frontend/src/features/calendar
```

The shell exposes Calendar to authenticated users.

The feature owns the academy scheduling experience, including:

- Monthly calendar rendering
- Today view
- Event details
- Event creation and editing
- Recurring event workflows
- Calendar-specific responsive behavior
- Loading, conflict, and error handling

Mutation controls are determined by user permissions within the calendar feature and backend authorization.

---

## Business Audit Log

The Business Audit Log is implemented under:

```text
frontend/src/features/audit
```

The shell exposes `/audit-log` only to Head Coaches.

The route is also protected by a dedicated Head Coach route wrapper.

The feature owns:

- Audit event rendering
- Filtering
- Date-range selection
- Pagination
- Event-detail disclosure
- Loading and error states
- Recent academy activity integration

Assistant Coach and Player accounts do not receive the Audit Log navigation item.

---

## User Settings

User Settings is available through the sidebar footer rather than the primary navigation group.

The settings link preserves the previous route in navigation state when appropriate, allowing the settings experience to retain awareness of where the user entered from.

Settings-specific behavior lives under:

```text
frontend/src/features/settings
```

---

## Logout

Logout is integrated directly into the sidebar footer.

The control is supplied by the authentication feature rather than implemented by the shell itself.

This keeps session termination behavior centralized in the authentication domain while making logout consistently available throughout the authenticated application.

---

## Not Found Behavior

Unknown authenticated routes render the application's Not Found page within the main application routing structure.

The document title resolves to:

```text
Page Not Found | VK Cricket Academy
```

The rest of the authenticated routing and application infrastructure remains intact.

---

## Responsive Design

The shell has two primary layout modes.

### Desktop

At widths of approximately 768px and above:

- The sidebar remains visible.
- The sidebar may be expanded or collapsed.
- Main content shifts horizontally according to sidebar width.
- The mobile header is hidden.

### Mobile

Below the desktop breakpoint:

- The persistent sidebar moves off-canvas.
- A mobile header is shown.
- Navigation opens as a modal drawer.
- Main content occupies the available viewport width.
- Background interaction is disabled while navigation is open.

The shell prevents horizontal page overflow and leaves feature pages responsible for responsive behavior within the shared content region.

---

## Accessibility

Accessibility behavior is built into the application shell rather than left entirely to individual feature pages.

The shell includes:

- Semantic navigation landmarks
- Semantic main content
- A skip-to-content link
- `aria-current` for active navigation
- Accessible navigation labels
- Keyboard-operable sidebar controls
- Mobile focus trapping
- Escape dismissal
- Focus restoration
- Background inertness during modal navigation
- Route-change focus management
- Programmatic main-content focus
- Accessible page-title changes

Individual features remain responsible for the accessibility of controls and interactions within their own routes.

---

## Visual Structure

The shell uses the application's restrained operational visual language.

The primary surfaces are:

- Dark slate sidebar
- Light application background
- White content/header surfaces
- Academy accent treatments
- Slate text and border hierarchy

The shell intentionally avoids decorative effects that would compete with operational academy workflows.

Feature pages may introduce domain-specific presentation while remaining within the shared visual system.

---

## Frontend Architecture

The frontend uses a feature-oriented structure:

```text
frontend/src/
├── app/
│   ├── App.tsx
│   ├── router.tsx
│   └── HeadCoachRoute.tsx
│
├── features/
│   ├── audit/
│   ├── auth/
│   ├── calendar/
│   ├── coaches/
│   ├── players/
│   ├── settings/
│   └── teams/
│
├── layouts/
│   ├── components/
│   ├── AppLayout.tsx
│   ├── SidebarContext.tsx
│   └── useAppLayoutEffects.ts
│
├── pages/
├── shared/
├── styles/
├── assets/
└── main.tsx
```

### `app/`

Owns application-level routing and route guards.

### `features/`

Contains domain-specific functionality.

### `layouts/`

Contains persistent application-shell behavior such as the sidebar, mobile navigation, and shared content frame.

### `shared/`

Contains reusable frontend components, APIs, utilities, icons, and infrastructure used across multiple features.

### `pages/`

Contains top-level page components or wrappers that are not fully owned by a feature module.

---

## Architectural Boundaries

The application shell is intentionally kept separate from domain features.

The shell is responsible for:

- Navigation
- Layout
- Responsive framing
- Route-transition behavior
- Global shell accessibility

Feature modules are responsible for:

- Domain data
- API calls
- Forms
- Domain-specific permissions
- Domain-specific state
- Feature loading and error behavior
- Business interactions

Authentication is treated as a cross-cutting feature and supplies identity/session state to both the routing layer and shell.

---

## Current Evolution

The original application shell specification introduced the basic routing and responsive navigation structure.

Since then, the shell has evolved to support:

- Real authenticated feature pages instead of placeholders
- Authentication-aware routing
- Role-aware navigation
- Head Coach-only Audit Log access
- Coach-route visibility restrictions
- Integrated logout
- User Settings in the sidebar footer
- Route-level browser titles
- Route-change focus management
- More robust mobile focus handling
- Background inertness while the navigation drawer is active

The original shell remains the structural foundation of the frontend, but it now functions as the shared authenticated frame for the full VK Cricket Academy application.
