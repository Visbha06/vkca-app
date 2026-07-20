# Implementation Plan: Frontend Authentication and Account Management

**Branch**: `004-frontend-auth-accounts` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-frontend-auth-accounts/spec.md`

## Summary

Build the frontend authentication and account management layer for the VK Cricket Academy web application. This includes a login page, protected-route wrapper, shared auth state (React Context), session restoration on load, token refresh interceptor, logout control in the sidebar, and a user settings modal with profile editing and password change. Integrates with existing backend auth API (spec 002) and the existing app shell (spec 003). Adds one new backend endpoint (`PATCH /api/v1/auth/me`) and coordinates with `POST /api/v1/users/{id}/change-password` for password changes.

## Technical Context

**Language/Version**: TypeScript 5.x (strict mode), React 18+

**Primary Dependencies**: react, react-router-dom, Tailwind CSS 4 (@tailwindcss/vite), Vitest, Playwright

**Storage**: None (access token in memory only; refresh token in HttpOnly cookie managed by backend)

**Testing**: Vitest (unit/component tests) + Playwright (E2E)

**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge) — desktop, tablet, mobile

**Project Type**: Web application — single-page app (SPA) frontend + REST API backend

**Performance Goals**: Login → home page <5s, session restore <3s, logout <2s, WCAG 2.1 AA

**Constraints**: No localStorage/sessionStorage for tokens, no mock auth, backend-authoritative, hardcoded px forbidden per Constitution III

**Scale/Scope**: ~20 new components, ~77 functional requirements, 5 user stories, 1 E2E test

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Clean Code | ✅ PASS | Components under 200 lines; single-responsibility. |
| II. Simple UX | ✅ PASS | Login is one form; settings is one modal; logout is one click. |
| III. Responsive Design | ✅ PASS | FR-066–FR-069: 320px–2560px, Tailwind breakpoints, 44px targets. |
| IV. Minimal Dependencies | ✅ PASS | No new npm dependencies anticipated; all primitives in existing stack. |
| V. Testing Discipline | ✅ PASS | Unit tests for all components/logic; ≥1 E2E Playwright test. |
| VI. MCP Server Priority | ✅ PASS | Codebase exploration complete via spec/clarify phases. |
| VII. Database Migrations | ✅ PASS | Only if `PATCH /api/v1/auth/me` needs schema changes (unlikely; name fields exist). |
| VIII. UX Completeness in Specs | ✅ PASS | Spec references PRODUCT.md and DESIGN.md; all states covered. |
| IX. Optimistic Concurrency Control | ✅ PASS | N/A for auth reads; refresh deduplication (FR-026/027) prevents races. |
| X. Strongly-Typed API Boundaries | ✅ PASS | TypeScript types will mirror Pydantic schemas; no `any`. |
| XI. Frontend State Discipline | ✅ PASS | Auth context for shared state; split container/presentational. |
| XII. Documentation | ✅ PASS | `docs/frontend-auth-accounts.md` after implementation. |

**Gate Result**: All 12 principles PASS. No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/004-frontend-auth-accounts/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── auth-state-contract.md
│   ├── route-contract.md
│   └── backend-api-contract.md
├── checklists/
│   └── requirements.md
└── spec.md
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── api/
│   │   └── client.ts              # NEW: fetch wrapper with token injection + refresh
│   ├── auth/
│   │   ├── AuthContext.tsx          # NEW: shared auth state (React Context)
│   │   ├── AuthProvider.tsx         # NEW: provider with session restore
│   │   ├── ProtectedRoute.tsx       # NEW: route guard wrapper
│   │   ├── GuestRoute.tsx           # NEW: redirects authenticated users away from /login
│   │   ├── types.ts                 # NEW: AuthUser, AuthState, LoginCredentials
│   │   └── utils.ts                 # NEW: CSRF cookie reader, token helpers
│   ├── components/
│   │   ├── LogoutButton.tsx         # NEW: red exit icon in sidebar footer
│   │   ├── AccountSettingsModal.tsx  # NEW: profile + password-change modal
│   │   └── PasswordInput.tsx        # NEW: input with show/hide toggle
│   ├── pages/
│   │   ├── LoginPage.tsx            # NEW: login form page
│   │   └── SettingsPage.tsx         # MODIFIED: now opens AccountSettingsModal
│   ├── layouts/
│   │   └── AppLayout.tsx            # MODIFIED: add LogoutButton to footer
│   ├── App.tsx                      # MODIFIED: add /login route + auth wrapper
│   └── main.tsx                     # MODIFIED: wrap app in AuthProvider
├── e2e/
│   └── auth-flow.spec.ts            # NEW: E2E test for login → nav → settings → logout
└── src/tests/
    ├── LoginPage.test.tsx           # NEW
    ├── AuthContext.test.tsx         # NEW
    ├── ProtectedRoute.test.tsx      # NEW
    ├── AccountSettingsModal.test.tsx # NEW
    ├── PasswordInput.test.tsx       # NEW
    └── LogoutButton.test.tsx        # NEW

backend/
├── src/
│   ├── routes/
│   │   └── auth.py                  # MODIFIED: add PATCH /api/v1/auth/me
│   └── schemas/
│       └── auth.py                  # MODIFIED: add ProfileUpdate schema
└── tests/
    └── unit/
        └── test_auth_routes.py      # MODIFIED: add PATCH /me tests
```

**Structure Decision**: Web application pattern. Frontend adds `auth/` module for cross-cutting auth concerns, `api/client.ts` for centralized HTTP logic, and new components/pages. Backend adds one route handler and one Pydantic schema. No new directories at the project root level.

## Complexity Tracking

> No constitution violations. This section is intentionally empty.
