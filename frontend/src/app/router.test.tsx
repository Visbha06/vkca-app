// @vitest-environment node

import { renderToStaticMarkup } from 'react-dom/server'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { describe, expect, it } from 'vitest'
import { appRoutes } from '@app/router'
import { AuthContext, type AuthContextValue } from '@features/auth'

const routeCases = [
  ['/', 'Welcome back, Coach Asha'],
  ['/players', 'Player Directory'],
  ['/teams', 'Teams'],
  ['/coaches', 'Coaches Portal'],
  ['/calendar', 'Calendar'],
  ['/settings', 'User Settings'],
] as const

const headCoach: NonNullable<AuthContextValue['user']> = {
  id: 'head-coach-1',
  first_name: 'Asha',
  last_name: 'Coach',
  email: 'asha@vkca.test',
  role: 'head coach',
  is_active: true,
  created_at: '',
  updated_at: '',
  session: { session_id: '', created_at: '', last_used_at: '', expires_at: '' },
}

function renderRoute(path: string, user: AuthContextValue['user'] = headCoach) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] })
  const authValue: AuthContextValue = {
    user,
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

  it('renders the Audit Log for a Head Coach', () => {
    const markup = renderRoute('/audit-log', headCoach)

    expect(markup).toContain('>Audit Log</h1>')
    expect(markup).not.toContain('403 Forbidden')
  })

  it('renders Data Quality for a Head Coach', () => {
    const markup = renderRoute('/data-quality', headCoach)

    expect(markup).toContain('>Data Quality</h1>')
    expect(markup).not.toContain('403 Forbidden')
  })

  it.each(['assistant coach', 'player'] as const)(
    'keeps business audit data out of the direct Audit Log route for %s users',
    (role) => {
      const markup = renderRoute('/audit-log', { ...headCoach, role })

      expect(markup).toContain('403 Forbidden')
      expect(markup).toContain('Audit Log is available to Head Coaches only.')
      expect(markup).not.toContain('Review safe, recorded academy activity')
    },
  )

  it.each(['assistant coach', 'player'] as const)(
    'protects the direct Data Quality route for %s users',
    (role) => {
      const markup = renderRoute('/data-quality', { ...headCoach, role })

      expect(markup).toContain('403 Forbidden')
      expect(markup).toContain('Data Quality is available to Head Coaches only.')
      expect(markup).not.toContain('>Data Quality</h1>')
    },
  )
})
