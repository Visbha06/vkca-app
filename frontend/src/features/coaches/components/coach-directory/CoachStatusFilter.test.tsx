// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import CoachStatusFilter from './CoachStatusFilter'

describe('CoachStatusFilter', () => {
  it('defaults to active and reports changes', () => {
    const onFilterChange = vi.fn()
    render(<CoachStatusFilter value="active" onFilterChange={onFilterChange} />)
    const filter = screen.getByRole('combobox', { name: 'Coach status' })
    expect(filter).toHaveValue('active')
    expect(screen.getByRole('option', { name: 'Inactive' })).toBeVisible()
    expect(screen.getByRole('option', { name: 'All' })).toBeVisible()
    fireEvent.change(filter, { target: { value: 'inactive' } })
    expect(onFilterChange).toHaveBeenCalledWith('inactive')
  })
})
