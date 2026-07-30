// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CoachesPageHeader from './CoachesPageHeader'

afterEach(cleanup)

describe('CoachesPageHeader', () => {
  it('shows the heading and Head Coach add action', () => {
    const onFilterChange = vi.fn()
    render(<CoachesPageHeader canAddCoach isFetching={false} status="active" totalCoaches={1} onAdd={vi.fn()} onFilterChange={onFilterChange} />)
    expect(screen.getByRole('heading', { name: 'Coaches Portal' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Add Coach' })).toBeVisible()
    expect(screen.getByText('1 active coach')).toBeVisible()
    fireEvent.change(screen.getByRole('combobox', { name: 'Coach status' }), { target: { value: 'all' } })
    expect(onFilterChange).toHaveBeenCalledWith('all')
  })

  it('hides the add action from Assistant Coaches', () => {
    render(<CoachesPageHeader canAddCoach={false} isFetching={false} status="active" onAdd={vi.fn()} onFilterChange={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Add Coach' })).not.toBeInTheDocument()
  })
})
