// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import CoachCardGrid from './CoachCardGrid'

describe('CoachCardGrid', () => {
  it('shows skeletons and the assistant-coach empty message', () => {
    const { rerender } = render(<CoachCardGrid coaches={[]} showSkeletons onSelect={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading coaches')
    rerender(<CoachCardGrid coaches={[]} showSkeletons={false} onSelect={vi.fn()} />)
    expect(screen.getByText('No Assistant Coaches have been added yet.')).toBeVisible()
  })

  it('distinguishes a filter with no matching coaches', () => {
    render(<CoachCardGrid coaches={[]} showSkeletons={false} isFiltered onSelect={vi.fn()} />)
    expect(screen.getByText('No coaches match this status filter.')).toBeVisible()
  })
})
