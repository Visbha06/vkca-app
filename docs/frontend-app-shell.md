# Frontend Application Shell

## Purpose

The frontend application shell gives VK Cricket Academy a persistent, responsive frame for current and future pages. It provides the academy home page, client-side routing, a shared sidebar, accessible navigation controls, and placeholder destinations without requiring a backend service.

## User flows

- Open the home page to see the academy logo and welcome heading. The entrance animation is disabled when reduced motion is preferred.
- Use the sidebar to move between pages without a full browser reload. The current destination is highlighted and exposed with `aria-current="page"`.
- On screens 768px and wider, collapse the sidebar to icons or expand it to show labels. The selection persists while navigating.
- Below 768px, open navigation from the header. Selecting a destination, pressing Escape, or activating the backdrop closes the overlay drawer.
- Visit an unknown URL to see the Not Found page inside the same navigable shell.

## Routes

| Path | Page |
|---|---|
| `/` | Home |
| `/players` | Player Directory |
| `/teams` | Teams |
| `/coaches` | Coaches Portal |
| `/calendar` | Calendar |
| `/settings` | User Settings |
| Any other path | Page Not Found |

The five non-home feature routes intentionally contain only a heading and a future-update message. They do not include mock data or unfinished controls.

## Configuration and validation

The shell uses React Router for navigation, React context for in-memory sidebar state, Tailwind CSS for responsive styling, and the academy accent color `#559eac`. No environment variables or backend services are required.

From `frontend/`, use:

```bash
npm run dev
npm test
npx playwright install --with-deps chromium
npm run test:e2e
npm run lint
npx tsc -b --noEmit
```

The Playwright suite starts the Vite development server automatically and validates the primary journey at 375px and 1280px viewport widths.
