// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeamCard from '../components/TeamCard'
import type { TeamResponse } from '../types/team'

const team: TeamResponse = {
  id: 'team-1', name: 'Falcons', age_group: 'J', player_count: 8,
  created_at: '2026-07-25T10:00:00Z', updated_at: '2026-07-25T10:00:00Z', version_number: 1,
}

afterEach(cleanup)

describe('TeamCard', () => {
  it('renders team identity, age group, and player count', () => {
    render(<TeamCard team={team} onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'View Falcons' })).toBeVisible()
    expect(screen.getByText('Juniors')).toBeVisible()
    expect(screen.getByText('8 / 15 players')).toBeVisible()
  })

  it('uses a keyboard-focusable button to select the team', () => {
    const onSelect = vi.fn()
    render(<TeamCard team={team} onSelect={onSelect} />)
    const card = screen.getByRole('button', { name: 'View Falcons' })
    card.focus()
    expect(card).toHaveFocus()
    fireEvent.click(card)
    expect(onSelect).toHaveBeenCalledWith(team)
  })
})
