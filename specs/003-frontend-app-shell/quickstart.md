# Quickstart: Frontend Application Shell

**Feature**: 003-frontend-app-shell
**Date**: 2026-07-18

## Prerequisites

- Node.js 20+ and npm 10+
- Project cloned and in the `003-frontend-app-shell` branch
- Backend services **not required** — this is a frontend-only verification

## Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies (adds tailwindcss, react-router-dom, testing libs)
npm install

# Verify TypeScript compiles without errors
npx tsc -b --noEmit
```

## Run the Application

```bash
# Start dev server
npm run dev
```

Open the printed URL (default: `http://localhost:5173`).

## Validation Scenarios

### 1. Home Page with Application Shell

**Steps**:
1. Open `http://localhost:5173` in a browser

**Expected**:
- Sidebar visible on the left with navigation links: Home, Player Directory, Teams, Coaches Portal, Calendar, User Settings
- Each sidebar link has an icon and a text label
- Academy logo (`placeholderLogo.png`) and "Welcome to VK Cricket Academy!" title fade into view
- The Home link is visually active (highlighted with academy color #559eac)
- No full browser reload occurred

### 2. Navigate Between Pages

**Steps**:
1. Click "Player Directory" in the sidebar
2. Click "Teams"
3. Click "Calendar"
4. Click "User Settings"
5. Click "Home"

**Expected**:
- URL updates to `/players`, `/teams`, `/calendar`, `/settings`, `/` respectively
- Each page displays its heading and placeholder message
- The active sidebar link updates on each click
- Sidebar state (expanded/collapsed) remains consistent
- No full page reload (SPA navigation)

### 3. Sidebar Collapse/Expand

**Steps**:
1. Click the collapse icon (chevron « or arrow ◀) at the bottom/top of the sidebar
2. Click the expand icon (chevron » or arrow ▶)

**Expected**:
- Collapsed: labels hidden, only icons visible, toggle shows expand icon
- Expanded: labels visible, toggle shows collapse icon
- Main content area resizes smoothly (no layout shift jump)
- Toggle is keyboard-accessible (Tab to focus, Enter/Space to activate)

### 4. 404 Not Found Page

**Steps**:
1. Navigate to `http://localhost:5173/nonexistent-route`

**Expected**:
- Page displays "Page Not Found" heading within the shared layout
- Sidebar and navigation remain visible
- User can click a sidebar link to return to a valid page

### 5. Placeholder Pages

**Steps**:
1. Navigate to `/players`, `/teams`, `/coaches`, `/calendar`, `/settings`

**Expected**:
- Each page displays its name as an `<h1>` heading
- Each page shows a placeholder message (e.g., "This section will be available in a future update.")
- No fake data, forms, or interactive controls present
- All pages use the shared layout

### 6. Responsive — Mobile Overlay Drawer

**Steps**:
1. Resize browser to ≤768px width (or use DevTools mobile view)
2. Observe the sidebar is hidden; hamburger menu button is visible
3. Click the hamburger button
4. Click "Teams" in the overlay drawer

**Expected**:
- Initial state: sidebar hidden, hamburger visible, main content full-width
- After hamburger click: sidebar slides in as overlay, backdrop visible
- After "Teams" click: drawer closes, `/teams` page renders
- Tapping outside the drawer also closes it

### 7. Responsive — Desktop/Tablet Inline Sidebar

**Steps**:
1. Resize browser to >768px width
2. Toggle sidebar between expanded and collapsed

**Expected**:
- Sidebar always visible inline beside content
- Main content resizes (no overlay behavior)
- Toggle button shows chevron/arrow icons

### 8. Accessibility Checks

**Steps**:
1. Tab through all interactive elements
2. Inspect the sidebar toggle with a screen reader (or DevTools accessibility panel)
3. Check the page heading structure

**Expected**:
- All links and toggle buttons receive visible focus rings
- Sidebar toggle announces "Collapse sidebar" / "Expand sidebar" (accessible label)
- Active navigation link has `aria-current="page"`
- Each page has exactly one `<h1>` element
- Logo image has non-empty `alt` text

### 9. Reduced Motion

**Steps**:
1. Enable `prefers-reduced-motion: reduce` in browser DevTools (Rendering tab or OS setting)
2. Reload the home page

**Expected**:
- Logo and title appear immediately (no fade-in animation)
- Sidebar transitions are instant (no slide animation)

## Run Tests

```bash
# Run all unit tests
npx vitest run

# Run with coverage
npx vitest run --coverage
```

**Expected**: All tests pass. Coverage should include:
- AppLayout rendering with sidebar
- Each route renders the correct page component
- Sidebar expand/collapse behavior
- Active navigation state updates on click
- HomePage logo, title, and alt text
- Placeholder page headings
- 404 page for unknown routes
- Sidebar toggle keyboard accessibility (Enter/Space)
- Mobile overlay drawer opens/closes

## Run Linting

```bash
npm run lint
```

**Expected**: Zero lint errors.
