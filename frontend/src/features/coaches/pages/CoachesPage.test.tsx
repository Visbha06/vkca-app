// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@features/auth'
import CoachesPage from './CoachesPage'
import { fetchCoachDetails, fetchCoaches } from '../api/coachApi'

vi.mock('../api/coachApi', () => ({
  fetchCoachDetails: vi.fn(),
  fetchCoaches: vi.fn(),
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
})
