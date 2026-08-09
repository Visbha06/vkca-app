// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import DataQualityFilters from './DataQualityFilters'

describe('DataQualityFilters', () => {
  it('updates filters and can clear them as a single operation', () => {
    const onChange = vi.fn()
    const onClear = vi.fn()
    render(<DataQualityFilters filters={{ severity: 'warning', domain: 'players' }} onChange={onChange} onClear={onClear} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Severity' }), { target: { value: 'critical' } })
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(onChange).toHaveBeenCalledWith('severity', 'critical')
    expect(onClear).toHaveBeenCalledOnce()
  })
})
