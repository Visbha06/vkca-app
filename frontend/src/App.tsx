import {
  createBrowserRouter,
  createMemoryRouter,
  type RouteObject,
} from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import HomePage from './pages/HomePage'
import NotFoundPage from './pages/NotFoundPage'

export const appRoutes: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'players',
        element: (
          <h1 className="text-3xl font-bold text-slate-900">
            Player Directory
          </h1>
        ),
      },
      {
        path: 'teams',
        element: <h1 className="text-3xl font-bold text-slate-900">Teams</h1>,
      },
      {
        path: 'coaches',
        element: (
          <h1 className="text-3xl font-bold text-slate-900">
            Coaches Portal
          </h1>
        ),
      },
      {
        path: 'calendar',
        element: (
          <h1 className="text-3xl font-bold text-slate-900">Calendar</h1>
        ),
      },
      {
        path: 'settings',
        element: (
          <h1 className="text-3xl font-bold text-slate-900">
            User Settings
          </h1>
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
