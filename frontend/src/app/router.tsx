import {
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from 'react-router'
import { GuestRoute, ProtectedRoute } from '@features/auth'
import AppLayout from '@/layouts/AppLayout'
import HomePage from '@/pages/home/HomePage'
import NotFoundPage from '@/pages/NotFoundPage'
import RouteErrorPage from '@/pages/RouteErrorPage'
import {
  DeferredAuditLogRoute,
  DeferredCalendarRoute,
  DeferredCoachesRoute,
  DeferredDataQualityRoute,
  DeferredLoginRoute,
  DeferredPlayersRoute,
  DeferredSettingsRoute,
  DeferredTeamsRoute,
} from './DeferredRoutes'
import HeadCoachRoute from './HeadCoachRoute'

export const appRoutes: RouteObject[] = [
  {
    path: '/login',
    element: (
      <GuestRoute>
        <DeferredLoginRoute />
      </GuestRoute>
    ),
    errorElement: <RouteErrorPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    errorElement: <RouteErrorPage />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'players',
        element: (
          <DeferredPlayersRoute />
        ),
      },
      {
        path: 'teams',
        element: (
          <DeferredTeamsRoute />
        ),
      },
      {
        path: 'coaches',
        element: (
          <DeferredCoachesRoute />
        ),
      },
      {
        path: 'calendar',
        element: (
          <DeferredCalendarRoute />
        ),
      },
      {
        path: 'audit-log',
        element: (
          <HeadCoachRoute>
            <DeferredAuditLogRoute />
          </HeadCoachRoute>
        ),
      },
      {
        path: 'data-quality',
        element: (
          <HeadCoachRoute
            forbiddenTitle="Data Quality is available to Head Coaches only."
            forbiddenDescription="Your account does not have access to current academy health checks or remediation tools."
          >
            <DeferredDataQualityRoute />
          </HeadCoachRoute>
        ),
      },
      {
        path: 'settings',
        element: (
          <DeferredSettingsRoute />
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

const router =
  typeof document === 'undefined'
    ? createMemoryRouter(appRoutes)
    : createBrowserRouter(appRoutes)

export default router
