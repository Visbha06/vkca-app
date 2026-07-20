import {
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from 'react-router-dom'
import GuestRoute from './auth/GuestRoute'
import ProtectedRoute from './auth/ProtectedRoute'
import AppLayout from './layouts/AppLayout'
import CalendarPage from './pages/CalendarPage'
import CoachesPage from './pages/CoachesPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import PlayersPage from './pages/PlayersPage'
import RouteErrorPage from './pages/RouteErrorPage'
import SettingsPage from './pages/SettingsPage'
import TeamsPage from './pages/TeamsPage'

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
