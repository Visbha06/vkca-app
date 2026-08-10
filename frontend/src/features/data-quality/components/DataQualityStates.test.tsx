// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import {
  DataQualityEmptyState,
  DataQualityErrorState,
  DataQualityLoadingState,
  DataQualitySummaryLoadingState,
} from './DataQualityStates'

describe('DataQuality states', () => {
  it('uses accessible loading and healthy status messages', () => {
    render(
      <>
        <DataQualitySummaryLoadingState />
        <DataQualityLoadingState />
        <DataQualityEmptyState />
      </>,
    )

    expect(screen.getByText('Loading current academy health…')).toBeVisible()
    expect(screen.getByTestId('data-quality-summary-skeleton')).toHaveAttribute(
      'aria-hidden',
      'true',
    )
    expect(screen.getAllByTestId('data-quality-finding-skeleton')).toHaveLength(2)
    expect(screen.getByText('No data quality issues found')).toBeVisible()
  })

  it('distinguishes filtered results and provides a keyboard-safe retry path', () => {
    render(
      <>
        <DataQualityEmptyState filtered />
        <DataQualityErrorState
          hasRetainedResults
          message="Unable to refresh data quality. Please try again."
          onRetry={() => undefined}
        />
      </>,
    )

    expect(screen.getByText('No findings match these filters')).toBeVisible()
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unable to refresh data quality. Please try again. Previous results are still shown.',
    )
    expect(screen.getByRole('button', { name: 'Retry' })).toHaveClass(
      'min-h-11',
      'focus:ring-2',
    )
  })
})
