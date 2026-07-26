// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeamFilter, {
  UNASSIGNED_FILTER,
} from '@features/players/components/player-directory/TeamFilter'

afterEach(cleanup)

describe('TeamFilter', () => {
  it('renders All, team, and Unassigned options', () => {
    render(
      <TeamFilter
        teams={[
          { id: 'team-1', name: 'Junior XI' },
          { id: 'team-2', name: 'Senior XI' },
        ]}
        value={null}
        onChange={vi.fn()}
      />,
    )

    const filter = screen.getByRole('combobox', { name: 'Filter by team' })
    expect(filter).toHaveValue('')
    expect(screen.getByRole('option', { name: 'All Players' })).toBeVisible()
    expect(screen.getByRole('option', { name: 'Junior XI' })).toBeVisible()
    expect(screen.getByRole('option', { name: 'Unassigned Players' })).toBeVisible()
  })

  it('reports team, Unassigned, and All selections', () => {
    const onChange = vi.fn()
    render(
      <TeamFilter
        teams={[{ id: 'team-1', name: 'Junior XI' }]}
        value={null}
        onChange={onChange}
      />,
    )

    const filter = screen.getByRole('combobox', { name: 'Filter by team' })
    fireEvent.change(filter, { target: { value: 'team-1' } })
    fireEvent.change(filter, { target: { value: UNASSIGNED_FILTER } })
    fireEvent.change(filter, { target: { value: '' } })

    expect(onChange).toHaveBeenNthCalledWith(1, 'team-1')
    expect(onChange).toHaveBeenNthCalledWith(2, UNASSIGNED_FILTER)
    expect(onChange).toHaveBeenNthCalledWith(3, null)
  })

  it('uses the native keyboard-accessible select control', () => {
    render(<TeamFilter teams={[]} value={null} onChange={vi.fn()} />)
    const filter = screen.getByRole('combobox', { name: 'Filter by team' })
    filter.focus()
    expect(filter).toHaveFocus()
    expect(filter.tagName).toBe('SELECT')
  })
})
