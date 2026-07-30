// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CoachDetailsModal from './CoachDetailsModal'
import type { CoachResponse } from '../../types/coach'

const coach: CoachResponse = {
  id: 'coach-1',
  first_name: 'Vikram',
  last_name: 'Kumar',
  email: 'vikram@vkca.test',
  role: 'head coach',
  is_active: true,
  version_number: 1,
  created_at: '2026-07-01T10:00:00Z',
  updated_at: '2026-07-15T10:00:00Z',
  teams: [{ id: 'team-1', name: 'U13 Lions' }],
}

afterEach(() => {
  cleanup()
  document.body.style.overflow = ''
})

describe('CoachDetailsModal', () => {
  it('renders coach details, assigned teams, and fixed placeholder statistics', () => {
    render(
      <CoachDetailsModal
        coach={coach}
        currentUserRole="head coach"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'Vikram Kumar' })).toBeVisible()
    expect(screen.getByText('vikram@vkca.test')).toBeVisible()
    expect(screen.getByText('Head Coach')).toBeVisible()
    expect(screen.getByText('Active')).toBeVisible()
    expect(screen.getByText('U13 Lions')).toBeVisible()
    expect(screen.getByText('Availability for next practice')).toBeVisible()
    expect(screen.getByText('Not available')).toBeVisible()
    expect(screen.getByText('Notes made')).toBeVisible()
    expect(screen.getByText('0')).toBeVisible()
  })

  it('keeps management controls unavailable to Assistant Coaches', () => {
    render(
      <CoachDetailsModal
        coach={{ ...coach, teams: [] }}
        currentUserRole="assistant coach"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('No teams assigned')).toBeVisible()
    expect(screen.queryByText('Head Coach controls')).not.toBeInTheDocument()
  })

  it('closes with Escape and the close control while trapping focus', () => {
    const onClose = vi.fn()
    render(
      <CoachDetailsModal
        coach={coach}
        currentUserRole="head coach"
        onClose={onClose}
      />,
    )
    const close = screen.getByRole('button', { name: 'Close coach details' })

    expect(document.body.style.overflow).toBe('hidden')
    expect(close).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(close).toHaveFocus()
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(close)
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
