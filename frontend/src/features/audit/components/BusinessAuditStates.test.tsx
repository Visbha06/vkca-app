// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { BusinessAuditLoadingState } from './BusinessAuditStates'

afterEach(cleanup)

describe('BusinessAuditLoadingState', () => {
  it('renders a decorative, reduced-motion-safe event skeleton', () => {
    const { container } = render(<BusinessAuditLoadingState />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(container.querySelector('[data-audit-loading-skeleton]')).toHaveAttribute(
      'aria-hidden',
      'true',
    )

    const rows = container.querySelectorAll('[data-audit-skeleton-row]')
    expect(rows).toHaveLength(3)
    rows.forEach((row) => {
      expect(row).toHaveClass('animate-pulse', 'motion-reduce:animate-none')
    })
  })
})
