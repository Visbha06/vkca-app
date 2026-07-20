// @vitest-environment node

import { renderToStaticMarkup } from 'react-dom/server'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { appRoutes } from '../App'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'

const routeCases = [
  ['/', 'Good evening, Coach'],
  ['/players', 'Player Directory'],
  ['/teams', 'Teams'],
  ['/coaches', 'Coaches Portal'],
  ['/calendar', 'Calendar'],
  ['/settings', 'User Settings'],
] as const

function renderRoute(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] })
  const authValue: AuthContextValue = {
    user: null,
    accessToken: path === '/login' ? null : 'test-token',
    isAuthenticated: path !== '/login',
    isInitializing: false,
    isLoginPending: false,
    isLogoutPending: false,
    login: async () => undefined,
    logout: async () => undefined,
    refreshSession: async () => false,
    updateUser: () => undefined,
  }

  return renderToStaticMarkup(
    <AuthContext.Provider value={authValue}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  )
}

describe('application routes', () => {
  it.each(routeCases)('renders the correct page for %s', (path, heading) => {
    const markup = renderRoute(path)

    expect(markup).toContain(`>${heading}</h1>`)
  })

  it('renders the not found page for an unknown route', () => {
    const markup = renderRoute('/not-a-real-page')

    expect(markup).toContain('>Page Not Found</h1>')
  })
})
