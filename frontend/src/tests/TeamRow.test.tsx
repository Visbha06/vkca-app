// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeamRow from '../components/TeamRow'
import type { TeamResponse } from '../types/team'

const team: TeamResponse = {
  id: 'team-1', name: 'Falcons', age_group: 'J', player_count: 8,
  created_at: '2026-07-25T10:00:00Z', updated_at: '2026-07-25T10:00:00Z', version_number: 1,
}

afterEach(cleanup)

describe('TeamRow', () => {
  it('renders team identity, age group, capacity, and updated date', () => {
    render(<TeamRow team={team} onSelect={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'View Falcons' })).toBeVisible()
    expect(screen.getByText('J')).toBeVisible()
    expect(screen.getByText('8 of 15 players')).toBeVisible()
    expect(screen.getByText('7 places available')).toBeVisible()
    expect(screen.getByText('25 Jul 2026')).toBeVisible()
  })

  it('uses a keyboard-focusable row button to select the team', () => {
    const onSelect = vi.fn()
    render(<TeamRow team={team} onSelect={onSelect} />)
    const row = screen.getByRole('button', { name: 'View Falcons' })
    row.focus()
    expect(row).toHaveFocus()
    fireEvent.click(row)
    expect(onSelect).toHaveBeenCalledWith(team)
  })

  it('clamps inconsistent roster counts and describes a full roster in text', () => {
    render(
      <TeamRow
        team={{ ...team, player_count: 18 }}
        onSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('18 of 15 players')).toBeVisible()
    expect(screen.getByText('Roster full')).toBeVisible()
    expect(screen.queryByText(/-3 places/)).not.toBeInTheDocument()
  })
})
