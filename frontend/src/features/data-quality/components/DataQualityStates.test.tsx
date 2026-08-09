// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DataQualityEmptyState, DataQualityLoadingState } from './DataQualityStates'

describe('DataQuality states', () => {
  it('uses accessible loading and healthy status messages', () => {
    render(<><DataQualityLoadingState /><DataQualityEmptyState /></>)

    expect(screen.getByText('Loading current academy health…')).toBeVisible()
    expect(screen.getByText('No data quality issues found')).toBeVisible()
  })
})
