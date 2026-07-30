// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@features/auth'
import CoachesPage from './CoachesPage'
import {
  createCoach,
  deactivateCoach,
  fetchCoachDetails,
  fetchCoaches,
  reactivateCoach,
} from '../api/coachApi'
import { fetchTeams } from '@features/teams/api/teamApi'

vi.mock('../api/coachApi', () => ({
  createCoach: vi.fn(),
  deactivateCoach: vi.fn(),
  fetchCoachDetails: vi.fn(),
  fetchCoaches: vi.fn(),
  reactivateCoach: vi.fn(),
}))

vi.mock('@features/teams/api/teamApi', () => ({
  fetchTeams: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const auth: AuthContextValue = { user: { id: 'hc', first_name: 'Vikram', last_name: 'Kumar', email: 'coach@vkca.test', role: 'head coach', is_active: true, created_at: '', updated_at: '', session: { session_id: '', created_at: '', last_used_at: '', expires_at: '' } }, accessToken: 'token', isAuthenticated: true, isInitializing: false, isLoginPending: false, isLogoutPending: false, login: vi.fn(), logout: vi.fn(), refreshSession: vi.fn(), updateUser: vi.fn() }

describe('CoachesPage', () => {
  it('renders the empty directory after loading', async () => {
    vi.mocked(fetchCoaches).mockResolvedValue({ coaches: [], page: 1, page_size: 12, total_coaches: 0, total_pages: 0, has_previous: false, has_next: false })
    render(<AuthContext.Provider value={auth}><CoachesPage /></AuthContext.Provider>)
    expect(await screen.findByText('No Assistant Coaches have been added yet.')).toBeVisible()
  })

  it('renders cards, changes the status filter, and shows a safe error', async () => {
    vi.mocked(fetchCoaches)
      .mockResolvedValueOnce({ coaches: [{ id: 'coach-1', first_name: 'Vikram', last_name: 'Kumar', email: 'coach@vkca.test', role: 'head coach', is_active: true, version_number: 1, created_at: '', updated_at: '', teams: [] }], page: 1, page_size: 12, total_coaches: 1, total_pages: 1, has_previous: false, has_next: false })
      .mockRejectedValueOnce(new Error('network details'))
    render(<AuthContext.Provider value={auth}><CoachesPage /></AuthContext.Provider>)
    expect(await screen.findByText('Vikram Kumar')).toBeVisible()
    fireEvent.change(screen.getByRole('combobox', { name: 'Coach status' }), { target: { value: 'inactive' } })
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load coaches. Please try again.')
    expect(screen.queryByText('network details')).not.toBeInTheDocument()
    await waitFor(() => expect(fetchCoaches).toHaveBeenLastCalledWith({ status: 'inactive', page: 1, pageSize: 12 }, expect.any(AbortSignal)))
  })

  it('opens active coach details and keeps inactive cards out of an Assistant Coach tab order', async () => {
    const activeCoach = { id: 'coach-1', first_name: 'Vikram', last_name: 'Kumar', email: 'coach@vkca.test', role: 'head coach' as const, is_active: true, version_number: 1, created_at: '', updated_at: '', teams: [] }
    vi.mocked(fetchCoaches).mockResolvedValue({ coaches: [activeCoach], page: 1, page_size: 12, total_coaches: 1, total_pages: 1, has_previous: false, has_next: false })
    vi.mocked(fetchCoachDetails).mockResolvedValue(activeCoach)
    render(<AuthContext.Provider value={auth}><CoachesPage /></AuthContext.Provider>)
    fireEvent.click(await screen.findByRole('button', { name: /view vikram kumar/i }))
    expect(await screen.findByRole('dialog', { name: 'Vikram Kumar' })).toBeVisible()

    cleanup()
    vi.mocked(fetchCoaches).mockResolvedValue({ coaches: [{ ...activeCoach, is_active: false }], page: 1, page_size: 12, total_coaches: 1, total_pages: 1, has_previous: false, has_next: false })
    render(<AuthContext.Provider value={{ ...auth, user: { ...auth.user!, role: 'assistant coach' } }}><CoachesPage /></AuthContext.Provider>)
    const inactiveCard = await screen.findByRole('button', { name: /view vikram kumar/i })
    expect(inactiveCard).toBeDisabled()
    expect(inactiveCard).toHaveAttribute('tabindex', '-1')
    fireEvent.click(inactiveCard)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens Add Coach only for a Head Coach', async () => {
    vi.mocked(fetchCoaches).mockResolvedValue({
      coaches: [],
      page: 1,
      page_size: 12,
      total_coaches: 0,
      total_pages: 0,
      has_previous: false,
      has_next: false,
    })
    vi.mocked(fetchTeams).mockResolvedValue({
      teams: [],
      page: 1,
      page_size: 100,
      total_teams: 0,
      total_pages: 0,
    })
    render(
      <AuthContext.Provider value={auth}>
        <CoachesPage />
      </AuthContext.Provider>,
    )
    fireEvent.click(
      await screen.findByRole('button', { name: 'Add Coach' }),
    )
    expect(
      screen.getByRole('dialog', { name: 'Add Assistant Coach' }),
    ).toBeVisible()

    cleanup()
    render(
      <AuthContext.Provider
        value={{
          ...auth,
          user: { ...auth.user!, role: 'assistant coach' },
        }}
      >
        <CoachesPage />
      </AuthContext.Provider>,
    )
    expect(
      await screen.findByText('No Assistant Coaches have been added yet.'),
    ).toBeVisible()
    expect(
      screen.queryByRole('button', { name: 'Add Coach' }),
    ).not.toBeInTheDocument()
    expect(createCoach).not.toHaveBeenCalled()
    expect(deactivateCoach).not.toHaveBeenCalled()
    expect(reactivateCoach).not.toHaveBeenCalled()
  })

  it('adds a created coach to the directory without retaining the password', async () => {
    vi.mocked(fetchCoaches).mockResolvedValue({
      coaches: [],
      page: 1,
      page_size: 12,
      total_coaches: 0,
      total_pages: 0,
      has_previous: false,
      has_next: false,
    })
    vi.mocked(fetchTeams).mockResolvedValue({
      teams: [],
      page: 1,
      page_size: 100,
      total_teams: 0,
      total_pages: 0,
    })
    vi.mocked(createCoach).mockResolvedValue({
      id: 'coach-2',
      first_name: 'Asha',
      last_name: 'Patel',
      email: 'asha@vkca.test',
      role: 'assistant coach',
      is_active: true,
      version_number: 1,
      created_at: '',
      updated_at: '',
      teams: [],
      temporary_password: 'Aa1!temporary-token',
    })
    render(
      <AuthContext.Provider value={auth}>
        <CoachesPage />
      </AuthContext.Provider>,
    )

    fireEvent.click(
      await screen.findByRole('button', { name: 'Add Coach' }),
    )
    fireEvent.change(screen.getByLabelText('First name'), {
      target: { value: 'Asha' },
    })
    fireEvent.change(screen.getByLabelText('Last name'), {
      target: { value: 'Patel' },
    })
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'asha@vkca.test' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create coach' }))

    expect(
      await screen.findByRole('button', { name: /view asha patel details/i }),
    ).toBeVisible()
    expect(
      screen.getByText('Asha Patel was added successfully.'),
    ).toBeVisible()
    expect(screen.getByDisplayValue('Aa1!temporary-token')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(
      screen.queryByDisplayValue('Aa1!temporary-token'),
    ).not.toBeInTheDocument()
  })
})
