// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Pagination from '@shared/components/navigation/Pagination'

afterEach(cleanup)

describe('Pagination', () => {
  it('renders page numbers and moves to a selected page', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        ariaLabel="Player pages"
        page={2}
        totalPages={4}
        isLoading={false}
        onPageChange={onPageChange}
      />,
    )

    expect(screen.getByRole('button', { name: 'Page 2' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Page 4' }))
    expect(onPageChange).toHaveBeenCalledWith(4)
  })

  it('disables previous and next controls at their boundaries', () => {
    const { rerender } = render(
      <Pagination ariaLabel="Player pages" page={1} totalPages={3} isLoading={false} onPageChange={vi.fn()} />,
    )

    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeEnabled()

    rerender(
      <Pagination ariaLabel="Player pages" page={3} totalPages={3} isLoading={false} onPageChange={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })

  it('prevents navigation while a page is loading', () => {
    render(
      <Pagination ariaLabel="Player pages" page={2} totalPages={3} isLoading onPageChange={vi.fn()} />,
    )

    expect(screen.getByRole('navigation', { name: 'Player pages' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getAllByRole('button').every((button) => button.hasAttribute('disabled'))).toBe(true)
  })
})
