// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Pagination from '@shared/components/navigation/Pagination'

afterEach(cleanup)

describe('Pagination', () => {
  it('renders fewer than 10 pages and moves to a selected page', () => {
    const onPageChange = vi.fn()
    const { container } = render(
      <Pagination
        ariaLabel="Player pages"
        page={2}
        totalPages={7}
        isLoading={false}
        onPageChange={onPageChange}
      />,
    )

    const activePage = screen.getByRole('button', { name: 'Page 2' })
    const inactivePage = screen.getByRole('button', { name: 'Page 3' })

    expect(activePage).toHaveAttribute('aria-current', 'page')
    expect(activePage).toHaveClass('border-slate-900', 'bg-slate-900', 'text-white')
    expect(activePage).not.toHaveClass('border-slate-300', 'bg-white', 'text-slate-800')
    expect(inactivePage).toHaveClass('border-slate-300', 'bg-white', 'text-slate-800')
    expect(inactivePage).not.toHaveClass('border-slate-900', 'bg-slate-900', 'text-white')
    expect(screen.getByRole('navigation', { name: 'Player pages' })).toHaveClass(
      'grid',
      'grid-cols-[auto_minmax(0,1fr)_auto]',
    )
    expect(container.querySelector('[data-pagination-pages]')).toHaveClass(
      'flex-nowrap',
      'overflow-x-auto',
      'overscroll-x-contain',
    )
    expect(screen.getByRole('group', { name: 'Page numbers' })).toBeVisible()
    expect(screen.getAllByRole('button', { name: /^Page \d+$/ })).toHaveLength(7)
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Page 7' }))
    expect(onPageChange).toHaveBeenCalledWith(7)
  })

  it('renders exactly 10 page-number buttons without another range', () => {
    render(
      <Pagination ariaLabel="Player pages" page={1} totalPages={10} isLoading={false} onPageChange={vi.fn()} />,
    )

    expect(screen.getAllByRole('button', { name: /^Page \d+$/ })).toHaveLength(10)
    expect(screen.getByRole('button', { name: 'Page 10' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeEnabled()
  })

  it('moves forward and backward between 10-page ranges', () => {
    const onPageChange = vi.fn()
    const { rerender } = render(
      <Pagination ariaLabel="Player pages" page={1} totalPages={23} isLoading={false} onPageChange={onPageChange} />,
    )

    expect(screen.getAllByRole('button', { name: /^Page \d+$/ })).toHaveLength(10)
    expect(screen.queryByRole('button', { name: 'Page 11' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next page range' }))
    expect(onPageChange).toHaveBeenLastCalledWith(11)

    rerender(
      <Pagination ariaLabel="Player pages" page={11} totalPages={23} isLoading={false} onPageChange={onPageChange} />,
    )
    expect(screen.getByRole('button', { name: 'Page 11' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Page 20' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Page 10' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Previous page range' }))
    expect(onPageChange).toHaveBeenLastCalledWith(10)

    rerender(
      <Pagination ariaLabel="Player pages" page={21} totalPages={23} isLoading={false} onPageChange={onPageChange} />,
    )
    expect(screen.getAllByRole('button', { name: /^Page \d+$/ })).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Page 21' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Next page range' })).toBeDisabled()
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
    expect(screen.getByRole('button', { name: 'Page 2' })).toHaveClass(
      'border-slate-900',
      'bg-slate-900',
      'text-white',
    )
    expect(screen.getByRole('button', { name: 'Page 2' })).not.toHaveClass(
      'disabled:border-slate-200',
      'disabled:bg-slate-100',
      'disabled:text-slate-400',
    )
  })
})
