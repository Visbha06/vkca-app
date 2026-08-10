// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router'
import { AuthContext, type AuthContextValue } from '@features/auth'
import HeadCoachRoute from './HeadCoachRoute'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const baseAuthValue: AuthContextValue = {
  user: null,
  accessToken: 'test-token',
  isAuthenticated: true,
  isInitializing: false,
  isLoginPending: false,
  isLogoutPending: false,
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
  updateUser: vi.fn(),
}

function renderRoute(role: 'head coach' | 'assistant coach' | 'player') {
  render(
    <AuthContext.Provider
      value={{
        ...baseAuthValue,
        user: {
          id: `${role}-1`,
          first_name: 'Asha',
          last_name: 'Coach',
          email: `${role}@vkca.test`,
          role,
          is_active: true,
          created_at: '',
          updated_at: '',
          session: {
            session_id: '',
            created_at: '',
            last_used_at: '',
            expires_at: '',
          },
        },
      }}
    >
      <MemoryRouter initialEntries={['/data-quality']}>
        <HeadCoachRoute
          forbiddenTitle="Data Quality is available to Head Coaches only."
          forbiddenDescription="Health checks are restricted to Head Coaches."
        >
          <h1>Protected Data Quality</h1>
        </HeadCoachRoute>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('HeadCoachRoute', () => {
  it('renders protected content for Head Coaches', () => {
    renderRoute('head coach')

    expect(screen.getByRole('heading', { name: 'Protected Data Quality' })).toBeInTheDocument()
  })

  it.each(['assistant coach', 'player'] as const)(
    'renders configurable Forbidden copy for %s users',
    (role) => {
      renderRoute(role)

      expect(
        screen.getByRole('heading', {
          name: 'Data Quality is available to Head Coaches only.',
        }),
      ).toBeInTheDocument()
      expect(
        screen.getByText('Health checks are restricted to Head Coaches.'),
      ).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Protected Data Quality' })).not.toBeInTheDocument()
    },
  )

  it('does not mount an unauthorized child that could issue an API request', () => {
    const request = vi.spyOn(globalThis, 'fetch')

    function RequestingChild() {
      void fetch('/api/v1/data-quality')
      return <h1>Should not render</h1>
    }

    render(
      <AuthContext.Provider
        value={{
          ...baseAuthValue,
          user: {
            id: 'player-1',
            first_name: 'Asha',
            last_name: 'Player',
            email: 'player@vkca.test',
            role: 'player',
            is_active: true,
            created_at: '',
            updated_at: '',
            session: {
              session_id: '',
              created_at: '',
              last_used_at: '',
              expires_at: '',
            },
          },
        }}
      >
        <MemoryRouter initialEntries={['/data-quality']}>
          <HeadCoachRoute>
            <RequestingChild />
          </HeadCoachRoute>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(request).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { name: 'Should not render' })).not.toBeInTheDocument()
  })
})
