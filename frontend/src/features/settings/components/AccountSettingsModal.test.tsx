// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { apiClient } from '@shared/api/client'
import { AuthContext, type AuthContextValue, type AuthUser } from '@features/auth'
import AccountSettingsModal from '@features/settings/components/AccountSettingsModal'
import { SettingsPage } from '@features/settings'

const authenticatedUser: AuthUser = {
  id: 'user-1',
  first_name: 'Vikram',
  last_name: 'Kumar',
  email: 'coach@vkca.test',
  role: 'head coach',
  is_active: true,
  created_at: '2026-07-01T09:00:00Z',
  updated_at: '2026-07-19T09:00:00Z',
  session: {
    session_id: 'session-1',
    created_at: '2026-07-19T09:00:00Z',
    last_used_at: '2026-07-19T09:00:00Z',
    expires_at: '2026-08-18T09:00:00Z',
  },
}

function makeAuthValue(
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
  return {
    user: authenticatedUser,
    accessToken: 'test-token',
    isAuthenticated: true,
    isInitializing: false,
    isLoginPending: false,
    isLogoutPending: false,
    login: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refreshSession: vi.fn().mockResolvedValue(true),
    updateUser: vi.fn(),
    ...overrides,
  }
}

function LocationProbe() {
  const location = useLocation()
  return <p>Location: {location.pathname}{location.search}</p>
}

function renderModal(
  overrides: Partial<AuthContextValue> = {},
  onClose = vi.fn(),
) {
  const authValue = makeAuthValue(overrides)
  const view = render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter>
        <Routes>
          <Route
            path="*"
            element={
              <>
                <AccountSettingsModal onClose={onClose} />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
  return { authValue, onClose, ...view }
}

function enterCompliantPasswords() {
  fireEvent.change(screen.getByLabelText('New password'), {
    target: { value: 'UpdatedPassword!1' },
  })
  fireEvent.change(screen.getByLabelText('Confirm new password'), {
    target: { value: 'UpdatedPassword!1' },
  })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  document.body.style.overflow = ''
})

describe('AccountSettingsModal', () => {
  it('renders prefilled editable names and read-only account details', () => {
    renderModal()

    expect(screen.getByRole('dialog', { name: 'User Settings' })).toBeVisible()
    expect(screen.getByLabelText('First name')).toHaveValue('Vikram')
    expect(screen.getByLabelText('Last name')).toHaveValue('Kumar')
    expect(screen.getByLabelText('Email address')).toHaveValue('coach@vkca.test')
    expect(screen.getByLabelText('Email address')).toHaveAttribute('readonly')
    expect(screen.getByLabelText('Role')).toHaveValue('Head coach')
    expect(screen.getByLabelText('Role')).toHaveAttribute('readonly')
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('blocks empty profile fields with associated validation errors', () => {
    const request = vi.spyOn(apiClient, 'request')
    renderModal()

    fireEvent.change(screen.getByLabelText('First name'), {
      target: { value: '   ' },
    })
    fireEvent.change(screen.getByLabelText('Last name'), {
      target: { value: '' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save profile' }))

    expect(screen.getByLabelText('First name')).toHaveAccessibleDescription(
      'First name is required.',
    )
    expect(screen.getByLabelText('Last name')).toHaveAccessibleDescription(
      'Last name is required.',
    )
    expect(request).not.toHaveBeenCalled()
  })

  it('updates the profile and shared auth state without reloading', async () => {
    const updatedUser = {
      ...authenticatedUser,
      first_name: 'Vik',
      last_name: 'Kumar-Singh',
    }
    vi.spyOn(apiClient, 'request').mockResolvedValue(updatedUser)
    const updateUser = vi.fn()
    renderModal({ updateUser })

    fireEvent.change(screen.getByLabelText('First name'), {
      target: { value: ' Vik ' },
    })
    fireEvent.change(screen.getByLabelText('Last name'), {
      target: { value: 'Kumar-Singh' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save profile' }))

    await waitFor(() =>
      expect(apiClient.request).toHaveBeenCalledWith('/api/v1/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ first_name: 'Vik', last_name: 'Kumar-Singh' }),
      }),
    )
    expect(updateUser).toHaveBeenCalledWith(updatedUser)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Your profile has been updated.',
    )
  })

  it('shows safe profile-update failure feedback', async () => {
    vi.spyOn(apiClient, 'request').mockRejectedValue(
      new Error('raw database connection details'),
    )
    renderModal()

    fireEvent.change(screen.getByLabelText('First name'), {
      target: { value: 'Updated' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save profile' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to update your profile. Please try again.',
    )
    expect(screen.queryByText(/database connection/i)).not.toBeInTheDocument()
  })

  it('reports every password policy violation and a confirmation mismatch', () => {
    const request = vi.spyOn(apiClient, 'request')
    renderModal()

    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'short' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'different' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(screen.getByText('Password must be at least 12 characters.')).toBeVisible()
    expect(screen.getByText('Password must include an uppercase letter.')).toBeVisible()
    expect(screen.getByText('Password must include a number.')).toBeVisible()
    expect(screen.getByText('Password must include a special character.')).toBeVisible()
    expect(screen.getByText('Passwords must match.')).toBeVisible()
    expect(request).not.toHaveBeenCalled()
  })

  it('changes the password, clears auth, and redirects with confirmation', async () => {
    vi.spyOn(apiClient, 'request').mockResolvedValue(undefined)
    const logout = vi.fn().mockResolvedValue(undefined)
    renderModal({ logout })
    enterCompliantPasswords()

    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    await waitFor(() =>
      expect(apiClient.request).toHaveBeenCalledWith(
        '/api/v1/users/user-1/change-password',
        {
          method: 'POST',
          body: JSON.stringify({
            new_password: 'UpdatedPassword!1',
            confirm_password: 'UpdatedPassword!1',
          }),
        },
      ),
    )
    await waitFor(() => expect(logout).toHaveBeenCalledOnce())
    expect(await screen.findByText(
      'Location: /login?reason=password-changed',
    )).toBeInTheDocument()
  })

  it('clears password fields and shows safe feedback when the request fails', async () => {
    vi.spyOn(apiClient, 'request').mockRejectedValue(
      new Error('raw password service details'),
    )
    renderModal()
    enterCompliantPasswords()

    fireEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to change your password. Please try again.',
    )
    expect(screen.getByLabelText('New password')).toHaveValue('')
    expect(screen.getByLabelText('Confirm new password')).toHaveValue('')
    expect(screen.queryByText(/password service/i)).not.toBeInTheDocument()
  })

  it('traps focus and closes from Escape, backdrop, and the close button', () => {
    const onClose = vi.fn()
    renderModal({}, onClose)

    const firstField = screen.getByLabelText('First name')
    const lastAction = screen.getByRole('button', {
      name: 'Close account settings',
    })
    lastAction.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(firstField).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByTestId('account-settings-backdrop'))
    fireEvent.click(
      screen.getByRole('button', { name: 'Close account settings' }),
    )
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('restores focus and body scrolling when unmounted', () => {
    const trigger = document.createElement('button')
    trigger.textContent = 'User Settings trigger'
    document.body.appendChild(trigger)
    trigger.focus()

    const { unmount } = renderModal()
    expect(screen.getByLabelText('First name')).toHaveFocus()

    unmount()
    expect(trigger).toHaveFocus()
    expect(document.body.style.overflow).toBe('')
    trigger.remove()
  })
})

describe('SettingsPage', () => {
  it('returns to the previous route when closing the modal', () => {
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <MemoryRouter
          initialEntries={[
            { pathname: '/settings', state: { from: '/players' } },
          ]}
        >
          <Routes>
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/players" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Close account settings' }),
    )
    expect(screen.getByText('Location: /players')).toBeInTheDocument()
  })

  it('returns home after a direct settings-route visit', () => {
    render(
      <AuthContext.Provider value={makeAuthValue()}>
        <MemoryRouter initialEntries={['/settings']}>
          <Routes>
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.getByText('Location: /')).toBeInTheDocument()
  })
})
