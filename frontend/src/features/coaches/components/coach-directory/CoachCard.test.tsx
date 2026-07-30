// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CoachCard from './CoachCard'
import type { CoachResponse } from '../../types/coach'

const coach: CoachResponse = {
  id: 'coach-1', first_name: 'Vikram', last_name: 'Kumar', email: 'coach@vkca.test',
  role: 'head coach', is_active: true, version_number: 1,
  created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
  teams: [{ id: 'one', name: 'U13 Lions' }, { id: 'two', name: 'U15 Tigers' }, { id: 'three', name: 'U11 Cubs' }],
}

afterEach(cleanup)

describe('CoachCard', () => {
  it('shows identity, role, teams, and opens on click', () => {
    const onSelect = vi.fn()
    render(<CoachCard coach={coach} onSelect={onSelect} />)
    expect(screen.getByText('Vikram Kumar')).toBeVisible()
    expect(screen.getByText('Head Coach')).toBeVisible()
    expect(screen.getByText(/\+1 more/)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: /view vikram kumar/i }))
    expect(onSelect).toHaveBeenCalledWith(coach)
  })

  it('uses the assistant-coach avatar treatment and muted inactive state', () => {
    const inactiveAssistant = { ...coach, role: 'assistant coach' as const, is_active: false, teams: [] }
    const view = render(<CoachCard coach={inactiveAssistant} onSelect={vi.fn()} />)
    expect(view.getByText('VK').className).toContain('bg-sky-100')
    expect(view.getByText('Inactive')).toBeVisible()
    expect(view.getByText('No teams assigned')).toBeVisible()
  })
})
