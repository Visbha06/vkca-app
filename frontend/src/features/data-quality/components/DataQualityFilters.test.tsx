// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DATA_QUALITY_RULE_PRESENTATION } from '../utils/dataQualityRulePresentation'
import DataQualityFilters from './DataQualityFilters'

afterEach(cleanup)

describe('DataQualityFilters', () => {
  it('renders friendly metadata for every supported rule instead of raw IDs', () => {
    render(<DataQualityFilters filters={{}} onChange={vi.fn()} onClear={vi.fn()} />)

    const ruleSelect = screen.getByRole('combobox', { name: 'Rule' })
    const presentations = Object.entries(DATA_QUALITY_RULE_PRESENTATION)

    expect(presentations).toHaveLength(17)
    for (const [ruleId, { label }] of presentations) {
      expect(within(ruleSelect).getByRole('option', { name: label })).toHaveValue(ruleId)
      expect(within(ruleSelect).queryByRole('option', { name: ruleId })).not.toBeInTheDocument()
    }
  })

  it('emits the canonical rule ID when a friendly rule is selected', () => {
    const onChange = vi.fn()
    render(<DataQualityFilters filters={{}} onChange={onChange} onClear={vi.fn()} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Rule' }), {
      target: { value: 'coach.inactive_assigned' },
    })

    expect(onChange).toHaveBeenCalledWith('ruleId', 'coach.inactive_assigned')
  })

  it('keeps All rules as the empty rule filter', () => {
    const onChange = vi.fn()
    render(<DataQualityFilters filters={{ ruleId: 'player.active_unassigned' }} onChange={onChange} onClear={vi.fn()} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Rule' }), {
      target: { value: '' },
    })

    expect(onChange).toHaveBeenCalledWith('ruleId', '')
  })

  it('keeps severity, domain, and Clear filters independent', () => {
    const onChange = vi.fn()
    const onClear = vi.fn()
    render(<DataQualityFilters filters={{ severity: 'warning', domain: 'players' }} onChange={onChange} onClear={onClear} />)

    fireEvent.change(screen.getByRole('combobox', { name: 'Severity' }), { target: { value: 'critical' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Domain' }), { target: { value: 'coaches' } })
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    expect(onChange).toHaveBeenCalledWith('severity', 'critical')
    expect(onChange).toHaveBeenCalledWith('domain', 'coaches')
    expect(onClear).toHaveBeenCalledOnce()
  })

  it('disables Clear filters when no filter is active', () => {
    render(<DataQualityFilters filters={{}} onChange={vi.fn()} onClear={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled()
  })
})
