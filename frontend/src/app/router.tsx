import {
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from 'react-router'
import { GuestRoute, LoginPage, ProtectedRoute } from '@features/auth'
import { BusinessAuditLogPage } from '@features/audit'
import { DataQualityPage } from '@features/data-quality'
import AppLayout from '@/layouts/AppLayout'
import CalendarPage from '@/pages/CalendarPage'
import CoachesPage from '@/pages/CoachesPage'
import HomePage from '@/pages/home/HomePage'
import NotFoundPage from '@/pages/NotFoundPage'
import { PlayersPage } from '@features/players'
import RouteErrorPage from '@/pages/RouteErrorPage'
import { SettingsPage } from '@features/settings'
import { TeamsPage } from '@features/teams'
import HeadCoachRoute from './HeadCoachRoute'

export const appRoutes: RouteObject[] = [
  {
    path: '/login',
    element: (
      <GuestRoute>
        <LoginPage />
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
        element: <PlayersPage />,
      },
      {
        path: 'teams',
        element: <TeamsPage />,
      },
      {
        path: 'coaches',
        element: <CoachesPage />,
      },
      {
        path: 'calendar',
        element: <CalendarPage />,
      },
      {
        path: 'audit-log',
        element: (
          <HeadCoachRoute>
            <BusinessAuditLogPage />
          </HeadCoachRoute>
        ),
      },
      {
        path: 'data-quality',
        element: (
          <HeadCoachRoute>
            <DataQualityPage />
          </HeadCoachRoute>
        ),
      },
      {
        path: 'settings',
        element: <SettingsPage />,
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
