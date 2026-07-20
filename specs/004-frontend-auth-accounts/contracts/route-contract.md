# Route Contract

**Feature**: 004-frontend-auth-accounts
**Date**: 2026-07-19

## Route Table (updated)

All routes are defined in `frontend/src/App.tsx`.

| # | Path | Component | Auth Required | Notes |
|---|------|-----------|---------------|-------|
| 1 | `/login` | `LoginPage` | No (GuestRoute) | Redirects authenticated users to `/` |
| 2 | `/` | `HomePage` | Yes (ProtectedRoute) | Wrapped in AppLayout |
| 3 | `/players` | `PlayersPage` | Yes (ProtectedRoute) | Wrapped in AppLayout |
| 4 | `/teams` | `TeamsPage` | Yes (ProtectedRoute) | Wrapped in AppLayout |
| 5 | `/coaches` | `CoachesPage` | Yes (ProtectedRoute) | Wrapped in AppLayout |
| 6 | `/calendar` | `CalendarPage` | Yes (ProtectedRoute) | Wrapped in AppLayout |
| 7 | `/settings` | `SettingsPage` | Yes (ProtectedRoute) | Opens modal; wrapped in AppLayout |
| 8 | `*` | `NotFoundPage` | Yes (ProtectedRoute) | Wrapped in AppLayout |

## Route Structure

```
<AuthProvider>
  <RouterProvider>
    <Routes>
      <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route index element={<HomePage />} />
        <Route path="players" element={<PlayersPage />} />
        <Route path="teams" element={<TeamsPage />} />
        <Route path="coaches" element={<CoachesPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  </RouterProvider>
</AuthProvider>
```

## Route Guards

### ProtectedRoute

```typescript
function ProtectedRoute({ children }: { children: ReactNode }): ReactNode
```

**Behavior**:
- If `isInitializing`: render nothing or a loading indicator (prevents redirect flash).
- If `!isAuthenticated`: redirect to `/login?redirect=<current path>`.
- If `isAuthenticated`: render `children`.

### GuestRoute

```typescript
function GuestRoute({ children }: { children: ReactNode }): ReactNode
```

**Behavior**:
- If `isInitializing`: render nothing or a loading indicator.
- If `isAuthenticated`: redirect to `/` (or to the `redirect` query param if present).
- If `!isAuthenticated`: render `children`.

## Redirect Preservation

- When a protected route redirects to `/login`, the current path is preserved as a query parameter: `/login?redirect=/players`.
- LoginPage reads `redirect` from search params. On successful login, navigates to `redirect` if present, otherwise `/`.
- The `redirect` parameter is cleared after successful login navigation.

## Loading State During Initialization

- While `isInitializing === true`, route guards render a centered loading indicator (spinner with accessible label).
- No protected content is rendered before initialization completes.
- The loading indicator uses the Cool Canvas (`#f8fafc`) background consistent with the app shell.

## Modified Files

- `frontend/src/App.tsx`: Restructured route tree with `ProtectedRoute` and `GuestRoute` wrappers.
- `frontend/src/main.tsx`: Wrapped in `<AuthProvider>`.
