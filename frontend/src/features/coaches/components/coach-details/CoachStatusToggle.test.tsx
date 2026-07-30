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
import CoachStatusToggle from './CoachStatusToggle'
import type { CoachResponse } from '../../types/coach'

const coach: CoachResponse = {
  id: 'coach-2',
  first_name: 'Asha',
  last_name: 'Patel',
  email: 'asha@vkca.test',
  role: 'assistant coach',
  is_active: true,
  version_number: 3,
  created_at: '',
  updated_at: '',
  teams: [],
}

afterEach(cleanup)

describe('CoachStatusToggle', () => {
  it('is only visible to Head Coaches', () => {
    render(
      <CoachStatusToggle
        coach={coach}
        currentUserId="assistant-1"
        currentUserRole="assistant coach"
        isUpdating={false}
        onStatusChange={vi.fn()}
      />,
    )
    expect(
      screen.queryByRole('button', { name: /deactivate/i }),
    ).not.toBeInTheDocument()
  })

  it('blocks self-deactivation with an explanation', () => {
    render(
      <CoachStatusToggle
        coach={{ ...coach, id: 'head-1', role: 'head coach' }}
        currentUserId="head-1"
        currentUserRole="head coach"
        isUpdating={false}
        onStatusChange={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('button', { name: 'Deactivate coach' }),
    ).toBeDisabled()
    expect(screen.getByText(/cannot deactivate your own account/i)).toBeVisible()
  })

  it('explains every consequence before deactivation', async () => {
    const onStatusChange = vi.fn().mockResolvedValue(undefined)
    render(
      <CoachStatusToggle
        coach={coach}
        currentUserId="head-1"
        currentUserRole="head coach"
        isUpdating={false}
        onStatusChange={onStatusChange}
      />,
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Deactivate coach' }),
    )
    const confirmation = screen.getByRole('alertdialog')
    expect(confirmation).toHaveTextContent(/no longer be able to log in/i)
    expect(confirmation).toHaveTextContent(/sessions will be revoked/i)
    expect(confirmation).toHaveTextContent(
      /team assignments and historical data will be preserved/i,
    )
    expect(confirmation).toHaveTextContent(/reactivated later/i)
    fireEvent.click(
      screen.getByRole('button', { name: 'Confirm deactivation' }),
    )
    await waitFor(() =>
      expect(onStatusChange).toHaveBeenCalledWith(false),
    )
  })

  it('reactivates directly and communicates a loading state', () => {
    const onStatusChange = vi.fn()
    const { rerender } = render(
      <CoachStatusToggle
        coach={{ ...coach, is_active: false }}
        currentUserId="head-1"
        currentUserRole="head coach"
        isUpdating={false}
        onStatusChange={onStatusChange}
      />,
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Reactivate coach' }),
    )
    expect(onStatusChange).toHaveBeenCalledWith(true)

    rerender(
      <CoachStatusToggle
        coach={{ ...coach, is_active: false }}
        currentUserId="head-1"
        currentUserRole="head coach"
        isUpdating
        onStatusChange={onStatusChange}
      />,
    )
    expect(screen.getByRole('button', { name: 'Reactivating…' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Updating coach status')
  })
})
