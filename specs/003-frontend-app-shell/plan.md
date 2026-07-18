# Implementation Plan: Frontend Application Shell

**Branch**: `003-frontend-app-shell` | **Date**: 2026-07-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-frontend-app-shell/spec.md`

## Summary

Build the React + TypeScript frontend application shell for VK Cricket Academy. Deliver a shared layout with collapsible sidebar, client-side routing to 6 routes + 404 page, academy color theme (#559eac), responsive design (desktop/tablet inline sidebar, mobile overlay drawer), accessibility (keyboard nav, ARIA, reduced-motion), and comprehensive unit tests. Styled with Tailwind CSS 4.

## Technical Context

**Language/Version**: TypeScript 6.0 (strict mode), React 19.2

**Primary Dependencies**: React 19.2, React Router 7, Tailwind CSS 4, Vite 8

**Storage**: N/A — sidebar state held in React context (in-memory, session only)

**Testing**: Vitest 3 + React Testing Library + jsdom + @testing-library/jest-dom

**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge — latest 2 versions)

**Project Type**: Web application (frontend SPA)

**Performance Goals**: <3s initial load, <1s route transition, no Cumulative Layout Shift during sidebar toggle

**Constraints**: WCAG 2.1 AA compliance, Tailwind spacing scale only (no hardcoded pixels), components ≤200 lines, no `any` type

**Scale/Scope**: 6 routes, 1 shared layout, ~8 components, 5 placeholder pages, 1 404 page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Clean Code | ✅ PASS | Components will be single-responsibility; App.tsx will be replaced with router setup |
| II. Simple UX | ✅ PASS | Sidebar navigation is single primary interaction; all pages reachable in ≤2 clicks |
| III. Responsive Design | ✅ PASS | Tailwind breakpoints `md:` (768px) for sidebar behavior switch; tested at 320–2560px |
| IV. Minimal Dependencies | ✅ PASS | Only react-router-dom and tailwindcss added to existing Vite scaffold |
| V. Testing Discipline | ✅ PASS | Unit tests mandatory for all components and routing; E2E test will be added in a follow-up task |
| VI. MCP Server Priority | N/A | Frontend-only feature; no codebase search needed |
| VII. Database Schema Migrations | N/A | No database involvement |
| VIII. UX Completeness in Specs | ✅ PASS | Spec covers layouts, states, responsive behavior, accessibility, edge cases |
| IX. Optimistic Concurrency Control | N/A | No data writes or concurrent access |
| X. Strongly-Typed API Boundaries | ✅ PASS | TypeScript strict mode; no `any`; route params typed; NavLink props typed |
| XI. Frontend State & Component Discipline | ✅ PASS | Components ≤200 lines; Tailwind spacing scale only; container/presentational split for Sidebar |
| XII. Documentation | ✅ PASS | `docs/frontend-app-shell.md` to be created after implementation |

**Gate Result**: PASS — no violations. All applicable principles satisfied by the plan.

## Project Structure

### Documentation (this feature)

```text
specs/003-frontend-app-shell/
├── plan.md              # This file
├── research.md          # Phase 0: technology decisions and rationale
├── data-model.md        # Phase 1: routes, navigation items, sidebar state
├── quickstart.md        # Phase 1: runnable validation guide
├── contracts/           # Phase 1: route specifications
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── eslint.config.js
├── public/
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.tsx                  # Entry point: BrowserRouter + App
    ├── App.tsx                   # Root: AppLayout wrapping <Outlet />
    ├── index.css                 # Tailwind directives + theme tokens
    ├── layouts/
    │   └── AppLayout.tsx         # Shared layout: Sidebar + main content
    ├── components/
    │   ├── Sidebar.tsx           # Sidebar container (expand/collapse logic)
    │   ├── SidebarNavLink.tsx    # Single navigation link with active state
    │   ├── SidebarToggle.tsx     # Collapse/expand icon button
    │   └── MobileNavToggle.tsx   # Hamburger button (mobile only)
    ├── pages/
    │   ├── HomePage.tsx          # Logo + welcome title with fade-in
    │   ├── PlayersPage.tsx       # Placeholder
    │   ├── TeamsPage.tsx         # Placeholder
    │   ├── CoachesPage.tsx       # Placeholder
    │   ├── CalendarPage.tsx      # Placeholder
    │   ├── SettingsPage.tsx      # Placeholder
    │   └── NotFoundPage.tsx      # 404 page
    ├── assets/
    │   └── placeholderLogo.png   # Academy logo placeholder
    └── __tests__/
        ├── AppLayout.test.tsx
        ├── Sidebar.test.tsx
        ├── routes.test.tsx
        ├── HomePage.test.tsx
        └── ResponsiveNav.test.tsx
```

**Structure Decision**: Single frontend SPA. The existing Vite scaffold (`frontend/`) is preserved as the base. New directories `layouts/`, `components/`, `pages/`, and `__tests__/` are added. The default Vite template files (hero image, counter, etc.) are removed. React Router's `<Outlet />` pattern enables the shared layout to persist across routes.

## Complexity Tracking

> No constitution violations. This section intentionally left empty.
