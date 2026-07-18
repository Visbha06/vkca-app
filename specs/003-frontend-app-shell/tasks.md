# Tasks: Frontend Application Shell

**Input**: Design documents from `specs/003-frontend-app-shell/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Unit tests are MANDATORY per the constitution (V. Testing Discipline). One E2E Playwright test per spec is REQUIRED — placed in the Polish phase. Integration tests are N/A (no backend integration in scope).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths relative to `frontend/`. Parent directory is `/home/visbha/vkca-app/frontend/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install dependencies and configure toolchain

- [ ] T001 Install production dependencies: `react-router-dom` in `frontend/package.json`
- [ ] T002 [P] Install dev dependencies: `tailwindcss`, `@tailwindcss/vite` in `frontend/package.json`
- [ ] T003 [P] Install test dependencies: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` in `frontend/package.json`
- [ ] T004 [P] Enable strict TypeScript mode (`strict: true`) in `frontend/tsconfig.app.json`
- [ ] T005 Configure Vite with Tailwind CSS plugin in `frontend/vite.config.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 [P] Set up Tailwind CSS directives and academy theme tokens (color #559eac, sidebar widths, breakpoint) in `frontend/src/index.css`
- [ ] T007 [P] Create SidebarContext with expanded/mobileOpen state and toggle actions in `frontend/src/layouts/SidebarContext.tsx`
- [ ] T008 Create AppLayout shell component with sidebar container + main content area + `<Outlet />` in `frontend/src/layouts/AppLayout.tsx`
- [ ] T009 Configure React Router with layout route (`createBrowserRouter`) wrapping AppLayout in `frontend/src/App.tsx`
- [ ] T010 Update entry point to use `RouterProvider` in `frontend/src/main.tsx`
- [ ] T011 [P] Create placeholder academy logo image (simple colored SVG or PNG) at `frontend/src/assets/placeholderLogo.png`
- [ ] T012 [P] Clean up old Vite template files: remove `frontend/src/App.css`, unused assets in `frontend/src/assets/` (hero.png, react.svg, vite.svg if no longer referenced)
- [ ] T013 Verify dev server starts (`npm run dev`) and renders AppLayout shell with sidebar and empty main content area

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - View Application Shell with Home Page (Priority: P1) 🎯 MVP

**Goal**: Visitor opens the app and sees the academy logo and welcome title with a fade-in animation within the shared layout.

**Independent Test**: Open `http://localhost:5173` — verify sidebar + main content layout, academy logo, "Welcome to VK Cricket Academy!" title, fade-in animation, academy color accents, Home link active.

### Tests for User Story 1 (MANDATORY unit tests) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T014 [P] [US1] Write unit tests for HomePage (renders logo, renders welcome title, logo has alt text, title is h1) in `frontend/src/tests/HomePage.test.tsx`

### Implementation for User Story 1

- [ ] T015 [US1] Create HomePage component with placeholder logo image and "Welcome to VK Cricket Academy!" heading in `frontend/src/pages/HomePage.tsx`
- [ ] T016 [US1] Add fade-in animation CSS keyframes with `prefers-reduced-motion` gate in `frontend/src/index.css`
- [ ] T017 [US1] Wire HomePage as the index route (`/`) in `frontend/src/App.tsx`
- [ ] T018 [US1] Run HomePage unit tests (`npx vitest run`) and verify all pass
- [ ] T019 [US1] Manual browser verification: logo fades in, title visible, Home link active, reduced-motion preference disables animation

**Checkpoint**: Home page fully functional — MVP deliverable

---

## Phase 4: User Story 2 - Navigate Between Pages (Priority: P2)

**Goal**: User clicks sidebar links to navigate between pages without full browser reloads; active page is visually indicated.

**Independent Test**: Click each sidebar link — verify URL updates, page content changes, active state follows, no full page reload, sidebar state persists.

### Tests for User Story 2 (MANDATORY unit tests) ⚠️

- [ ] T020 [P] [US2] Write unit tests for routing (each route renders correct page component, unknown route renders 404) in `frontend/src/tests/routes.test.tsx`

### Implementation for User Story 2

- [ ] T021 [P] [US2] Create SidebarNavLink component using React Router's `NavLink` with active-state styling and `aria-current` in `frontend/src/components/SidebarNavLink.tsx`
- [ ] T022 [US2] Create inline SVG icon components for all 6 navigation items (Home, Players, Teams, Coaches, Calendar, Settings) — add as inline SVGs or a shared icons file in `frontend/src/components/NavIcons.tsx`
- [ ] T023 [US2] Add all 6 navigation items using SidebarNavLink with icons to sidebar in `frontend/src/layouts/AppLayout.tsx`
- [ ] T024 [US2] Create NotFoundPage component (catch-all route) in `frontend/src/pages/NotFoundPage.tsx`
- [ ] T025 [US2] Add all routes (`/`, `/players`, `/teams`, `/coaches`, `/calendar`, `/settings`, `*`) to router config in `frontend/src/App.tsx`
- [ ] T026 [US2] Run route unit tests and verify all pass
- [ ] T027 [US2] Manual browser verification: navigate all 6 routes + unknown route → 404 page; verify active state follows; verify no full reload

**Checkpoint**: All routes navigable, active states working, 404 handled

---

## Phase 5: User Story 4 - View Placeholder Pages (Priority: P4)

**Goal**: Each route displays a page with a heading and placeholder message; no fake data or controls.

**Independent Test**: Navigate to each of the 5 placeholder routes — verify heading, placeholder message, no fake data.

### Implementation for User Story 4

- [ ] T028 [P] [US4] Create PlayersPage placeholder (h1: "Player Directory", message) in `frontend/src/pages/PlayersPage.tsx`
- [ ] T029 [P] [US4] Create TeamsPage placeholder (h1: "Teams", message) in `frontend/src/pages/TeamsPage.tsx`
- [ ] T030 [P] [US4] Create CoachesPage placeholder (h1: "Coaches Portal", message) in `frontend/src/pages/CoachesPage.tsx`
- [ ] T031 [P] [US4] Create CalendarPage placeholder (h1: "Calendar", message) in `frontend/src/pages/CalendarPage.tsx`
- [ ] T032 [P] [US4] Create SettingsPage placeholder (h1: "User Settings", message) in `frontend/src/pages/SettingsPage.tsx`
- [ ] T033 [US4] Manual verification: navigate to each placeholder page, confirm heading + message, confirm no fake data/forms/controls

**Checkpoint**: All placeholder pages render correctly

---

## Phase 6: User Story 3 - Expand and Collapse Sidebar (Priority: P3)

**Goal**: User toggles sidebar between expanded (labels + icons + collapse icon) and collapsed (icons only + expand icon) states using click or keyboard.

**Independent Test**: Click toggle control — verify collapse/expand, labels hide/show, icons remain, main content resizes, keyboard works (Tab + Enter/Space), state persists across navigation.

### Tests for User Story 3 (MANDATORY unit tests) ⚠️

- [ ] T034 [P] [US3] Write unit tests for sidebar behavior (expand/collapse, keyboard toggle, active state, state persists across navigation) in `frontend/src/tests/Sidebar.test.tsx`

### Implementation for User Story 3

- [ ] T035 [P] [US3] Create SidebarToggle component with chevron icons (collapsed shows expand arrow, expanded shows collapse arrow) and accessible label in `frontend/src/components/SidebarToggle.tsx`
- [ ] T036 [US3] Implement `expanded` state toggle logic in `frontend/src/layouts/SidebarContext.tsx` (add `toggleExpanded` action)
- [ ] T037 [US3] Style collapsed sidebar: hide labels, keep icons visible with tooltips (`title` attribute), reduce sidebar width in `frontend/src/layouts/AppLayout.tsx` and `frontend/src/components/SidebarNavLink.tsx`
- [ ] T038 [US3] Ensure main content area dynamically adjusts margin when sidebar toggles using Tailwind transition classes in `frontend/src/layouts/AppLayout.tsx`
- [ ] T039 [US3] Run sidebar unit tests and verify all pass
- [ ] T040 [US3] Manual verification: toggle via click, toggle via keyboard (Tab → Enter/Space), verify state persists across page navigation, verify no content overlap

**Checkpoint**: Sidebar fully interactive with expand/collapse and keyboard support

---

## Phase 7: User Story 5 - Responsive and Accessible Interface (Priority: P5)

**Goal**: Application is usable on desktop (inline collapsible sidebar), tablet (inline collapsible sidebar), and mobile (overlay drawer); all UI is keyboard-accessible and screen-reader friendly.

**Independent Test**: Resize to 1920px, 768px, 375px — verify adaptive layout. Tab through all elements — verify focus rings and keyboard operability. Check mobile overlay drawer behavior.

### Tests for User Story 5 (MANDATORY unit tests) ⚠️

- [ ] T041 [P] [US5] Write unit tests for AppLayout (renders sidebar, renders main content area, provides SidebarContext) in `frontend/src/tests/AppLayout.test.tsx`
- [ ] T042 [P] [US5] Write responsive navigation tests (mobile overlay opens on hamburger click, closes on link tap) in `frontend/src/tests/ResponsiveNav.test.tsx`

### Implementation for User Story 5

- [ ] T043 [P] [US5] Create MobileNavToggle component (hamburger menu button, visible only on mobile, accessible label) in `frontend/src/components/MobileNavToggle.tsx`
- [ ] T044 [US5] Implement mobile overlay drawer state (`mobileOpen`, `openMobile`, `closeMobile`) in `frontend/src/layouts/SidebarContext.tsx`
- [ ] T045 [US5] Add responsive CSS: sidebar as overlay with backdrop on mobile (<768px), inline collapsible on desktop/tablet (≥768px) in `frontend/src/index.css`
- [ ] T046 [US5] Integrate MobileNavToggle into AppLayout header bar (visible only on mobile) in `frontend/src/layouts/AppLayout.tsx`
- [ ] T047 [US5] Add keyboard accessibility: visible focus rings (Tailwind `focus:ring-*`), `aria-label` on toggle, `aria-current="page"` on active link, semantic `<nav>` landmark in `frontend/src/components/SidebarNavLink.tsx`, `frontend/src/components/SidebarToggle.tsx`, `frontend/src/components/MobileNavToggle.tsx`
- [ ] T048 [US5] Manual responsive verification: test at 320px, 768px, 1024px, 1440px, 1920px — no horizontal overflow, sidebar behavior correct at each breakpoint
- [ ] T049 [US5] Manual accessibility verification: Tab through all controls, verify focus rings, test with keyboard only (no mouse), verify screen reader announces toggle state, verify text contrast meets WCAG AA (4.5:1 normal, 3:1 large) using browser DevTools
- [ ] T050 [US5] Run all unit tests (`npx vitest run`) — verify full suite passes

**Checkpoint**: Fully responsive, accessible application shell — all user stories complete

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: E2E test, documentation, final validation

- [ ] T051 [P] Write E2E Playwright test covering primary user journey at 375px and 1280px viewports (open home page → navigate via sidebar → toggle sidebar → test mobile overlay) in `frontend/e2e/app-shell.spec.ts`
- [ ] T052 [P] Write feature documentation with concise version of spec (purpose, user flows, routes, configuration) in `docs/frontend-app-shell.md`
- [ ] T053 [P] Run ESLint and fix any errors (`npm run lint`)
- [ ] T054 Run TypeScript strict check (`npx tsc -b --noEmit`) and fix any type errors
- [ ] T055 Run quickstart.md validation: work through all 9 scenarios and confirm expected outcomes
- [ ] T056 Final code review: verify all components ≤200 lines, no `any` types, Tailwind spacing scale used consistently, no hardcoded pixels, text contrast meets WCAG AA across all pages

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 Home Page (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 Navigation (Phase 4)**: Depends on Foundational (Phase 2) — can parallel with US1
- **US4 Placeholder Pages (Phase 5)**: Depends on US2 Navigation (routes must exist)
- **US3 Sidebar Toggle (Phase 6)**: Depends on US2 Navigation (sidebar links must exist)
- **US5 Responsive + A11y (Phase 7)**: Depends on US3 Sidebar Toggle (toggle must exist)
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependencies on other stories
- **US2 (P2)**: After Foundational — no dependencies on other stories (can parallel with US1)
- **US4 (P4)**: After US2 — depends on route definitions
- **US3 (P3)**: After US2 — depends on sidebar links being rendered
- **US5 (P5)**: After US3 — depends on sidebar toggle existing

### Within Each User Story

- Tests MUST be written and FAIL before implementation (constitution V)
- Components before integration into AppLayout
- Core implementation before manual verification
- Story complete before moving to next in dependency chain

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 can run in parallel (different config files)
- **Phase 2**: T006, T007, T011, T012 can run in parallel (different files)
- **Phase 3**: T014 (test) can run while T008-T010 finish; T015 and T016 can run in parallel
- **Phase 4**: T020 (test), T021, T022 can run in parallel; T024 can run in parallel
- **Phase 5**: T028-T032 (all 5 placeholder pages) can run in parallel
- **Phase 6**: T034 (test) and T035 can run in parallel
- **Phase 7**: T041, T042 (tests), T043 can run in parallel
- **Phase 8**: T051, T052, T053 can run in parallel
- **Cross-phase**: US1 and US2 phases can proceed in parallel after Foundational

---

## Parallel Example: Phase 4 (US2 Navigation)

```bash
# Launch all parallel tasks together:
Task: "T020: Write route unit tests in frontend/src/tests/routes.test.tsx"
Task: "T021: Create SidebarNavLink component in frontend/src/components/SidebarNavLink.tsx"
Task: "T022: Create NavIcons (inline SVGs) in frontend/src/components/NavIcons.tsx"
Task: "T024: Create NotFoundPage in frontend/src/pages/NotFoundPage.tsx"
```

## Parallel Example: Phase 5 (US4 Placeholder Pages)

```bash
# All 5 placeholder pages can be created simultaneously:
Task: "Create PlayersPage placeholder in frontend/src/pages/PlayersPage.tsx"
Task: "Create TeamsPage placeholder in frontend/src/pages/TeamsPage.tsx"
Task: "Create CoachesPage placeholder in frontend/src/pages/CoachesPage.tsx"
Task: "Create CalendarPage placeholder in frontend/src/pages/CalendarPage.tsx"
Task: "Create SettingsPage placeholder in frontend/src/pages/SettingsPage.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (Home Page)
4. **STOP and VALIDATE**: `npm run dev` + browser verification
5. Demo the home page with layout shell

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (Home Page) → Test independently → **MVP!**
3. Add US2 (Navigation) → Test independently → All routes work
4. Add US4 (Placeholder Pages) → Test independently → All pages have content
5. Add US3 (Sidebar Toggle) → Test independently → Sidebar interactive
6. Add US5 (Responsive + A11y) → Test independently → **Full feature**
7. Complete Polish → Ship-ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Home Page) — Phase 3
   - Developer B: US2 (Navigation) — Phase 4
3. Once US2 is done:
   - Developer A: US4 (Placeholder Pages) — all 5 pages in parallel
   - Developer B: US3 (Sidebar Toggle) — Phase 6
4. Once US3 is done:
   - Both: US5 (Responsive + A11y) — Phase 7
5. Both: Polish — Phase 8

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach per constitution V)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All CSS must use Tailwind utilities and spacing scale — no hardcoded pixels (constitution III, XI)
- No `any` types in any component or test file (constitution X)
- Components must not exceed 200 lines (constitution XI)
- Run `npm run lint` after each phase to catch issues early