// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  DataQualityEmptyState,
  DataQualityErrorState,
  DataQualityLoadingState,
} from './DataQualityStates'

describe('DataQuality states', () => {
  it('uses accessible loading and healthy status messages', () => {
    render(<><DataQualityLoadingState /><DataQualityEmptyState /></>)

    expect(screen.getByText('Loading current academy health…')).toBeVisible()
    expect(screen.getByText('No data quality issues found')).toBeVisible()
  })

  it('distinguishes filtered results and provides a keyboard-safe retry path', () => {
    render(
      <>
        <DataQualityEmptyState filtered />
        <DataQualityErrorState
          hasRetainedResults
          message="Unable to load data quality. Please try again."
          onRetry={() => undefined}
        />
      </>,
    )

    expect(screen.getByText('No findings match these filters')).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Previous results are still shown.',
    )
    expect(screen.getByRole('button', { name: 'Retry' })).toHaveClass(
      'min-h-11',
      'focus:ring-2',
    )
  })
})
