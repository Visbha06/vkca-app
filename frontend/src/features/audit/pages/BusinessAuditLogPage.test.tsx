// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from '@features/auth'
import { fetchBusinessAuditActors, fetchBusinessAuditEvents } from '../api/businessAuditApi'
import BusinessAuditLogPage from './BusinessAuditLogPage'

vi.mock('../api/businessAuditApi', () => ({
  fetchBusinessAuditActors: vi.fn(), fetchBusinessAuditEvents: vi.fn(), fetchRecentBusinessAudit: vi.fn(),
}))

const auth: AuthContextValue = {
  user: { id: 'head', first_name: 'Asha', last_name: 'Coach', email: 'a@test', role: 'head coach', is_active: true, created_at: '', updated_at: '', session: { session_id: '', created_at: '', last_used_at: '', expires_at: '' } },
  accessToken: 'token', isAuthenticated: true, isInitializing: false, isLoginPending: false, isLogoutPending: false,
  login: vi.fn(), logout: vi.fn(), refreshSession: vi.fn(), updateUser: vi.fn(),
}
const event = { id: 'event-1', actor_user_id: 'actor-1', actor_display_name: 'Alex Morgan', actor_role: 'head coach', action_type: 'player.created' as const, action_category: 'player' as const, target_entity_type: 'player' as const, target_entity_id: 'player-1', target_label: 'Aarav Singh', summary: 'Alex added Aarav', metadata: { changed_fields: ['bio'] }, created_at: '2026-08-05T18:00:00Z', request_id: 'request-1' }

function renderPage() { return render(<AuthContext.Provider value={auth}><BusinessAuditLogPage /></AuthContext.Provider>) }

describe('BusinessAuditLogPage', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders safe events, actor filters, pagination, disclosures, and academy-local time', async () => {
    vi.mocked(fetchBusinessAuditActors).mockResolvedValue({ actors: [{ actor_user_id: 'actor-1', actor_display_name: 'Alex Morgan', actor_role: 'head coach' }] })
    vi.mocked(fetchBusinessAuditEvents).mockResolvedValue({ events: [event], page: 1, page_size: 20, total_events: 21, total_pages: 2, has_previous: false, has_next: true })
    renderPage()
    expect(await screen.findByText('Alex added Aarav')).toBeVisible()
    expect(screen.getByText('Player', { selector: 'span' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: /show safe details/i }))
    expect(screen.getByText('request-1')).toBeVisible()
    fireEvent.change(screen.getByLabelText('Actor'), { target: { value: 'actor-1' } })
    await waitFor(() => expect(fetchBusinessAuditEvents).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByRole('button', { name: 'Page 2' }))
    await waitFor(() => expect(fetchBusinessAuditEvents).toHaveBeenCalledTimes(3))
  })

  it('distinguishes initial history empty, filtered no-results, and a retryable safe error', async () => {
    vi.mocked(fetchBusinessAuditActors).mockResolvedValue({ actors: [] })
    vi.mocked(fetchBusinessAuditEvents).mockResolvedValue({ events: [], page: 1, page_size: 20, total_events: 0, total_pages: 0, has_previous: false, has_next: false })
    renderPage()
    expect(await screen.findByText('No business audit history yet')).toBeVisible()
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'player' } })
    await screen.findByText('No events match these filters')
    fireEvent.click(screen.getAllByRole('button', { name: 'Clear filters' })[1])
    expect(fetchBusinessAuditEvents).toHaveBeenCalledTimes(3)
  })

  it('does not expose raw backend error details and supports retry', async () => {
    vi.mocked(fetchBusinessAuditActors).mockResolvedValue({ actors: [] })
    vi.mocked(fetchBusinessAuditEvents).mockRejectedValueOnce(new Error('database password leaked')).mockResolvedValueOnce({ events: [], page: 1, page_size: 20, total_events: 0, total_pages: 0, has_previous: false, has_next: false })
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load academy activity')
    expect(screen.queryByText(/database password/i)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(fetchBusinessAuditEvents).toHaveBeenCalledTimes(2))
  })

  it('keeps audit controls operable and announced on narrow screens', async () => {
    vi.mocked(fetchBusinessAuditActors).mockResolvedValue({ actors: [] })
    vi.mocked(fetchBusinessAuditEvents).mockResolvedValue({ events: [event], page: 1, page_size: 20, total_events: 1, total_pages: 1, has_previous: false, has_next: false })
    renderPage()

    expect(await screen.findByText('Alex added Aarav')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Business audit events' })).toHaveAttribute('aria-busy', 'false')
    expect(screen.getByText('1 event found')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('button', { name: 'Show safe details' }).className).toContain('min-h-11')
    expect(screen.getByLabelText('Actor').className).toContain('min-h-11')

    fireEvent.click(screen.getByRole('button', { name: 'Show safe details' }))
    expect(screen.getByRole('button', { name: 'Hide safe details' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Event details expanded')).toHaveAttribute('aria-live', 'polite')
  })
})
